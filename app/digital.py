"""Mode routing. Each digital connection owns distinct audio ports and a private node."""
import json, os, re, socket, struct
from pathlib import Path
RUN=Path('/var/lib/asterisk/allmode')
ROOT=Path('/opt/allmode-dmr')
PROFILES={
 'M17':dict(node='1993',tx=32007,rx=34007,tlv=36100,format='M17_3200'),
 'D-STAR':dict(node='1994',tx=32006,rx=34006,tlv=32100,mb=32103,remote=6077,format='DSTAR'),
 'DMR':dict(node='1999',tx=32001,rx=34001,tlv=31100,mb=31103,codec=2470,format='DMR'),
 'YSF':dict(node='1998',tx=32002,rx=34002,tlv=35100,mb=35103,codec=2471,format='YSFN',gateway='YSFGateway',remote=6073),
 'P25':dict(node='1997',tx=32003,rx=34003,tlv=34100,mb=34103,format='P25',gateway='P25Gateway',remote=6074),
 'NXDN':dict(node='1996',tx=32004,rx=34004,tlv=33100,mb=33103,codec=2472,format='NXDN',gateway='NXDNGateway',remote=6075),
 'FCS':dict(node='1995',tx=32005,rx=34005,tlv=35200,mb=35203,codec=2473,format='YSFN',gateway='YSFGateway',remote=6076),
}
PRIVATE={v['node']:k for k,v in PROFILES.items()}

def load(name,default):
 try:return json.loads((RUN/name).read_text())
 except (OSError,ValueError):return default

def save(name,data):
 path=RUN/name;temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(data));temporary.chmod(0o600);os.replace(temporary,path)

def catalog():
 result={}
 for mode in ['YSF','P25','NXDN']:
  rows=[]
  try:lines=(ROOT/'hosts'/(mode+'Hosts.txt')).read_text().splitlines()
  except OSError:lines=[]
  for line in lines:
   if not line or line.startswith('#'):continue
   fields=line.split(';') if mode=='YSF' else line.split()
   if len(fields)<(5 if mode=='YSF' else 3) or not fields[0].isdigit():continue
   rows.append({'target':fields[0].zfill(5) if mode=='YSF' else str(int(fields[0])),'name':fields[1] if mode=='YSF' else fields[3] if len(fields)>3 else fields[1]})
  result[mode]=rows
 try:
  from dstar_worker import hosts
  result['D-STAR']=[{'target':name+('A' if name.startswith('XLX') else 'C'),'name':name+' (choose module A–Z)'} for name in sorted(hosts())]
 except OSError:result['D-STAR']=[]
 import codec_selection
 config=codec_selection.read('nxdn-native.json',{})
 if config and not config.get('disabled') and str(config.get('target')) not in {r['target'] for r in result['NXDN']}:
  result['NXDN'].append({'target':str(config['target']),'name':'Configured NXDN reflector'})
 config=codec_selection.read('ysf-native.json',{})
 if config and not config.get('disabled') and str(config.get('target')).zfill(5) not in {r['target'] for r in result['YSF']}:
  result['YSF'].append({'target':str(config['target']).zfill(5),'name':'Configured YSF reflector (V/D2 only)'})
 config=codec_selection.read('p25-native.json',{})
 if config and not config.get('disabled') and str(config.get('target')) not in {r['target'] for r in result['P25']}:
  result['P25'].append({'target':str(config['target']),'name':'Configured P25 reflector (Phase 1 only)'})
 config=codec_selection.read('m17-native.json',{})
 result['M17']=[]
 try:
  for line in (ROOT/'hosts/M17Hosts.txt').read_text().splitlines():
   f=line.split()
   if len(f)>=3 and re.fullmatch(r'M17-[A-Z0-9]{3}',f[0]):result['M17'].append({'target':f[0]+' A','name':f[0]+' (choose module A-Z)'})
 except OSError:pass
 if config and not config.get('disabled'):
  result['M17'].append({'target':config['target'],'name':'Configured M17 reflector (Codec2 3200)'})
 return result

def available():
 result=[]
 import codec_selection
 codec=codec_selection.read('dstar-codec.json',{});probe=codec_selection.read('dstar-probe.json',{})
 selected_backend=codec_selection.desired()['backend']
 external_ok=probe.get('passed') and all(codec.get(k)==probe.get(k) for k in ('host','port'))
 import dmr_native
 if dmr_native.configured():result.append('DMR')
 if __import__('nxdn_native').configured():result.append('NXDN')
 if __import__('ysf_native').configured():result.append('YSF')
 if __import__('p25_native').configured():result.append('P25')
 if __import__('m17_native').configured():result.append('M17')
 software_ok=Path('/opt/allmode-vocoder-prototype/current/build/liballmode_dstar.so').is_file()
 selected_ok=(external_ok and load('enabled-networks.json',{}).get('dstar')) if selected_backend=='hardware' else software_ok
 if selected_ok and (ROOT/'hosts/DCSHosts.txt').exists():result.append('D-STAR')
 for mode in ['FCS']:
  p=PROFILES[mode]
  if (ROOT/p['gateway']/p['gateway']).exists() and (ROOT/'hosts'/((('YSF' if mode=='FCS' else mode))+'Hosts.txt')).exists():result.append(mode)
 return result

def ready(mode):
 if mode=='M17':return bool(__import__('m17_native').status().get('connected'))
 if mode=='P25':return bool(__import__('p25_native').status().get('connected'))
 if mode=='YSF':return bool(__import__('ysf_native').status().get('connected'))
 if mode=='NXDN':return bool(__import__('nxdn_native').status().get('connected'))
 if mode=='DMR':
  import dmr_native
  return bool(dmr_native.status().get('authenticated'))
 return (RUN/('dmr-ready' if mode=='DMR' else 'ready-'+mode)).exists()

def audio(mode):
 import math
 values=load('audio-modes.json',{}).get(mode,load('audio.json',{'receive':1,'transmit':1}))
 if not isinstance(values,dict) or set(values)!={'receive','transmit'} or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not .25<=v<=4 for v in values.values()):return {'receive':1,'transmit':1}
 return values

def request(modes):
 if not set(modes)<=set(PROFILES):raise ValueError('Unsupported digital mode.')
 import codec_selection
 if 'M17' in modes and codec_selection.desired()['backend']=='hardware':raise ValueError('M17 external hardware unsupported; select software')
 if 'P25' in modes and codec_selection.desired()['backend']=='hardware':raise ValueError('P25 Phase 1 external hardware unsupported; select software')
 if 'YSF' in modes and codec_selection.desired()['backend']=='hardware':raise ValueError('YSF V/D2 external hardware unsupported; select software')
 if 'NXDN' in modes and codec_selection.desired()['backend']=='hardware':raise ValueError('NXDN external hardware is unsupported; select software')
 if codec_selection.desired()['backend']=='hardware' and len(set(modes)&{'D-STAR','DMR'})>1:raise ValueError('The external vocoder can serve only one digital mode at a time')
 save('digital-modes.json',list(dict.fromkeys(modes)))

def validate(mode,target,node):
 if not isinstance(target,str) or not target.isascii():raise ValueError('Enter a destination.')
 target=target.strip()
 if mode=='AllStar':
  if not re.fullmatch(r'[0-9]{4,6}',target) or target==node or target in PRIVATE:raise ValueError('Enter a different AllStar node (4–6 digits).')
 elif mode=='EchoLink':
  if not re.fullmatch(r'[0-9]{1,6}',target) or not int(target):raise ValueError('Enter an EchoLink node (1–6 digits).')
 elif mode=='M17':
  target=target.upper()
  from native_m17.protocol import destination
  destination(target)
  if target.rsplit(' ',1)[0] not in {row['target'].rsplit(' ',1)[0] for row in catalog()['M17']}:raise ValueError('M17 destination has no applied reflector endpoint')
 elif mode=='FCS':
  target=target.upper().removeprefix('FCS')
  if not re.fullmatch(r'00[1-5][0-9]{2}',target):raise ValueError('Enter an FCS room such as 00120.')
 elif mode=='D-STAR':
  from dstar_worker import hosts,split_target
  target=target.upper().replace(' ','');reflector,_=split_target(target)
  if reflector not in hosts():raise ValueError('Reflector is not in the installed DCS directory.')
 elif mode in PROFILES:
  if not target.isdigit() or not (0 if mode=='YSF' else 1)<=int(target)<=(65535 if mode=='NXDN' else 99999 if mode=='YSF' else 16777215):raise ValueError('Enter a valid numeric destination.')
  if mode=='YSF':target=target.zfill(5)
  if mode in ('YSF','P25','NXDN') and target not in {row['target'] for row in catalog()[mode]}:raise ValueError('Destination is not in the installed reflector list.')
 else:raise ValueError('Mode is unavailable.')
 return target

def peer(mode,target):
 if mode in PROFILES:return PROFILES[mode]['node']
 return '3'+target.zfill(6) if mode=='EchoLink' else target

def control(mode,message):
 data=message.encode('ascii')
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:sock.sendto(struct.pack('BB',5,len(data))+data,('127.0.0.1',PROFILES[mode]['tlv']))

def tune(mode,target):
 # The gateway commands only select a reflector; they transmit no voice or test tone.
 if mode not in ('YSF','FCS','D-STAR','M17'):control(mode,'txTg='+target)
 if mode in ('YSF','FCS','D-STAR'):
  command=('LinkYSF '+target if mode=='YSF' else 'LinkFCS '+target if mode=='FCS' else 'Link '+target).encode('ascii')
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:sock.sendto(command,('127.0.0.1',PROFILES[mode]['remote']))
 targets=load('digital-targets.json',{});targets[mode]=target;save('digital-targets.json',targets)
 if mode=='DMR':(RUN/'talkgroup').write_text(target)

def unlink(mode):
 if mode=='M17':return # worker shutdown sends DISC to its configured peer
 if mode=='DMR':control(mode,'txTg=9')
 else:
  command=b'UnLink' if mode in ('YSF','FCS','D-STAR') else b'TalkGroup 9999'
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:sock.sendto(command,('127.0.0.1',PROFILES[mode]['remote']))

def bridging():return load('bridge.json',{}).get('enabled',False)

def forwarding(controller,enabled):
 import system_client
 system_client.request('bridge-forwarding',enabled=enabled)
 save('bridge.json',{'enabled':enabled,'connections':[]})

