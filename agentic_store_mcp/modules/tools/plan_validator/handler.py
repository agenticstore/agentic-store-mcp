"""Validate a structured agent plan against declared steps and confirmations."""
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
_RISK=re.compile(r'\b(delete|deploy|publish|push|send|payment|credential|production|execute)\b',re.I)
def run(args: dict[str, Any]) -> dict[str, Any]:
    plan=args.get('plan')
    if not plan and args.get('plan_path'): plan=json.loads(Path(args['plan_path']).expanduser().read_text())
    if not isinstance(plan,dict): raise ValueError("Provide a plan object or plan_path")
    steps=plan.get('steps',[])
    if not isinstance(steps,list) or not steps: raise ValueError("Plan needs a non-empty steps array")
    findings=[]
    for index,step in enumerate(steps,1):
        if not isinstance(step,dict) or not step.get('action'): findings.append({'step':index,'severity':'error','message':'Each step needs an action'}) ; continue
        text=str(step['action'])+' '+str(step.get('tool',''))
        if _RISK.search(text) and step.get('requires_approval') is not True: findings.append({'step':index,'severity':'warning','message':'Potential side effect is missing requires_approval=true'})
        if not step.get('success_criteria'): findings.append({'step':index,'severity':'warning','message':'Missing success_criteria'})
    return {'read_only':True,'valid':not any(x['severity']=='error' for x in findings),'steps_checked':len(steps),'findings':findings,'recommendations':['Use read-only discovery before write steps.','Add a task_checkpoint after significant execution steps.']}
