"""Build a local handoff bundle from explicit development lifecycle artifacts."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
def _load(value:Any)->Any:
 if not value:return None
 path=Path(value).expanduser().resolve();return json.loads(path.read_text()) if path.is_file() else {'missing_path':str(path)}
def run(args:dict[str,Any])->dict[str,Any]:
 bundle={'created_at':datetime.now(timezone.utc).isoformat(),'goal':args.get('goal',''),'summary':args.get('summary',''),'plan':_load(args.get('plan_path')),'tasks':_load(args.get('task_board_path')),'risks':_load(args.get('risk_register_path')),'decisions':_load(args.get('decision_log_path')),'checkpoint':_load(args.get('checkpoint_path')),'next_actions':args.get('next_actions',[])}
 output=args.get('output_path')
 if output:
  if args.get('confirm_write') is not True:raise ValueError('Set confirm_write=true to write a handoff bundle')
  target=Path(output).expanduser().resolve();target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(bundle,indent=2)+'\n');bundle['written_to']=str(target)
 else:bundle['read_only']=True
 return bundle
