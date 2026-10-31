# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit-start native DMR/USRP worker. Never invoked by importing this file."""
import json,math,os,selectors,signal,socket,struct,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from homebrew import Peer,configuration
from managed_config import validate
from native2450 import Codec
from voice_bridge import VoiceBridge
HEADER=struct.Struct('!4s7I')

def gain(pcm,amount):
    if len(pcm)!=320 or not math.isfinite(amount) or not .25<=amount<=4:raise ValueError('Invalid audio gain')
    return struct.pack('<160h',*(max(-32768,min(32767,round(x*amount))) for x in struct.unpack('<160h',pcm)))

class Worker:
    def __init__(self,config,endpoint,backend,codec_factory=Codec,ports=(34001,32001,31100),clock=time.monotonic,publish=lambda _:None,hardware_factory=None):
        self.config=validate(config);self.clock=clock;self.publish=publish;self.backend=backend
        selection=backend()
        self.factories={'software':codec_factory,'hardware':hardware_factory or self.hardware}
        if selection['backend'] not in self.factories:raise ValueError('Unknown selected codec')
        self.active_backend=selection['backend']
        self.request_id=selection['id'];self.sequence=0;self.done=False;self.note=None;self.rx_gain=1.;self.tx_gain=1.
        self.ports=ports;self.selector=selectors.DefaultSelector();self.sockets=[];self.engine=None
        codec=self.factories[self.active_backend]()
        try:
            for name,port in [('audio',ports[0]),('control',ports[2]),('network',0)]:
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('0.0.0.0' if name=='network' else '127.0.0.1',port));sock.setblocking(False)
                setattr(self,name,sock);self.sockets.append(sock);self.selector.register(sock,selectors.EVENT_READ,name)
            n=config['networks'][config['selected']]
            self.peer=Peer(endpoint,config['peer'],n['password'].encode(),configuration(config['peer'],config['callsign'],color=config['color']),self.network.sendto,clock)
            self.engine=VoiceBridge(config['source'],config['peer'],n['talkgroup'],codec,self.peer.voice,self.send_audio,clock,config['slot'],config['color'])
        except Exception:
            codec.close()
            for sock in self.sockets:sock.close()
            self.selector.close();raise
        self.last_publish=0;self.peer.start()
    @staticmethod
    def hardware():
        from hardware2450 import Codec as HardwareCodec
        return HardwareCodec()
    def send_audio(self,key,pcm):
        if pcm:pcm=gain(pcm,self.rx_gain)
        self.audio.sendto(HEADER.pack(b'USRP',self.sequence,0,int(key),0,0,0,0)+pcm,('127.0.0.1',self.ports[1]));self.sequence=(self.sequence+1)&0xffffffff
    def audio_input(self,data,source):
        if source!=('127.0.0.1',self.ports[1]) or len(data) not in (32,352):return
        eye,seq,memory,key,tg,kind,mpx,reserved=HEADER.unpack(data[:32])
        if eye!=b'USRP' or kind or key not in (0,1):return
        if self.peer.state!='connected':return
        self.engine.pcm(bool(key),gain(data[32:],self.tx_gain) if len(data)==352 else b'')
    def control_input(self,data,source):
        if source[0]!='127.0.0.1' or len(data)<2 or data[0]!=5 or data[1]!=len(data)-2:return
        try:
            command=data[2:].decode('ascii');key,value=command.split('=',1)
            if key=='txTg':
                target=int(value)
                if not 1<=target<=0xffffff:raise ValueError()
                if self.engine.busy:raise ValueError('Wait for stream end before changing talkgroup')
                self.engine.target=target
            elif key in ('usrpGain','tlvGain'):
                amount=float(value)
                if not math.isfinite(amount) or not .25<=amount<=4:raise ValueError()
                if key=='usrpGain':self.rx_gain=amount
                else:self.tx_gain=amount
        except (UnicodeError,ValueError):self.note='Rejected invalid or busy control request'
    def step(self,timeout=.01):
        for event,_ in self.selector.select(timeout):
            data,source=event.fileobj.recvfrom(2048)
            if event.data=='network':
                voice=self.peer.receive(data,source)
                if voice is not None:self.engine.network(voice)
            elif event.data=='audio':self.audio_input(data,source)
            else:self.control_input(data,source)
        self.peer.tick()
        if self.peer.state=='failed':self.note=self.peer.note;self.done=True;return
        if self.peer.state=='connected':self.engine.tick()
        selected=self.backend();queued=selected['id']!=self.request_id
        if queued and not self.engine.busy:
            if selected['backend']!=self.active_backend:
                target=self.engine.target
                self.engine.close() # old backend is closed before the new one opens
                self.active_backend=None
                try:
                    codec=self.factories[selected['backend']]()
                    self.engine=VoiceBridge(self.config['source'],self.config['peer'],target,codec,self.peer.voice,self.send_audio,self.clock,self.config['slot'],self.config['color'])
                    self.active_backend=selected['backend'];self.request_id=selected['id']
                except Exception:
                    self.note='Selected DMR codec unavailable; stopped without fallback';self.done=True
            else:self.request_id=selected['id']
        now=self.clock()
        if now-self.last_publish>=.25:
            self.publish(dict(pid=os.getpid(),updated=time.time(),network=self.config['selected'],authenticated=self.peer.state=='connected' and not self.done,
                              state=self.peer.state,note=self.note,active=self.active_backend if not self.done else None,requested=selected['backend'],queued=queued,busy=self.engine.busy))
            self.last_publish=now
    def close(self):
        try:
            if self.engine:self.engine.close()
            self.peer.close()
        finally:
            for sock in self.sockets:sock.close()
            self.selector.close()
            self.publish(dict(pid=os.getpid(),updated=time.time(),authenticated=False,state='stopped',active=None,note=self.note))

def main():
    import codec_selection,digital
    config=validate(codec_selection.read('dmr-native.json'))
    # Fail before DNS/network I/O if the selected codec is unsupported.
    import dmr_native
    if codec_selection.desired()['backend']=='hardware' and not dmr_native.hardware_supported():raise ValueError('External DMR capability has not been verified')
    n=config['networks'][config['selected']];endpoint=(socket.gethostbyname(n['host']),n['port'])
    worker=Worker(config,endpoint,codec_selection.desired,publish=lambda s:digital.save('dmr-native-status.json',s))
    signal.signal(signal.SIGTERM,lambda *_:setattr(worker,'done',True));signal.signal(signal.SIGINT,lambda *_:setattr(worker,'done',True))
    print('Starting USRP; native DMR '+worker.active_backend+' selected',flush=True)
    try:
        while not worker.done:worker.step()
    finally:worker.close()
if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Never print config, credentials, auth packet or traceback locals.
        print('Native DMR stopped: '+type(exc).__name__,flush=True);sys.exit(1)
