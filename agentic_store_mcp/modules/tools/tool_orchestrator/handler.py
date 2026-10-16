"""Recommend a minimal, risk-aware tool profile for an agent task."""
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
ROOT=Path(__file__).parent.parent.parent
CONTROL={'tool_orchestrator','tool_profile_manage','tool_profile_audit'}
PROFILES={
 'private-code-review': {'terms':{'code','bug','python','typescript','review','refactor'},'tools':{'file_scan','file_read','file_search','code_symbols','code_references','python_lint_checker','git_change_summary','test_runner','workspace_snapshot','task_checkpoint'}},
 'data-analysis': {'terms':{'data','csv','json','sqlite','dataset','analysis'},'tools':{'file_extract','data_profile','data_quality_check','data_contract_check','structured_data_query','data_lineage_map','document_compare','database_inspect','database_query'}},
 'research-evidence': {'terms':{'research','web','source','citation','evidence'},'tools':{'agentic_web_search','agentic_web_crawl','browser_evidence_capture','citation_verify','file_extract','memory_write','memory_search'}},
 'release-manager': {'terms':{'release','deploy','version','package','dependency'},'tools':{'git_change_summary','dependency_upgrade_plan','dependency_change_impact','test_runner','release_readiness_check','approval_gate','update_change_log','risk_register'}},
 'security-review': {'terms':{'security','secret','vulnerability','audit','privacy'},'tools':{'repo_scanner','dependency_audit','code_scanning_alerts','dependabot_alerts','prompt_firewall','git_change_summary','risk_register'}},
 'product-planning': {'terms':{'plan','product','decision','task','roadmap'},'tools':{'spinup_memory','update_plan','task_board','decision_log','risk_register','update_milestones','task_checkpoint','handoff_bundle'}},
}
def _registry()->dict[str,dict[str,Any]]:
 output={}
 for schema_path in ROOT.rglob('schema.json'):
  try:data=json.loads(schema_path.read_text())
  except (OSError,json.JSONDecodeError):continue
  output[data.get('name',schema_path.parent.name)] = data
 return output
def run(args:dict[str,Any])->dict[str,Any]:
 goal=str(args.get('goal','')).lower().strip()
 if not goal:raise ValueError("'goal' is required")
 privacy=args.get('privacy','balanced'); risk=args.get('risk_level','balanced')
 words=set(re.findall(r'[a-z0-9_]+',goal)); scored=[]
 for name,profile in PROFILES.items():scored.append((len(words&profile['terms']),name,profile))
 scored.sort(reverse=True); score,name,profile=scored[0]
 registry=_registry(); selected=set(profile['tools'])|CONTROL
 if privacy=='local_only':selected={x for x in selected if not registry.get(x,{}).get('annotations',{}).get('openWorldHint',False)}|CONTROL
 if risk=='read_only':selected={x for x in selected if registry.get(x,{}).get('annotations',{}).get('readOnlyHint',False)}|CONTROL
 selected={x for x in selected if x in registry}
 missing_connectors=sorted({connector for tool in selected for connector in registry[tool].get('connectors',[])})
 return {'read_only':True,'goal':goal,'recommendation':{'profile_name':name,'confidence':'high' if score>=2 else 'medium','enabled_tools':sorted(selected),'always_enabled_control_tools':sorted(CONTROL),'excluded_by_privacy':privacy,'excluded_by_risk':risk,'connectors_required':missing_connectors,'apply_command':f'Use tool_profile_manage with action=create, then restart your MCP client with agentic-store-mcp --profile {name}.'},'alternatives':[item[1] for item in scored[1:4]]}
