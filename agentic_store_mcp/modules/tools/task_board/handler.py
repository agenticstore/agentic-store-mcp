"""Maintain a small local task board with explicit work states."""
from __future__ import annotations
import json,uuid
from pathlib import Path
from typing import Any
VALID={'todo','in_progress','blocked','done'}
def run(args:dict[str,Any])->dict[str,Any]:
 path=Path(args.get('path','')).expanduser().resolve();action=args.get('action','list')
 if not str(args.get('path','')):raise ValueError('path is required')
 board=json.loads(path.read_text()) if path.is_file() else {'tasks':[]}
 if action=='list':return {'read_only':True,'tasks':board['tasks']}
 if args.get('confirm_write') is not True:raise ValueError('Set confirm_write=true to modify tasks')
 if action=='add':
  task=args.get('task');
  if not isinstance(task,dict) or not task.get('title'):raise ValueError('task requires title')
  task.setdefault('id',uuid.uuid4().hex[:8]);task.setdefault('status','todo');board['tasks'].append(task);result=task
 elif action=='update':
  task=next((x for x in board['tasks'] if x.get('id')==args.get('id')),None)
  if not task:raise ValueError('Unknown task id')
  changes=args.get('changes',{});task.update(changes)
  if task.get('status') not in VALID:raise ValueError('Invalid status')
  result=task
 else:raise ValueError('action must be list, add, or update')
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(board,indent=2)+'\n');return {'written':True,'task':result,'total':len(board['tasks'])}
