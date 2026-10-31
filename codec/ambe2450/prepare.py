"""Extract only AMBE2450 sources/tests from the already pinned upstream commit."""
from pathlib import Path
import subprocess,hashlib,json,re
R=Path(__file__).resolve().parent;UP=R.parents[1]/'.source-cache/mbelib'
SHA='a3c7bbdae9eb21cbfab57006c1a5daca7bdcba7f'
assert subprocess.check_output(['git','-C',str(UP),'rev-parse','HEAD']).decode().strip()==SHA
tree=set(subprocess.check_output(['git','-C',str(UP),'ls-tree','-r','--name-only',SHA]).decode().splitlines())
pending=['src/ambe/ambe3600x2450.c','src/ambe/ambe3600x2450_enc.c','tests/test_ambe2450_encoder.c','tests/test_ambe2450_frame_types.c']
files={}
while pending:
 name=pending.pop()
 if name in files:continue
 assert 'tetra' not in name.lower() and 'op25' not in name.lower()
 data=subprocess.check_output(['git','-C',str(UP),'show',SHA+':'+name]);files[name]=hashlib.sha256(data).hexdigest()
 dest=R/'vendor'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 for inc in re.findall(r'^\s*#include\s+"([^"]+)"',data.decode(),re.M):
  for p in [(Path(name).parent/inc).as_posix(),'src/internal/'+inc,'include/'+inc]:
   if p in tree:
    if p not in files:pending.append(p)
    break
(R/'manifest.json').write_text(json.dumps({'commit':SHA,'files':files},indent=2))
print('Extracted',len(files),'source files; no TETRA or binary plugins')
