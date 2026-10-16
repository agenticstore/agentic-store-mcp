"""Persist named AgenticStore tool profiles and provide restart instructions."""
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
DEFAULT=Path.home()/'.config'/'agentic-store'/'tool-profiles.json'
CONTROL={'tool_orchestrator','tool_profile_manage','tool_profile_audit'}
def _store(value:Any)->Path:return Path(value).expanduser().resolve() if value else DEFAULT
def _read(path:Path)->dict[str,Any]:return json.loads(path.read_text()) if path.is_file() else {'profiles':{},'active_profile':None}
def _valid_name(value:str)->str:
 if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}',value):raise ValueError('Profile name must be lowercase letters, numbers, and hyphens')
 return value
def run(args:dict[str,Any])->dict[str,Any]:
 action=args.get('action','list');path=_store(args.get('store_path'));store=_read(path)
 if action=='list':return {'read_only':True,'store_path':str(path),'active_profile':store.get('active_profile'),'profiles':sorted(store['profiles'])}
 name=args.get('name')
 if action=='read':
  if name not in store['profiles']:raise ValueError('Unknown profile')
  return {'read_only':True,'profile':store['profiles'][name]}
 if action not in {'create','update','delete','apply'}:raise ValueError('Invalid action')
 if args.get('confirm_write') is not True:raise ValueError('Set confirm_write=true to change profiles')
 name=_valid_name(str(name or ''))
 if action in {'create','update'}:
  tools=args.get('enabled_tools')
  if not isinstance(tools,list) or not all(isinstance(item,str) for item in tools):raise ValueError('enabled_tools must be an array of tool names')
  store['profiles'][name]={'name':name,'enabled_tools':sorted(set(tools)|CONTROL),'description':str(args.get('description',''))}
 elif action=='delete':store['profiles'].pop(name,None);store['active_profile']=None if store.get('active_profile')==name else store.get('active_profile')
 elif action=='apply':
  if name not in store['profiles']:raise ValueError('Unknown profile')
  store['active_profile']=name
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(store,indent=2)+'\n')
 profile=store['profiles'].get(name)
 return {'written':True,'store_path':str(path),'active_profile':store.get('active_profile'),'profile':profile,'restart_command':f'agentic-store-mcp --profile {name}' if profile else None}
