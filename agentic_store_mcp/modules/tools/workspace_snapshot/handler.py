"""Create a bounded, optionally persisted local workspace manifest."""
from __future__ import annotations
import hashlib, json, platform, subprocess, sys
from pathlib import Path
from typing import Any
_SKIP={'.git','.venv','venv','node_modules','dist','build','__pycache__'}
def _git(root: Path, *args: str) -> str | None:
    try:
        r=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=10)
        return r.stdout.strip() if r.returncode==0 else None
    except OSError: return None
def _hash(path: Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(65536),b''): digest.update(chunk)
    return digest.hexdigest()
def run(args: dict[str, Any])->dict[str, Any]:
    root=Path(args.get('path','.')).expanduser().resolve()
    if not root.is_dir(): raise ValueError("'path' must be a directory")
    maximum=min(max(int(args.get('max_files',500)),1),2000); files=[]
    for item in root.rglob('*'):
        if len(files)>=maximum: break
        if any(part in _SKIP for part in item.parts) or not item.is_file() or item.stat().st_size>5*1024*1024: continue
        files.append({'path':str(item.relative_to(root)),'size_bytes':item.stat().st_size,'sha256':_hash(item)})
    snapshot={'root':str(root),'git':{'branch':_git(root,'branch','--show-current'),'commit':_git(root,'rev-parse','HEAD'),'status':_git(root,'status','--porcelain')},'environment':{'python':sys.version.split()[0],'platform':platform.platform()},'manifests':[name for name in ('pyproject.toml','package.json','requirements.txt','Cargo.toml','go.mod') if (root/name).is_file()],'files':files,'truncated':len(files)>=maximum}
    compare=args.get('compare_to')
    if compare:
        previous=json.loads(Path(compare).expanduser().read_text())
        old={item['path']:item['sha256'] for item in previous.get('files',[])}; new={item['path']:item['sha256'] for item in files}
        snapshot['comparison']={'added':sorted(new.keys()-old.keys()),'removed':sorted(old.keys()-new.keys()),'changed':sorted(name for name in new.keys()&old.keys() if new[name]!=old[name])}
    output=args.get('output_path')
    if output:
        if args.get('confirm_write') is not True: raise ValueError("Set confirm_write=true to write a snapshot")
        target=Path(output).expanduser().resolve(); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(snapshot,indent=2)+"\n"); snapshot['written_to']=str(target)
    return snapshot
