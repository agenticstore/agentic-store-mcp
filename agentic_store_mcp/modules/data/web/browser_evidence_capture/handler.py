"""Fetch a public page and optionally persist a bounded local evidence record."""
from __future__ import annotations
import json,re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request,urlopen
class _Text(HTMLParser):
 def __init__(self): super().__init__();self.parts=[];self.title='';self.in_title=False
 def handle_starttag(self,t,a): self.in_title=t=='title'
 def handle_endtag(self,t): self.in_title=False
 def handle_data(self,d): self.parts.append(d); self.title+=d if self.in_title else ''
def run(args:dict[str,Any])->dict[str,Any]:
    url=args.get('url',''); parsed=urlparse(url)
    if parsed.scheme not in {'http','https'} or not parsed.netloc:raise ValueError('url must be public http or https')
    limit=min(max(int(args.get('max_chars',12000)),500),50000)
    request=Request(url,headers={'User-Agent':'AgenticStoreEvidence/1.0'})
    with urlopen(request,timeout=15) as response: raw=response.read(2_000_000); content_type=response.headers.get('Content-Type','')
    body=raw.decode('utf-8','replace'); parser=_Text(); parser.feed(body)
    text=re.sub(r'\s+',' ',' '.join(parser.parts)).strip(); terms=args.get('terms',[]); excerpts=[]
    for term in terms[:10]:
        pos=text.lower().find(str(term).lower())
        if pos>=0: excerpts.append({'term':term,'excerpt':text[max(0,pos-180):pos+420]})
    evidence={'url':url,'captured_at':datetime.now(timezone.utc).isoformat(),'title':parser.title.strip()[:500],'content_type':content_type,'text':text[:limit],'text_truncated':len(text)>limit,'excerpts':excerpts}
    output=args.get('output_path')
    if output:
        if args.get('confirm_write') is not True:raise ValueError('Set confirm_write=true to save evidence locally')
        target=Path(output).expanduser().resolve();target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(evidence,indent=2)+'\n');evidence['written_to']=str(target)
    return evidence
