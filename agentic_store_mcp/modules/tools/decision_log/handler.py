"""Maintain a local append-only development decision log."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
def run(args:dict[str,Any])->dict[str,Any]:
 path=Path(args.get('path','')).expanduser().resolve();action=args.get('action','read')
 if not str(args.get('path','')):raise ValueError('path is required')
 entries=json.loads(path.read_text()) if path.is_file() else []
 if action=='read':return {'read_only':True,'entries':entries[-min(int(args.get('limit',50)),200):]}
 if action!='append' or args.get('confirm_write') is not True:raise ValueError('Use action=append and confirm_write=true to add a decision')
 decision=args.get('decision')
 if not isinstance(decision,dict) or not decision.get('summary') or not decision.get('rationale'):raise ValueError('decision requires summary and rationale')
 decision.setdefault('recorded_at',datetime.now(timezone.utc).isoformat());entries.append(decision);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(entries,indent=2)+'\n')
 return {'written':True,'entry':decision,'total':len(entries)}
