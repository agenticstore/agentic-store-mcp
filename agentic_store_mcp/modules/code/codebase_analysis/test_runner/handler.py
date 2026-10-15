"""Run a bounded, allowlisted project verification command."""
from __future__ import annotations
import shutil, subprocess, time
from pathlib import Path
from typing import Any

def _command(root: Path, task: str) -> list[str]:
    if (root/'package.json').is_file():
        if task not in {'test','lint','build','typecheck'}: raise ValueError('Unsupported JavaScript task')
        npm=shutil.which('npm')
        if not npm: raise ValueError('npm is not installed')
        return [npm,'run',task,'--if-present']
    if task=='test': return [str(root/'.venv/bin/python') if (root/'.venv/bin/python').exists() else 'python','-m','unittest','discover']
    if task=='lint':
        ruff=shutil.which('ruff')
        if not ruff: raise ValueError('ruff is not installed; only allowlisted runner commands are supported')
        return [ruff,'check','.']
    raise ValueError('Python projects support test and lint tasks')
def run(args: dict[str, Any])->dict[str, Any]:
    if args.get('confirm_execute') is not True: raise ValueError('Set confirm_execute=true to run a project command')
    root=Path(args.get('path','.')).expanduser().resolve()
    if not root.is_dir(): raise ValueError("'path' must be a directory")
    task=args.get('task')
    if not isinstance(task,str): raise ValueError("'task' is required")
    command=_command(root,task); timeout=min(max(int(args.get('timeout_seconds',120)),1),300); started=time.monotonic()
    try: result=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=timeout,check=False)
    except subprocess.TimeoutExpired as error: return {'executed':True,'task':task,'command':command,'passed':False,'timed_out':True,'duration_seconds':round(time.monotonic()-started,2),'output':(error.stdout or '')[-12000:]}
    output=(result.stdout+'\n'+result.stderr).strip()
    return {'executed':True,'task':task,'command':command,'passed':result.returncode==0,'exit_code':result.returncode,'timed_out':False,'duration_seconds':round(time.monotonic()-started,2),'output':output[-12000:],'output_truncated':len(output)>12000}
