"""Build with existing GCC and existing pinned base objects; no installation."""
from pathlib import Path
import hashlib,json,subprocess,os
R=Path(__file__).resolve().parent;B=R/'build';B.mkdir(exist_ok=True);os.chdir(R)
m=json.loads((R/'manifest.json').read_text())
for n,h in m['files'].items():assert hashlib.sha256((R/'vendor'/n).read_bytes()).hexdigest()==h
flags=['-std=c99','-O2','-fPIC','-ffp-contract=off','-DMBE_STATIC','-D_DEFAULT_SOURCE','-DPFFFT_STATIC_DEFINE','-Wall','-Wextra','-Ivendor/src/internal','-I../vendor/mbelib/include','-I../vendor/mbelib/src/internal','-I../src','-I../build/include']
objects=list((R.parent/'build').glob('*.o'))
for source in ['vendor/src/ambe/ambe3600x2450.c','vendor/src/ambe/ambe3600x2450_enc.c','allmode_2450.c']:
 out=B/(Path(source).stem+'.o');subprocess.run(['gcc',*flags,'-c',source,'-o',str(out)],check=True);objects.append(out)
subprocess.run(['gcc','-shared',*[str(p) for p in objects],'-lm','-o',str(B/'liballmode_2450.so')],check=True)
for name in ['test_ambe2450_encoder','test_ambe2450_frame_types']:
 exe=B/name
 subprocess.run(['gcc',*flags,'-UNDEBUG','-include','../vendor/mbelib/tests/enable_assertions.h','vendor/tests/'+name+'.c',*[str(p) for p in objects],'-lm','-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('AMBE2450 native build and two upstream suites passed')
