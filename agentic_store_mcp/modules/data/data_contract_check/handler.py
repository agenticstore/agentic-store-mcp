"""Validate local tabular data against a checked-in JSON contract."""
from __future__ import annotations
import csv,json,re,sqlite3
from pathlib import Path
from typing import Any
def _rows(path: Path, table: str|None)->list[dict[str,Any]]:
    if path.suffix=='.csv':
        with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
    if path.suffix in {'.json','.jsonl'}:
        raw=[json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.suffix=='.jsonl' else json.loads(path.read_text())
        if not isinstance(raw,list) or not all(isinstance(x,dict) for x in raw):raise ValueError('JSON must be an array of objects')
        return raw
    if path.suffix in {'.db','.sqlite','.sqlite3'}:
        if not table:raise ValueError('table required for SQLite')
        con=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
        try:
            allowed={x[0] for x in con.execute("select name from sqlite_master where type='table'")}
            if table not in allowed:raise ValueError('Unknown SQLite table')
            cur=con.execute(f'SELECT * FROM "{table.replace(chr(34),chr(34)*2)}" LIMIT 10000'); return [dict(zip([c[0] for c in cur.description],row)) for row in cur]
        finally:con.close()
    raise ValueError('Supported: CSV, JSON, JSONL, SQLite')
def run(args:dict[str,Any])->dict[str,Any]:
    path=Path(args.get('path','')).expanduser().resolve(); contract_path=Path(args.get('contract_path','')).expanduser().resolve()
    if not path.is_file() or not contract_path.is_file():raise ValueError('path and contract_path must be existing files')
    contract=json.loads(contract_path.read_text()); rows=_rows(path,args.get('table')); columns={k for row in rows for k in row}; failures=[]
    for col in contract.get('required_columns',[]):
        if col not in columns: failures.append({'check':'required_column','column':col})
    for col in contract.get('unique',[]):
        values=[str(r.get(col)) for r in rows if r.get(col) not in (None,'')]
        if len(values)!=len(set(values)):failures.append({'check':'unique','column':col})
    for col, rule in contract.get('columns',{}).items():
        values=[r.get(col) for r in rows if r.get(col) not in (None,'')]
        if rule.get('nullable') is False and any(r.get(col) in (None,'') for r in rows):failures.append({'check':'nullable','column':col})
        if 'enum' in rule and any(v not in rule['enum'] for v in values):failures.append({'check':'enum','column':col})
        if 'pattern' in rule and any(not re.fullmatch(rule['pattern'],str(v)) for v in values):failures.append({'check':'pattern','column':col})
        nums=[float(v) for v in values if str(v).replace('.','',1).isdigit()]
        if 'min' in rule and any(v<float(rule['min']) for v in nums):failures.append({'check':'min','column':col})
        if 'max' in rule and any(v>float(rule['max']) for v in nums):failures.append({'check':'max','column':col})
    return {'read_only':True,'rows_checked':len(rows),'contract':str(contract_path),'passed':not failures,'failures':failures}
