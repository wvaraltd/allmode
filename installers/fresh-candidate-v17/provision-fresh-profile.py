#!/usr/bin/python3
import guard_proof
"""Publish a fresh-only preset after installed-stack native validation. No station edits."""
import argparse,hashlib,json,os,pathlib,secrets,stat,subprocess,time
STATE_DIRS=('var/lib/allmode','var/lib/allmode-system','var/lib/asterisk/allmode')
PACKAGES=('ara-allmode','ara-allmode-dvswitch','ara-allmode-dvswitch-guard','mmdvm-bridge')

def directory(path):
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in pathlib.Path(path).parts[1:]:
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
  return fd
 except BaseException:os.close(fd);raise

def regular_bytes(path,owner):
 parent=directory(path.parent)
 try:fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
 finally:os.close(parent)
 with os.fdopen(fd,'rb') as stream:
  info=os.fstat(stream.fileno())
  if not stat.S_ISREG(info.st_mode) or info.st_uid!=owner or info.st_mode&0o022:raise ValueError('Input must be a trusted regular file')
  return stream.read(),info

def no_prior_state(root):
 def empty(fd):
  for name in os.listdir(fd):
   info=os.stat(name,dir_fd=fd,follow_symlinks=False)
   if not stat.S_ISDIR(info.st_mode):return False
   child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
   try:
    if not empty(child):return False
   finally:os.close(child)
  return True
 for rel in STATE_DIRS:
  try:fd=directory(root/rel)
  except FileNotFoundError:continue
  try:
   if not empty(fd):raise ValueError('Existing station state found; fresh preset refused')
  finally:os.close(fd)

def validate_report(data,binary_hash,architecture):
 if not isinstance(data,list) or len(data)!=2:raise ValueError('Two-cycle native loopback validation required')
 for cycle,row in enumerate(data):
  if not isinstance(row,dict) or row.get('cycle')!=cycle or row.get('binary_sha256')!=binary_hash:raise ValueError('Validation identity mismatch')
  if row.get('scope')!='loopback-only; no RF; architecture '+architecture:raise ValueError('Native loopback scope mismatch')
  if any(row.get(key) is not True for key in ('pass_','authenticated','rx_voice_golden','tx_voice_matches_codec','owned_exporter')):raise ValueError('Native validation did not pass')

def provision(root,report,package_status,service_state,apply=False,owner=0,architecture='aarch64',guard_evidence=None,guard_snapshot=None):
 root=pathlib.Path(root);report=pathlib.Path(report)
 if architecture!='aarch64':raise ValueError('Native ARM64 validation required')
 if any(package_status(name)!='installed' for name in PACKAGES):raise ValueError('Required packages must be fully configured')
 for unit in ('asterisk','allmode-setup','allmode-system','allmode-digital','mmdvm_bridge'):
  if service_state(unit,'ActiveState')!='inactive':raise ValueError('All station services must be inactive for fresh provisioning')
 if guard_snapshot is None:raise ValueError('Current actual stock guard snapshot required')
 guard_proof.validate(guard_evidence,guard_snapshot())
 if os.path.lexists(root/'etc/allmode/allow-upstream-mmdvm-service'):raise ValueError('Stock-daemon consent marker conflicts with ALLMODE ownership')
 no_prior_state(root)
 binary,_=regular_bytes(root/'opt/MMDVM_Bridge/MMDVM_Bridge',owner)
 raw,info=regular_bytes(report,owner)
 if not 0<=time.time()-info.st_mtime<=3600:raise ValueError('Native validation report is stale')
 validate_report(json.loads(raw),hashlib.sha256(binary).hexdigest(),architecture)
 target=root/'etc/allmode';fd=directory(target)
 try:
  info=os.fstat(fd)
  if info.st_uid!=owner or info.st_mode&0o022:raise ValueError('Profile directory must be administrator-owned')
  name='install-profile.json'
  try:os.stat(name,dir_fd=fd,follow_symlinks=False)
  except FileNotFoundError:pass
  else:raise ValueError('Profile already exists; refusing overwrite')
  if not apply:return
  temp='.install-profile-'+secrets.token_hex(12)
  output=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
  try:
   with os.fdopen(output,'w') as stream:
    stream.write('{"version":1,"dvswitch_dmr_default":true}\n');stream.flush();os.fchmod(stream.fileno(),0o644);os.fsync(stream.fileno())
   # Atomic exclusive publication: unlike replace(), never clobber a racing file.
   guard_proof.validate(guard_evidence,guard_snapshot())
   os.link(temp,name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False);os.fsync(fd)
  finally:os.unlink(temp,dir_fd=fd)
 finally:os.close(fd)

def main():
 p=argparse.ArgumentParser();p.add_argument('--validation-report',required=True,type=pathlib.Path);p.add_argument('--guard-proof',required=True,type=pathlib.Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
 if os.geteuid()!=0:p.error('Administrator access required')
 def package(name):return subprocess.check_output(['dpkg-query','-W','-f=${db:Status-Status}',name],text=True).strip()
 def service(unit,field):return subprocess.check_output(['systemctl','show','--value','--property='+field,unit+'.service'],text=True).strip()
 def runner(argv,**kwargs):return subprocess.check_output(argv,text=True,timeout=kwargs.get('timeout',20))
 try:
  evidence=guard_proof.read(pathlib.Path('/'),str(a.guard_proof.absolute()),0)
  provision(pathlib.Path('/'),a.validation_report,package,service,a.apply,architecture=os.uname().machine,guard_evidence=json.loads(evidence),guard_snapshot=lambda:guard_proof.snapshot(pathlib.Path('/'),runner))
 except (OSError,ValueError,subprocess.CalledProcessError) as e:raise SystemExit(str(e))
 print('Fresh-only local DVSwitch preset created; RF remains stopped.' if a.apply else 'Eligible fresh station; dry run made no changes.')
if __name__=='__main__':main()
