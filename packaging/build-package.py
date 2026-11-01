#!/usr/bin/python3
"""Build locally, never install. Release mode requires native Debian 13 ARM64."""
import argparse, hashlib, json, os, pathlib, shutil, struct, subprocess
from package_modes import normalize, CORE_EXEC, validate_archive
P=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--source',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);ap.add_argument('--version',default='0.8.0~beta9-7');ap.add_argument('--release',action='store_true');a=ap.parse_args()
src=a.source.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
arch=subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()
if a.release and (arch!='arm64' or 'VERSION_ID="13"' not in pathlib.Path('/etc/os-release').read_text()): ap.error('Release requires native Debian 13 ARM64 build executor')
# Build from retained source, not any prebaked machine binaries.
work=out/'source';shutil.rmtree(work,ignore_errors=True);shutil.copytree(src,work,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc','downloads'))
for d in [work/'codec/build',work/'codec/ambe2450/build',work/'app/native_p25/build',work/'app/native_ysf/build']: shutil.rmtree(d,ignore_errors=True)
subprocess.run(['bash','build-native.sh'],cwd=work,check=True)
stage=out/'stage';shutil.rmtree(stage,ignore_errors=True);(stage/'DEBIAN').mkdir(parents=True)
for source,target in [(work/'app','opt/allmode'),(work/'codec','opt/allmode-vocoder-prototype/current')]: shutil.copytree(source,stage/target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.o','test_*.py','test_*.c','test_*.cjs'))
# Fail closed on mixed architecture; never label an x86 binary ARM64.
elfs={}
for f in stage.rglob('*'):
 if f.is_file():
  b=f.read_bytes()
  if b[:4]==b'\x7fELF':
   machine=struct.unpack_from('<H',b,18)[0]
   if machine!={'arm64':183,'amd64':62}[arch]: raise SystemExit('Wrong ELF architecture: '+str(f))
   elfs[str(f.relative_to(stage))]=hashlib.sha256(b).hexdigest()
# Resolve native ABI dependencies on the release builder; structural containers
# without full dpkg library metadata are not release-capable.
(out/'debian').mkdir(exist_ok=True)
(out/'debian/control').write_text('Source: ara-allmode\nSection: hamradio\nPriority: optional\nMaintainer: ARA <allmode@localhost>\n\nPackage: ara-allmode\nArchitecture: any\nDescription: ALLMODE\n')
shared=[f for f in stage.rglob('*.so') if f.read_bytes()[:4]==b'\x7fELF']
check=subprocess.run(['dpkg-shlibdeps','-O',*sum((['-e',str(f)] for f in shared),[])],cwd=out,text=True,capture_output=True)
if a.release and check.returncode: raise SystemExit('Release ABI dependency resolution failed: '+check.stderr)
shlibs=check.stdout.strip().removeprefix('shlibs:Depends=') if check.returncode==0 else 'libc6, libstdc++6'
(out/'shlibdeps.log').write_text(check.stdout+check.stderr)
for source,target in [(P/'config.json','etc/allmode/service.json'),(P/'launch.py','usr/libexec/ara-allmode/launch.py'),(P/'backup.py','usr/libexec/ara-allmode/backup.py'),(P/'secure-dirs.py','usr/libexec/ara-allmode/secure-dirs.py'),(P/'maintenance-upgrade.py','usr/libexec/ara-allmode/maintenance-upgrade.py')]:
 dest=stage/target;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
units=stage/'usr/lib/systemd/system';units.mkdir(parents=True)
for f in (P/'units').glob('*'): shutil.copy2(f,units/f.name)
tmp=stage/'usr/lib/tmpfiles.d';tmp.mkdir(parents=True)
(tmp/'ara-allmode.conf').write_text('d /run/allmode-favorites 2770 allmode asterisk -\n')
doc=stage/'usr/share/doc/ara-allmode';doc.mkdir(parents=True)
for f in ['THIRD-PARTY.md','RELEASE-NOTES.md','RF-MEMORIES.md']: shutil.copy2(work/f,doc/f)
for f in P.glob('*.md'): shutil.copy2(f,doc/f.name)
(doc/'BUILD.json').write_text(json.dumps({'version':a.version,'architecture':arch,'release_candidate':a.release,'source_release':json.loads((src/'release.json').read_text()),'elf_sha256':elfs},indent=2)+'\n')
for script in ['preinst','postinst','postrm','prerm']: shutil.copy2(P/script,stage/'DEBIAN'/script)
(stage/'DEBIAN/conffiles').write_text('/etc/allmode/service.json\n')
(stage/'DEBIAN/control').write_text(f'''Package: ara-allmode
Version: {a.version}
Architecture: {arch}
Maintainer: ARA ALLMODE packaging team <allmode@localhost>
Section: hamradio
Priority: optional
Depends: python3, python3-serial, python3-bitarray, libcodec2-1.2, {shlibs}, adduser, systemd, asl3-asterisk, asl3-asterisk-modules, ara-allmode-meter
Recommends: alsa-utils, network-manager, iproute2
Description: ALLMODE standalone local radio console (staged tester packaging)
 Generic station onboarding and bundled source-built software codecs.
 No station credentials or upstream DVSwitch binaries are included.
 Services are not automatically started by package installation.
''')
# Include the staging root; reject symlinks and hardlinks before chmod.
normalize(stage, CORE_EXEC)
package=out/f'ara-allmode_{a.version}_{arch}.deb'
subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(package)],check=True)
validate_archive(package)
print(package)
