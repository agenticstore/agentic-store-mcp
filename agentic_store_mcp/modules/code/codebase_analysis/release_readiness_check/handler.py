"""Read-only local release readiness report."""
from __future__ import annotations
import re,subprocess
from pathlib import Path
from typing import Any
def _git(root:Path,*args:str)->str:
 r=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=15);return r.stdout.strip()
def run(args:dict[str,Any])->dict[str,Any]:
 root=Path(args.get('path','.')).expanduser().resolve()
 if not (root/'.git').exists():raise ValueError("'path' must be a Git repository")
 changed=_git(root,'status','--porcelain').splitlines(); pyproject=root/'pyproject.toml'; readme=root/'README.md'; changelog=next((root/x for x in ('CHANGELOG.md','CHANGELOG.rst','docs/CHANGELOG.md') if (root/x).is_file()),None)
 version=None
 if pyproject.is_file():
  match=re.search(r'^version\s*=\s*["\']([^"\']+)',pyproject.read_text(),re.M);version=match.group(1) if match else None
 checks=[{'name':'clean_working_tree','passed':not changed,'detail':f'{len(changed)} changed paths'},{'name':'package_version','passed':bool(version),'detail':version or 'No version found'},{'name':'readme_present','passed':readme.is_file(),'detail':str(readme)},{'name':'changelog_present','passed':changelog is not None,'detail':str(changelog) if changelog else 'No changelog found'},{'name':'ignore_present','passed':(root/'.gitignore').is_file(),'detail':'.gitignore'}]
 return {'read_only':True,'branch':_git(root,'branch','--show-current'),'commit':_git(root,'rev-parse','HEAD'),'checks':checks,'ready':all(item['passed'] for item in checks),'next_steps':['Run test_runner for test and lint where supported.','Run repo_scanner and dependency_audit before publishing.','Review git_change_summary, then commit and tag the release.']}
