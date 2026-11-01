#!/usr/bin/python3
"""Explicit offline local backup. No restore or service mutation is performed."""
import argparse,os,pathlib,subprocess,tarfile
p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
if os.geteuid()!=0:p.error('Root required to read station secrets')
for unit in ['asterisk','allmode-setup','allmode-system','allmode-digital']:
 if subprocess.run(['systemctl','is-active','--quiet',unit+'.service']).returncode==0:p.error('Stop idle station services before consistent backup')
paths=['etc/allmode','etc/asterisk','etc/systemd/system/allmode-setup.service','etc/systemd/system/allmode-setup.service.d','etc/systemd/system/allmode-system.service','etc/systemd/system/allmode-digital.service','var/lib/allmode','var/lib/allmode-system','var/lib/asterisk/allmode','opt/allmode','opt/allmode-vocoder-prototype','opt/MMDVM_Bridge','var/lib/mmdvm','var/lib/dvswitch','usr/share/ircddbgateway']
# Exclusive creation, owner-only mode, refuse overwrite and symlink destinations.
fd=os.open(a.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as stream:
 with tarfile.open(fileobj=stream,mode='w:gz',dereference=False) as tar:
  for path in paths:
   if pathlib.Path('/'+path).exists():tar.add('/'+path,arcname=path,recursive=True)
print('Private backup created. Contains secrets; do not upload or serve it publicly.')
