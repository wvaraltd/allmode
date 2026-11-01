#!/usr/bin/python3
"""One-command controlled code upgrade after operator enters radio maintenance.
No auto-disconnect/PTT inference; Asterisk must already be stopped. Dry-run default.
"""
import argparse,datetime,json,os,pathlib,re,subprocess,sys,tempfile
SERVICES=['allmode-digital.service','allmode-setup.service','allmode-system.service']
def active(unit):return subprocess.run(['systemctl','is-active','--quiet',unit],capture_output=True).returncode==0
def transaction_allowed(output,allowed):
 changed=[]
 for line in output.splitlines():
  if line.startswith(('Inst ','Remv ')):
   action,name=line.split()[:2];name=name.split(':')[0]
   if action=='Remv' or name not in allowed:raise ValueError('Transaction changes unrelated package: '+name)
   changed.append(name)
 return changed

def durable_json(path,value):
 fd,name=tempfile.mkstemp(prefix='.journal-',dir=path.parent)
 try:
  with os.fdopen(fd,'w') as f:
   json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(name,path)
  directory=os.open(path.parent,os.O_DIRECTORY)
  try:os.fsync(directory)
  finally:os.close(directory)
 finally:
  if os.path.exists(name):os.unlink(name)

def versions(names):
 return {name:subprocess.check_output(['dpkg-query','-W','-f=${db:Status-Status} ${Version}',name],text=True).strip() for name in sorted(names)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--version',required=True);p.add_argument('--meter-version');p.add_argument('--apply',action='store_true');a=p.parse_args()
 if not re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*',a.version):p.error('Invalid package version')
 packages=['ara-allmode='+a.version];allowed={'ara-allmode'}
 if a.meter_version:
  if not re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*',a.meter_version):p.error('Invalid meter version')
  packages+=['ara-allmode-meter='+a.meter_version];allowed.add('ara-allmode-meter')
 command=['apt-get','install','--only-upgrade','--no-remove',*packages]
 audit=subprocess.run(['dpkg','--audit'],text=True,capture_output=True)
 if audit.returncode or audit.stdout.strip() or audit.stderr.strip():sys.exit('Resolve pending dpkg state before updating; no services changed.')
 before=versions(allowed)
 if any(not value.startswith('installed ') for value in before.values()):sys.exit('Maintenance command is for existing installed packages only')
 simulation=subprocess.run(['apt-get','-s',*command[1:]],text=True,capture_output=True,env=dict(os.environ,LC_ALL='C'))
 if simulation.returncode:sys.exit('APT simulation failed. Review dependency state; no services changed.\n'+simulation.stderr)
 try: changes=transaction_allowed(simulation.stdout,allowed)
 except ValueError as e:sys.exit(str(e)+'; no services changed.')
 print(simulation.stdout)
 if not a.apply:print('Dry run only. Add --apply after placing the radio in maintenance.');return
 if os.geteuid()!=0:sys.exit('Root required for apply')
 if active('asterisk.service'):sys.exit('Radio is running; safe TX state cannot be established. Use System & maintenance → Stop radio services after confirming RF idle, then rerun this same command. No services changed.')
 if not changes:print('Requested versions already installed. Nothing changed.');return
 prior=[u for u in SERVICES if active(u)]
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 base=pathlib.Path('/var/backups/ara-allmode');base.mkdir(mode=0o700,parents=True,exist_ok=True)
 if base.is_symlink() or base.stat().st_uid!=0 or base.stat().st_mode&0o077:sys.exit('Backup directory must be root-owned and mode 0700')
 journal=base/(stamp+'.json');fd=os.open(journal,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 os.close(fd)
 record={'prior_services':prior,'packages':packages,'versions_before':before,'phase':'prepared'}
 def phase(name):
  record['phase']=name;record['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();durable_json(journal,record)
 phase('prepared')
 try:
  for unit in SERVICES:subprocess.run(['systemctl','stop',unit],check=True)
  if active('asterisk.service'):raise RuntimeError('Asterisk became active; upgrade refused')
  subprocess.run(['/usr/bin/python3','/usr/libexec/ara-allmode/backup.py','--output',str(base/(stamp+'.tar.gz'))],check=True)
  phase('backed-up')
  # Download authenticated exact packages, then dpkg only those files. Unlike a
  # second apt solver transaction, this cannot install unrelated dependencies.
  with tempfile.TemporaryDirectory(prefix='download-',dir=base) as directory:
   subprocess.run(['apt-get','download',*packages],cwd=directory,check=True)
   files=sorted(pathlib.Path(directory).glob('*.deb'));found={}
   for file in files:
    info=subprocess.check_output(['dpkg-deb','-f',str(file),'Package','Version'],text=True).splitlines()
    fields=dict(line.split(': ',1) for line in info)
    found[fields['Package']]=fields['Version']
   expected=dict(item.split('=',1) for item in packages)
   if found!=expected or len(files)!=len(expected):raise RuntimeError('Downloaded package identities differ from request')
   phase('installing')
   subprocess.run(['dpkg','--install',*[str(f) for f in files]],check=True)
  record['versions_after']=versions(allowed)
  if record['versions_after']!={name:'installed '+version for name,version in expected.items()}:raise RuntimeError('Installed versions differ from request')
  phase('installed')
  subprocess.run(['/usr/libexec/ara-allmode/launch.py','--check'],check=True)
  phase('config-validated')
  for unit in reversed(prior):subprocess.run(['systemctl','start',unit],check=True)
  phase('console-restored-radio-stopped')
 except (subprocess.CalledProcessError,RuntimeError,OSError,ValueError):
  record['failed_phase']=record['phase'];phase('failed-radio-stopped')
  sys.exit('Upgrade did not complete. Radio remains in maintenance; inspect '+str(journal)+' and private backup. Do not auto-resume RF; repair dpkg or use documented rollback.')
 print('Code updated; previous console/helper services restored. Radio remains stopped. Validate before explicitly activating RF.')
if __name__=='__main__':main()
