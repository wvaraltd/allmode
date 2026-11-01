#!/usr/bin/python3
"""ALLMODE Debian 13 ARM64 bootstrap. Default is a read-only plan; --apply required.
No OS-wide upgrade, live RF stop, key bypass, credentials, or station identity defaults.
"""
import argparse,atexit,ipaddress,datetime,fcntl,hashlib,importlib.util,json,os,pathlib,re,secrets,shlex,shutil,stat,subprocess,tarfile,tempfile,urllib.request
HERE=pathlib.Path(__file__).resolve().parent
CORE='0.8.0~beta9-3';ADDON='0.8.0~beta9-1';GUARD_PACKAGE='0.8.0~beta9-1';METER='0.8.0~beta9+abid1486d408855'
UPSTREAM={'mmdvm-bridge':'1.6.8-20241231-96','dvswitch-base':'1.6.0-20250507-99'}
ASL='2:22.10.1+asl3-3.10.8-1.deb13'
DBUS='1.16.2-2'
DBUS_NEW={'dbus','dbus-bin','dbus-daemon','dbus-system-bus-common','dbus-session-bus-common','libdbus-1-3','libexpat1','libc6','libsystemd0','init-system-helpers','base-files'}
RADIO=('asterisk.service','allmode-digital.service','mmdvm_bridge.service')
APP=('allmode-directories.timer','allmode-directories.service','allmode-setup.service','allmode-system.service')
BASE_UNITS=('allmode-setup.service','allmode-system.service','allmode-digital.service','allmode-directories.service','allmode-directories.timer')
ASL_KEY_URL='https://raw.githubusercontent.com/AllStarLink/asl-apt-repos/32d4dd6af2baf2d313ce15b6b27023cfafcc8030/allstarlink.gpg'
ASL_KEY_SHA='af652e0473ed95d73345a8c6912cb38ac29001b67c30ea767fa99fa7cbd5e9de'
KEYS={
 'ara-allmode':('https://rf.ara.radio/allmode/apt/allmode-archive-keyring.gpg','59DAB5C15B5F96D5660E0D94503AE6F5AD483087'),
 'dvswitch':('https://dvswitch.org/DVSwitch_Repository/dvswitch-keyring.gpg','6DDFC33CD5FC678659642DF572147EC1E788D4C3'),
 'allstarlink':(ASL_KEY_URL,'F2AF416869932ABB39E165E5409D50181BD84509')}
SOURCES={
 'ara-allmode.list':'deb [arch=arm64 signed-by=/etc/apt/keyrings/ara-allmode.gpg] https://rf.ara.radio/allmode/apt/ trixie main\n',
 'dvswitch.list':'deb [arch=arm64 signed-by=/etc/apt/keyrings/dvswitch.gpg] https://dvswitch.org/DVSwitch_Repository bookworm hamradio\n',
 'allstarlink.list':'deb [signed-by=/etc/apt/keyrings/allstarlink.gpg] https://repo.allstarlink.org/public trixie main\n'}
PIN='Package: mmdvm-bridge dvswitch-base\nPin: origin dvswitch.org\nPin-Priority: 500\n\nPackage: *\nPin: origin dvswitch.org\nPin-Priority: -1\n'
STATE=('var/lib/allmode','var/lib/allmode-system','var/lib/asterisk/allmode','etc/asterisk')
LOG_DIR=None
APT_AUTH=['-o','APT::Get::AllowUnauthenticated=false','-o','Acquire::AllowInsecureRepositories=false','-o','Acquire::AllowDowngradeToInsecureRepositories=false','-o','Acquire::AllowWeakRepositories=false','-o','Acquire::Check-Valid-Until=true']
GUARD='[Unit]\nConditionPathExists=/etc/allmode/permit-asterisk-during-bootstrap\n'

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
launcher=module('allmode_launch',HERE/'packaging/launch.py')
profile=module('allmode_profile',HERE/'provision-fresh-profile.py')

def run(argv,**kw):
 result=subprocess.run(argv,text=True,capture_output=True,env=dict(os.environ,LC_ALL='C'),**kw)
 log=None
 if LOG_DIR is not None:
  log=LOG_DIR/(secrets.token_hex(12)+'.json')
  fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'w') as stream:json.dump({'argv':argv,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},stream);stream.flush();os.fsync(stream.fileno())
 if result.returncode:raise RuntimeError('Command failed with exit '+str(result.returncode)+('; private diagnostic: '+str(log) if log else ' before installer changes: '+argv[0]))
 return result.stdout

def acquire_lock(path,owner=0):
 fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
 try:
  info=os.fstat(fd)
  if not stat.S_ISREG(info.st_mode) or info.st_uid!=owner or info.st_mode&0o077:raise ValueError('Unsafe bootstrap lock file')
  fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  return fd
 except BaseException:os.close(fd);raise

def safe_directory(path,owner=0):
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for part in pathlib.Path(path).parts[1:]:
   try:os.mkdir(part,0o755,dir_fd=fd)
   except FileExistsError:pass
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
  st=os.fstat(fd)
  if st.st_uid!=owner or st.st_mode&0o022:raise ValueError('Unsafe administrator directory: '+str(path))
  return fd
 except BaseException:os.close(fd);raise

def atomic_new(path,data,mode=0o644,owner=0,identical=True):
 path=pathlib.Path(path);fd=safe_directory(path.parent,owner)
 try:
  try:old=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
  except FileNotFoundError:old=None
  if old is not None:
   with os.fdopen(old,'rb') as stream:
    st=os.fstat(stream.fileno())
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=owner or st.st_mode&0o022:raise ValueError('Unsafe existing file: '+str(path))
    if identical and stream.read()==data:return
   raise ValueError('Existing different file retained: '+str(path))
  tmp='.allmode-'+secrets.token_hex(12);out=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
  try:
   with os.fdopen(out,'wb') as stream:stream.write(data);stream.flush();os.fchmod(stream.fileno(),mode);os.fsync(stream.fileno())
   os.link(tmp,path.name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False);os.fsync(fd)
  finally:os.unlink(tmp,dir_fd=fd)
 finally:os.close(fd)

def fingerprints(colons):
 found=[];primary=False
 for line in colons.splitlines():
  fields=line.split(':')
  if fields[0]=='pub':primary=True
  elif fields[0]=='sub':primary=False
  elif fields[0]=='fpr' and primary:found.append(fields[9]);primary=False
 return found

def get(url,target,sha=None):
 if not url.startswith('https://'):raise ValueError('HTTPS required')
 with urllib.request.urlopen(url,timeout=60) as response:
  if not response.url.startswith('https://'):raise ValueError('Unsafe redirect')
  data=response.read(32*1024*1024+1)
 if len(data)>32*1024*1024:raise ValueError('Download exceeds bound')
 if sha and hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Pinned artifact digest mismatch')
 pathlib.Path(target).write_bytes(data)

def trust(root,work,runner=run):
 keydir=root/'etc/apt/keyrings';sources=root/'etc/apt/sources.list.d'
 for name,(url,expected) in KEYS.items():
  path=work/(name+'.gpg')
  digest=('e87906811436a2aa356abd3100139f4a8ae3faeaef5d6f8a22652fb515ebbe78' if name=='dvswitch' else ASL_KEY_SHA if name=='allstarlink' else None)
  get(url,path,digest)
  home=work/('gpg-'+name);home.mkdir(mode=0o700,exist_ok=True)
  if fingerprints(runner(['gpg','--homedir',str(home),'--batch','--show-keys','--with-colons',str(path)]))!=[expected]:raise ValueError('Archive key fingerprint mismatch: '+name)
  existing=keydir/(name+'.gpg')
  if os.path.lexists(existing):
   existing_data,_=profile.regular_bytes(existing,0)
   if fingerprints(runner(['gpg','--homedir',str(home),'--batch','--show-keys','--with-colons',str(existing)]))!=[expected]:raise ValueError('Conflicting installed trust retained: '+name)
  else:atomic_new(existing,path.read_bytes())
 for name,content in SOURCES.items():
  path=sources/name
  if os.path.lexists(path):
   existing_data,_=profile.regular_bytes(path,0)
   active='\n'.join(x.strip() for x in existing_data.decode().splitlines() if x.strip() and not x.lstrip().startswith('#'))+'\n'
   if active!=content:raise ValueError('Existing repository definition needs review: '+str(path))
  else:atomic_new(path,content.encode())
 atomic_new(root/'etc/apt/preferences.d/ara-dvswitch',PIN.encode())
 runner(['apt-get',*APT_AUTH,'-o','DPkg::Lock::Timeout=300','update'])

def solve(output,requested):
 planned={}
 for line in output.splitlines():
  if line.startswith('Remv '):raise ValueError('Package removals refused')
  if line.startswith('Inst '):
   match=re.match(r'Inst ([A-Za-z0-9+.:_-]+)(?: \[([^]]+)\])? \(([^ ]+)',line)
   if not match:raise ValueError('Unrecognized apt plan')
   name,old,version=match.groups();name=name.split(':')[0]
   if old and not name.startswith('ara-allmode'):raise ValueError('Non-ALLMODE upgrade refused: '+name)
   if name in ('asl3-asterisk','asl3-asterisk-dev','asl3-asterisk-modules') and version!=ASL:raise ValueError('Unexpected ASL ABI transaction')
   planned[name]=version
 for name,version in requested.items():
  if name in planned and planned[name]!=version:raise ValueError('Requested version mismatch')
 return planned

def durable_record(path,value):
 path=pathlib.Path(path);fd=profile.directory(path.parent);temp='.record-'+secrets.token_hex(12)
 try:
  output=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
  try:
   with os.fdopen(output,'w') as stream:json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
   os.replace(temp,path.name,src_dir_fd=fd,dst_dir_fd=fd);os.fsync(fd)
  finally:
   try:os.unlink(temp,dir_fd=fd)
   except FileNotFoundError:pass
 finally:os.close(fd)

def record_transaction(requested,closure):
 if LOG_DIR is None or not LOG_DIR.exists():return
 path=LOG_DIR.parent/'transactions.json'
 records=json.loads(path.read_text()) if path.exists() else []
 records.append({'requested':requested,'closure':closure,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 durable_record(path,records)

def resume_pending_check(work,runner=run):
 allowed={};path=work/'transactions.json'
 if path.exists():
  raw,_=profile.regular_bytes(path,0)
  for row in json.loads(raw):allowed.update(row['closure']);allowed.update(row['requested'])
 text=runner(['dpkg-query','-W','-f=${Package}\t${Version}\t${db:Status-Status}\t${Architecture}\n'])
 for line in text.splitlines():
  name,version,status,architecture=line.split('\t')
  if status in ('installed','not-installed','config-files'):continue
  if allowed.get(name)!=version or architecture not in ('arm64','all'):raise ValueError('Unrecorded pending package state; resume refused: '+name)


def install(requested,runner=run,allowed_new=None):
 specs=[k+'='+v for k,v in sorted(requested.items())]
 plan=runner(['apt-get',*APT_AUTH,'-s','--no-remove','install',*specs]);closure=solve(plan,requested)
 if allowed_new is not None and set(closure)-set(allowed_new):raise ValueError('Unrelated system-bus dependency refused: '+', '.join(sorted(set(closure)-set(allowed_new))))
 record_transaction(requested,closure)
 exact=dict(closure,**requested);specs=[k+'='+v for k,v in sorted(exact.items())]
 # Revalidate the pinned closure, then isolate its authenticated downloads. The
 # real apt transaction cannot obtain a new dependency or use an unrelated cache.
 if solve(runner(['apt-get',*APT_AUTH,'-s','--no-remove','install',*specs]),exact)!=closure:raise ValueError('APT transaction changed during preparation')
 parent=LOG_DIR.parent if LOG_DIR is not None and LOG_DIR.exists() else None
 with tempfile.TemporaryDirectory(prefix='transaction-',dir=parent) as folder:
  archives=pathlib.Path(folder)/'archives';archives.mkdir(mode=0o700);(archives/'partial').mkdir(mode=0o700)
  cache=['-o','Dir::Cache::archives='+str(archives)]
  runner(['apt-get',*APT_AUTH,*cache,'-o','DPkg::Lock::Timeout=300','--download-only','--no-remove','-y','install',*specs])
  found={}
  for file in archives.glob('*.deb'):
   info=runner(['dpkg-deb','-f',str(file),'Package','Version','Architecture'])
   fields=dict(line.split(': ',1) for line in info.splitlines() if ': ' in line)
   name=fields.get('Package');version=fields.get('Version')
   if fields.get('Architecture') not in ('arm64','all') or name in found:raise ValueError('Invalid downloaded package architecture or duplicate')
   found[name]=version
  if found!=closure:raise ValueError('Downloaded archives differ from reviewed transaction')
  if LOG_DIR is not None and LOG_DIR.exists():durable_record(LOG_DIR.parent/('archives-'+secrets.token_hex(8)+'.json'),{file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in archives.glob('*.deb')})
  runner(['apt-get',*APT_AUTH,*cache,'-o','DPkg::Lock::Timeout=300','-o','Dpkg::Options::=--force-confold','--no-download','--no-remove','-y','install',*specs])
  installed=runner(['dpkg-query','-W','-f=${Package}\t${Version}\t${db:Status-Status}\n',*sorted(exact)])
  actual={}
  for line in installed.splitlines():
   name,version,status=line.split('\t')
   if status!='installed':raise ValueError('Package not fully configured: '+name)
   actual[name]=version
  if actual!=exact:raise ValueError('Installed package versions do not match reviewed transaction')

def guard_condition_json(raw,marker):
 value=json.loads(raw)
 if value.get('type')!='a(sbbsi)' or not isinstance(value.get('data'),list):raise ValueError('Unrecognized systemd condition representation')
 for row in value['data']:
  if isinstance(row,list) and len(row)==5 and row[0]=='ConditionPathExists' and row[1] is False and row[2] is False and row[3]==marker:return
 raise ValueError('Required non-trigger, non-negated guard is not effective')

def effective_guard(unit,marker,root,runner=run):
 if os.path.lexists(root/marker.lstrip('/')):raise ValueError('Guard consent path must be absent')
 runner(['systemctl','show','--value','--property=LoadState',unit])
 raw=json.loads(runner(['busctl','--json=short','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager','GetUnit','s',unit]))
 path=raw.get('data')
 if isinstance(path,list) and len(path)==1:path=path[0]
 if raw.get('type')!='o' or not isinstance(path,str) or not path.startswith('/org/freedesktop/systemd1/unit/'):raise ValueError('Cannot resolve exact systemd unit')
 conditions=runner(['busctl','--json=short','get-property','org.freedesktop.systemd1',path,'org.freedesktop.systemd1.Unit','Conditions'])
 guard_condition_json(conditions,marker)

def system_bus_check(runner=run):
 # The same system-scope transport used by effective_guard must answer before
 # any guard installation/inspection. PID1's private socket is not substituted.
 runner(['busctl','--system','--timeout=15s','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.DBus.Peer','Ping'])

def ensure_system_bus(runner=run):
 try:
  system_bus_check(runner)
  return
 except RuntimeError:
  pass
 installed=runner(['dpkg-query','-W','-f=${Package}\t${db:Status-Status}\n'])
 if any(line.split('\t')[0].split(':')[0] in ('dbus','dbus-broker') and line.split('\t')[-1]=='installed' for line in installed.splitlines()):
  raise ValueError('Existing system bus is unavailable; repair its service explicitly before bootstrap. No guards changed.')
 # Use existing signed Debian trust before adding ALLMODE/upstream sources.
 # The reviewed version is pinned; no system-wide upgrade or bus restart.
 runner(['apt-get',*APT_AUTH,'-o','DPkg::Lock::Timeout=300','update'])
 install({'dbus':DBUS},runner,allowed_new=DBUS_NEW)
 # Debian's static unit is intentionally not started by package postinst.
 # Start only the bus we just installed; never enable/unmask/restart a prior bus.
 runner(['systemctl','start','dbus.socket','dbus.service'])
 try:system_bus_check(runner)
 except RuntimeError as error:
  raise ValueError('Debian dbus installed but system bus is unavailable; no guards changed. Inspect private command diagnostics and dbus.service before retry.') from error

def ensure_bootstrap_tools(runner=run):
 needed=[]
 if not shutil.which('gpg'):needed.append('gpg')
 if not pathlib.Path('/etc/ssl/certs/ca-certificates.crt').is_file():needed.append('ca-certificates')
 if not needed:return
 # Only existing system trust is used to obtain initial verifier/CA tooling.
 runner(['apt-get',*APT_AUTH,'-o','DPkg::Lock::Timeout=300','update'])
 versions={}
 for name in needed:
  text=runner(['apt-cache','policy',name]);match=re.search(r'^\s*Candidate:\s*(\S+)',text,re.M)
  if not match or match[1]=='(none)':raise ValueError('No authenticated system candidate for '+name)
  versions[name]=match[1]
 install(versions,runner)

def legacy_config(unit_text):
 command=None;section=None
 for raw in unit_text.splitlines():
  line=raw.strip()
  if line.startswith('['):section=line
  elif section=='[Service]' and line.startswith('ExecStart='):
   value=line[len('ExecStart='):]
   if '\\' in value or '$' in value or '%' in value:raise ValueError('Complex legacy ExecStart requires review')
   command=shlex.split(value) if value else None
 if not command or command[:2]!=['/usr/bin/python3','/opt/allmode/server.py']:raise ValueError('Unsupported legacy entry point')
 result=dict(schema=1,port=8787,public_origin='http://127.0.0.1:8787',auth_file=None,hardware=False,lan_proxy=False)
 args=command[2:];seen=set()
 while args:
  option=args.pop(0)
  if option in seen:raise ValueError('Repeated legacy option')
  seen.add(option)
  if option=='--managed':continue
  if option in ('--hardware','--lan-proxy'):result[option[2:].replace('-','_')]=True
  elif option in ('--port','--public-origin','--auth-file') and args:
   value=args.pop(0);result[option[2:].replace('-','_')]=int(value) if option=='--port' else value
  else:raise ValueError('Unsupported legacy option: '+option)
 if '--managed' not in seen:raise ValueError('Legacy managed mode required')
 return result

def state_hashes(root):
 result={}
 for name in STATE:
  path=root/name
  if not path.exists():continue
  for file in path.rglob('*'):
   info=file.lstat()
   if stat.S_ISDIR(info.st_mode):continue
   metadata={'uid':info.st_uid,'gid':info.st_gid,'mode':stat.S_IMODE(info.st_mode)}
   if stat.S_ISLNK(info.st_mode):metadata['link']=os.readlink(file)
   elif stat.S_ISREG(info.st_mode):
    parent=profile.directory(file.parent)
    try:fd=os.open(file.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
    finally:os.close(parent)
    with os.fdopen(fd,'rb') as stream:
     current=os.fstat(stream.fileno())
     if not stat.S_ISREG(current.st_mode) or (current.st_ino,current.st_dev)!=(info.st_ino,info.st_dev):raise ValueError('Station file changed during snapshot')
     metadata.update(uid=current.st_uid,gid=current.st_gid,mode=stat.S_IMODE(current.st_mode),sha256=hashlib.file_digest(stream,'sha256').hexdigest())
   else:raise ValueError('Unsupported special station-state file: '+str(file))
   result[str(file.relative_to(root))]=metadata
 return result

def backup(root,work):
 paths=['etc/systemd/system/mmdvm_bridge.service.d','etc/systemd/system/multi-user.target.wants/mmdvm_bridge.service','etc/systemd/system/asterisk.service','etc/systemd/system/asterisk.service.d','etc/systemd/system/multi-user.target.wants/asterisk.service','etc/allmode','etc/asterisk','etc/apt/keyrings','etc/apt/sources.list.d','etc/apt/preferences.d','var/lib/allmode','var/lib/allmode-system','var/lib/asterisk/allmode','opt/allmode','opt/allmode-vocoder-prototype','opt/MMDVM_Bridge','var/lib/mmdvm','var/lib/dvswitch','usr/share/ircddbgateway']
 paths += [str(p.relative_to(root)) for p in (root/'etc/systemd/system').glob('allmode*')]
 paths += [str(p.relative_to(root)) for p in (root/'etc/systemd/system').glob('*.wants/allmode*')]
 paths += [str(p.relative_to(root)) for p in root.glob('usr/lib/**/format_allmode_meter.so')]
 fd=os.open(work/'before.tar.gz',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as stream:
  with tarfile.open(fileobj=stream,mode='w:gz',dereference=False) as tar:
   for path in paths:
    if os.path.lexists(root/path):tar.add(root/path,arcname=path)

def migrate_code(root,work):
 moved=work/'legacy';moved.mkdir(mode=0o700,exist_ok=True);ledger=work/'moves.json'
 if ledger.exists():entries=json.loads(ledger.read_text())
 else:
  paths=['opt/allmode','opt/allmode-vocoder-prototype']+['etc/systemd/system/'+x for x in BASE_UNITS]
  paths+=['etc/systemd/system/allmode-setup.service.d/'+x for x in ('lan.conf','runtime.conf')]
  entries=[]
  for rel in paths:
   old=root/rel
   if not os.path.lexists(old):continue
   info=old.lstat()
   if stat.S_ISLNK(info.st_mode):raise ValueError('Legacy code/unit symlink requires review: '+rel)
   if info.st_dev!=work.stat().st_dev:raise ValueError('Cross-filesystem migration requires a reviewed copy plan: '+rel)
   entries.append({'path':rel,'inode':info.st_ino,'device':info.st_dev,'status':'planned'})
  durable_record(ledger,entries)
 for row in entries:
  old=root/row['path'];target=moved/row['path']
  def matches(path):
   try:info=path.lstat();return not stat.S_ISLNK(info.st_mode) and (info.st_ino,info.st_dev)==(row['inode'],row['device'])
   except FileNotFoundError:return False
  if matches(target):row['status']='moved';durable_record(ledger,entries);continue
  if row['status']=='moved' or os.path.lexists(target) or not matches(old):raise ValueError('Legacy move provenance changed; refusing overwrite: '+row['path'])
  target.parent.mkdir(parents=True,exist_ok=True);os.rename(old,target);row['status']='moved';durable_record(ledger,entries)
 # rf-memories.conf remains in place; no recursive state ownership change.

def normalize_enablement_links(root,work,owner=0):
 ledger=work/'enablement-links.json'
 changes=json.loads(ledger.read_text()) if ledger.exists() else []
 for folder in (root/'etc/systemd/system').glob('*.wants'):
  fd=profile.directory(folder)
  try:
   for name in BASE_UNITS:
    try:info=os.stat(name,dir_fd=fd,follow_symlinks=False)
    except FileNotFoundError:continue
    if not stat.S_ISLNK(info.st_mode):raise ValueError('Administrator unit file in wants directory requires review')
    old=os.readlink(name,dir_fd=fd)
    if old!='/etc/systemd/system/'+name:continue
    new='/usr/lib/systemd/system/'+name
    if not (root/new.lstrip('/')).is_file():raise ValueError('Packaged unit is missing: '+name)
    change={'path':str((folder/name).relative_to(root)),'before':old,'after':new}
    if change not in changes:changes.append(change);durable_record(ledger,changes)
    temp='.allmode-link-'+secrets.token_hex(12);os.symlink(new,temp,dir_fd=fd)
    try:os.replace(temp,name,src_dir_fd=fd,dst_dir_fd=fd);os.fsync(fd)
    finally:
     try:os.unlink(temp,dir_fd=fd)
     except FileNotFoundError:pass

  finally:os.close(fd)
 durable_record(ledger,changes)

def write_journal(work,record):durable_record(work/'journal.json',record)

def native_validation(work,runner=run):
 # Run the published loopback harness unprivileged against installed immutable code.
 validation=pathlib.Path(tempfile.mkdtemp(prefix='ara-native-',dir='/var/tmp'))
 try:
  identity=runner(['id','-u','allmode']).strip();group=runner(['id','-g','allmode']).strip();validation.chmod(0o700)
  source=validation/'source';source.mkdir();source.chmod(0o755);(source/'app').symlink_to('/opt/allmode',target_is_directory=True);(source/'codec').symlink_to('/opt/allmode-vocoder-prototype/current',target_is_directory=True)
  # Private unprivileged process cannot touch root-owned live config, all sockets loopback.
  harness=validation/'verify.py';shutil.copyfile(HERE/'verify-dvswitch-loopback.py',harness);harness.chmod(0o644)
  # Finish every root write before exposing the workspace to its test UID.
  os.chown(validation,int(identity),int(group))
  runner(['runuser','-u','allmode','--','/usr/bin/python3',str(harness),'--source',str(source),'--binary','/opt/MMDVM_Bridge/MMDVM_Bridge','--output',str(validation/'result')])
  raw,_=profile.regular_bytes(validation/'result/loopback-results.json',int(identity));report=work/('native-validation-'+secrets.token_hex(8)+'.json');atomic_new(report,raw,0o600)
  return report
 finally:shutil.rmtree(validation)

def reject_packaged_migration(code,status):
 if code==0 and status.strip() not in ('not-installed','config-files',''):raise ValueError('Already package-managed: use /usr/libexec/ara-allmode/maintenance-upgrade.py, not legacy migration')

def bundle_identity():
 return {name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('bootstrap.py','provision-fresh-profile.py','verify-dvswitch-loopback.py','packaging/launch.py')}

def initial_access(environment=None):
 env=os.environ if environment is None else environment
 user=env.get('SUDO_USER','');connection=env.get('SSH_CONNECTION','').split();host=None
 if len(connection)==4:
  try:
   host=str(ipaddress.ip_address(connection[2]));port=int(connection[3])
   if not 1<=port<=65535:host=None
  except ValueError:host=None
 if re.fullmatch(r'[a-z_][a-z0-9_-]*',user) and host:
  destination=user+'@'+('['+host+']' if ':' in host else host)
  return 'On your computer run: ssh -p '+str(port)+' -N -L 8787:127.0.0.1:8787 '+shlex.quote(destination)+' . Then open http://127.0.0.1:8787/setup; keep the SSH window open.'
 return 'On your computer use the SAME SSH login and host used to reach this machine: ssh -N -L 8787:127.0.0.1:8787 LOGIN@HOST . Replace LOGIN@HOST with that existing SSH destination; no account/password is created. Then open http://127.0.0.1:8787/setup and keep SSH open.'

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('fresh','legacy-migrate'));parser.add_argument('--apply',action='store_true');parser.add_argument('--resume',type=pathlib.Path);a=parser.parse_args()
 record=None;work=None
 if a.resume:
  if os.geteuid()!=0:parser.error('Administrator access is needed to read a private resume journal')
  work=a.resume.absolute();fd=profile.directory(work)
  try:
   info=os.fstat(fd)
   if info.st_uid!=0 or info.st_mode&0o077:parser.error('Unsafe resume directory')
  finally:os.close(fd)
  raw,_=profile.regular_bytes(work/'journal.json',0);record=json.loads(raw)
  if record.get('schema')!=1 or record.get('bundle_sha256')!=bundle_identity():parser.error('Use the identical authenticated bootstrap version that created this journal')
  if a.mode and a.mode!=record.get('mode'):parser.error('Resume mode mismatch')
  a.mode=record['mode']
  if record.get('phase')=='console-ready-radio-stopped':print('This bootstrap completed already; no changes made.');return
 if a.mode is None:parser.error('Select --mode fresh or legacy-migrate, or --resume PRIVATE_DIRECTORY')
 print('Plan: signed Debian system-bus prerequisite; backup; scoped verified keys; apt update (indexes only); separate guard; pinned upstream; clean ALLMODE install; loopback validation; console only. RF never auto-starts.')
 if not a.apply:return
 if os.geteuid()!=0:parser.error('Run --apply with administrator permission')
 try:lock=acquire_lock('/run/lock/ara-allmode-bootstrap.lock')
 except BlockingIOError:parser.error('Another ALLMODE bootstrap is running; wait without removing locks')
 atexit.register(os.close,lock)
 if run(['dpkg','--print-architecture']).strip()!='arm64' or 'VERSION_ID="13"' not in pathlib.Path('/etc/os-release').read_text():parser.error('Requires Debian13 ARM64')
 for command in ('apt-get','dpkg-deb','runuser','systemctl','busctl'):
  if not shutil.which(command):parser.error('Required system tool missing: '+command)
 if record:resume_pending_check(work)
 else:
  audit=run(['dpkg','--audit'])
  if audit.strip():parser.error('Resolve pending dpkg state before bootstrap')
 for unit in RADIO:
  state=run(['systemctl','show','--value','--property=ActiveState',unit]).strip()
  if state!='inactive':parser.error('Put radio in /admin → Stop radio services after confirming RF idle; '+unit+' is not inactive')
 root=pathlib.Path('/')
 if record:
  configuration=record.get('configuration')
 elif a.mode=='fresh':
  profile.no_prior_state(root)
  if os.path.lexists('/etc/allmode/install-profile.json'):parser.error('Fresh profile already exists; do not overwrite prior installation settings')
  existing=subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}','asl3-asterisk'],capture_output=True,text=True)
  if existing.returncode==0 and existing.stdout.strip()=='installed':parser.error('Fresh mode requires no existing ASL installation; existing station needs supported migration, not reinitialization')
  if os.path.lexists('/etc/allmode/permit-asterisk-during-bootstrap'):parser.error('Unexpected commissioning consent marker')
  for name in ('/etc/asterisk','/etc/systemd/system/asterisk.service.d'):
   path=pathlib.Path(name)
   if path.exists() and any(path.iterdir()):parser.error('Fresh mode refuses preexisting Asterisk configuration: '+name)
  if os.path.lexists('/etc/systemd/system/asterisk.service'):parser.error('Fresh mode refuses existing administrator Asterisk unit')
 else:
  existing=subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}','ara-allmode'],capture_output=True,text=True)
  reject_packaged_migration(existing.returncode,existing.stdout)
  configuration=legacy_config(run(['systemctl','cat','--no-pager','allmode-setup.service']))
  with tempfile.NamedTemporaryFile(mode='w') as f:json.dump(configuration,f);f.flush();launcher.arguments(f.name)
 if work is None:
  stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');work=pathlib.Path('/var/backups/ara-allmode')/('bootstrap-'+stamp)
  fd=safe_directory(work.parent);os.fchmod(fd,0o700);os.close(fd);work.mkdir(mode=0o700)
 orchestrate(root,work,a.mode,configuration if a.mode=='legacy-migrate' else None,record=record)

def orchestrate(root,work,mode,configuration=None,runner=run,record=None):
 global LOG_DIR
 LOG_DIR=work/'commands';LOG_DIR.mkdir(mode=0o700,exist_ok=True)
 run=runner
 record=record or {'schema':1,'bundle_sha256':bundle_identity(),'configuration':configuration,'mode':mode,'phase':'prepared','radio_resumed':False,'previous_app_states':{unit:run(['systemctl','show','--value','--property=ActiveState',unit]).strip() for unit in APP}};record['attempts']=record.get('attempts',0)+1;write_journal(work,record)
 def phase(name):record['phase']=name;write_journal(work,record)
 try:
  ensure_system_bus(runner);phase('system-bus-ready')
  for unit in APP:
   if run(['systemctl','show','--value','--property=LoadState',unit]).strip()=='loaded':run(['systemctl','stop',unit])
  if 'before_state' not in record:
   partial=work/'before.tar.gz'
   if partial.exists():partial.rename(work/('before-incomplete-'+secrets.token_hex(6)+'.tar.gz'))
   backup(root,work);record['before_state']=state_hashes(root)
  before=record['before_state'];phase('backed-up')
  # Persistent drop-in survives interruption/reboot; legacy radio is never resumed.
  if os.path.lexists(root/'etc/allmode/permit-asterisk-during-bootstrap'):raise ValueError('Unexpected commissioning consent marker')
  guardpaths=[root/('etc/systemd/system/'+unit+'.d/00-allmode-provisioning.conf') for unit in RADIO]
  if 'previous_radio_enablement' not in record:
   record['previous_radio_enablement']={unit:run(['systemctl','show','--value','--property=UnitFileState',unit]).strip() for unit in RADIO};write_journal(work,record)
  for guardpath in guardpaths:atomic_new(guardpath,GUARD.encode())
  run(['systemctl','daemon-reload'])
  for unit in RADIO:
   if run(['systemctl','show','--value','--property=LoadState',unit]).strip()=='loaded':
    run(['systemctl','disable',unit]);effective_guard(unit,'/etc/allmode/permit-asterisk-during-bootstrap',root,runner)
  phase('radio-reboot-inhibited')
  ensure_bootstrap_tools(runner);trust(root,work,runner);phase('trust-and-indexes-ready')
  install({'ara-allmode-dvswitch-guard':GUARD_PACKAGE},runner);run(['systemctl','daemon-reload']);phase('guard-installed')
  # MB guard must be present and its opt-in marker absent before dependency install.
  guard=root/'usr/lib/systemd/system/mmdvm_bridge.service.d/ara-allmode-owner.conf'
  if 'ConditionPathExists=/etc/allmode/allow-upstream-mmdvm-service' not in guard.read_text() or os.path.lexists(root/'etc/allmode/allow-upstream-mmdvm-service'):raise ValueError('Invalid stock-daemon guard')
  install(UPSTREAM,runner);effective_guard('mmdvm_bridge.service','/etc/allmode/allow-upstream-mmdvm-service',root,runner);run(['systemctl','start','mmdvm_bridge.service'])
  if run(['systemctl','show','--value','--property=ActiveState','mmdvm_bridge.service']).strip()!='inactive' or run(['systemctl','show','--value','--property=ConditionResult','mmdvm_bridge.service']).strip()!='no':raise ValueError('Stock daemon guard did not inhibit start')
  phase('upstream-configured-inhibited')
  if mode=='legacy-migrate':
   atomic_new(root/'etc/allmode/service.json',(json.dumps(configuration,indent=2)+'\n').encode());migrate_code(root,work);run(['systemctl','daemon-reload']);phase('legacy-code-saved')
  install({'ara-allmode':CORE,'ara-allmode-meter':METER,'ara-allmode-dvswitch':ADDON},runner);phase('allmode-installed')
  if mode=='fresh':
   effective_guard('asterisk.service','/etc/allmode/permit-asterisk-during-bootstrap',root,runner)
   run(['systemctl','start','asterisk.service'])
   if run(['systemctl','show','--value','--property=ActiveState','asterisk.service']).strip()!='inactive' or run(['systemctl','show','--value','--property=ConditionResult','asterisk.service']).strip()!='no':raise ValueError('Asterisk commissioning guard failed')
   run(['systemctl','disable','asterisk.service'])
  else:
   if before!=state_hashes(root):raise ValueError('Station-state hash changed; stop and inspect private backup')
  run(['/usr/libexec/ara-allmode/launch.py','--check']);report=native_validation(work,runner);phase('native-validation-passed')
  if mode=='fresh':
   marker=root/'etc/allmode/install-profile.json'
   if os.path.lexists(marker):
    raw,_=profile.regular_bytes(marker,0)
    if not record.get('profile_attempted') or json.loads(raw)!={'version':1,'dvswitch_dmr_default':True}:raise ValueError('Existing profile is not this bootstrap intent; refusing overwrite')
   else:
    record['profile_attempted']=True;write_journal(work,record)
    run(['/usr/bin/python3',str(HERE/'provision-fresh-profile.py'),'--validation-report',str(report),'--apply'])
  # Keep guard through every failure-prone validation. Disable RF at commit before
  # removing only our unchanged drop-in. Explicit wizard activation may enable it.
  run(['systemctl','disable','asterisk.service'])
  if run(['systemctl','show','--value','--property=UnitFileState','asterisk.service']).strip() not in ('disabled','static',''):raise ValueError('Asterisk is still enabled; refusing commit')
  if run(['systemctl','show','--value','--property=ActiveState','asterisk.service']).strip()!='inactive':raise ValueError('Radio became active; refusing commit')
  normalize_enablement_links(root,work)
  run(['systemctl','enable','allmode-system.service','allmode-setup.service','allmode-directories.timer','allmode-digital.service'])
  run(['systemctl','start','allmode-system.service','allmode-setup.service','allmode-directories.timer'])
  for guardpath in guardpaths:
   raw,_=profile.regular_bytes(guardpath,0)
   if raw!=GUARD.encode():raise ValueError('Commissioning guard changed; refusing cleanup')
  for guardpath in guardpaths:guardpath.unlink()
  run(['systemctl','daemon-reload']);phase('console-ready-radio-stopped')
  print('ALLMODE console ready. Radio remains stopped. Complete onboarding/validate preserved setup before explicit activation. Journal: '+str(work/'journal.json'))
  if mode=='fresh':print(initial_access()+' SSH authenticates this localhost-only session. Follow Guided setup with your own station/radio settings, review and apply, then explicitly activate only when ready. Radio remains disabled until then; no unauthenticated LAN listener was opened.')
 except BaseException:
  record['failed_phase']=record['phase'];phase('failed-radio-not-resumed')
  print('Stopped safely; RF was not resumed. Read the private command diagnostic, fix its stated cause, then resume the same audited transaction with: sudo python3 '+shlex.quote(str(HERE/'bootstrap.py'))+' --resume '+shlex.quote(str(work))+' --apply. No unrelated pending dpkg state will be configured.')
  raise
if __name__=='__main__':main()
