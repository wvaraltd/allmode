"""Root-owned, local-only configuration service with fixed operations and backups."""
import contextlib
import hashlib
import fcntl
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
import threading
from onboarding import Onboarding, GROUPS

ETC=Path('/etc/asterisk')
STATE=Path('/var/lib/allmode-system')
RUN=Path('/var/lib/asterisk/allmode')
RUNTIME_FILES=('dvswitch.json','m17-native.json','p25-native.json','ysf-native.json','nxdn-native.json','dmr-native.json','dmr-networks.json','dstar-backend-request.json','dstar-codec.json','dstar-identity.json','digital-modes.json','enabled-networks.json')
FILES=('rpt.conf','simpleusb.conf','rpt_http_registrations.conf','echolink.conf','modules.conf','extensions.conf','savenode.conf')

def fingerprint(config):
    return hashlib.sha256(json.dumps({g:config[g] for g in GROUPS},sort_keys=True).encode()).hexdigest()

def fingerprint_matches(config, supplied):
    """Only missing and explicit boolean False for dmr.dvswitch are equivalent."""
    if not config or not supplied:
        return False
    if supplied == fingerprint(config):
        return True
    dmr = config.get('dmr', {})
    if 'dvswitch' in dmr and dmr['dvswitch'] is not False:
        return False
    alternate = dict(config)
    alternate['dmr'] = dict(dmr)
    if 'dvswitch' in dmr:
        del alternate['dmr']['dvswitch']
    else:
        alternate['dmr']['dvswitch'] = False
    return supplied == fingerprint(alternate)


def require_optional_tool(name, package):
    path = shutil.which(name)
    if not path:
        raise ValueError(name + ' is unavailable (' + package + '). No networking changes were made. Ask the administrator to review installation; ALLMODE will not install or start it automatically.')
    return path


def optional_diagnostics():
    return {name: bool(shutil.which(name)) for name in
            ('ip', 'nmcli', 'aplay', 'arecord', 'amixer', 'alsactl')}


WIFI_PROFILES=Path('/etc/NetworkManager/system-connections')
WIFI_ROOT_UID=0

def wifi_security(value):
    """Conservative nmcli capability classification, not an authentication claim."""
    if not isinstance(value,str):return None,'Unknown Wi-Fi security; configure this network with an administrator.'
    text=value.strip().upper()
    if text in ('','--'):return 'open',''
    words=set(text.split())
    if words and words<=set(('WPA','WPA1','WPA2','WPA3')) and words&set(('WPA','WPA1','WPA2')):
        return 'wpa-psk',''
    return None,'Only open or WPA/WPA2 Personal networks are supported here; enterprise, WEP, WPA3-only and unknown security require administrator setup.'


def wifi_scan_rows(output):
    rows=[]
    for line in output.splitlines():
        fields=[''];escaped=False
        for char in line:
            if escaped:
                fields[-1]+=char if char in ('\\',':') else '\\'+char;escaped=False
            elif char=='\\':escaped=True
            elif char==':':fields.append('')
            else:fields[-1]+=char
        if escaped or len(fields)!=3 or not fields[0]:continue
        ssid,signal,security=fields
        if not signal.isascii() or not signal.isdigit() or not 0<=int(signal)<=100:continue
        kind,reason=wifi_security(security)
        rows.append(dict(ssid=ssid,signal=signal,security=security,security_mode=kind,unsupported_reason=reason))
    return rows


def wifi_keyfile_string(value):
    # GLib keyfile escaping; preserve literal backslashes and boundary spaces.
    return value.replace('\\','\\\\').replace(' ','\\s')


def wifi_profile(uid):
    import configparser,stat,uuid
    try:valid=isinstance(uid,str) and str(uuid.UUID(uid))==uid
    except (ValueError,AttributeError):valid=False
    if not valid:raise ValueError('Choose an ARA saved Wi-Fi profile.')
    path=WIFI_PROFILES/('ara-'+uid+'.nmconnection')
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd) as file:
            st=os.fstat(file.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=WIFI_ROOT_UID or st.st_mode&0o077 or st.st_size>65536:raise ValueError('Untrusted Wi-Fi profile.')
            profile=configparser.RawConfigParser();profile.read_file(file)
        if profile.get('connection','uuid')!=uid or profile.get('connection','type')!='wifi':raise ValueError('Wi-Fi profile identity mismatch.')
        previous=profile.getboolean('connection','autoconnect',fallback=False)
    except (OSError,ValueError,configparser.Error):raise ValueError('Choose an ARA saved Wi-Fi profile.') from None
    return path,previous


def wifi_schedule(uid,nmcli,scheduler):
    _,previous=wifi_profile(uid)
    try:run([nmcli,'connection','modify','uuid',uid,'connection.autoconnect','yes'])
    except Exception:raise ValueError('Wi-Fi profile is saved, but automatic-connection configuration was not confirmed; no connection switch was scheduled by this request. Check network status before retrying.') from None
    try:
        # Fixed argv; password stays only in the root-private keyfile.
        run([scheduler,'--quiet','--on-active=3s',nmcli,'connection','up','uuid',uid])
    except Exception:
        try:run([nmcli,'connection','modify','uuid',uid,'connection.autoconnect','yes' if previous else 'no'])
        except Exception:raise ValueError('Wi-Fi profile is saved. Connection scheduling and automatic-connection restoration are unconfirmed; a queued switch may still occur. Check network status before retrying.') from None
        raise ValueError('Wi-Fi profile is saved. Connection scheduling was not confirmed; the prior automatic-connection setting was restored, but a queued switch may still occur. Check network status before retrying.') from None
    return dict(ok=True,id=uid,scheduled=True,connected=False,message='Connection switch scheduled, not yet verified. The browser may disconnect; find the node at ara-allmode.local or its new IP address.')


def normalized(config):
    if not isinstance(config,dict):raise ValueError('Invalid station configuration.')
    data={g:dict({k:d for k,_,_,d in rows},**config.get(g,{})) for g,rows in GROUPS.items()}
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
    if node in ('1993','1994','1995','1996','1997','1998','1999'):raise ValueError('That node number is reserved for a local digital adapter.')
    levels=levels or dict(rx=650,txa=600,txb=500)
    for key in ('rx','txa','txb'):
        if type(levels.get(key)) is not int or not 0<=levels[key]<=999:raise ValueError('Audio levels must be integers from 0 to 999.')
    rpt=templates['rpt.conf']
    rpt=re.sub(r'(?ms)^\[(?:1999|1996|1998|1997|1993)\][^\n]*\n.*?(?=^\[|\Z)','',rpt)
    rpt=section(rpt,'nodes',f'{node}=radio@127.0.0.1/{node},NONE\n1994=radio@127.0.0.1/1994,NONE'+('\n1999=radio@127.0.0.1/1999,NONE' if any(c[g]['enabled'] for g in ('brandmeister','tgif')) else '')+('\n1996=radio@127.0.0.1/1996,NONE' if c['other'].get('nxdn') else '')+('\n1998=radio@127.0.0.1/1998,NONE' if c['other'].get('ysf') else '')+('\n1997=radio@127.0.0.1/1997,NONE' if c['other'].get('p25') else '')+('\n1993=radio@127.0.0.1/1993,NONE' if c['other'].get('m17') else ''))
    rpt+='\n['+node+'](node-main)\n'+f'rxchannel = {"SimpleUSB/"+node if radio else "Local/pseudo"}\nduplex = 0\nidrecording = |i{c["station"]["callsign"]}\nidtime = 540000\nhangtime = 0\ntotime = 180000\nlinktolink = no\ntelemdefault = 0\n'
    rpt+='\n[1994](node-main)\nrxchannel = USRP/127.0.0.1:34006:32006\nduplex = 0\nhangtime = 0\nidrecording =\nidtime = 0\nlinktolink = no\ntelemdefault = 0\n'
    if any(c[g]['enabled'] for g in ('brandmeister','tgif')):
        import dvswitch_config
        transport=dvswitch_config.load() if c['dmr'].get('dvswitch') else dvswitch_config.DEFAULT
        rpt+=f'\n[1999](node-main)\nrxchannel = USRP/127.0.0.1:{transport["usrp_receive"]}:{transport["usrp_send"]}\nduplex = 0\nhangtime = 0\nidrecording =\nidtime = 0\nlinktolink = no\ntelemdefault = 0\n'
    if c['other'].get('nxdn'):
        rpt+='\n[1996](node-main)\nrxchannel = USRP/127.0.0.1:34004:32004\nduplex = 0\nhangtime = 0\nidrecording =\nidtime = 0\nlinktolink = no\ntelemdefault = 0\n'
    if c['other'].get('ysf'):
        rpt+='\n[1998](node-main)\nrxchannel = USRP/127.0.0.1:34002:32002\nduplex = 0\nhangtime = 0\nidrecording =\nidtime = 0\nlinktolink = no\ntelemdefault = 0\n'
    if c['other'].get('p25'):
        rpt+='\n[1997](node-main)\nrxchannel = USRP/127.0.0.1:34003:32003\nduplex = 0\nhangtime = 0\nidrecording =\nidtime = 0\nlinktolink = no\ntelemdefault = 0\n'
    if c['other'].get('m17'):
        rpt+='\n[1993](node-main)\nrxchannel = USRP/127.0.0.1:34007:32007\nduplex = 0\nhangtime = 0\nidrecording =\nidtime = 0\nlinktolink = no\ntelemdefault = 0\n'
    usb=templates['simpleusb.conf']
    # SHARI uses the SA818's combined COR/tone decision, not a second USB tone pin.
    # Set the inherited defaults too: external tuning menus may omit node overrides.
    def shari_defaults(match):
        body=match.group(0)
        for key,value in [('carrierfrom','usbinvert'),('ctcssfrom','no')]:
            pattern=r'(?m)^\s*'+key+r'\s*=.*$'
            if re.search(pattern,body):body=re.sub(pattern,key+' = '+value,body)
            else:body+='\n'+key+' = '+value+'\n'
        return body
    usb=re.sub(r'(?ms)^\[node-main\]\(!\)[^\n]*\n.*?(?=^\[|\Z)',shari_defaults,usb)
    for old_node in {node,'1999'}:
        usb=re.sub(r'(?ms)^\['+re.escape(old_node)+r'\][^\n]*\n.*?(?=^\[|\Z)','',usb)
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
    values={'dstar-codec.json':dict(type='hardware' if config['dstar']['enabled'] else 'software',host=config['dstar']['host'],port=config['dstar']['port']),
            'dstar-identity.json':dict(callsign=config['station']['callsign'],terminal=config['dstar']['terminal']),
            'digital-modes.json':[], 'enabled-networks.json':{g:config[g].get('enabled',False) for g in ('allstar','echolink','brandmeister','tgif','dstar')}}
    import codec_selection
    from native_dmr.managed_config import from_station
    previous=codec_selection.read('dmr-native.json',{})
    native=from_station(config,previous)
    from native_nxdn.config import from_station as nxdn_from_station
    from native_ysf.config import from_station as ysf_from_station
    from native_p25.config import from_station as p25_from_station
    from native_m17.config import from_station as m17_from_station
    values['m17-native.json']=m17_from_station(config) or {'version':1,'disabled':True}
    values['p25-native.json']=p25_from_station(config) or {'version':1,'disabled':True}
    values['ysf-native.json']=ysf_from_station(config) or {'version':1,'disabled':True}
    values['nxdn-native.json']=nxdn_from_station(config) or {'version':1,'disabled':True}
    values['dmr-native.json']=native or {'version':1,'disabled':True}
    import dvswitch_config
    transport=dvswitch_config.load()
    if 'dvswitch' in config.get('dmr',{}):transport['dmr_transport']='dvswitch' if config['dmr']['dvswitch'] else 'native'
    values['dvswitch.json']=dvswitch_config.validate(transport)
    if native:values['dmr-networks.json']={'Network':native['selected']}
    for name,data in values.items():atomic(RUN/name,json.dumps(data),0o600,account.pw_uid,account.pw_gid)
    import codec_selection
    codec_selection.request('hardware' if config['dstar']['enabled'] else 'software')

def active():return run(['systemctl','is-active','asterisk'],check=False).strip()=='active'

def config_drift(state):
    expected=state.get('config_hashes',{})
    return [name for name,digest in expected.items() if not (ETC/name).is_file() or hashlib.sha256((ETC/name).read_bytes()).hexdigest()!=digest]

class CpuUsageSampler:
    """Aggregate busy-jiffy percentage, sampled only by existing health requests."""
    def __init__(self, reader=None, clock=time.monotonic):
        self.reader=reader or (lambda: Path('/proc/stat').read_text().splitlines()[0])
        self.clock=clock
        self.lock=threading.Lock()
        self.previous=None
        self.last_attempt=None
        self.percent=None
        self.interval=None

    def sample(self):
        with self.lock:
            now=self.clock()
            if self.last_attempt is not None and 0<=now-self.last_attempt<1:
                return dict(cpu_usage_percent=self.percent,cpu_usage_interval_seconds=self.interval)
            self.last_attempt=now
            try:
                fields=self.reader().split()
                if fields[0]!='cpu' or len(fields)<5:raise ValueError('Missing aggregate CPU counters')
                # Guest/guest_nice are already counted in user/nice: do not add twice.
                ticks=[int(value) for value in fields[1:9]]
                if any(value<0 for value in ticks):raise ValueError('Invalid CPU counter')
                total=sum(ticks);idle=ticks[3]+(ticks[4] if len(ticks)>4 else 0)
                current=(total,idle,now)
                self.percent=None;self.interval=None
                if self.previous is not None:
                    old_total,old_idle,old_time=self.previous
                    delta=total-old_total;idle_delta=idle-old_idle
                    if delta>0 and 0<=idle_delta<=delta and now>old_time:
                        self.percent=round(100*(delta-idle_delta)/delta,1)
                        self.interval=round(now-old_time,3)
                self.previous=current
            except (OSError,ValueError,IndexError):
                self.previous=None;self.percent=None;self.interval=None
            return dict(cpu_usage_percent=self.percent,cpu_usage_interval_seconds=self.interval)


CPU_USAGE=CpuUsageSampler()


def health():
    result={}
    result.update(CPU_USAGE.sample())
    try:result['uptime_seconds']=int(float(Path('/proc/uptime').read_text().split()[0]))
    except (OSError,ValueError,IndexError):result['uptime_seconds']=None
    try:result['cpu_celsius']=round(int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,1)
    except (OSError,ValueError):result['cpu_celsius']=None
    space=shutil.disk_usage('/');result['storage_free_gb']=round(space.free/1024**3,1);result['storage_used_percent']=round(100*(space.total-space.free)/space.total)
    result['kernel']=os.uname().release if hasattr(os,'uname') else None
    return result

def status():
    import codec_selection
    s=load_state();running=active();out='';drift=config_drift(s)
    if running:
        try:out=cli('rpt show registrations')
        except ValueError:pass
    # Raw registration lines may include passwords on some versions; never return them.
    registered=bool(re.search(r'\bRegistered\b',out,re.I)) and not bool(re.search(r'\bUnregistered\b',out,re.I))
    return dict(codec=codec_selection.snapshot(),health=health(),available=True,applied=bool(s),active=running,node=s.get('node'),radio_enabled=s.get('radio',False) and running,
                fingerprint=None if drift else s.get('fingerprint'),config_drift=drift,levels=s.get('levels',dict(rx=650,txa=600,txb=500)),registered=registered,
                registration='Registered' if registered else 'Pending or unavailable',audio_verified=s.get('audio_verified',False))

@contextlib.contextmanager
def radio_lock():
    import radio_readback
    with radio_readback.serial_lock():yield

def wait_for_radio_device(node, attempts=20):
    """A running repeater is not proof its USB sound device attached."""
    for _ in range(attempts):
        try:
            cli('susb active '+node)
            output=cli('susb show settings')
            card=re.search(r'^Card is (\d+)\s*$',output,re.M)
            device=re.search(r'^Device String is (.+)$',output,re.M)
            if ('Active radio interface is ['+node+']') in output and card and device and device[1].strip().lower() not in ('unassigned','none',''):
                return
        except ValueError:pass
        time.sleep(.5)
    raise ValueError('SimpleUSB did not attach a USB sound device. Check the SHARI USB connection.')


def open_program_record():
    try:
        return os.open('/var/lib/allmode/program.json',os.O_RDONLY|os.O_NOFOLLOW)
    except FileNotFoundError:
        raise ValueError('Radio programming is not complete. Open Setup > Program your SHARI radio, review your frequencies and tones, and press Program radio before activation.') from None

def reconcile_rf_config(node, files, favorites=None):
    """Reapply only explicitly reviewed isolation plus saved memories before restart.

    All parsing occurs in an isolated staging tree. Effective includes are copied,
    never dropped. Any ambiguity leaves the live configuration untouched.
    """
    from favorites_store import Store
    from rf_memories import Config, unmanaged
    approval_path=STATE/'rf-isolation.json'
    favorites_path=STATE/'favorites.json'
    if not approval_path.exists() and not favorites_path.exists():return files, {}
    if favorites is None:favorites=Store(favorites_path).snapshot()['favorites'] if favorites_path.exists() else []
    if not approval_path.exists():
        if any(row['enabled'] for row in favorites):
            raise ValueError('Enabled RF memories need a persisted owner-reviewed isolation plan before applying station configuration.')
        return files, {}
    approval=json.loads(approval_path.read_text())
    if not isinstance(approval,dict) or approval.get('node')!=node:
        raise ValueError('Station node changed; review RF source isolation again before applying configuration.')
    overrides=approval.get('node_overrides');sections=approval.get('new_sections')
    required={'functions','macro','link_functions','phone_functions','dphone_functions'}
    if not isinstance(overrides,dict) or set(overrides)!=required or not all(isinstance(v,str) and re.fullmatch(r'allmode-[0-9]+-[a-z_]+',v) for v in overrides.values()) or not isinstance(sections,str):
        raise ValueError('Saved RF isolation approval is malformed; review it again.')
    # Validate the existing include graph before staging any replacement.
    effective_files,current_sections,current_locations,current_effective=Config(ETC/'rpt.conf',node).read()
    if current_locations.get(node)!=(ETC/'rpt.conf').resolve():
        raise ValueError('The physical station node is in an included file. Automatic station regeneration with RF memories is unsupported for this topology; review and reconcile it manually. No configuration was changed.')
    root=ETC.resolve()
    def map_includes(text,source,target):
        return re.sub(r'(?m)^(\s*#(?:include|tryinclude)\s+["<]?)'+re.escape(str(source))+r'/',lambda m:m[1]+str(target)+'/',text)
    with tempfile.TemporaryDirectory(prefix='allmode-rf-render-') as temporary:
        staging=Path(temporary)
        approval_config=staging/'approval.conf';approval_config.write_text(sections)
        _,approved_sections,_,approved_effective=Config(approval_config,node).read()
        if set(approved_sections)!=set(overrides.values()):
            raise ValueError('Saved isolation tables do not match their approved bindings.')
        for name in approved_sections:
            if name not in current_sections or current_effective(name)!=approved_effective(name):
                raise ValueError('An owner-edited RF function or macro table needs review; station apply will not overwrite it.')
        approval_config.unlink()
        for path,(raw,_) in effective_files.items():
            relative=path.relative_to(root);dest=staging/relative;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(map_includes(raw,root,staging))
        text=unmanaged(files['rpt.conf'])
        # Baselines captured after isolation may already contain identical tables.
        if sections in text:text=text.replace(sections,'',1)
        pattern=r'(?ms)(^\['+re.escape(node)+r'\](?:\([^\n]*\))?[^\n]*\n)(.*?)(?=^\[|\Z)'
        def bind(match):
            body=match[2]
            if re.search(r'(?m)^\s*#',body):raise ValueError('Node-section includes need manual isolation review.')
            for key in overrides:body=re.sub(r'(?m)^\s*'+re.escape(key)+r'\s*=.*\n?', '', body)
            return match[1]+body.rstrip()+'\n'+''.join(k+'='+v+'\n' for k,v in overrides.items())+'\n'
        text,count=re.subn(pattern,bind,text)
        if count!=1:raise ValueError('Generated node is ambiguous; RF isolation was not changed.')
        text=text.rstrip()+'\n\n; Persisted owner-reviewed RF source isolation\n'+sections
        (staging/'rpt.conf').write_text(map_includes(text,root,staging))
        _,planned,_=Config(staging/'rpt.conf',node).plan(favorites)
        output=dict(files);extra={}
        for path,text in planned.items():
            relative=path.relative_to(staging);text=map_includes(text,staging,root)
            if str(relative) in output:output[str(relative)]=text
            elif text!=effective_files[root/relative][0]:extra[root/relative]=text
        return output, extra


def install_config(config,radio=False,levels=None):
    from favorites_store import Store
    STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    store=Store(STATE/'favorites.json')
    # Same lock order as favorite saves: store first, then effective RF config.
    with store._lock():
        with (STATE/'rf-memories.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            favorites=store._read()['favorites']
            return _install_config_locked(config,radio,levels,favorites)


def _install_config_locked(config,radio=False,levels=None,favorites=None):
    STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    baseline=STATE/'baseline';baseline.mkdir(mode=0o700,exist_ok=True)
    for name in FILES:
        if not (baseline/name).exists():shutil.copy2(ETC/name,baseline/name)
    templates={name:(baseline/name).read_text() for name in FILES}
    levels=levels or load_state().get('levels',dict(rx=650,txa=600,txb=500))
    node,files=render(config,templates,radio,levels)
    files,rf_extra=reconcile_rf_config(node,files,favorites)
    backup=STATE/('backup-'+str(time.time_ns()));backup.mkdir(mode=0o700)
    old=load_state();was_active=active()
    digital_active=run(['systemctl','is-active','allmode-digital'],check=False).strip()=='active'
    private_paths=[STATE/'state.json',STATE/'config.json']+[RUN/name for name in RUNTIME_FILES]+list(rf_extra)
    previous={}
    for index,path in enumerate(private_paths):
        saved=backup/('private-'+str(index))
        if path.exists():shutil.copy2(path,saved);previous[path]=saved
        else:previous[path]=None
    for name in FILES:shutil.copy2(ETC/name,backup/name)
    with radio_lock():
        if radio:
            fd=open_program_record()
            with os.fdopen(fd) as f:program=json.load(f)
            if program.get('state')!='acknowledged-not-verified' or program.get('acknowledged')!=['AT+DMOSETGROUP','AT+DMOSETVOLUME','AT+SETFILTER','AT+SETTAIL']:
                raise ValueError('Complete radio programming before activation.')
        run(['systemctl','stop','allmode-digital'],check=False)
        run(['systemctl','stop','asterisk'])
        try:
            for name,text in files.items():
                st=(ETC/name).stat();atomic(ETC/name,text,0o640,st.st_uid,st.st_gid)
            for path,text in rf_extra.items():
                st=path.stat();atomic(path,text,st.st_mode & 0o777,st.st_uid,st.st_gid)
            runtime_config(config)
            run(['systemctl','unmask','asterisk'])
            run(['systemctl','start','asterisk'],timeout=25)
            for _ in range(15):
                try:
                    if 'STATISTICS' in cli('rpt stats '+node):break
                except ValueError:pass
                time.sleep(.5)
            else:raise ValueError('Configured node did not become ready.')
            if radio:wait_for_radio_device(node)
            s=dict(node=node,fingerprint=fingerprint(config),radio=radio,levels=levels or old.get('levels',dict(rx=650,txa=600,txb=500)),audio_verified=False)
            run(['systemctl','enable','asterisk'])
            atomic(STATE/'config.json',json.dumps(config))
            s['config_hashes']={name:hashlib.sha256((ETC/name).read_bytes()).hexdigest() for name in FILES}
            save_state(s)
            if radio:run(['systemctl','start','allmode-digital'])
            else:run(['systemctl','stop','allmode-digital'])
        except Exception as error:
            run(['systemctl','stop','allmode-digital'],check=False)
            run(['systemctl','stop','asterisk'],check=False)
            for path,saved in previous.items():
                if saved is None:path.unlink(missing_ok=True)
                else:
                    st=saved.stat();atomic(path,saved.read_text(),st.st_mode & 0o777,st.st_uid,st.st_gid)
            for name in FILES:shutil.copy2(backup/name,ETC/name)
            if was_active:run(['systemctl','start','asterisk'],check=False)
            if digital_active:run(['systemctl','start','allmode-digital'],check=False)
            raise ValueError('Startup failed. Previous Asterisk configuration restored. '+str(error)) from error
    return status()

def handle(request):
    if not isinstance(request,dict):raise ValueError('Expected an operation.')
    action=request.get('action')
    if action=='status':return status()
    if action=='installation-state':
        return {'applied_config':bool((STATE/'config.json').exists()),'applied_state':bool((STATE/'state.json').exists())}
    if action=='codec-state':
        import codec_selection
        return codec_selection.snapshot()
    if action=='codec-select':
        import codec_selection
        return codec_selection.request(request.get('backend'))
    if action=='owner-password':
        pending=Path('/etc/allmode/os-owner-pending')
        auth=Path('/var/lib/allmode/auth.json')
        if not pending.exists() or not json.loads(auth.read_text()).get('unclaimed'):raise ValueError('Owner enrollment is closed.')
        password=request.get('password')
        if not isinstance(password,str) or not 4<=len(password)<=128 or any(c in password for c in '\r\n\0'):raise ValueError('Invalid password.')
        result=subprocess.run(['chpasswd'],input='ara:'+password+'\n',text=True,capture_output=True,timeout=10)
        if result.returncode:raise ValueError('Could not enroll the local owner account.')
        pending.unlink()
        return dict(ok=True)
    if action=='network-status':
        tools=optional_diagnostics()
        addresses=run(['ip','-brief','address'],check=False) if tools['ip'] else 'Unavailable: ip (iproute2) is not installed.'
        routes=run(['ip','route'],check=False) if tools['ip'] else 'Unavailable: ip (iproute2) is not installed.'
        dns=run(['nmcli','-f','GENERAL.DEVICE,GENERAL.STATE,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS','device','show'],check=False) if tools['nmcli'] else 'Unavailable: nmcli (NetworkManager) is not installed; Wi-Fi management is unavailable.'
        missing_audio=[name for name in ('aplay','arecord','amixer','alsactl') if not tools[name]]
        audio=('Unavailable ALSA command-line diagnostics: '+', '.join(missing_audio)) if missing_audio else 'ALSA command-line diagnostic tools are available.'
        return dict(output=addresses+'\nRoutes\n'+routes+'\nDetails\n'+dns+'\n'+audio+' Audio hardware and receive/transmit have not been tested by this status request.',tools=tools,audio_tested=False)
    if action=='wifi-scan':
        nmcli=require_optional_tool('nmcli','network-manager')
        output=run([nmcli,'-t','-f','SSID,SIGNAL,SECURITY','device','wifi','list','--rescan','yes'],timeout=25)
        return dict(networks=wifi_scan_rows(output))
    if action=='wifi-save':
        import configparser,uuid,io
        nmcli=require_optional_tool('nmcli','network-manager')
        connect=request.get('connect',False);hidden=request.get('hidden',False)
        if type(connect) is not bool or type(hidden) is not bool:raise ValueError('Wi-Fi hidden and connect choices must be on or off.')
        scheduler=require_optional_tool('systemd-run','systemd') if connect else None
        ssid=request.get('ssid');password=request.get('password','');security=request.get('security','wpa-psk')
        try:valid_ssid=isinstance(ssid,str) and 1<=len(ssid.encode('utf-8'))<=32 and not any(ord(c)<32 or ord(c)==127 for c in ssid)
        except UnicodeError:valid_ssid=False
        if not valid_ssid:raise ValueError('Enter a Wi-Fi name of 1–32 UTF-8 bytes without control characters.')
        if security not in ('wpa-psk','open'):raise ValueError('Choose WPA/WPA2 Personal or explicitly choose an open network. Other security requires administrator setup.')
        if security=='open':
            if password!='':raise ValueError('Open networks do not use a password; confirm the open-network choice.')
        elif not isinstance(password,str) or not ((8<=len(password)<=63 and all(32<=ord(c)<=126 for c in password)) or re.fullmatch('[0-9A-Fa-f]{64}',password)):
            raise ValueError('Enter the WPA/WPA2 Personal password (8–63 ASCII characters or 64 hex digits).')
        uid=str(uuid.uuid4());dest=WIFI_PROFILES/('ara-'+uid+'.nmconnection')
        if dest.exists() or dest.is_symlink():raise ValueError('Wi-Fi profile identity collision; no existing profile was changed.')
        config=configparser.RawConfigParser()
        config['connection']={'id':'ARA Wi-Fi '+uid[:8],'uuid':uid,'type':'wifi','autoconnect':'false'}
        # Documented NM decimal-byte SSID form preserves exact UTF-8 bytes,
        # including spaces, backslashes and numeric/semicolon SSID strings.
        config['wifi']={'mode':'infrastructure','ssid':''.join(str(x)+';' for x in ssid.encode('utf-8')),'hidden':'true' if hidden else 'false'}
        if security=='wpa-psk':config['wifi-security']={'key-mgmt':'wpa-psk','psk':wifi_keyfile_string(password)}
        config['ipv4']={'method':'auto'};config['ipv6']={'method':'auto'}
        out=io.StringIO();config.write(out)
        atomic(dest,out.getvalue())
        try:run([nmcli,'connection','load',str(dest)])
        except Exception:raise ValueError('Wi-Fi profile was saved, but loading it was not confirmed. No connection switch was scheduled by this request. Check network status before retrying.') from None
        if connect:return wifi_schedule(uid,nmcli,scheduler)
        return dict(ok=True,id=uid,scheduled=False,connected=False,message='Wi-Fi saved without changing connectivity. Choose Connect now to activate it and enable future automatic connections.')
    if action=='wifi-connect':
        nmcli=require_optional_tool('nmcli','network-manager')
        scheduler=require_optional_tool('systemd-run','systemd')
        return wifi_schedule(request.get('id',''),nmcli,scheduler)
    if action in ('digital-identities','digital-identities-save'):
        import codec_selection,pwd
        from native_m17.protocol import address
        station=json.loads((STATE/'config.json').read_text());call=station['station']['callsign']
        saved=codec_selection.read('digital-quick-identities.json',{})
        if action=='digital-identities-save':
            values=request.get('values')
            if not isinstance(values,dict) or set(values)!={'nxdn','p25','m17'}:raise ValueError('Supply NXDN, P25 and M17 identities')
            clean={}
            for key,limit in (('nxdn',65535),('p25',16777215)):
                v=values[key]
                if not isinstance(v,str) or (v and (not re.fullmatch('[0-9]+',v) or not 1<=int(v)<=limit)):raise ValueError(key.upper()+' ID must be blank or 1 to '+str(limit))
                clean[key]=v
            v=values['m17']
            if not isinstance(v,str):raise ValueError('Enter an M17 callsign')
            v=v.strip().upper()
            if v:address(v)
            clean['m17']=v
            for key in ('nxdn','p25'):saved[key.upper()]={'id':clean[key],'callsign':call}
            saved['M17']={'id':v,'callsign':call}
            a=pwd.getpwnam('allmode');atomic(RUN/'digital-quick-identities.json',json.dumps(saved),0o600,a.pw_uid,a.pw_gid)
        values={}
        for key in ('nxdn','p25'):
            entry=saved.get(key.upper(),{});previous=codec_selection.read(key+'-native.json',{})
            values[key]=str(entry.get('id','')) if entry.get('callsign')==call else str(station.get('other',{}).get(key+'_id') or (previous.get('source','') if previous.get('callsign')==call else ''))
        entry=saved.get('M17',{});values['m17']=(entry.get('id') or call) if entry.get('callsign')==call else call
        return {'values':values,'message':'Digital IDs saved. Used on your next connection.'}
    if action=='digital-prepare':
        import digital_connect,directory_sync,codec_selection,pwd
        mode=request.get('mode')
        if mode not in digital_connect.MODES:raise ValueError('Unsupported digital mode')
        if not __import__(mode.lower()+'_native').installed():raise ValueError(mode+' adapter is not installed')
        if codec_selection.desired()['backend']!='software':raise ValueError(mode+' requires the software digital codec')
        station=json.loads((STATE/'config.json').read_text())
        station['dstar']['enabled']=False # validated live codec selection above
        previous=codec_selection.read(mode.lower()+'-native.json',{})
        identities=codec_selection.read('digital-quick-identities.json',{})
        result=digital_connect.prepare(mode,request.get('target'),request.get('source_id'),station,previous,identities,directory_sync.endpoint)
        if request.get('check') is True:return {'ok':True}
        if __import__(mode.lower()+'_native').status().get('state') not in ('stopped',None):raise ValueError(mode+' is still stopping; retry shortly')
        a=pwd.getpwnam('allmode')
        atomic(RUN/(mode.lower()+'-native.json'),json.dumps(result),0o600,a.pw_uid,a.pw_gid)
        if mode in ('NXDN','P25'):
            identities[mode]={'id':result['source'],'callsign':result['callsign']}
            atomic(RUN/'digital-quick-identities.json',json.dumps(identities),0o600,a.pw_uid,a.pw_gid)
        return {'ok':True}
    if action=='dmr-network':
        import codec_selection,dmr_native,pwd
        from native_dmr.managed_config import update
        result=update(codec_selection.read('dmr-native.json'),{'Network':request.get('network')})
        if request.get('check') is True:return {'selected':result['selected']}
        if dmr_native.status().get('state') not in ('stopped',None):raise ValueError('DMR is still stopping; retry shortly.')
        a=pwd.getpwnam('allmode')
        atomic(RUN/'dmr-native.json',json.dumps(result),0o600,a.pw_uid,a.pw_gid)
        atomic(RUN/'dmr-networks.json',json.dumps({'Network':result['selected']}),0o600,a.pw_uid,a.pw_gid)
        return {'selected':result['selected']}
    if action=='dmr-settings':
        import codec_selection
        from native_dmr.managed_config import public_fields
        return public_fields(codec_selection.read('dmr-native.json'))
    if action=='dmr-save':
        import codec_selection,dmr_native
        from native_dmr.managed_config import update,public_fields
        values=request.get('values')
        import setup_api
        values=setup_api.validate('dmr',values)
        state=load_state()
        if active():
            RADIO_PARROT.idle(RADIO_PARROT.stats(state.get('node')))
        if dmr_native.status().get('state') not in ('stopped',None):raise ValueError('Disconnect DMR before saving network settings')
        result=update(codec_selection.read('dmr-native.json'),values)
        import pwd
        a=pwd.getpwnam('allmode')
        atomic(RUN/'dmr-native.json',json.dumps(result),0o600,a.pw_uid,a.pw_gid)
        atomic(RUN/'dmr-networks.json',json.dumps({'Network':result['selected']}),0o600,a.pw_uid,a.pw_gid)
        return public_fields(result)
    if action=='apply':
        config=normalized(request.get('config'))
        import dmr_native
        issue=dmr_native.problem(config) or __import__('nxdn_native').problem(config) or __import__('ysf_native').problem(config) or __import__('p25_native').problem(config) or __import__('m17_native').problem(config)
        if issue:raise ValueError(issue+'. Saved settings are unchanged; nothing applied.')
        resume_radio=bool(load_state().get('radio')) and active()
        result=install_config(config,resume_radio)
        result['message']='Settings applied. Radio restarted and USB device verified.' if resume_radio else 'Settings applied. Radio remains stopped; start it from Audio levels when ready.'
        return result
    if action=='test-ambe':
        config=normalized(request.get('config'))
        if not config['dstar']['enabled']:raise ValueError('Enable and save external AMBE settings first.')
        if run(['systemctl','is-active','allmode-digital'],check=False).strip()=='active' and 'D-STAR' in json.loads((RUN/'digital-modes.json').read_text() if (RUN/'digital-modes.json').exists() else '[]'):
            raise ValueError('Disconnect D-STAR before testing its AMBE server.')
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
        if not fingerprint_matches(config,request.get('fingerprint')):raise ValueError('Apply the latest saved settings before activation.')
        if config_drift(load_state()):raise ValueError('Resolve configuration changes before activation.')
        # Require a complete radio acknowledgement record, not merely a draft.
        fd=open_program_record()
        with os.fdopen(fd) as f:program=json.load(f)
        if program.get('state')!='acknowledged-not-verified' or len(program.get('acknowledged',[]))!=4:raise ValueError('Complete radio programming before activation.')
        result=install_config(config,True,load_state().get('levels'))
        return result
    if action=='audio':
        levels=request.get('levels')
        if not isinstance(levels,dict) or set(levels)!={'rx','txa','txb'} or any(type(v) is not int or not 0<=v<=999 for v in levels.values()):raise ValueError('Audio levels must be integers from 0 to 999.')
        state=load_state()
        if not active() or not state.get('radio'):raise ValueError('Start the radio before adjusting audio.')
        node=state['node']
        cli('susb active '+node)
        for key in ('rx','txa','txb'):cli('susb tune '+key+' '+str(levels[key]))
        actual=cli('susb show settings')
        for key,label in (('rx','Rx'),('txa','Tx A'),('txb','Tx B')):
            match=re.search(re.escape(label)+r' Level currently set to (\d+)',actual)
            if not match or int(match.group(1))!=levels[key]:raise ValueError('Radio did not confirm '+label+' level. Settings were not saved.')
        import setup_api
        conf=ETC/'simpleusb.conf'
        before_hash=hashlib.sha256(conf.read_bytes()).hexdigest()
        setup_api.write_section(conf,node,{'rxmixerset':str(levels['rx']),'txmixaset':str(levels['txa']),'txmixbset':str(levels['txb'])})
        state['levels']=dict(levels)
        # Do not clear a pre-existing configuration-drift warning.
        if state.get('config_hashes',{}).get('simpleusb.conf')==before_hash:
            state['config_hashes']['simpleusb.conf']=hashlib.sha256(conf.read_bytes()).hexdigest()
        save_state(state)
        return dict(ok=True,levels=levels,message='Audio levels are live and saved. Radio readback confirmed.')
    if action=='audio-confirm':
        s=load_state()
        if request.get('checked') is not True or not active() or not s.get('radio'):raise ValueError('Start the radio and complete receive/transmit checks first.')
        s['audio_verified']=True;s['audio_verification']='Operator reported receive/transmit check';save_state(s)
        return status()
    if action=='bridge-forwarding':
        enabled=request.get('enabled')
        if type(enabled) is not bool:raise ValueError('Choose bridge forwarding on or off.')
        state=load_state()
        if not active():raise ValueError('Start the radio first.')
        if config_drift(state):raise ValueError('Resolve configuration changes before bridging.')
        import setup_api
        path=ETC/'rpt.conf';before=path.read_bytes()
        try:
            setup_api.write_section(path,state['node'],{'linktolink':'yes' if enabled else 'no'})
            cli('module reload app_rpt.so')
        except Exception:
            path.write_bytes(before)
            cli('module reload app_rpt.so')
            raise
        state.setdefault('config_hashes',{})['rpt.conf']=hashlib.sha256(path.read_bytes()).hexdigest();save_state(state)
        return {'enabled':enabled}
    if action=='cli':
        s=load_state();node=re.escape(s.get('node','NONE'));command=request.get('command','')
        patterns=[rf'rpt (?:stats|lstats|xnode) {node}',r'module show like chan_echolink\.so',rf'rpt cmd {node} ilink [138] [0-9]{{4,7}}']
        if not isinstance(command,str) or not any(re.fullmatch(p,command) for p in patterns):raise ValueError('Command is not permitted.')
        return dict(output=cli(command))
    raise ValueError('Unknown system operation.')


from radio_parrot import make_manager
RADIO_PARROT=make_manager(cli)
from audio_meter import Meter
AUDIO_METER=Meter(cli)
_handle=handle
def handle(request):
    with RADIO_PARROT.lock:
        action=request.get('action') if isinstance(request,dict) else None
        if action in ('favorites-status','favorites-save','favorites-import'):
            from favorites_store import Store, ConflictError
            from rf_memories import Config, SOCKET
            import stat
            state=load_state()
            def reload_memories():
                output=cli('module reload app_rpt.so')
                if any(word in output.lower() for word in ('failed','not found','does not support','error')):
                    raise ValueError('Asterisk rejected RF memory reload; configuration restored.')
            rf=Config(ETC/'rpt.conf',state.get('node'),reload=reload_memories,lock=STATE/'rf-memories.lock')
            @contextlib.contextmanager
            def transaction(old,new):
                nonlocal state,rf
                # Store has acquired its cross-process lock before entering here.
                # Refresh after waiting for an explicit isolation/apply operation.
                state=load_state()
                rf=Config(ETC/'rpt.conf',state.get('node'),reload=reload_memories,lock=STATE/'rf-memories.lock')
                if any(f.get('enabled') for f in new['favorites']):
                    if RADIO_PARROT.active:raise ValueError('Stop the radio parrot before enabling RF memories.')
                    if not state.get('radio') or not active():raise ValueError('Local radio service is unavailable; RF enable refused.')
                    try:ready=stat.S_ISSOCK(Path(SOCKET).stat().st_mode)
                    except OSError:ready=False
                    if not ready:raise ValueError('Local RF recall service is unavailable; RF enable refused.')
                expected=state.get('config_hashes',{})
                baseline_matches=not config_drift(state)
                if any(f.get('enabled') for f in new['favorites']) and not baseline_matches:
                    raise ValueError('Review existing station configuration drift before enabling RF memories.')
                # Never adopt unrelated drift as an approved configuration.
                old_state=(STATE/'state.json').read_text() if (STATE/'state.json').exists() else None
                try:
                    with rf.transaction(new['favorites']):
                        if expected and baseline_matches:
                            revised=dict(state)
                            revised['config_hashes']={name:hashlib.sha256((ETC/name).read_bytes()).hexdigest() for name in expected}
                            save_state(revised)
                        yield
                except BaseException:
                    if old_state is None:(STATE/'state.json').unlink(missing_ok=True)
                    else:atomic(STATE/'state.json',old_state)
                    raise
            store=Store(STATE/'favorites.json',transaction=transaction)
            try:
                if action=='favorites-save':result=store.replace(request.get('payload'))
                elif action=='favorites-import':result=store.import_legacy(request.get('payload'))
                else:result=store.snapshot()
            except ConflictError as exc:return {'error':str(exc),'code':'conflict'}
            result['rf']=rf.status(result['favorites'])
            try:ready=stat.S_ISSOCK(Path(SOCKET).stat().st_mode)
            except OSError:ready=False
            if not ready:result['rf']={'available':False,'reason':'Local RF recall service is unavailable.'}
            if action!='favorites-status':
                import logging
                logging.getLogger('allmode.favorites').info('Favorites saved revision=%s count=%s enabled=%s',result['revision'],len(result['favorites']),sum(bool(f.get('enabled')) for f in result['favorites']))
            if not state.get('radio') or not active():result['rf']={'available':False,'reason':'Local radio service is unavailable.'}
            return result
        if action=='audio-meter':return AUDIO_METER.snapshot(load_state().get('node'))
        if action=='radio-parrot-state':return RADIO_PARROT.status()
        if action=='radio-parrot-stop':
            result=RADIO_PARROT.stop()
            from radio_codec_audio import Capture
            Capture(cli).clear()
            return result
        if action=='radio-parrot-heartbeat':return RADIO_PARROT.ping()
        if action=='radio-parrot-arm':
            state=load_state()
            if not state.get('radio') or not active():raise ValueError('SHARI radio is not active')
            modes=json.loads((RUN/'digital-modes.json').read_text()) if (RUN/'digital-modes.json').exists() else []
            # Idle unlinked adapters receive no radio PCM; node isolation is authoritative.
            return RADIO_PARROT.arm(state.get('node'),request.get('confirm'),request.get('mode','analog'))
        if RADIO_PARROT.active and action not in ('status','audio'):
            if action!='cli' or not str(request.get('command','')).startswith(('rpt stats ','rpt lstats ','rpt xnode ','module show ')):
                raise ValueError('Stop the radio parrot before changing settings or connections')
        return _handle(request)

def parrot_watchdog():
    while True:
        time.sleep(.25)
        try:RADIO_PARROT.tick()
        except Exception:pass # lease remains; next iteration retries cleanup

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(10)
        try:
            data=self.rfile.readline(1048577)
            if len(data)>1048576:raise ValueError('Request too large.')
            request=json.loads(data)
            if len(data)>16384 and (not isinstance(request,dict) or request.get('action') not in ('favorites-save','favorites-import')):
                raise ValueError('Request too large.')
            result=handle(request)
        except ValueError as error:
            result={'error':str(error)}
        except (OSError,TypeError,KeyError,subprocess.TimeoutExpired):
            # Never put credentials or command output into client errors/logs.
            result={'error':'Operation failed. Check prerequisites and system service logs.'}
            import traceback;traceback.print_exc(limit=0)
        self.wfile.write(json.dumps(result).encode()+b'\n')

if __name__=='__main__':
    import grp,threading,signal
    def shutdown_meter(signum,frame):raise SystemExit(0)
    signal.signal(signal.SIGTERM,shutdown_meter)
    if RADIO_PARROT.active:RADIO_PARROT.stop('Recovered previous radio test')
    threading.Thread(target=parrot_watchdog,daemon=True).start()
    path=Path('/run/allmode-system/control.sock');path.unlink(missing_ok=True)
    with socketserver.UnixStreamServer(str(path),Handler) as server:
        os.chown(path,0,grp.getgrnam('allmode').gr_gid);os.chmod(path,0o660)
        try:server.serve_forever()
        finally:AUDIO_METER.stop()
