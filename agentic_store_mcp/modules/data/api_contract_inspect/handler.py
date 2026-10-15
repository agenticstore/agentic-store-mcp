"""Inspect local OpenAPI, GraphQL, or JSON Schema files without network access."""
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
def run(args:dict[str,Any])->dict[str,Any]:
    path=Path(args.get('path','')).expanduser().resolve()
    if not path.is_file():raise ValueError("'path' must be an existing file")
    text=path.read_text(errors='replace'); result={'read_only':True,'path':str(path),'format':'unknown','endpoints':[],'auth_schemes':[],'required_fields':[],'examples':0}
    if path.suffix=='.json':
        data=json.loads(text)
        if 'openapi' in data or 'swagger' in data:
            result['format']='openapi'; result['endpoints']=[{'path':key,'methods':sorted(value.keys())} for key,value in data.get('paths',{}).items()]; result['auth_schemes']=sorted(data.get('components',{}).get('securitySchemes',{}).keys()); result['examples']=text.count('example')
        elif '$schema' in data or 'properties' in data:
            result['format']='json-schema'; result['required_fields']=data.get('required',[]); result['examples']=text.count('example')
    elif path.suffix in {'.graphql','.gql'}:
        result['format']='graphql'; result['endpoints']=re.findall(r'\b(?:type|interface)\s+(Query|Mutation|Subscription)\s*\{([^}]*)\}',text,re.S); result['required_fields']=re.findall(r'(\w+)\s*:\s*[\w\[\]!]+',text)[:200]
    elif path.suffix in {'.yaml','.yml'}:
        result['format']='openapi-yaml'; result['endpoints']=[{'path':line.strip().rstrip(':'),'methods':[]} for line in text.splitlines() if re.match(r'^\s*/[^:]+:\s*$',line)]; result['auth_schemes']=re.findall(r'^\s{4}([\w-]+):\s*$',text,re.M)[:50]
    else:raise ValueError('Supported formats: JSON, YAML, GraphQL')
    return result
