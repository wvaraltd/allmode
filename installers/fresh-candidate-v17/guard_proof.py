"""Bounded condition-semantics proof; never starts the stock daemon/dependencies."""
import hashlib,json,os,pathlib,re,secrets,stat,time
STOCK='mmdvm_bridge.service'
MARKER='/etc/allmode/allow-upstream-mmdvm-service'
FRAGMENT=('[Unit]\nDefaultDependencies=no\nConditionPathExists='+MARKER+'\n[Service]\nType=oneshot\nStandardOutput=null\nStandardError=null\nExecStart=/usr/bin/false\n').encode()

def directory(root,relative,owner=0,create=False):
 fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  info=os.fstat(fd)
  if info.st_uid!=owner or info.st_mode&0o022:raise ValueError('Untrusted proof root')
  for part in pathlib.PurePosixPath(relative).parts:
   if part in ('','/','.','..'):raise ValueError('Unsafe proof path')
   if create:
    try:os.mkdir(part,0o755,dir_fd=fd)
    except FileExistsError:pass
   child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
   info=os.fstat(fd)
   if info.st_uid!=owner or info.st_mode&0o022:raise ValueError('Untrusted proof path')
  return fd
 except BaseException:os.close(fd);raise

def read(root,path,owner=0):
 path=pathlib.PurePosixPath(path)
 if not path.is_absolute() or '..' in path.parts:raise ValueError('Absolute trusted path required')
 fd=directory(root,str(path.parent).lstrip('/'),owner)
 try:
  file=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
  with os.fdopen(file,'rb') as stream:
   info=os.fstat(stream.fileno())
   if not stat.S_ISREG(info.st_mode) or info.st_uid!=owner or info.st_mode&0o022 or info.st_size>1024*1024:raise ValueError('Untrusted proof/config file')
   data=stream.read(1024*1024+1)
   after=os.fstat(stream.fileno());named=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
   identity=lambda item:(item.st_dev,item.st_ino,item.st_mode,item.st_uid,item.st_gid,item.st_size,item.st_mtime_ns,item.st_ctime_ns)
   if len(data)>1024*1024 or identity(info)!=identity(after) or identity(info)!=identity(named):raise ValueError('Proof/config file changed during bounded read')
   return data
 finally:os.close(fd)

def value(raw,kind):
 item=json.loads(raw)
 if item.get('type')!=kind:raise ValueError('Unexpected systemd property type')
 return item.get('data')

def conditions_for(unit,runner):
 runner(['systemctl','show','--value','--property=LoadState',unit])
 path=value(runner(['busctl','--json=short','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager','GetUnit','s',unit]),'o')
 if isinstance(path,list) and len(path)==1:path=path[0]
 if not isinstance(path,str) or not path.startswith('/org/freedesktop/systemd1/unit/'):raise ValueError('Invalid stock unit object')
 conditions=value(runner(['busctl','--json=short','get-property','org.freedesktop.systemd1',path,'org.freedesktop.systemd1.Unit','Conditions']),'a(sbbsi)')
 return conditions

def snapshot(root,runner,owner=0):
 if os.path.lexists(pathlib.Path(root)/MARKER.lstrip('/')):raise ValueError('Stock consent marker must be absent')
 conditions=conditions_for(STOCK,runner)
 if not isinstance(conditions,list) or not any(isinstance(row,list) and len(row)==5 and row[0]=='ConditionPathExists' and row[1] is False and row[2] is False and row[3]==MARKER for row in conditions):raise ValueError('Actual stock effective guard absent')
 state={field:runner(['systemctl','show','--value','--property='+field,STOCK]).strip() for field in ('LoadState','ActiveState','MainPID','FragmentPath','DropInPaths')}
 if (state['LoadState'],state['ActiveState'],state['MainPID'])!=('loaded','inactive','0'):raise ValueError('Stock unit is not loaded and inactive')
 paths=[state['FragmentPath'],*state['DropInPaths'].split()]
 if not paths[0]:raise ValueError('Stock unit fragment absent')
 state['config_sha256']={path:hashlib.sha256(read(root,path,owner)).hexdigest() for path in paths}
 state['conditions']=conditions
 boot=read(root,'/proc/sys/kernel/random/boot_id',owner).decode().strip()
 if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',boot):raise ValueError('Boot identity unavailable')
 state['boot_id']=boot
 return state

def anchor_fragment(probe):
 if not re.fullmatch(r'ara-allmode-guard-proof-[0-9a-f]{32}\.service',probe):raise ValueError('Invalid probe dependency identity')
 return ('[Unit]\nDefaultDependencies=no\nAfter='+probe+'\n[Service]\nType=oneshot\nRemainAfterExit=yes\nStandardOutput=null\nStandardError=null\nExecStart=/usr/bin/true\n').encode()

def semantic_probe(root,execute,owner=0,before_cleanup=None):
 # Active harmless anchor retains the skipped probe's loaded-unit reference.
 # After alone orders/references the probe; it does not pull in a start job.
 runner=lambda argv:execute(argv,timeout=20)
 token=secrets.token_hex(16)
 unit='ara-allmode-guard-proof-'+token+'.service'
 anchor='ara-allmode-guard-anchor-'+token+'.service'
 files={unit:FRAGMENT,anchor:anchor_fragment(unit)}
 for name in files:
  if runner(['systemctl','show','--value','--property=LoadState',name]).strip()!='not-found':raise ValueError('Proof/anchor unit collision')
 fd=directory(root,'run/systemd/system',owner,create=True);created=[];result=None
 try:
  for name,data in files.items():
   try:os.stat(name+'.d',dir_fd=fd,follow_symlinks=False)
   except FileNotFoundError:pass
   else:raise ValueError('Proof/anchor drop-in collision')
   out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
   created.append(name)
   with os.fdopen(out,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.fsync(fd);runner(['systemctl','daemon-reload'])
  for name,data in files.items():
   if read(root,'/run/systemd/system/'+name,owner)!=data:raise ValueError('Owned probe/anchor changed before start')
  runner(['systemctl','start',anchor])
  anchor_state={field:runner(['systemctl','show','--value','--property='+field,anchor]).strip() for field in ('ActiveState','SubState','MainPID')}
  if anchor_state!={'ActiveState':'active','SubState':'exited','MainPID':'0'}:raise ValueError('Harmless retention anchor is not active')
  runner(['systemctl','start',unit])
  result={field:runner(['systemctl','show','--value','--property='+field,unit]).strip() for field in ('ConditionResult','ConditionTimestampMonotonic','ActiveState','MainPID','ExecMainStartTimestampMonotonic')}
  probe_conditions=conditions_for(unit,runner)
  validate_probe(result,probe_conditions)
  if before_cleanup is not None:before_cleanup()
 finally:
  errors=[]
  try:
   for name in created:
    try:
     if read(root,'/run/systemd/system/'+name,owner)!=files[name]:raise ValueError('Owned proof/anchor file changed; refusing stop/removal')
     runner(['systemctl','stop',name])
     if read(root,'/run/systemd/system/'+name,owner)!=files[name]:raise ValueError('Owned file changed during cleanup')
     os.unlink(name,dir_fd=fd);os.fsync(fd)
    except Exception as error:errors.append(str(error))
   if created:
    try:runner(['systemctl','daemon-reload'])
    except Exception as error:errors.append(str(error))
  finally:os.close(fd)
  if errors:raise ValueError('Proof cleanup failed: '+'; '.join(errors))
 return {'probe_unit':unit,'fragment_sha256':hashlib.sha256(FRAGMENT).hexdigest(),'probe':result,'probe_conditions':probe_conditions,'anchor_unit':anchor,'anchor_fragment_sha256':hashlib.sha256(files[anchor]).hexdigest(),'anchor_state':anchor_state,'cleanup_complete':True}

def prove(root,execute,owner=0):
 runner=lambda argv:execute(argv,timeout=20)
 before=snapshot(root,runner,owner)
 def unchanged():
  if before!=snapshot(root,runner,owner):raise ValueError('Stock state/config changed during proof')
 evidence=semantic_probe(root,execute,owner,before_cleanup=unchanged)
 if before!=snapshot(root,runner,owner):raise ValueError('Stock state/config changed during cleanup')
 return dict(evidence,schema=1,kind='harmless-condition-semantics-not-stock-startup',created_at=time.time(),stock=before)

def validate(evidence,current,now=None):
 now=time.time() if now is None else now
 if not isinstance(evidence,dict) or evidence.get('schema')!=1 or evidence.get('kind')!='harmless-condition-semantics-not-stock-startup':raise ValueError('Explicit condition proof required')
 stamp=evidence.get('created_at')
 if not isinstance(stamp,(int,float)) or not 0<=now-stamp<=3600:raise ValueError('Condition proof stale')
 if evidence.get('stock')!=current or evidence.get('cleanup_complete') is not True:raise ValueError('Condition proof not bound to current stock configuration/state')
 if not re.fullmatch(r'ara-allmode-guard-proof-[0-9a-f]{32}\.service',str(evidence.get('probe_unit'))):raise ValueError('Invalid owned proof identity')
 if evidence.get('fragment_sha256')!=hashlib.sha256(FRAGMENT).hexdigest():raise ValueError('Invalid harmless condition fragment')
 expected_anchor=evidence['probe_unit'].replace('-proof-','-anchor-')
 if evidence.get('anchor_unit')!=expected_anchor or evidence.get('anchor_fragment_sha256')!=hashlib.sha256(anchor_fragment(evidence['probe_unit'])).hexdigest() or evidence.get('anchor_state')!={'ActiveState':'active','SubState':'exited','MainPID':'0'}:raise ValueError('Invalid harmless retention evidence')
 validate_probe(evidence.get('probe'),evidence.get('probe_conditions'))

def validate_probe(result,conditions):
 if not isinstance(result,dict):raise ValueError('Harmless proof result absent')
 if any(result.get(key)!=value for key,value in {'ConditionResult':'no','ActiveState':'inactive','MainPID':'0','ExecMainStartTimestampMonotonic':'0'}.items()):raise ValueError('Harmless proof did not skip execution')
 stamp=result.get('ConditionTimestampMonotonic','')
 if not isinstance(stamp,str) or not stamp.isdigit() or int(stamp)<=0:raise ValueError('Condition evaluation timestamp absent')
 if conditions!=[['ConditionPathExists',False,False,MARKER,-1]]:raise ValueError('Exact condition evaluation failure evidence absent')
