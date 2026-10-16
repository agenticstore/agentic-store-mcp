"""Compare bounded local text, HTML, Markdown, DOCX, PPTX, XLSX, and PDF documents."""
from __future__ import annotations
import difflib, re, shutil, subprocess, zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
class _Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,data):self.parts.append(data)
def _ooxml(path:Path)->str:
 with zipfile.ZipFile(path) as archive:
  names=archive.namelist()
  if path.suffix.lower()=='.docx':names=['word/document.xml']
  elif path.suffix.lower()=='.pptx':names=[x for x in names if x.startswith('ppt/slides/slide') and x.endswith('.xml')]
  elif path.suffix.lower()=='.xlsx':names=[x for x in names if x.startswith('xl/worksheets/') and x.endswith('.xml')]
  return '\n'.join(re.sub('<[^>]+>',' ',archive.read(name).decode('utf-8','replace')) for name in names)
def _extract(path:Path, max_chars:int)->str:
 suffix=path.suffix.lower()
 if suffix=='.pdf':
  exe=shutil.which('pdftotext')
  if not exe:raise ValueError('PDF comparison requires pdftotext')
  text=subprocess.run([exe,str(path),'-'],capture_output=True,text=True,timeout=20,check=False).stdout
 elif suffix in {'.docx','.pptx','.xlsx'}:text=_ooxml(path)
 elif suffix in {'.html','.htm'}:
  parser=_Text();parser.feed(path.read_text(errors='replace'));text=' '.join(parser.parts)
 else:text=path.read_text(errors='replace')
 return re.sub(r'\s+',' ',text).strip()[:max_chars]
def run(args:dict[str,Any])->dict[str,Any]:
 left,right=Path(args.get('left_path','')).expanduser().resolve(),Path(args.get('right_path','')).expanduser().resolve()
 if not left.is_file() or not right.is_file():raise ValueError('left_path and right_path must be existing files')
 limit=min(max(int(args.get('max_chars',30000)),1000),100000); a,b=_extract(left,limit),_extract(right,limit)
 diff=list(difflib.unified_diff(a.splitlines(),b.splitlines(),fromfile=left.name,tofile=right.name,n=2)); output='\n'.join(diff)
 return {'read_only':True,'left_chars':len(a),'right_chars':len(b),'diff':output[:limit],'diff_truncated':len(output)>limit,'similarity':round(difflib.SequenceMatcher(None,a,b).ratio(),4)}
