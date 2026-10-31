"""Supervise independent digital adapters. Starts voice paths only on console request."""
import configparser, json, os, signal, subprocess, time, socket, threading, re
from pathlib import Path
import digital
ROOT=digital.ROOT
RUN=digital.RUN

def gateway_command(data):
    match=re.fullmatch(rb'TalkGroup\s*([0-9]{1,8})\x00?',data)
    return b'TalkGroup '+match[1] if match else None


def ini(path):
    c=configparser.ConfigParser(interpolation=None,inline_comment_prefixes=(';',),strict=False);c.optionxform=str
    text=path.read_text();c.read_string(text[text.find('['):]);return c


def put(c,section,**values):
    if not c.has_section(section):c.add_section(section)
    for key,value in values.items():c.set(section,key,str(value))


def output(c,path):
    with path.open('w') as file:c.write(file,space_around_delimiters=False)
    path.chmod(0o600);return str(path)


class Adapter:
    def __init__(self,mode):
        self.mode=mode;self.p=digital.PROFILES[mode];self.children=[];self.logs=[]
        self.ready=RUN/('dmr-ready' if mode=='DMR' else 'ready-'+mode);self.ready.unlink(missing_ok=True)
        self.directory=RUN/mode;self.directory.mkdir(exist_ok=True)
        self.started=time.monotonic();self.initialised=False;self.authenticated=False
        self.relay_stop=threading.Event();self.relay_thread=None;self.relay_socket=None
    def start(self):
        mode,p=self.mode,self.p
        if mode=='D-STAR':
            self.launch('analog',['python3','-u','/opt/allmode/dstar_worker.py'],dict(os.environ))
            return
        if mode=='M17':
            self.launch('analog',['python3','-u','/opt/allmode/native_m17/worker.py'],dict(os.environ))
            return
        if mode=='P25':
            self.launch('analog',['python3','-u','/opt/allmode/native_p25/worker.py'],dict(os.environ))
            return
        if mode=='YSF':
            self.launch('analog',['python3','-u','/opt/allmode/native_ysf/worker.py'],dict(os.environ))
            return
        if mode=='NXDN':
            self.launch('analog',['python3','-u','/opt/allmode/native_nxdn/worker.py'],dict(os.environ))
            return
        if mode=='DMR':
            self.launch('analog',['python3','-u','/opt/allmode/native_dmr/worker.py'],dict(os.environ))
            return
        mb=ini(ROOT/'MMDVM_Bridge/allmode-tgif.ini')
        account=digital.load('dmr-networks.json',{})
        self.dmr_network=account.get('Network','TGIF')
        if mode=='DMR' and account:
            master=account.get('Master','3104')
            if self.dmr_network not in ('TGIF','BrandMeister') or master not in ('3102','3103','3104'):raise ValueError('Invalid DMR network configuration')
            address=master+'.master.brandmeister.network' if self.dmr_network=='BrandMeister' else 'tgif.network'
            password=account.get('BMPassword' if self.dmr_network=='BrandMeister' else 'TGIFPassword','')
            if not password:raise ValueError('Selected DMR network password is missing')
            put(mb,'DMR Network',Address=address,Port=62031,Password=password,Options='')
        for section in ('D-Star','DMR','System Fusion','P25','NXDN','D-Star Network','DMR Network','System Fusion Network','P25 Network','NXDN Network'):put(mb,section,Enable=0)
        section={'DMR':'DMR','YSF':'System Fusion','FCS':'System Fusion','P25':'P25','NXDN':'NXDN'}[mode]
        put(mb,section,Enable=1);put(mb,section+' Network',Enable=1)
        put(mb,'Log',DisplayLevel=3,FileLevel=0)
        call=mb.get('General','Callsign');dmrid=int(mb.get('General','Id'))//100
        if mode=='FCS':put(mb,'System Fusion Network',LocalPort=3201,GatewayPort=4201)
        if mode=='NXDN':put(mb,'NXDN',Id=179)
        dv=ini(ROOT/'MMDVM_Bridge/DVSwitch.ini')
        dvsection='YSF' if mode=='FCS' else mode
        put(dv,dvsection,address='127.0.0.1',txPort=p['tlv'],rxPort=p['mb'])
        if mode=='NXDN':
            put(dv,'NXDN',fallbackID=dmrid,nxdnFallbackID=179,RemotePort=p['remote'])
            dv.remove_option('NXDN','translate')
        if mode in ('YSF','FCS'):put(dv,'YSF',fallbackID=dmrid,RemotePort=p['remote'])
        if mode in ('P25','NXDN'):
            # Packaged MMDVM emits "TalkGroup10"; gateways require "TalkGroup 10".
            put(dv,mode,RemotePort=p['remote']+100)
            self.start_control_relay()
        ab=ini(ROOT/'analog-test.ini')
        put(ab,'GENERAL',useEmulator='true' if 'codec' in p else 'false',pcmPort=2222+int(p['node'])-1995,transferRootDir=str(self.directory))
        if 'codec' in p:put(ab,'GENERAL',emulatorAddress='127.0.0.1:'+str(p['codec']))
        target=str(digital.load('digital-targets.json',{}).get(mode,'9'))
        if not target.isascii() or not target.isdigit() or not 1<=int(target)<=16777215:target='9'
        put(ab,'AMBE_AUDIO',address='127.0.0.1',txPort=p['mb'],rxPort=p['tlv'],ambeMode=p['format'],gatewayDmrId=179 if mode=='NXDN' else dmrid,repeaterID=17900 if mode=='NXDN' else mb.get('General','Id'),txTg=9 if mode in ('YSF','FCS') else target,txTs=2)
        put(ab,'USRP',address='127.0.0.1',txPort=p['tx'],rxPort=p['rx'])
        dvfile=output(dv,self.directory/'DVSwitch.ini')
        env=dict(os.environ,DVSWITCH=dvfile)
        if mode!='DMR':
            gateway=p['gateway'];gw=ini(ROOT/gateway/(gateway+'.ini'))
            put(gw,'General',Callsign=call,Daemon=0)
            put(gw,'Log',DisplayLevel=2,FileLevel=0,FilePath=str(self.directory))
            put(gw,'Voice',Enabled=0)
            put(gw,'Network',InactivityTimeout=0)
            gw.remove_option('Network','Startup')
            put(gw,'Remote Commands',Enable=1,Port=p['remote'])
            radio=digital.load('radio.json',{})
            rf_frequency=int(float(radio.get('frequency',0))*1000000) or 1
            for sec in ('Info',):
                if gw.has_section(sec):put(gw,sec,RXFrequency=rf_frequency,TXFrequency=rf_frequency,Latitude=0,Longitude=0,Location='ALLMODE',Description='Analog gateway - RF frequency unset' if rf_frequency==1 else 'Analog gateway')
            if mode in ('YSF','FCS'):
                put(gw,'General',Id=dmrid)
                put(gw,'YSF Network',Enable=1 if mode=='YSF' else 0,Hosts=str(ROOT/'hosts/YSFHosts.txt'),Port=42000 if mode=='YSF' else 42002)
                put(gw,'FCS Network',Enable=1 if mode=='FCS' else 0,Rooms=str(ROOT/'hosts/FCSRooms.txt'),Port=42001 if mode=='YSF' else 42003)
                if mode=='FCS':put(gw,'General',RptPort=3201,LocalPort=4201)
            else:
                put(gw,'Network',HostsFile1=str(ROOT/'hosts'/(mode+'Hosts.txt')),HostsFile2=str(ROOT/'hosts/empty.txt'))
            if mode!='FCS':
                parrot={'YSF':'YSFParrot','P25':'P25Parrot','NXDN':'NXDNParrot'}[mode]
                port={'YSF':42012,'P25':42011,'NXDN':42021}[mode]
                self.launch('parrot',[str(ROOT/parrot/parrot),str(port)],env)
            self.launch('gateway',[str(ROOT/gateway/gateway),output(gw,self.directory/'gateway.ini')],env)
        if 'codec' in p:self.launch('codec',[str(ROOT/'md380-emu/qemu-arm-static'),str(ROOT/'md380-emu/md380-emu'),'-S',str(p['codec'])],env)
        self.launch('mmdvm',[str(ROOT/'MMDVM_Bridge/MMDVM_Bridge'),output(mb,self.directory/'mmdvm.ini')],env)
        self.launch('analog',[str(ROOT/'Analog_Bridge/Analog_Bridge'),output(ab,self.directory/'analog.ini')],env)
    def launch(self,name,command,env):
        path=self.directory/(name+'.log');fd=os.open(path,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600);log=os.fdopen(fd,'w');self.logs.append(log)
        self.children.append(subprocess.Popen(['stdbuf','-oL']+command,cwd=self.directory,env=env,stdout=log,stderr=log))
        time.sleep(.5)
    def start_control_relay(self):
        self.relay_socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.relay_socket.bind(('127.0.0.1',self.p['remote']+100));self.relay_socket.settimeout(.2)
        def relay():
            while not self.relay_stop.is_set():
                try:data,_=self.relay_socket.recvfrom(128)
                except socket.timeout:continue
                command=gateway_command(data)
                if command:self.relay_socket.sendto(command,('127.0.0.1',self.p['remote']))
        self.relay_thread=threading.Thread(target=relay,daemon=True);self.relay_thread.start()
    def check(self):
        alive=all(c.poll() is None for c in self.children) and (self.relay_thread is None or self.relay_thread.is_alive())
        try:text=(self.directory/'analog.log').read_text(errors='replace')[-16000:]
        except OSError:text=''
        self.initialised=self.initialised or 'Starting USRP' in text
        if self.mode=='DMR':
            import dmr_native
            self.authenticated=bool(dmr_native.status().get('authenticated'))
            success=text.rfind('login success');failure=max(text.rfind('login failed'),text.rfind('connection lost'))
            if max(success,failure)>=0:self.authenticated=success>failure
        usable=alive and self.initialised and (self.mode!='DMR' or self.authenticated)
        if self.mode=='NXDN':usable=alive and bool(__import__('nxdn_native').status().get('connected'))
        if self.mode=='YSF':usable=alive and bool(__import__('ysf_native').status().get('connected'))
        if self.mode=='P25':usable=alive and bool(__import__('p25_native').status().get('connected'))
        if self.mode=='M17':usable=alive and bool(__import__('m17_native').status().get('connected'))
        if usable:self.ready.touch()
        else:self.ready.unlink(missing_ok=True)
        return alive
    def network_status(self):
        if self.mode=='M17':
            s=__import__('m17_native').status()
            return 'M17 3200 reflector ACK confirmed; interoperability unverified' if s.get('connected') else s.get('note') or s.get('state','stopped')
        if self.mode=='P25':
            s=__import__('p25_native').status()
            return 'P25 Phase 1 poll response confirmed; interoperability unverified' if s.get('connected') else s.get('note') or s.get('state','stopped')
        if self.mode=='YSF':
            s=__import__('ysf_native').status()
            return 'YSF V/D2 poll response confirmed; interoperability unverified' if s.get('connected') else s.get('note') or s.get('state','stopped')
        if self.mode=='NXDN':
            s=__import__('nxdn_native').status()
            return 'NXDN poll response confirmed; interoperability unverified' if s.get('connected') else s.get('note') or s.get('state','stopped')
        if self.mode=='D-STAR':return digital.load('dstar-status.json',{}).get('network','Waiting for reflector selection')
        if self.mode=='DMR':
            import dmr_native
            s=dmr_native.status()
            return s.get('network','DMR')+' login confirmed' if s.get('authenticated') else s.get('note') or s.get('state','stopped')
        try:text=(self.directory/'gateway.log').read_text(errors='replace')[-4000:]
        except OSError:text=''
        for line in reversed(text.splitlines()):
            if any(word in line for word in ('Unlinked','Disconnect by remote','Link has failed')):return 'Unlinked'
            if 'Linked to reflector' in line or 'Switched to reflector' in line:return 'Reflector selected; voice not verified'
            if 'Linked to ' in line:return 'Reflector handshake confirmed'
            if 'Connect by remote' in line:return 'Reflector selected; voice not verified'
        return 'Waiting for reflector selection'
    def stop(self):
        self.ready.unlink(missing_ok=True)
        self.relay_stop.set()
        if self.relay_thread:self.relay_thread.join(timeout=1)
        if self.relay_socket:self.relay_socket.close()
        for c in self.children:
            if c.poll() is None:c.terminate()
        for c in self.children:
            try:c.wait(timeout=3)
            except subprocess.TimeoutExpired:c.kill();c.wait()
        for log in self.logs:log.close()


def main():
    RUN.mkdir(exist_ok=True);adapters={};errors={};last_codec_request=None
    def stop(*_):raise SystemExit()
    signal.signal(signal.SIGTERM,stop)
    restart=RUN/'restart-dmr';restart.unlink(missing_ok=True)
    try:
        while True:
            desired=digital.load('digital-modes.json',[])
            if not isinstance(desired,list) or not set(desired)<=set(digital.PROFILES):desired=[]
            import codec_selection
            request_id=codec_selection.desired()['id']
            if request_id!=last_codec_request:errors.pop('DMR',None);errors.pop('NXDN',None);errors.pop('YSF',None);errors.pop('P25',None);errors.pop('M17',None);last_codec_request=request_id
            if restart.exists():
                errors.pop('DMR',None)
                restart.unlink(missing_ok=True)
                if 'DMR' in adapters:adapters.pop('DMR').stop()
            desired=[mode for mode in desired if mode in digital.available()]
            for mode in list(errors):
                if mode not in desired:errors.pop(mode,None)
            for mode in list(adapters):
                if mode not in desired:adapters.pop(mode).stop()
            for mode in [mode for mode in desired if mode in digital.available()]:
                if mode not in adapters and not (mode in ('DMR','NXDN','YSF','P25','M17') and mode in errors):
                    adapter=Adapter(mode)
                    try:
                        adapter.start();adapters[mode]=adapter;errors.pop(mode,None)
                        settings=digital.audio(mode)
                        for command in [f"usrpGain={settings['receive']}",f"tlvGain={settings['transmit']}",'usrpAudio=AUDIO_USE_GAIN','tlvAudio=AUDIO_USE_GAIN']:digital.control(mode,command)
                    except Exception as error:adapter.stop();errors[mode]=type(error).__name__
            for mode in list(adapters):
                if not adapters[mode].check():adapters.pop(mode).stop();errors[mode]='Adapter process exited'
            digital.save('digital-health.json',{mode:{'running':mode in adapters,'ready':digital.ready(mode),'error':errors.get(mode),'network':adapters[mode].network_status() if mode in adapters else 'Adapter stopped'} for mode in digital.PROFILES})
            time.sleep(2)
    finally:
        for adapter in adapters.values():adapter.stop()
        digital.save('digital-health.json',{})

if __name__=='__main__':main()
