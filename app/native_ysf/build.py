from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parent;B=R/'build';B.mkdir(exist_ok=True)
for n,h in json.loads((R/'PROVENANCE.json').read_text())['files'].items():assert hashlib.sha256((R/n).read_bytes()).hexdigest()==h
src=['YSFFICH.cpp','YSFConvolution.cpp','Golay24128.cpp','CRC.cpp']
subprocess.run(['g++','-std=c++11','-O2','-fPIC','-shared','-Wall','-Wextra','-I'+str(R/'vendor'),str(R/'fec.cpp'),*[str(R/'vendor'/n) for n in src],'-o',str(B/'liballmode_ysf.so')],check=True)
subprocess.run(['g++','-std=c++11','-O2','-I'+str(R/'reference'),str(R/'reference/fixture.cpp'),*[str(R/'reference'/n) for n in ['YSFFICH.cpp','YSFConvolution.cpp','Golay24128.cpp','CRCenc.cpp']],'-o',str(B/'fixture')],check=True)
