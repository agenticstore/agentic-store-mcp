"""Estimate local import impact for dependency manifest changes."""
from __future__ import annotations
import re, subprocess
from pathlib import Path
from typing import Any
_MANIFEST=re.compile(r'(requirements[^/]*\.txt|pyproject\.toml|package(?:-lock)?\.json|uv\.lock|poetry\.lock|yarn\.lock|pnpm-lock\.yaml)$')
def run(args: dict[str, Any])->dict[str, Any]:
    root=Path(args.get('path','.')).expanduser().resolve()
    if not (root/'.git').exists(): raise ValueError("'path' must be a Git repository")
    base=args.get('base_ref','HEAD'); command=['git','-C',str(root),'diff','--unified=0',base]
    result=subprocess.run(command,capture_output=True,text=True,timeout=20,check=False)
    if result.returncode: raise ValueError(result.stderr.strip() or 'Git diff failed')
    changed=[]; current=None
    for line in result.stdout.splitlines():
        if line.startswith('+++ b/'): current=line[6:]
        elif current and line.startswith('+') and not line.startswith('+++') and _MANIFEST.search(current):
            match=re.match(r'\+\s*([A-Za-z0-9_.-]+)',line)
            if match: changed.append(match.group(1).replace('-','_').lower())
    packages=sorted(set(changed))[:100]; references={}
    for package in packages:
        pattern=re.compile(rf'^(?:from|import)\s+{re.escape(package)}\b|(?:require\(|from\s+["\']){re.escape(package)}',re.M)
        hits=[]
        for file in root.rglob('*'):
            if any(part in {'.git','.venv','venv','node_modules','dist','build'} for part in file.parts) or not file.is_file() or file.suffix not in {'.py','.js','.ts','.tsx','.jsx'} or file.stat().st_size>512000: continue
            try:
                if pattern.search(file.read_text(errors='replace')): hits.append(str(file.relative_to(root)))
            except OSError: pass
        references[package]=hits[:100]
    return {'read_only':True,'base_ref':base,'changed_dependencies':packages,'impact':references,'note':'Import references are heuristic; review lockfile and runtime dependencies before release.'}
