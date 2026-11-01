#!/usr/bin/python3
"""Inspect a .deb without installing; verify generic config and payload boundaries."""
import argparse,hashlib,json,pathlib,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('package',type=pathlib.Path);a=p.parse_args()
with tempfile.TemporaryDirectory() as temp:
 root=pathlib.Path(temp);subprocess.run(['dpkg-deb','--raw-extract',str(a.package),str(root)],check=True)
 assert not (root/'var/lib').exists(),'Persistent station state must not be a package payload'
 c=json.loads((root/'etc/allmode/service.json').read_text());assert c['public_origin']=='http://127.0.0.1:8787' and c['auth_file'] is None
 assert (root/'DEBIAN/conffiles').read_text().splitlines()==['/etc/allmode/service.json']
 for file in root.rglob('*'):
  assert not file.is_symlink(),'Unexpected package symlink'
  if file.is_file():assert file.stat().st_mode&0o6000==0,'Unexpected setuid/setgid payload'
 print(json.dumps({'sha256':hashlib.sha256(a.package.read_bytes()).hexdigest(),'generic_config':True,'no_station_state_payload':True,'no_setuid_or_symlinks':True},indent=2))
