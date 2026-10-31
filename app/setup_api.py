"""Small, allowlisted setup API for the local radio appliance."""
import re, os, time, shutil, json, subprocess
import digital
from pathlib import Path

AST=Path('/etc/asterisk')
DMR=Path('/opt/allmode-dmr')
RUN=Path('/var/lib/asterisk/allmode')
# name, label, type, limits/options
SCHEMAS={
 'allstar': [('idrecording','Callsign','call',None),('totime','Transmit timeout (ms)','int',(10000,600000)),('idtime','Identification interval (ms)','int',(60000,600000)),('hangtime','Hang time (ms)','int',(0,10000)),('propagate_dtmf','Pass radio DTMF','bool',None),('propagate_phonedtmf','Pass phone DTMF','bool',None)],
 'radio': [('frequency','Simplex frequency (MHz)','frequency',None),('tone','RX and TX CTCSS tone (Hz; 0 = both off)','tone',None),('squelch','Squelch','int',(0,8)),('bandwidth','Bandwidth','int',(0,1))],
 'usb': [('rxmixerset','To network — receive level','int',(0,999)),('txmixaset','To radio — channel A','int',(0,999)),('txmixbset','To radio — channel B','int',(0,999))],
 'usb-options': [('carrierfrom','Carrier detect','choice',('no','usb','usbinvert')),('ctcssfrom','Tone detect','choice',('no','usb','usbinvert')),('invertptt','Invert PTT','bool',None),('plfilter','PL filter','bool',None),('deemphasis','Receive de-emphasis','bool',None),('preemphasis','Transmit pre-emphasis','bool',None),('rxondelay','Receive delay (20 ms steps)','int',(0,100)),('txoffdelay','Transmit delay (20 ms steps)','int',(0,100))],
 'dmr': [('Network','DMR network','choice',('TGIF','BrandMeister')),('Master','BrandMeister USA master','choice',('3102','3103','3104')),('Callsign','Callsign','call',None),('Id','DMR ID with 2-digit extension','int',(100000000,999999999)),('ColorCode','Color code','int',(0,15)),('Jitter','Jitter buffer (ms)','int',(60,1000)),('TGIFPassword','TGIF hotspot password','password',None),('BMPassword','BrandMeister hotspot security password','password',None)],
 'echolink': [('call','EchoLink callsign','elcall',None),('node','EchoLink node number','int',(1,999999)),('name','Your name','text',None),('qth','Location','text',None),('email','Email','text',None),('pwd','EchoLink password','password',None)]
}
TITLES={'allstar':'AllStar setup','usb':'USB audio tuning','dmr':'DMR setup','echolink':'EchoLink setup','radio':'Radio frequency and tone','usb-options':'USB radio options'}

def section(text,name):
    values={}; active=False; parents=[]
    for line in text.splitlines():
        clean=line.split(';',1)[0].strip()
        m=re.match(r'^\[([^]]+)\](?:\(([^)]*)\))?',clean)
        if m:
            active=m[1]==name
            if active:parents=[v.strip() for v in (m[2] or '').split(',') if v.strip() and v.strip()!='!']
        elif active and '=' in clean:
            key,value=clean.split('=',1);values[key.strip()]=value.strip()
    inherited={}
    for parent in parents: inherited.update(section(text,parent))
    inherited.update(values);return inherited

def read(path):
    try:return path.read_text()
    except OSError:return ''

def location(group,node):
    return {'allstar':(AST/'rpt.conf',node),'usb-options':(AST/'simpleusb.conf',node),'dmr':(DMR/'MMDVM_Bridge/allmode-tgif.ini','General'),'echolink':(AST/'echolink.conf','el0')}[group]

def validate(group,values):
    if group not in SCHEMAS or not isinstance(values,dict):raise ValueError('Choose a setup section.')
    allowed={f[0]:f for f in SCHEMAS[group]}
    if not values or set(values)-set(allowed):raise ValueError('Unknown setup field.')
    result={}
    for key,value in values.items():
        _,label,kind,limit=allowed[key]
        if kind=='int':
            if isinstance(value,bool) or not re.fullmatch(r'[0-9]{1,10}',str(value)):raise ValueError(label+' must be a number.')
            value=int(value)
            if not limit[0]<=value<=limit[1]:raise ValueError(f'{label}: use {limit[0]}–{limit[1]}.')
            value=str(value)
        elif kind=='choice':
            if value not in limit:raise ValueError(label+' has an invalid option.')
        elif kind in ('frequency','tone'):
            if isinstance(value,bool):raise ValueError(label+' must be a number.')
            try:number=float(value)
            except (ValueError,TypeError):raise ValueError(label+' must be a number.')
            if kind=='frequency' and not (144<=number<=148 or 420<=number<=450):raise ValueError('Use 144–148 MHz or 420–450 MHz for your installed module.')
            if kind=='tone' and number not in [0,67,71.9,74.4,77,79.7,82.5,85.4,88.5,91.5,94.8,97.4,100,103.5,107.2,110.9,114.8,118.8,123,127.3,131.8,136.5,141.3,146.2,151.4,156.7,159.8,162.2,165.5,167.9,171.3,173.8,177.3,179.9,183.5,186.2,189.9,192.8,196.6,199.5,203.5,206.5,210.7,218.1,225.7,229.1,233.6,241.8,250.3,254.1]:raise ValueError('Use a standard CTCSS tone or 0.')
            value=str(number)
        elif kind=='bool':
            if not isinstance(value,bool):raise ValueError(label+' must be on or off.')
            value='yes' if value else 'no'
        else:
            if not isinstance(value,str) or len(value)>96 or any(c in value for c in '\r\n;[]=\\') or any(ord(c)<32 for c in value):raise ValueError(label+' contains invalid characters.')
            value=value.strip()
            if kind=='password' and not value:continue
            if kind in ('call','elcall') and not re.fullmatch(r'[A-Za-z0-9]{3,12}(?:-[LR])?' if kind=='elcall' else r'[A-Za-z0-9]{3,12}',value):raise ValueError('Enter a valid callsign.')
            if kind in ('call','elcall') and not any(c.isdigit() for c in value):raise ValueError('Callsign must include a number.')
            if key=='idrecording':value='|i'+value.upper()
        result[key]=value
    return result

def write_section(path,name,updates):
    text=path.read_text(); lines=text.splitlines(keepends=True); out=[];active=False;found=False;remaining=dict(updates)
    for line in lines:
        m=re.match(r'^\s*\[([^]]+)\]',line)
        if m:
            if active:
                out.extend(f'{k} = {v}\n' for k,v in remaining.items());remaining={}
            active=m[1]==name;found=found or active
        if active and '=' in line and not line.lstrip().startswith(';'):
            key=line.split('=',1)[0].strip()
            if key in updates:
                if key in remaining:out.append(f'{key} = {remaining.pop(key)}\n')
                continue
        out.append(line)
    if active:out.extend(f'{k} = {v}\n' for k,v in remaining.items())
    if not found:raise ValueError('Configuration section missing.')
    new=''.join(out)
    if path.name=='allmode-tgif.ini':new=re.sub(r'^([^;\n=]+?)\s*=\s*',lambda m:m[1].strip()+'=',new,flags=re.M)
    backup=RUN/'backups';backup.mkdir(exist_ok=True)
    dest=backup/(path.name+'.'+str(time.time_ns()));dest.write_text(text);dest.chmod(0o600)
    # Preserve ownership and permissions of the existing Asterisk files.
    with path.open('w') as file:file.write(new)
    if path.name in ('echolink.conf','allmode-tgif.ini'):path.chmod(0o600)


def snapshot(controller):
    groups=[]
    for group,schema in SCHEMAS.items():
        if group=='radio':
            try:values=json.loads((RUN/'radio.json').read_text())
            except (OSError,ValueError):values={}
        elif group=='dmr' and (RUN/'dmr-native.json').exists():
            import system_client
            values=system_client.request('dmr-settings')
        elif group=='usb':
            output=controller.run_cli('susb show settings')
            values={}
            for key,label in [('rxmixerset','Rx'),('txmixaset','Tx A'),('txmixbset','Tx B')]:
                m=re.search(re.escape(label)+r' Level currently set to (\d+)',output)
                values[key]=m[1] if m else ''
        else:
            path,name=location(group,controller.node);text=read(path)
            if group=='usb-options':
                for extra in sorted((AST/'custom/simpleusb').glob('*.conf')):text+='\n'+read(extra)
            values=section(text,name)
            if group=='dmr':
                values.update(section(text,'DMR'));values.update(section(text,'DMR Network'))
                account=digital.load('dmr-networks.json',{})
                values.update(Network=account.get('Network','TGIF'),Master=account.get('Master','3104'))
        fields=[]
        for key,label,kind,limit in schema:
            value=values.get(key,'no' if kind=='bool' else '')
            if kind=='password':value=''
            elif kind=='bool':value=value.lower() in ('yes','1','true')
            elif key=='idrecording':value=value.removeprefix('|i')
            fields.append(dict(key=key,label=label,type=kind,value=value,limits=limit))
        groups.append(dict(id=group,title=TITLES[group],fields=fields))
    total,used,free=shutil.disk_usage('/')
    system_extra={}
    try:
        net=json.loads(subprocess.run(['/usr/sbin/ip','-j','address','show','wlan0'],capture_output=True,text=True,timeout=3).stdout)[0]
        system_extra['Wi-Fi']=net['operstate']
        system_extra['IP address']=', '.join(a['local'] for a in net['addr_info'] if a['family']=='inet')
        mem={line.split(':')[0]:line.split(':')[1].strip() for line in read(Path('/proc/meminfo')).splitlines() if ':' in line}
        system_extra['Memory available']=f"{int(mem['MemAvailable'].split()[0])/1024:.0f} MB"
    except (OSError,ValueError,IndexError,KeyError,subprocess.TimeoutExpired):pass
    return dict(groups=groups,system={**system_extra,'Hardware':'SHARI / Pi Zero 2 W','Node':controller.node,'IAX port':section(read(AST/'iax.conf'),'general').get('bindport','4569'),'Storage total':f'{total/2**30:.1f} GB','Storage free':f'{free/2**30:.1f} GB','Uptime':f'{float(read(Path("/proc/uptime")).split()[0])/3600:.1f} hours','Operating system':next((s.split('=',1)[1].strip('"') for s in read(Path('/etc/os-release')).splitlines() if s.startswith('PRETTY_NAME=')),'Unknown'),'Asterisk':controller.run_cli('core show version').strip()},radio={'Frequency and tone':'SA818 programming required; module has no supported settings readback','Receiver channel':section(read(AST/'rpt.conf'),controller.node).get('rxchannel','Unknown')})

def save(controller,payload):
    if not isinstance(payload,dict) or set(payload)!={'group','values'}:raise ValueError('Supply a section and its values.')
    group=payload['group'];values=validate(group,payload['values'])
    current=controller.snapshot()
    if current['targets'] or current['pending'] or current['receiving']:raise ValueError('Disconnect and wait for the radio to be idle before saving setup.')
    if not values:raise ValueError('No settings to save.')
    if group=='radio':
        raise ValueError('Use the SA818S hardware page in maintenance mode to program the radio.')
    elif group=='usb':
        backup=RUN/'backups';backup.mkdir(exist_ok=True)
        dest=backup/('simpleusb.conf.'+str(time.time_ns()));dest.write_text((AST/'simpleusb.conf').read_text());dest.chmod(0o600)
        controller.run_cli('susb active '+controller.node)
        for key,value in values.items():controller.run_cli('susb tune '+{'rxmixerset':'rx','txmixaset':'txa','txmixbset':'txb'}[key]+' '+value)
        controller.run_cli('susb tune save')
    elif group=='dmr' and (RUN/'dmr-native.json').exists():
        import system_client
        system_client.request('dmr-save',values=values)
    elif group=='dmr':
        path,name=location(group,controller.node)
        account=digital.load('dmr-networks.json',{})
        if 'TGIFPassword' not in account:
            account['TGIFPassword']=section(path.read_text(),'DMR Network').get('Password','')
        account.update({k:v for k,v in values.items() if k in ('Network','Master','TGIFPassword','BMPassword')})
        account.setdefault('Network','TGIF');account.setdefault('Master','3104')
        if not account.get('BMPassword' if account['Network']=='BrandMeister' else 'TGIFPassword'):
            raise ValueError('Enter the selected network hotspot password before saving.')
        for section_name,keys in [('General',{'Callsign','Id'}),('DMR',{'ColorCode'}),('DMR Network',{'Jitter','Password'})]:
            subset={k:v for k,v in values.items() if k in keys}
            if subset:write_section(path,section_name,subset)
        # Analog_Bridge identity must match MMDVM_Bridge.
        identity={}
        if 'ColorCode' in values:identity['colorCode']=values['ColorCode']
        if 'Id' in values:identity.update(gatewayDmrId=str(int(values['Id'])//100),repeaterID=values['Id'])
        if identity:write_section(DMR/'analog-test.ini','AMBE_AUDIO',identity)
        digital.save('dmr-networks.json',account)
        (RUN/'restart-dmr').touch()
    else:
        path,name=location(group,controller.node)
        if group=='echolink':
            values['astnode']=controller.node
            values['context']='radio-secure'
            existing=section(path.read_text(),name)
            if not values.get('pwd',existing.get('pwd','')) or values.get('pwd',existing.get('pwd','')).lower() in ('password','invalid'):raise ValueError('Enter your EchoLink account password.')
        write_section(path,name,values)
        if group=='usb-options':(RUN/'restart-radio').touch()
        elif group=='allstar':controller.run_cli('module reload app_rpt.so')
        else:
            modules=AST/'modules.conf'
            text=modules.read_text()
            backup=RUN/'backups'/('modules.conf.'+str(time.time_ns()));backup.write_text(text);backup.chmod(0o600)
            modules.write_text(re.sub(r'^noload\s*=\s*chan_echolink.so[^\n]*','load = chan_echolink.so',text,flags=re.M))
            status=controller.run_cli('module show like chan_echolink.so')
            controller.run_cli('module reload chan_echolink.so' if '1 modules loaded' in status else 'module load chan_echolink.so')
    controller.record(TITLES[group]+' saved.')
    return controller.snapshot()
