"""Map local references to a data file across a bounded workspace."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any
_SKIP={'.git','.venv','venv','node_modules','dist','build','__pycache__'}
def run(args:dict[str,Any])->dict[str,Any]:
 source=Path(args.get('path','')).expanduser().resolve(); root=Path(args.get('root',source.parent)).expanduser().resolve()
 if not source.is_file() or not root.is_dir():raise ValueError('path must be a file and root must be a directory')
 names={source.name,str(source)}; pattern=re.compile('|'.join(re.escape(x) for x in names))
 references=[]
 for file in root.rglob('*'):
  if any(part in _SKIP for part in file.parts) or not file.is_file() or file==source or file.stat().st_size>512000:continue
  try:
   for line_no,line in enumerate(file.read_text(errors='replace').splitlines(),1):
    if pattern.search(line):references.append({'path':str(file.relative_to(root)),'line':line_no,'excerpt':line.strip()[:300]})
  except OSError:pass
  if len(references)>=500:break
 return {'read_only':True,'source':str(source),'root':str(root),'references':references[:500],'truncated':len(references)>=500,'note':'Lineage is inferred from direct path references; inspect transformations separately.'}
