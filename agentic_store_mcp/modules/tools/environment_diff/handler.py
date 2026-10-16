"""Compare environment variable names and masked value fingerprints."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
def _read(path:Path)->dict[str,str]:
 data={}
 for line in path.read_text(errors='replace').splitlines():
  line=line.strip()
  if not line or line.startswith('#') or '=' not in line: continue
  key,value=line.split('=',1);data[key.strip()]=value.strip().strip('"\'')
 return data
def _fingerprint(value:str)->str:return hashlib.sha256(value.encode()).hexdigest()[:12]
def run(args:dict[str,Any])->dict[str,Any]:
 left,right=Path(args.get('left_path','')).expanduser().resolve(),Path(args.get('right_path','')).expanduser().resolve()
 if not left.is_file() or not right.is_file():raise ValueError('left_path and right_path must be existing files')
 a,b=_read(left),_read(right); common=a.keys()&b.keys()
 return {'read_only':True,'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':sorted(key for key in common if a[key]!=b[key]),'unchanged':sorted(key for key in common if a[key]==b[key]),'value_fingerprints':{key:{'left':_fingerprint(a[key]),'right':_fingerprint(b[key])} for key in common if a[key]!=b[key]}}
