"""Local ALLMODE simulator. No radio commands or external dependencies."""
import argparse
import json
import re
import threading
import subprocess
import time
import socket
import struct
import math
import os
import setup_api
import digital
import sa818_hardware
import web_auth
import lan_origin
import onboarding
import operator_store
import operator_features
import directory_api
import system_client
import parrot_integration
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs

WEB = Path(__file__).parent / 'web'
MODES = ['AllStar', 'EchoLink', 'DMR', 'YSF', 'NXDN', 'P25', 'M17', 'D-STAR']
AUDIO_FILE = Path('/var/lib/asterisk/allmode/audio.json')


def audio_settings():
    try:
        values = json.loads(AUDIO_FILE.read_text())
        return validate_audio(values)
    except (OSError, ValueError, TypeError):
        return {'receive': 1.0, 'transmit': 1.0}


def validate_audio(values,minimum=0.5,maximum=1.5):
    if not isinstance(values, dict) or set(values) != {'receive', 'transmit'}:
        raise ValueError('Supply receive and transmit gain.')
    for value in values.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f'Audio gains must be between {minimum} and {maximum}.')
    return {key: round(float(value), 2) for key, value in values.items()}


def bridge_control(message):
    data = message.encode('ascii')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(struct.pack('BB', 5, len(data)) + data, ('127.0.0.1', 31100))


class Controller:
    def __init__(self):
        self.lock = threading.RLock()
        self.mode = 'AllStar'
        self.target = None
        self.events = []
        self.record('Simulator started. RF transmission is disabled.')

    def record(self, message):
        self.events.insert(0, {'time': datetime.now(timezone.utc).isoformat(), 'message': message})
        self.events = self.events[:40]

    def snapshot(self):
        return {'simulation': True, 'mode': self.mode, 'target': self.target,
                'connected': self.target is not None, 'transmit_enabled': False,
                'hardware': 'SHARI PiHat / Raspberry Pi 4 â€” design target',
                'modes': MODES, 'events': list(self.events)}

    def command(self, action, value):
        with self.lock:
            if action == 'mode':
                if value not in MODES:
                    raise ValueError('Choose a supported mode.')
                if self.target:
                    raise ValueError('Disconnect before changing modes.')
                self.mode = value
                self.record(f'Selected {value}.')
            elif action == 'connect':
                if self.target:
                    raise ValueError('Disconnect the current destination first.')
                if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _./#-]{0,47}', value):
                    raise ValueError('Enter a destination using letters, numbers, spaces, or _./#-.')
                if self.mode in ['AllStar', 'DMR', 'NXDN', 'P25'] and not value.isascii():
                    raise ValueError('Use an ASCII destination.')
                if self.mode in ['AllStar', 'DMR', 'NXDN', 'P25'] and not value.isdigit():
                    raise ValueError('This mode needs a numeric node, talkgroup, or reflector ID.')
                self.target = value
                self.record(f'Simulated connection: {self.mode} â†’ {value}. No network traffic sent.')
            elif action == 'disconnect':
                self.target = None
                self.record('Disconnected. Node idle.')
            else:
                raise ValueError('Unknown command.')
            return self.snapshot()


class LiveController(Controller):
    def __init__(self, node, controls=False):
        if not re.fullmatch(r'[0-9]{4,10}', node):
            raise ValueError('Invalid local node number')
        super().__init__()
        self.node = node
        self.controls = controls
        self.pending = None
        self.digital_target = None
        self.stages = []
        self.bridge_error = None
        try:
            saved = Path('/var/lib/asterisk/allmode/talkgroup').read_text().strip()
            if saved.isascii() and saved.isdigit() and 1 <= int(saved) <= 16777215:
                self.digital_target = saved
        except OSError:
            pass
        self.events = []
        self.record('Live AllStar controller started. Browser audio is not implemented.')

    def run_cli(self, command):
        result = subprocess.run(['/usr/sbin/asterisk', '-rx', command], capture_output=True, text=True, timeout=4)
        if result.returncode or any(word in result.stdout.lower() for word in ['no such command', 'unable to connect', 'usage:', 'unable to load', 'unable to reload', 'does not support reloading', 'module could not be loaded']):
            raise ValueError('Asterisk command failed')
        return result.stdout

    def snapshot(self):
        output = self.run_cli(f'rpt stats {self.node}')
        if 'STATISTICS' not in output:
            raise ValueError('Asterisk status unavailable')
        fields = {}
        for line in output.splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                fields[key.rstrip('. ')] = value.strip()
        if 'Nodes currently connected to us' not in fields:
            raise ValueError('Unrecognized Asterisk status')
        links = fields['Nodes currently connected to us']
        targets = re.findall(r'\b[0-9]{4,10}\b', links)
        link_stats = self.run_cli(f'rpt lstats {self.node}')
        established = []
        for line in link_stats.splitlines():
            columns = line.split()
            if len(columns) >= 6 and columns[0].isdigit() and columns[-1] == 'ESTABLISHED':
                established.append(columns[0])
        if len(established)==1 and established[0] in digital.PRIVATE:
            self.mode=digital.PRIVATE[established[0]]
        phase = 'connected' if established else 'idle'
        if self.pending:
            action, target, deadline = self.pending
            confirmed = target in established if action == 'connect' else target not in targets
            if confirmed:
                self.record(f'{action.capitalize()} confirmed for {target}.')
                self.pending = None
            elif time.monotonic() > deadline:
                self.record(f'{action.capitalize()} not confirmed for {target}. Check node connectivity.')
                self.pending = None
            else:
                phase = 'connecting' if action == 'connect' else 'disconnecting'
        for stage in list(self.stages):
            if stage['peer'] in established:
                self.record(f"{stage['mode']} radio link confirmed.")
                self.stages.remove(stage)
            elif time.monotonic()>stage['deadline']:
                self.bridge_error=f"{stage['mode']} could not start or connect."
                self.record(self.bridge_error)
                if digital.bridging():self.stop_bridge(targets)
                else:
                    self.run_cli(f"rpt cmd {self.node} ilink 1 {stage['peer']}")
                    digital.request([])
                    self.stages=[]
                break
            elif not stage['sent'] and (stage['mode'] not in digital.PROFILES or digital.ready(stage['mode'])):
                if stage['mode'] in digital.PROFILES and not stage.get('tuned'):
                    digital.tune(stage['mode'],stage['target']);stage['tuned']=True
                if stage['mode']=='D-STAR':
                    status=digital.load('dstar-status.json',{})
                    if not status.get('confirmed') or status.get('target')!=stage['target']:continue
                if stage['mode'] in ('NXDN','YSF','P25','M17'):
                    native=__import__(stage['mode'].lower()+'_native').status()
                    expected=stage['target'] if stage['mode']=='M17' else int(stage['target'])
                    if not native.get('connected') or native.get('target')!=expected:continue
                self.run_cli(f"rpt cmd {self.node} ilink 3 {stage['peer']}")
                stage['sent']=True
        if self.stages:phase='connecting'
        echo_ready = '1 modules loaded' in self.run_cli('module show like chan_echolink.so')
        if established and len(established)==1 and len(established[0])==7 and established[0].startswith('3'):
            self.mode='EchoLink'
        bridge_on=digital.bridging()
        if not bridge_on and '1994' in established and (not digital.ready('D-STAR') or not digital.load('dstar-status.json',{}).get('confirmed')):
            self.run_cli(f'rpt cmd {self.node} ilink 1 1994')
            digital.request([])
            self.bridge_error='D-STAR reflector connection lost. Radio link disconnected.'
            self.record(self.bridge_error)
        if not bridge_on:
            failed=[peer for peer in established if peer in digital.PRIVATE and peer!='1994' and not digital.ready(digital.PRIVATE[peer])]
            for peer in failed:self.run_cli(f'rpt cmd {self.node} ilink 1 {peer}')
            if failed:
                digital.request([]);self.bridge_error='Digital adapter stopped. Radio link disconnected.';self.record(self.bridge_error)
                established=[peer for peer in established if peer not in failed]
                phase='connected' if established else 'idle'
        if bridge_on and any(peer in digital.PRIVATE and (not digital.ready(digital.PRIVATE[peer]) or (digital.PRIVATE[peer]=='D-STAR' and not digital.load('dstar-status.json',{}).get('confirmed'))) for peer in established):
            self.bridge_error='A digital adapter stopped. The bridge has been stopped.'
            self.stop_bridge(targets);bridge_on=False
            self.record(self.bridge_error)
        mode_targets=digital.load('digital-targets.json',{})
        active=[]
        for peer in established:
            mode=digital.PRIVATE.get(peer,'EchoLink' if len(peer)==7 and peer.startswith('3') else 'AllStar')
            target=mode_targets.get(mode,self.digital_target or 'Unknown') if peer in digital.PRIVATE else str(int(peer[1:])) if mode=='EchoLink' else peer
            active.append({'mode':mode,'target':target,'peer':peer,'network_status':digital.load('digital-health.json',{}).get(mode,{}).get('network','Radio link confirmed')})
        if bridge_on:self.mode='Bridge'
        data = super().snapshot()
        digital_ready = Path('/var/lib/asterisk/allmode/dmr-ready').exists()
        data.update(simulation=False, readonly=not self.controls, node=self.node, modes=['AllStar'] + digital.available() + (['EchoLink'] if echo_ready else []),
                    connected=bool(established), target=', '.join(f"{row['mode']} {row['target']}" for row in active) if bridge_on else active[0]['target'] if len(active)==1 else ', '.join(established) or None, targets=targets,
                    digital_ready=digital_ready, echo_ready=echo_ready, dmr_network=digital.load('dmr-networks.json',{}).get('Network','TGIF'),
                    rssi=__import__('radio_readback').snapshot(self.controls),
                    audio=audio_settings(),
                    audio_modes={mode:digital.audio(mode) for mode in digital.PROFILES},
                    phase=phase, pending=bool(self.pending or self.stages), active_connections=active, bridge_enabled=bridge_on, bridge_error=self.bridge_error,
                    unavailable_modes={**({} if 'M17' in digital.available() else {'M17':'Configure and apply M17 reflector/module and host; Codec2 3200 only'}),**({} if 'D-STAR' in digital.available() else {'D-STAR':'D-STAR software adapter is not installed'}),**({} if echo_ready else {'EchoLink':'Enter your EchoLink account in Setup'})}, digital_health=digital.load('digital-health.json',{}),
                    hardware='SHARI / Pi Zero 2 W', system=fields.get('System'),
                    receiving=fields.get('Signal on input') == 'YES')
        return data

    def command(self, action, value):
        with self.lock:
            if not self.controls:
                raise ValueError('Live view is read-only.')
            if action == 'setup':
                return setup_api.save(self, value)
            current = self.snapshot()
            if action == 'bridge':
                return self.start_bridge(value,current)
            if action == 'stop-bridge':
                self.stop_bridge(current['targets']);return self.snapshot()
            if action == 'audio':
                if not isinstance(value,dict):raise ValueError('Choose a digital mode and audio levels.')
                mode=value.get('mode')
                if mode not in digital.PROFILES:raise ValueError('Choose a digital mode.')
                values=validate_audio({key:v for key,v in value.items() if key!='mode'},.25,4)
                settings=digital.load('audio-modes.json',{});settings[mode]=values;digital.save('audio-modes.json',settings)
                if digital.ready(mode):
                    for command in [f"usrpGain={values['receive']}", f"tlvGain={values['transmit']}", 'usrpAudio=AUDIO_USE_GAIN', 'tlvAudio=AUDIO_USE_GAIN']:digital.control(mode,command)
                self.record(f'{mode} audio levels saved'+(' and applied.' if digital.ready(mode) else '; applied on next connection.'))
                return self.snapshot()
            if action == 'mode' and value in current['modes']:
                if current['connected'] or current['pending'] or current['bridge_enabled']:
                    raise ValueError('Disconnect before switching modes.')
                self.mode = value
                return self.snapshot()
            if self.pending or self.stages:
                raise ValueError('Wait for the current request to finish.')
            if action == 'connect':
                if current['targets']:
                    raise ValueError('Disconnect the current link first.')
                if self.mode in digital.PROFILES:
                    target=digital.validate(self.mode,value,self.node)
                    self.bridge_error=None
                    if self.mode=='DMR':self.digital_target=target
                    digital.request(list(dict.fromkeys([self.mode])))
                    self.stages=[dict(mode=self.mode,target=target,peer=digital.peer(self.mode,target),sent=False,deadline=time.monotonic()+60)]
                    return self.snapshot()
                elif self.mode == 'EchoLink':
                    if not current['echo_ready'] or not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,6}',value) or int(value)==0:
                        raise ValueError('Enter an EchoLink node number (1â€“6 digits).')
                    index,target=3,'3'+value.zfill(6)
                elif not isinstance(value, str) or not re.fullmatch(r'[0-9]{4,6}', value) or value in [self.node, *digital.PRIVATE]:
                    raise ValueError('Enter a different AllStar node number (4â€“6 digits).')
                else:
                    index, target = 3, value
            elif action == 'disconnect':
                if current.get('bridge_enabled') or len(current['targets'])>1:
                    self.stop_bridge(current['targets']);return self.snapshot()
                if len(current['targets']) != 1:
                    raise ValueError('Disconnect requires exactly one current link. Manage multiple links through your existing AllStar tools.')
                index, target = 1, current['targets'][0]
                if target in digital.PRIVATE:
                    digital.unlink(digital.PRIVATE[target]);digital.request([])
            else:
                raise ValueError('Unsupported live command.')
            self.run_cli(f'rpt cmd {self.node} ilink {index} {target}')
            self.pending = (action, target, time.monotonic() + 30)
            self.record(f'{action.capitalize()} requested for {target}; waiting for node confirmation.')
            return self.snapshot()


    def stop_bridge(self,targets):
        self.stages=[];self.pending=None
        if digital.bridging():digital.forwarding(self,False)
        for target in targets:self.run_cli(f'rpt cmd {self.node} ilink 1 {target}')
        for mode in digital.load('digital-modes.json',['DMR']):
            if mode in digital.PROFILES:digital.unlink(mode)
        digital.request([]);self.mode='AllStar'
        self.record('Bridge stopped. Cross-network forwarding disabled.')

    def start_bridge(self,value,current):
        if not isinstance(value,dict) or set(value)!={'enabled','connections'} or not isinstance(value['enabled'],bool):raise ValueError('Supply the bridge selection.')
        if not value['enabled']:
            self.stop_bridge(current['targets']);return self.snapshot()
        if current['targets'] or current['pending'] or current.get('receiving'):raise ValueError('Disconnect and wait for the radio to be idle, then start the bridge.')
        rows=value['connections']
        if not isinstance(rows,list) or not 2<=len(rows)<=7:raise ValueError('Select at least two modes with destinations.')
        selected=[];seen=set()
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'mode','target'} or row['mode'] not in current['modes'] or row['mode'] in seen:raise ValueError('Select each available mode once.')
            mode=row['mode'];seen.add(mode);target=digital.validate(mode,row['target'],self.node)
            # Parrots replay received audio and cannot participate in a live cross-network bridge.
            if (mode in ('P25','NXDN') and target=='10') or (mode=='YSF' and target=='99999'):raise ValueError('Local echo tests cannot be included in a live bridge.')
            selected.append(dict(mode=mode,target=target,peer=digital.peer(mode,target),sent=False,deadline=time.monotonic()+60))
        digital.forwarding(self,True)
        digital.save('bridge.json',{'enabled':True,'connections':rows})
        digital.request(list(dict.fromkeys(['DMR']+[r['mode'] for r in selected if r['mode'] in digital.PROFILES])))
        self.stages=selected;self.bridge_error=None
        self.record('Starting selected cross-network bridge.')
        return self.snapshot()


def connect_destination(controller, mode, value, timeout=30, allow_bridge=False, network=None, source_id=None):
    """Validate first, then break the old link before making the new one."""
    with controller.lock:
        current=controller.snapshot()
        if current.get('simulation'):
            if allow_bridge:raise ValueError('Bridging requires a managed live station.')
            controller.command('mode',mode)
            return controller.command('connect',value)
        quick=mode in ('YSF','NXDN','P25','M17')
        if not quick and mode not in current.get('modes',[]):raise ValueError('This network is not available.')
        if current.get('readonly'):raise ValueError('Connection controls are unavailable.')
        if current.get('pending'):raise ValueError('Wait for the current request to finish.')
        if quick:
            system_client.request('digital-prepare',mode=mode,target=value,source_id=source_id,check=True)
        elif mode in digital.PROFILES:
            digital.validate(mode,value,controller.node)
        elif mode=='EchoLink':
            if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,6}',value) or int(value)==0:raise ValueError('Enter an EchoLink node number (1-6 digits).')
        elif not isinstance(value,str) or not re.fullmatch(r'[0-9]{4,6}',value) or value in [controller.node,*digital.PRIVATE]:
            raise ValueError('Enter a different AllStar node number (4-6 digits).')
        if mode=='DMR' and network is not None:
            system_client.request('dmr-network',network=network,check=True)
        if type(allow_bridge) is not bool:raise ValueError('Bridge permission must be true or false.')
        if allow_bridge:
            value=digital.validate(mode,value,controller.node)
            rows=current.get('active_connections',[])
            if any(r['mode']==mode and r['target']==value for r in rows):return current
            if mode in digital.PROFILES and any(r['mode']==mode for r in rows):raise ValueError('Only one destination per digital mode can be bridged. Uncheck bridging to replace it.')
            if len(rows)>=7:raise ValueError('Maximum seven bridge connections.')
            if any((r['mode'] in ('P25','NXDN') and r['target']=='10') or (r['mode']=='YSF' and r['target']=='99999') for r in rows+[{'mode':mode,'target':value}]):raise ValueError('Echo test destinations cannot be bridged.')
            modes=list(dict.fromkeys([r['mode'] for r in rows if r['mode'] in digital.PROFILES]+([mode] if mode in digital.PROFILES else [])))
            if mode=='DMR' and network is not None:
                system_client.request('dmr-network',network=network)
            if quick:system_client.request('digital-prepare',mode=mode,target=value,source_id=source_id)
            digital.request(modes)
            try:digital.forwarding(controller,True)
            except Exception:
                digital.request([r['mode'] for r in rows if r['mode'] in digital.PROFILES]);raise
            digital.save('bridge.json',{'enabled':True,'connections':[{'mode':r['mode'],'target':r['target']} for r in rows]+[{'mode':mode,'target':value}]})
            controller.stages=[dict(mode=mode,target=value,peer=digital.peer(mode,value),sent=False,deadline=time.monotonic()+60)]
            controller.bridge_error=None
            controller.record('Adding '+mode+' '+value+' with explicitly enabled link-to-link bridging.')
            return controller.snapshot()
        if current.get('connected') or current.get('targets') or current.get('bridge_enabled'):
            if hasattr(controller,'stop_bridge'):
                controller.stop_bridge(current.get('targets',[]))
            else:controller.command('disconnect',None)
            deadline=time.monotonic()+timeout
            while True:
                current=controller.snapshot()
                if not (current.get('connected') or current.get('targets') or current.get('pending') or current.get('bridge_enabled')):break
                if time.monotonic()>=deadline:raise ValueError('Previous connection has not disconnected yet. New connection was not started; retry shortly.')
                time.sleep(.25)
        if mode=='DMR' and network is not None:
            deadline=time.monotonic()+timeout
            while __import__('dmr_native').status().get('state') not in ('stopped',None):
                if time.monotonic()>=deadline:raise ValueError('DMR is still stopping; retry shortly.')
                time.sleep(.25)
            system_client.request('dmr-network',network=network)
        if quick:
            deadline=time.monotonic()+timeout
            while __import__(mode.lower()+'_native').status().get('state') not in ('stopped',None):
                if time.monotonic()>=deadline:raise ValueError(mode+' is still stopping; retry shortly.')
                time.sleep(.25)
            system_client.request('digital-prepare',mode=mode,target=value,source_id=source_id)
        controller.command('mode',mode)
        return controller.command('connect',value)


class ManagedController(LiveController):
    """Live controller stays available while the radio is stopped for maintenance."""
    def __init__(self):
        super().__init__('1990',False)
    def run_cli(self,command):
        return system_client.request('cli',command=command)['output']
    def snapshot(self):
        state=system_client.status()
        self.node=state.get('node') or '1990';self.controls=bool(state.get('radio_enabled'))
        if not state.get('active'):
            data=Controller.snapshot(self)
            data['rssi']=__import__('radio_readback').snapshot(False)
            data.update(simulation=False,readonly=True,node=self.node,modes=[],connected=False,target=None,
                        system='Maintenance â€” radio services stopped',unavailable_modes={},runtime=state)
            return data
        data=super().snapshot();data['runtime']=state
        data['transmit_enabled']=self.controls
        data['hardware']='SHARI HAT / Raspberry Pi'
        data['bridge_supported']=True
        data['quick_connect_modes']=[m for m in ('YSF','NXDN','P25','M17') if __import__(m.lower()+'_native').installed()]
        remembered=digital.load('digital-quick-identities.json',{})
        data['digital_source_ids']={m:digital.load(m.lower()+'-native.json',{}).get('source') or remembered.get(m,{}).get('id','') for m in ('NXDN','P25')}
        data['audio_modes']={mode:value for mode,value in data['audio_modes'].items() if mode in data['modes']}
        for mode in MODES:
            if mode not in data['modes']:
                data['unavailable_modes'][mode]=('Enter, apply and test external AMBE settings in Guided setup' if mode=='D-STAR' else
                    'Enter and apply your validated account in Guided setup' if mode=='EchoLink' else 'Adapter dependencies or account configuration are not ready')
        return data
    def command(self,action,value):
        if action in ('setup','bridge','stop-bridge'):
            raise ValueError('Use guided setup. Cross-network bridging is not enabled on this appliance.')
        self.snapshot()
        return super().command(action,value)


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            self.get_request()
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self.reply(503, {'error': 'Station data unavailable. Check the system service and retry.'})

    def get_request(self):
        path = urlparse(self.path).path
        auth = getattr(self.server, 'auth', None)
        if auth and auth.unclaimed:
            if path=='/api/claim':
                self.reply(200,{'unclaimed':True});return
            if path not in ('/setup','/claim.js','/operator.css','/login','/login.js','/hardware.css'):
                self.send_response(303);self.send_header('Location','/setup');self.send_header('Content-Length','0');self.end_headers();return
            if path in ('/setup','/operator.css','/claim.js'):
                name={'/setup':'claim.html','/operator.css':'operator.css','/claim.js':'claim.js'}[path]
                body=(WEB/name).read_bytes();self.send_response(200)
                self.send_header('Content-Type',{'html':'text/html','css':'text/css','js':'text/javascript'}[name.split('.')[-1]]+'; charset=utf-8')
                self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body);return
        if auth and path not in ('/login', '/login.js', '/hardware.css','/operator.css') and not auth.valid(self):
            if path.startswith('/api/'):
                self.reply(401, {'error':'Sign in required.'})
            else:
                self.send_response(303)
                self.send_header('Location','/login')
                self.send_header('Content-Length','0')
                self.end_headers()
            return
        if parrot_integration.get(self,path):return
        if path.startswith('/allmode/'):
            path = path[len('/allmode'):]
        if path == '/api/hardware':
            self.reply(200, self.server.hardware.snapshot())
            return
        if path == '/api/onboarding':
            result=self.server.onboarding.snapshot()
            result['complete']=operator_store.completed(self.server.onboarding)
            self.reply(200,result)
            return
        if path == '/api/profiles':
            self.reply(200,operator_store.profiles(self.server.onboarding));return
        if path == '/api/features':
            if not hasattr(self.server,'features'):self.server.features=operator_features.Features(self.server.onboarding.path.parent,self.server.controller)
            self.reply(200,self.server.features.snapshot());return
        if path == '/api/network':
            try:self.reply(200,system_client.request('network-status'))
            except (OSError,ValueError,AttributeError):self.reply(503,{'error':'Network interface status is available on the Pi.'})
            return
        if path == '/api/digital-identities':
            self.reply(200,system_client.request('digital-identities'));return
        if path == '/api/directory':
            try:self.reply(200,directory_api.directory(self.server.onboarding.path.parent,parse_qs(urlparse(self.path).query).get('source',['AllStar'])[0]))
            except ValueError as error:self.reply(400,{'error':str(error)})
            return
        if path == '/api/system':
            self.reply(200,system_client.status());return
        if path == '/api/destinations':
            self.reply(200,digital.catalog());return
        if path == '/api/setup':
            try:
                if isinstance(self.server.controller,ManagedController):
                    self.reply(200,{'groups':[],'system':{'Setup':'Open Guided setup to apply station settings.'},'radio':{}})
                elif not isinstance(self.server.controller, LiveController):
                    self.reply(200, {'groups': [], 'system': {'Mode': 'Simulation'}, 'radio': {}})
                else:
                    with self.server.controller.lock:
                        self.reply(200, setup_api.snapshot(self.server.controller))
            except (OSError, ValueError, subprocess.TimeoutExpired):
                self.reply(503, {'error': 'Setup data unavailable'})
            return
        if path == '/api/status':
            try:
                with self.server.controller.lock:
                    self.reply(200, self.server.controller.snapshot())
            except (ValueError, subprocess.TimeoutExpired):
                self.reply(503, {'error': 'Asterisk status unavailable'})
            return
        names = {'/station.css':'station.css','/station.js':'station.js','/': 'index.html', '/style.css': 'style.css', '/app.js': 'app.js', '/hardware': 'hardware.html', '/hardware.js': 'hardware.js', '/hardware.css': 'hardware.css'}
        names.update({'/login':'login.html','/login.js':'login.js'})
        names.update({'/setup':'first-run.html','/first-run.js':'first-run.js'})
        names.update({p:'operator.html' for p in ('/','/settings','/setup','/connections','/logs','/profiles','/network','/admin','/schedules','/airtime')})
        names.update({'/operator.js':'operator.js','/operator.css':'operator.css'})
        if path not in names:
            self.reply(404, {'error': 'Not found'})
            return
        file = WEB / names[path]
        data = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html', 'css': 'text/css', 'js': 'text/javascript'}[file.suffix[1:]] + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        # A local browser may mutate only from this server's origin.
        origin = self.headers.get('Origin')
        expected = getattr(self.server, 'public_origin', None) or 'http://' + self.headers.get('Host', '')
        same_origin = (lan_origin.allowed(self, getattr(self.server, 'public_origin', None))
                       if getattr(self.server, 'lan_proxy', False) else origin in expected.split(','))
        if not same_origin:
            self.reply(403, {'error': 'Same-origin browser access required.'})
            return
        auth = getattr(self.server, 'auth', None)
        if auth and auth.unclaimed and self.path=='/api/claim':
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1024 or self.headers.get('Content-Type')!='application/json':raise ValueError('Invalid request.')
                data=json.loads(self.rfile.read(size));auth.claim(data.get('password'))
                self.reply(200,{'ok':True})
            except (ValueError,TypeError,AttributeError):self.reply(400,{'error':'Choose an owner password of 4-128 characters. This station can only be claimed once.'})
            except OSError:self.reply(503,{'error':'Owner setup could not be saved. Check system service and storage, then retry.'})
            return
        if auth and self.path == '/login':
            auth.login(self)
            return
        if auth and not auth.valid(self):
            self.reply(401, {'error':'Sign in required.'})
            return
        if auth and self.path == '/logout':
            auth.logout(self)
            return
        if parrot_integration.post(self,self.path):return
        if self.path not in ['/api/command', '/allmode/api/command', '/api/hardware', '/allmode/api/hardware', '/api/onboarding','/api/system','/api/settings','/api/finish','/api/profiles','/api/password','/api/features']:
            self.reply(404, {'error': 'Not found'})
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8192:
                raise ValueError('Invalid request size.')
            if self.headers.get('Content-Type') != 'application/json':
                raise ValueError('JSON required.')
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError('Expected a JSON object.')
            if self.path == '/api/features':
                if not hasattr(self.server,'features'):self.server.features=operator_features.Features(self.server.onboarding.path.parent,self.server.controller)
                self.reply(200,self.server.features.action(payload))
            elif self.path == '/api/settings':
                self.reply(200,operator_store.update_group(self.server.onboarding,payload.get('group'),payload.get('values')))
            elif self.path == '/api/finish':
                self.reply(200,operator_store.finish(self.server.onboarding))
            elif self.path == '/api/profiles':
                self.reply(200,operator_store.profiles(self.server.onboarding,payload))
            elif self.path == '/api/password':
                if not auth:raise ValueError('Password changes are unavailable in this local preview.')
                auth.change(payload.get('current',''),payload.get('password',''))
                self.reply(200,{'ok':True,'message':'Password changed. Sign in again.'})
            elif self.path == '/api/system':
                action=payload.get('action')
                if action not in ('apply','activate','maintenance','audio','audio-confirm','test-ambe','wifi-scan','wifi-save','wifi-connect','digital-identities-save'):raise ValueError('Unknown system action.')
                if action in ('apply','test-ambe'):
                    result=system_client.request(action,config=self.server.onboarding.read())
                elif action=='activate':
                    from system_service import fingerprint
                    result=system_client.request(action,confirm=payload.get('confirm'),fingerprint=fingerprint(self.server.onboarding.read()))
                elif action=='audio':result=system_client.request(action,levels=payload.get('levels'))
                elif action=='audio-confirm':result=system_client.request(action,checked=payload.get('checked'))
                elif action=='wifi-save':result=system_client.request(action,ssid=payload.get('ssid'),password=payload.get('password'))
                elif action=='digital-identities-save':result=system_client.request(action,values=payload.get('values'))
                elif action=='wifi-connect':result=system_client.request(action,id=payload.get('id'))
                else:result=system_client.request(action)
                self.reply(200,result)
            elif self.path == '/api/onboarding':
                if payload == {'action':'skip-audio'}:
                    result=operator_store.skip_audio(self.server.onboarding)
                elif set(payload)=={'section','values'}:
                    result=self.server.onboarding.save_section(payload['section'],payload['values'])
                else:
                    result=self.server.onboarding.save(payload)
                self.reply(200,result)
            elif self.path.endswith('/api/hardware'):
                self.reply(200, self.server.hardware.action(payload))
            else:
                controller=self.server.controller
                with controller.lock:
                    if payload.get('action')=='connect-network':
                        result=connect_destination(controller,payload.get('mode'),payload.get('value'),allow_bridge=payload.get('allow_bridge',False),network=payload.get('network'),source_id=payload.get('source_id'))
                    else:result=controller.command(payload.get('action'),payload.get('value'))
                    self.reply(200,result)
        except (ValueError, TypeError, subprocess.TimeoutExpired) as error:
            self.reply(400, {'error': str(error)})
        except (OSError, ImportError):
            self.reply(503, {'error': 'Could not save settings or contact the bridge.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--live-node', help='Read-only local Asterisk node status')
    parser.add_argument('--enable-controls', action='store_true')
    parser.add_argument('--public-origin')
    parser.add_argument('--lan-proxy', action='store_true',
                        help='Trust loopback HTTPS proxy; allow current local IPv4 and configured names')
    parser.add_argument('--hardware', action='store_true', help='Enable SA818 commissioning with radio services stopped')
    parser.add_argument('--auth-file', help='Password hash file; use behind TLS reverse proxy')
    parser.add_argument('--managed',action='store_true',help='Use local system service for live node management')
    args = parser.parse_args()
    if args.hardware and args.live_node:
        parser.error('Hardware commissioning requires a separate maintenance session, without --live-node.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.public_origin = args.public_origin
    server.lan_proxy = args.lan_proxy
    server.auth = web_auth.Auth(args.auth_file) if args.auth_file else None
    server.onboarding = onboarding.Onboarding(managed=args.managed)
    server.hardware = sa818_hardware.Hardware(enabled=args.hardware)
    if args.hardware:
        server.public_origin = args.public_origin or f'http://127.0.0.1:{args.port}'
    if args.enable_controls and not args.public_origin:
        parser.error('Live controls require a fixed public origin and authenticated reverse proxy')
    server.controller = ManagedController() if args.managed else LiveController(args.live_node, args.enable_controls) if args.live_node else Controller()
    server.features=operator_features.Features(server.onboarding.path.parent,server.controller)
    stop_monitor=threading.Event()
    def monitor():
        while not stop_monitor.wait(2):
            parrot_integration.tick()
            try:server.features.tick()
            except (OSError,ValueError,subprocess.TimeoutExpired):pass
            if isinstance(server.controller,LiveController):
                try:
                    with server.controller.lock:
                        if server.controller.stages or server.controller.pending or digital.bridging() or server.controller.mode in digital.PROFILES:server.controller.snapshot()
                except (OSError,ValueError,subprocess.TimeoutExpired):pass
    threading.Thread(target=monitor,daemon=True).start()
    print(f'ALLMODE {"managed live controller" if args.managed else "live controller" if args.live_node else "preview"}: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        parrot_integration.close()
        stop_monitor.set()
        server.server_close()


if __name__ == '__main__':
    main()
