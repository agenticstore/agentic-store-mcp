"""Read local manifests and produce a dependency-upgrade validation plan."""
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
_SKIP={'.git','.venv','venv','node_modules','dist','build'}
def run(args:dict[str,Any])->dict[str,Any]:
 root=Path(args.get('path','.')).expanduser().resolve()
 if not root.is_dir():raise ValueError("'path' must be a directory")
 requested=[str(x).replace('-','_') for x in args.get('packages',[])]
 manifests=[p for p in (root/'pyproject.toml',root/'requirements.txt',root/'package.json',root/'package-lock.json',root/'uv.lock') if p.is_file()]
 if not manifests:raise ValueError('No supported dependency manifest found')
 if not requested:
  for manifest in manifests:
   requested.extend(re.findall(r'^\s*([A-Za-z0-9_.-]+)\s*(?:[<>=!~]|:)',manifest.read_text(errors='replace'),re.M))
 requested=sorted(set(requested))[:100]; impacts={}
 for package in requested:
  hits=[]; pattern=re.compile(rf'\b(?:import|from|require\(|from\s+["\'])[^\n]*\b{re.escape(package)}\b',re.I)
  for file in root.rglob('*'):
   if any(part in _SKIP for part in file.parts) or not file.is_file() or file.suffix not in {'.py','.js','.ts','.tsx','.jsx'} or file.stat().st_size>512000:continue
   if pattern.search(file.read_text(errors='replace')):hits.append(str(file.relative_to(root)))
  impacts[package]=hits[:50]
 return {'read_only':True,'manifests':[str(p.relative_to(root)) for p in manifests],'packages':requested,'import_impact':impacts,'plan':['Review upstream release notes and version constraints.','Upgrade one dependency set at a time.','Run test_runner for test, lint, and build after each batch.','Use dependency_change_impact and git_change_summary before committing.']}
