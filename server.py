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
import onboarding
import system_client
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

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
        self.lock = threading.Lock()
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
                    rssi=__import__('radio_readback').snapshot(),
                    audio=audio_settings(),
                    audio_modes={mode:digital.audio(mode) for mode in digital.PROFILES},
                    phase=phase, pending=bool(self.pending or self.stages), active_connections=active, bridge_enabled=bridge_on, bridge_error=self.bridge_error,
                    unavailable_modes={'M17':'M17 audio adapter is not installed',**({} if 'D-STAR' in digital.available() else {'D-STAR':'D-STAR software adapter is not installed'}),**({} if echo_ready else {'EchoLink':'Enter your EchoLink account in Setup'})}, digital_health=digital.load('digital-health.json',{}),
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
            data.update(simulation=False,readonly=True,node=self.node,modes=[],connected=False,target=None,
                        system='Maintenance â€” radio services stopped',unavailable_modes={},runtime=state)
            return data
        data=super().snapshot();data['runtime']=state
        data['transmit_enabled']=self.controls
        data['hardware']='SHARI HAT / Raspberry Pi'
        data['bridge_supported']=False
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
        path = urlparse(self.path).path
        auth = getattr(self.server, 'auth', None)
        if auth and path not in ('/login', '/login.js', '/hardware.css') and not auth.valid(self):
            if path.startswith('/api/'):
                self.reply(401, {'error':'Sign in required.'})
            else:
                self.send_response(303)
                self.send_header('Location','/login')
                self.send_header('Content-Length','0')
                self.end_headers()
            return
        if path.startswith('/allmode/'):
            path = path[len('/allmode'):]
        if path == '/api/hardware':
            self.reply(200, self.server.hardware.snapshot())
            return
        if path == '/api/onboarding':
            self.reply(200, self.server.onboarding.snapshot())
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
        if origin not in expected.split(','):
            self.reply(403, {'error': 'Same-origin browser access required.'})
            return
        auth = getattr(self.server, 'auth', None)
        if auth and self.path == '/login':
            auth.login(self)
            return
        if auth and not auth.valid(self):
            self.reply(401, {'error':'Sign in required.'})
            return
        if auth and self.path == '/logout':
            auth.logout(self)
            return
        if self.path not in ['/api/command', '/allmode/api/command', '/api/hardware', '/allmode/api/hardware', '/api/onboarding','/api/system']:
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
            if self.path == '/api/system':
                action=payload.get('action')
                if action not in ('apply','activate','maintenance','audio','audio-confirm','test-ambe'):raise ValueError('Unknown system action.')
                if action in ('apply','test-ambe'):
                    result=system_client.request(action,config=self.server.onboarding.read())
                elif action=='activate':
                    from system_service import fingerprint
                    result=system_client.request(action,confirm=payload.get('confirm'),fingerprint=fingerprint(self.server.onboarding.read()))
                elif action=='audio':result=system_client.request(action,levels=payload.get('levels'))
                elif action=='audio-confirm':result=system_client.request(action,checked=payload.get('checked'))
                else:result=system_client.request(action)
                self.reply(200,result)
            elif self.path == '/api/onboarding':
                if set(payload)=={'section','values'}:
                    result=self.server.onboarding.save_section(payload['section'],payload['values'])
                else:
                    result=self.server.onboarding.save(payload)
                self.reply(200,result)
            elif self.path.endswith('/api/hardware'):
                self.reply(200, self.server.hardware.action(payload))
            else:
                self.reply(200, self.server.controller.command(payload.get('action'), payload.get('value')))
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
    parser.add_argument('--hardware', action='store_true', help='Enable SA818 commissioning with radio services stopped')
    parser.add_argument('--auth-file', help='Password hash file; use behind TLS reverse proxy')
    parser.add_argument('--managed',action='store_true',help='Use local system service for live node management')
    args = parser.parse_args()
    if args.hardware and args.live_node:
        parser.error('Hardware commissioning requires a separate maintenance session, without --live-node.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.public_origin = args.public_origin
    server.auth = web_auth.Auth(args.auth_file) if args.auth_file else None
    server.onboarding = onboarding.Onboarding(managed=args.managed)
    server.hardware = sa818_hardware.Hardware(enabled=args.hardware)
    if args.hardware:
        server.public_origin = args.public_origin or f'http://127.0.0.1:{args.port}'
    if args.enable_controls and not args.public_origin:
        parser.error('Live controls require a fixed public origin and authenticated reverse proxy')
    server.controller = ManagedController() if args.managed else LiveController(args.live_node, args.enable_controls) if args.live_node else Controller()
    stop_monitor=threading.Event()
    def monitor():
        while not stop_monitor.wait(2):
            if isinstance(server.controller,LiveController):
                try:
                    with server.controller.lock:
                        if server.controller.stages or server.controller.pending or digital.bridging() or server.controller.mode=='D-STAR':server.controller.snapshot()
                except (OSError,ValueError,subprocess.TimeoutExpired):pass
    threading.Thread(target=monitor,daemon=True).start()
    print(f'ALLMODE {"managed live controller" if args.managed else "live controller" if args.live_node else "preview"}: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_monitor.set()
        server.server_close()


if __name__ == '__main__':
    main()
