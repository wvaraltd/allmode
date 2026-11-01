#!/usr/bin/python3
"""Unsigned OFFLINE staging only; signing/publishing is a separate approved step."""
import argparse,datetime,gzip,hashlib,pathlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('packages',nargs='+',type=pathlib.Path);a=p.parse_args()
root=a.output.resolve()
if any((root/'dists/trixie'/name).exists() for name in ['InRelease','Release.gpg']):p.error('Refusing to overwrite signed repository; stage a new generation')
pool=root/'pool/main/a/ara-allmode';pool.mkdir(parents=True,exist_ok=True)
architectures=set()
for f in a.packages:
 arch=subprocess.check_output(['dpkg-deb','-f',str(f),'Architecture'],text=True).strip();architectures.add(arch)
 dest=pool/f.name
 if dest.exists() and dest.read_bytes()!=f.read_bytes():p.error('Immutable pool filename already has different content: '+f.name)
 shutil.copy2(f,dest)
architectures.discard('all')
if not architectures:architectures.add('arm64')
for arch in sorted(architectures):
 d=root/f'dists/trixie/main/binary-{arch}';d.mkdir(parents=True,exist_ok=True)
 data=subprocess.check_output(['dpkg-scanpackages','-a',arch,'--multiversion','pool','/dev/null'],cwd=root)
 (d/'Packages').write_bytes(data);(d/'Packages.gz').write_bytes(gzip.compress(data,mtime=0))
dist=root/'dists/trixie';now=datetime.datetime.now(datetime.timezone.utc)
lines=['Origin: ARA','Label: ALLMODE tester staging','Suite: trixie','Codename: trixie',f'Date: {now:%a, %d %b %Y %H:%M:%S +0000}',f'Valid-Until: {now+datetime.timedelta(days=14):%a, %d %b %Y %H:%M:%S +0000}', 'Architectures: '+' '.join(sorted(architectures)),'Components: main','Description: UNSIGNED OFFLINE STAGING - NOT A PUBLISHED REPOSITORY','SHA256:']
for f in sorted(dist.rglob('*')):
 if f.is_file() and f.name in ('Packages','Packages.gz'):
  b=f.read_bytes();lines.append(f' {hashlib.sha256(b).hexdigest()} {len(b)} {f.relative_to(dist)}')
(dist/'Release').write_text('\n'.join(lines)+'\n')
print('Unsigned staging generated. No key was created, no signature or APT trust installed.')
