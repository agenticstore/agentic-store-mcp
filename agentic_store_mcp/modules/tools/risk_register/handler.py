"""Maintain a local development risk register."""
from __future__ import annotations
import json,uuid
from pathlib import Path
from typing import Any
VALID={'low','medium','high','critical'}
def run(args:dict[str,Any])->dict[str,Any]:
 path=Path(args.get('path','')).expanduser().resolve();action=args.get('action','list')
 if not str(args.get('path','')):raise ValueError('path is required')
 register=json.loads(path.read_text()) if path.is_file() else {'risks':[]}
 if action=='list':return {'read_only':True,'risks':register['risks']}
 if args.get('confirm_write') is not True:raise ValueError('Set confirm_write=true to modify risks')
 if action=='add':
  risk=args.get('risk');
  if not isinstance(risk,dict) or not risk.get('summary'):raise ValueError('risk requires summary')
  risk.setdefault('id',uuid.uuid4().hex[:8]);risk.setdefault('severity','medium');risk.setdefault('status','open');register['risks'].append(risk);result=risk
 elif action=='update':
  risk=next((x for x in register['risks'] if x.get('id')==args.get('id')),None)
  if not risk:raise ValueError('Unknown risk id')
  risk.update(args.get('changes',{}));result=risk
 else:raise ValueError('action must be list, add, or update')
 if result.get('severity') not in VALID:raise ValueError('severity must be low, medium, high, or critical')
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(register,indent=2)+'\n');return {'written':True,'risk':result,'total':len(register['risks'])}
