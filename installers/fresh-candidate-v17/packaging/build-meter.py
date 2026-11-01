#!/usr/bin/python3
"""Optional ABI-locked meter package; requires preinstalled matching headers.
Never calls apt and never upgrades running ASL. Run on native target builder.
"""
import argparse,hashlib,json,pathlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
def output(*cmd): return subprocess.check_output(cmd,text=True).strip()
arch=output('dpkg','--print-architecture')
if arch!='arm64': p.error('Native ARM64 builder required')
names=['asl3-asterisk','asl3-asterisk-dev','asl3-asterisk-modules']
versions={n:output('dpkg-query','-W','-f=${Version}',n) for n in names}
if len(set(versions.values()))!=1: p.error('Runtime, headers, and modules must have identical versions; no automatic changes made')
abi=versions[names[0]]
mods=[x for x in output('dpkg-query','-L','asl3-asterisk-modules').splitlines() if x.endswith('/modules/format_sln.so')]
if len(mods)!=1 or not pathlib.Path(mods[0]).is_file():p.error('Cannot identify module path')
out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);stage=out/'meter-stage';shutil.rmtree(stage,ignore_errors=True);(stage/'DEBIAN').mkdir(parents=True)
native=a.source.resolve()/'native-meter'
subprocess.run(['gcc','-O2','-Wall','-Wextra','-Werror',str(native/'test_fifo.c'),'-o',str(out/'test_fifo')],check=True)
subprocess.run([str(out/'test_fifo')],check=True)
module=stage/pathlib.Path(mods[0]).parent.relative_to('/')/'format_allmode_meter.so';module.parent.mkdir(parents=True)
subprocess.run(['gcc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror','-isystem','/usr/include',str(native/'format_allmode_meter.c'),'-o',str(module)],check=True)
version='0.8.0~beta9+abi'+hashlib.sha256(abi.encode()).hexdigest()[:12]
(stage/'DEBIAN/control').write_text(f'''Package: ara-allmode-meter
Version: {version}
Architecture: arm64
Maintainer: ARA ALLMODE packaging team <allmode@localhost>
Section: hamradio
Priority: optional
Depends: asl3-asterisk (= {abi}), asl3-asterisk-modules (= {abi}), libc6
Description: ALLMODE FIFO meter locked to exact ASL Asterisk ABI
 Built offline from source against matching ASL runtime headers.
''')
script=stage/'DEBIAN/preinst';script.write_text('''#!/bin/sh
set -eu
if command -v systemctl >/dev/null && systemctl is-active --quiet asterisk.service; then
 echo 'Confirm radio idle and stop Asterisk before changing meter ABI.' >&2; exit 1
fi
''');script.chmod(0o755)
doc=stage/'usr/share/doc/ara-allmode-meter';doc.mkdir(parents=True)
(doc/'BUILD.json').write_text(json.dumps({'asl_versions':versions,'architecture':arch,'source_sha256':hashlib.sha256((native/'format_allmode_meter.c').read_bytes()).hexdigest()},indent=2)+'\n')
shutil.copy2(native/'format_allmode_meter.c',doc);shutil.copy2(native/'meter_fifo.h',doc)
subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(out/f'ara-allmode-meter_{version}_arm64.deb')],check=True)
