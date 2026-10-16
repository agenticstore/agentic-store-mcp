"""Create, read, or resolve explicit local approvals at an explicit path."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def run(args: dict[str, Any]) -> dict[str, Any]:
    action=args.get('action','read'); path=Path(args.get('path','')).expanduser().resolve()
    if not str(args.get('path','')): raise ValueError("'path' is required")
    if action=='read':
        if not path.is_file(): raise ValueError('Approval record does not exist')
        return {'read_only':True,'approval':json.loads(path.read_text())}
    if args.get('confirm_write') is not True: raise ValueError('Set confirm_write=true to modify an approval record')
    if action=='request':
        request=args.get('request')
        if not isinstance(request,dict) or not request.get('action'): raise ValueError("request must include an action")
        record={'status':'pending','requested_at':datetime.now(timezone.utc).isoformat(),'request':request}
    elif action=='resolve':
        if not path.is_file(): raise ValueError('Approval record does not exist')
        record=json.loads(path.read_text()); decision=args.get('decision')
        if decision not in {'approved','rejected'}: raise ValueError("decision must be approved or rejected")
        record.update({'status':decision,'resolved_at':datetime.now(timezone.utc).isoformat(),'reason':args.get('reason','')})
    else: raise ValueError('action must be read, request, or resolve')
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(record,indent=2)+'\n')
    return {'written':True,'path':str(path),'approval':record}
