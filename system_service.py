"""Root-owned, local-only configuration service with fixed operations and backups."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import socketserver
import subprocess
import tempfile
import time
from onboarding import Onboarding, GROUPS

ETC=Path('/etc/asterisk')
STATE=Path('/var/lib/allmode-system')
RUN=Path('/var/lib/asterisk/allmode')
RUNTIME_FILES=('dstar-codec.json','dstar-identity.json','digital-modes.json','enabled-networks.json')
FILES=('rpt.conf','simpleusb.conf','rpt_http_registrations.conf','echolink.conf','modules.conf','extensions.conf','savenode.conf')

def fingerprint(config):
    return hashlib.sha256(json.dumps({g:config[g] for g in GROUPS},sort_keys=True).encode()).hexdigest()

def normalized(config):
    if not isinstance(config,dict):raise ValueError('Invalid station configuration.')
    data={g:config.get(g,{k:d for k,_,_,d in rows}) for g,rows in GROUPS.items()}
    with tempfile.TemporaryDirectory() as directory:
        check=Onboarding(directory);check.save(data);data=check.read()
    # Values are written as Asterisk/INI literals, never interpreted as directives.
    for group,rows in GROUPS.items():
        for key,_,kind,_ in rows:
            value=data[group][key]
            if isinstance(value,str) and any(c in value for c in '\n\r;[]#='):
                raise ValueError(group+': remove configuration punctuation from '+key+'.')
    password=data['allstar']['password']
    if data['allstar']['enabled'] and any(c in password for c in ':@\\"'):
        raise ValueError('AllStar node password contains unsupported registration punctuation.')
    return {g:data[g] for g in GROUPS}

def section(text,name,body):
    pattern=r'(?ms)^\['+re.escape(name)+r'\][^\n]*\n.*?(?=^\[|\Z)'
    value='['+name+']\n'+body.strip()+'\n\n'
    return re.sub(pattern,lambda _:value,text) if re.search(pattern,text) else text.rstrip()+'\n\n'+value

def render(config,templates,radio=False,levels=None):
    c=normalized(config);node=c['allstar']['node'] if c['allstar']['enabled'] else '1990'
    if node in ('1994','1995','1996','1997','1998','1999'):raise ValueError('That node number is reserved for a local digital adapter.')
    levels=levels or dict(rx=650,txa=600,txb=500)
    for key in ('rx','txa','txb'):
        if type(levels.get(key)) is not int or not 0<=levels[key]<=999:raise ValueError('Audio levels must be integers from 0 to 999.')
    rpt=templates['rpt.conf']
    rpt=re.sub(r'(?ms)^\[1999\][^\n]*\n.*?(?=^\[|\Z)','',rpt)
    rpt=section(rpt,'nodes',f'{node}=radio@127.0.0.1/{node},NONE\n1994=radio@127.0.0.1/1994,NONE')
    rpt+='\n['+node+'](node-main)\n'+f'rxchannel = {"SimpleUSB/"+node if radio else "Local/pseudo"}\nduplex = 0\nidrecording = |i{c["station"]["callsign"]}\nidtime = 540000\nhangtime = 0\ntotime = 180000\nlinktolink = no\ntelemdefault = 0\n'
    rpt+='\n[1994](node-main)\nrxchannel = USRP/127.0.0.1:34006:32006\nduplex = 0\nhangtime = 0\nidrecording =\nidtime = 0\nlinktolink = no\ntelemdefault = 0\n'
    usb=templates['simpleusb.conf']
    usb=re.sub(r'(?ms)^\[1999\][^\n]*\n.*?(?=^\[|\Z)','',usb)
    usb+=f'\n[{node}](node-main)\neeprom=0\nhdwtype=0\nrxboost=no\ncarrierfrom=usbinvert\nctcssfrom=no\ndeemphasis=no\npreemphasis=no\nplfilter=no\ninvertptt=no\nrxondelay=0\ntxoffdelay=0\nrxmixerset={levels["rx"]}\ntxmixaset={levels["txa"]}\ntxmixbset={levels["txb"]}\n'
    reg='[general]\nregister_interval=180\n[registrations]\n'
    if c['allstar']['enabled']:reg+=f'register => {node}:{c["allstar"]["password"]}@register.allstarlink.org\n'
    echo='; Disabled by ALLMODE\n'
    if c['echolink']['enabled']:
        e=c['echolink'];echo='[el0]\n'+''.join(f'{k}={v}\n' for k,v in dict(call=e['callsign'].upper(),pwd=e['password'],name=e['name'],qth=e['location'],email=e['email'],node=e['node'],astnode=node,maxstns=10,rtcptimeout=10,server1='nasouth.echolink.org',server2='naeast.echolink.org',server3='servers.echolink.org').items())
    modules=templates['modules.conf']
    for module,enabled in [('chan_echolink',c['echolink']['enabled']),('chan_usrp',True)]:
        modules=re.sub(r'(?m)^\s*(?:load|noload|require)\s*=\s*'+module+r'\.so[^\n]*',('load' if enabled else 'noload')+' = '+module+'.so',modules)
    extensions=re.sub(r'(?m)^(NODE\s*=\s*)[0-9]+',lambda m:m[1]+node,templates['extensions.conf'])
    saved=templates['savenode.conf']
    for key,value in [('NODE',node),('PASSWORD',c['allstar']['password'] if c['allstar']['enabled'] else '')]:
        replacement=key+'='+shlex.quote(value)
        saved=re.sub(r'(?m)^'+key+r'=.*$',lambda _:replacement,saved) if re.search(r'(?m)^'+key+'=',saved) else saved.rstrip()+'\n'+replacement+'\n'
    return node,dict(zip(FILES,[rpt,usb,reg,echo,modules,extensions,saved]))

def run(argv,timeout=15,check=True):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
    if check and result.returncode:raise ValueError('System operation failed: '+argv[0].split('/')[-1])
    return result.stdout

def cli(command):
    out=run(['/usr/sbin/asterisk','-rx',command],timeout=6)
    if any(s in out.lower() for s in ('no such command','unable to connect','usage:')):raise ValueError('Asterisk command failed.')
    return out

def atomic(path,text,mode=0o600,uid=0,gid=0):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.allmode-')
    try:
        os.fchmod(fd,mode);os.fchown(fd,uid,gid)
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def load_state():
    try:return json.loads((STATE/'state.json').read_text())
    except FileNotFoundError:return {}

def save_state(s):atomic(STATE/'state.json',json.dumps(s,indent=2))

def runtime_config(config):
    import pwd
    account=pwd.getpwnam('allmode')
    RUN.mkdir(mode=0o750,parents=True,exist_ok=True);os.chown(RUN,account.pw_uid,account.pw_gid)
    values={'dstar-codec.json':dict(type='hardware' if config['dstar']['enabled'] else 'disabled',host=config['dstar']['host'],port=config['dstar']['port']),
            'dstar-identity.json':dict(callsign=config['station']['callsign'],terminal=config['dstar']['terminal']),
            'digital-modes.json':[], 'enabled-networks.json':{g:config[g].get('enabled',False) for g in ('allstar','echolink','brandmeister','tgif','dstar')}}
    for name,data in values.items():atomic(RUN/name,json.dumps(data),0o600,account.pw_uid,account.pw_gid)

def active():return run(['systemctl','is-active','asterisk'],check=False).strip()=='active'

def config_drift(state):
    expected=state.get('config_hashes',{})
    return [name for name,digest in expected.items() if not (ETC/name).is_file() or hashlib.sha256((ETC/name).read_bytes()).hexdigest()!=digest]

def status():
    s=load_state();running=active();out='';drift=config_drift(s)
    if running:
        try:out=cli('rpt show registrations')
        except ValueError:pass
    # Raw registration lines may include passwords on some versions; never return them.
    registered=bool(re.search(r'\bRegistered\b',out,re.I)) and not bool(re.search(r'\bUnregistered\b',out,re.I))
    return dict(available=True,applied=bool(s),active=running,node=s.get('node'),radio_enabled=s.get('radio',False) and running,
                fingerprint=None if drift else s.get('fingerprint'),config_drift=drift,levels=s.get('levels',dict(rx=650,txa=600,txb=500)),registered=registered,
                registration='Registered' if registered else 'Pending or unavailable',audio_verified=s.get('audio_verified',False))

@contextlib.contextmanager
def radio_lock():
    import radio_readback
    with radio_readback.serial_lock():yield

def install_config(config,radio=False,levels=None):
    STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    baseline=STATE/'baseline';baseline.mkdir(mode=0o700,exist_ok=True)
    for name in FILES:
        if not (baseline/name).exists():shutil.copy2(ETC/name,baseline/name)
    templates={name:(baseline/name).read_text() for name in FILES}
    levels=levels or load_state().get('levels',dict(rx=650,txa=600,txb=500))
    node,files=render(config,templates,radio,levels)
    backup=STATE/('backup-'+str(time.time_ns()));backup.mkdir(mode=0o700)
    old=load_state();was_active=active()
    digital_active=run(['systemctl','is-active','allmode-digital'],check=False).strip()=='active'
    private_paths=[STATE/'state.json',STATE/'config.json']+[RUN/name for name in RUNTIME_FILES]
    previous={}
    for index,path in enumerate(private_paths):
        saved=backup/('private-'+str(index))
        if path.exists():shutil.copy2(path,saved);previous[path]=saved
        else:previous[path]=None
    for name in FILES:shutil.copy2(ETC/name,backup/name)
    with radio_lock():
        if radio:
            fd=os.open('/var/lib/allmode/program.json',os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd) as f:program=json.load(f)
            if program.get('state')!='acknowledged-not-verified' or program.get('acknowledged')!=['AT+DMOSETGROUP','AT+DMOSETVOLUME','AT+SETFILTER','AT+SETTAIL']:
                raise ValueError('Complete radio programming before activation.')
        run(['systemctl','stop','allmode-digital'],check=False)
        run(['systemctl','stop','asterisk'])
        try:
            for name,text in files.items():
                st=(ETC/name).stat();atomic(ETC/name,text,0o640,st.st_uid,st.st_gid)
            runtime_config(config)
            run(['systemctl','unmask','asterisk'])
            run(['systemctl','start','asterisk'],timeout=25)
            for _ in range(15):
                try:
                    if 'STATISTICS' in cli('rpt stats '+node):break
                except ValueError:pass
                time.sleep(.5)
            else:raise ValueError('Configured node did not become ready.')
            s=dict(node=node,fingerprint=fingerprint(config),radio=radio,levels=levels or old.get('levels',dict(rx=650,txa=600,txb=500)),audio_verified=False)
            run(['systemctl','enable','asterisk'])
            atomic(STATE/'config.json',json.dumps(config))
            s['config_hashes']={name:hashlib.sha256((ETC/name).read_bytes()).hexdigest() for name in FILES}
            save_state(s)
            if radio:run(['systemctl','start','allmode-digital'])
            else:run(['systemctl','stop','allmode-digital'])
        except Exception:
            run(['systemctl','stop','allmode-digital'],check=False)
            run(['systemctl','stop','asterisk'],check=False)
            for path,saved in previous.items():
                if saved is None:path.unlink(missing_ok=True)
                else:
                    st=saved.stat();atomic(path,saved.read_text(),st.st_mode & 0o777,st.st_uid,st.st_gid)
            for name in FILES:shutil.copy2(backup/name,ETC/name)
            if was_active:run(['systemctl','start','asterisk'],check=False)
            if digital_active:run(['systemctl','start','allmode-digital'],check=False)
            raise ValueError('Startup failed. Previous Asterisk configuration restored; check system logs.')
    return status()

def handle(request):
    if not isinstance(request,dict):raise ValueError('Expected an operation.')
    action=request.get('action')
    if action=='status':return status()
    if action=='apply':
        config=normalized(request.get('config'))
        if any(config[g]['enabled'] for g in ('brandmeister','tgif')):
            raise ValueError('DMR dependencies must be installed before applying an enabled DMR network.')
        return install_config(config,False)
    if action=='test-ambe':
        config=normalized(request.get('config'))
        if not config['dstar']['enabled']:raise ValueError('Enable and save external AMBE settings first.')
        if run(['systemctl','is-active','allmode-digital'],check=False).strip()=='active':
            raise ValueError('Enter maintenance before testing a codec that may be in use.')
        from dstar_hardware import HardwareCodec
        try:codec=HardwareCodec(config['dstar']['host'],config['dstar']['port'])
        except OSError:raise ValueError('AMBE server did not complete the AMBE3000 UDP handshake. Check the address, port, server availability and firewall.') from None
        try:
            voice=codec.encode(bytes(320),1)
            pcm=codec.decode(voice,1)
            if len(pcm)!=320:raise ValueError('AMBE audio response was invalid.')
        finally:codec.close()
        import pwd
        account=pwd.getpwnam('allmode')
        atomic(RUN/'dstar-probe.json',json.dumps(dict(host=config['dstar']['host'],port=config['dstar']['port'],passed=True,time=time.time())),0o600,account.pw_uid,account.pw_gid)
        return dict(ok=True,message='AMBE3000 handshake and silent encode/decode passed. No RF or reflector audio sent.')
    if action=='maintenance':
        run(['systemctl','stop','allmode-digital'],check=False);run(['systemctl','stop','asterisk']);return status()
    if action=='activate':
        if request.get('confirm')!='ACTIVATE':raise ValueError('Confirm activation first.')
        config=json.loads((STATE/'config.json').read_text())
        if request.get('fingerprint')!=fingerprint(config):raise ValueError('Apply the latest saved settings before activation.')
        # Require a complete radio acknowledgement record, not merely a draft.
        fd=os.open('/var/lib/allmode/program.json',os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as f:program=json.load(f)
        if program.get('state')!='acknowledged-not-verified' or len(program.get('acknowledged',[]))!=4:raise ValueError('Complete radio programming before activation.')
        result=install_config(config,True,load_state().get('levels'))
        return result
    if action=='audio':
        if not active():raise ValueError('Activate the radio before adjusting audio.')
        node=load_state()['node']
        if re.search(r'^\d+\s+.*ESTABLISHED',cli('rpt lstats '+node),re.M):raise ValueError('Disconnect network links before adjusting audio.')
        config=json.loads((STATE/'config.json').read_text())
        return install_config(config,load_state().get('radio',False),request.get('levels'))
    if action=='audio-confirm':
        s=load_state()
        if request.get('checked') is not True or not active() or not s.get('radio'):raise ValueError('Start the radio and complete receive/transmit checks first.')
        s['audio_verified']=True;s['audio_verification']='Operator reported receive/transmit check';save_state(s)
        return status()
    if action=='cli':
        s=load_state();node=re.escape(s.get('node','NONE'));command=request.get('command','')
        patterns=[rf'rpt (?:stats|lstats) {node}',r'module show like chan_echolink\.so',rf'rpt cmd {node} ilink [138] [0-9]{{4,7}}']
        if not isinstance(command,str) or not any(re.fullmatch(p,command) for p in patterns):raise ValueError('Command is not permitted.')
        return dict(output=cli(command))
    raise ValueError('Unknown system operation.')

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        try:
            data=self.rfile.readline(16385)
            if len(data)>16384:raise ValueError('Request too large.')
            result=handle(json.loads(data))
        except ValueError as error:
            result={'error':str(error)}
        except (OSError,TypeError,KeyError,subprocess.TimeoutExpired):
            # Never put credentials or command output into client errors/logs.
            result={'error':'Operation failed. Check prerequisites and system service logs.'}
            import traceback;traceback.print_exc(limit=0)
        self.wfile.write(json.dumps(result).encode()+b'\n')

if __name__=='__main__':
    import grp
    path=Path('/run/allmode-system/control.sock');path.unlink(missing_ok=True)
    with socketserver.UnixStreamServer(str(path),Handler) as server:
        os.chown(path,0,grp.getgrnam('allmode').gr_gid);os.chmod(path,0o660)
        server.serve_forever()
