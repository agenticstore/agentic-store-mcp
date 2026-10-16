"""Explain capability and risk composition of a named profile."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
DEFAULT=Path.home()/'.config'/'agentic-store'/'tool-profiles.json';ROOT=Path(__file__).parent.parent.parent
def run(args:dict[str,Any])->dict[str,Any]:
 store_path=Path(args.get('store_path',DEFAULT)).expanduser().resolve();store=json.loads(store_path.read_text()) if store_path.is_file() else {'profiles':{}}
 name=args.get('name') or store.get('active_profile')
 if not name or name not in store.get('profiles',{}):raise ValueError('Provide a known profile name or select an active profile')
 profile=store['profiles'][name]; registry={}
 for path in ROOT.rglob('schema.json'):
  try:data=json.loads(path.read_text());registry[data.get('name',path.parent.name)]=data
  except (OSError,json.JSONDecodeError):pass
 tools=[];missing=[]
 for tool in profile.get('enabled_tools',[]):
  if tool not in registry:missing.append(tool);continue
  annotation=registry[tool].get('annotations',{});tools.append({'name':tool,'annotations':annotation,'connectors':registry[tool].get('connectors',[])})
 return {'read_only':True,'profile':name,'tools':tools,'missing_tools':missing,'summary':{'total':len(tools),'read_only':sum(x['annotations'].get('readOnlyHint') is True for x in tools),'destructive':sum(x['annotations'].get('destructiveHint') is True for x in tools),'open_world':sum(x['annotations'].get('openWorldHint') is True for x in tools),'connectors':sorted({c for x in tools for c in x['connectors']})},'restart_required':True}
