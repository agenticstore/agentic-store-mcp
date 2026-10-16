"""Verify source availability and whether quoted terms remain on public pages."""
from __future__ import annotations
from datetime import datetime,timezone
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from typing import Any
def run(args:dict[str,Any])->dict[str,Any]:
 citations=args.get('citations')
 if not isinstance(citations,list) or not citations:raise ValueError('citations must be a non-empty array')
 results=[]
 for item in citations[:25]:
  url=item.get('url') if isinstance(item,dict) else str(item); terms=item.get('terms',[]) if isinstance(item,dict) else []
  parsed=urlparse(url)
  if parsed.scheme not in {'http','https'}:results.append({'url':url,'verified':False,'error':'Only http/https URLs allowed'});continue
  try:
   with urlopen(Request(url,headers={'User-Agent':'AgenticStoreCitationVerify/1.0'}),timeout=15) as response: body=response.read(1_000_000).decode('utf-8','replace');status=getattr(response,'status',200)
   missing=[term for term in terms[:10] if str(term).lower() not in body.lower()]
   results.append({'url':url,'status':status,'verified':not missing,'missing_terms':missing})
  except Exception as error:results.append({'url':url,'verified':False,'error':str(error)[:300]})
 return {'open_world':True,'checked_at':datetime.now(timezone.utc).isoformat(),'results':results}
