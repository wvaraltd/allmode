from pathlib import Path
import subprocess,hashlib,json
R=Path(__file__).resolve().parent;B=R/'build';B.mkdir(exist_ok=True)
for n,h in json.loads((R/'PROVENANCE.json').read_text())['files'].items():assert hashlib.sha256((R/n).read_bytes()).hexdigest()==h
subprocess.run(['g++','-std=c++11','-O2','-fwrapv','-fPIC','-shared','-pthread','-I'+str(R/'vendor'),str(R/'wrapper.cpp'),*[str(p) for p in sorted((R/'vendor').glob('*.cc'))],'-o',str(B/'liballmode_p25.so')],check=True)
