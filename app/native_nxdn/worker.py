# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated NXDN worker. Construction explicitly starts a configured peer.

No production supervisor registration or command-line public connection.
Tests inject a loopback endpoint and ephemeral USRP ports.
"""
import selectors,socket,struct,time,math,os,sys,signal
from pathlib import Path
if __package__:
    from .protocol import Peer
    from .bridge import Bridge
    from .config import validate
    from .raw_codec import Codec
else:
    from protocol import Peer
    from bridge import Bridge
    from config import validate
    from raw_codec import Codec
USRP=struct.Struct('!4s7I')

class Worker:
    def __init__(self,config,endpoint,ports,codec_factory=Codec,clock=time.monotonic):
        self.config=validate(config);self.clock=clock;self.sockets=[];self.selector=selectors.DefaultSelector();self.bridge=None
        self.ports=ports;self.sequence=0;self.done=False;self.note=None;self.rx_gain=1.;self.tx_gain=1.
        codec=codec_factory()
        try:
            self.net=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.sockets.append(self.net);self.net.bind(('127.0.0.1' if endpoint[0]=='127.0.0.1' else '0.0.0.0',0))
            self.audio=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.sockets.append(self.audio);self.audio.bind(('127.0.0.1',ports[0]))
            for sock,tag in [(self.net,'net'),(self.audio,'audio')]:
                sock.setblocking(False);self.selector.register(sock,selectors.EVENT_READ,tag)
            if len(ports)>2:
                self.control=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sockets.append(self.control)
                self.control.bind(('127.0.0.1',ports[2]));self.control.setblocking(False)
                self.selector.register(self.control,selectors.EVENT_READ,'control')
            self.peer=Peer(endpoint,config['callsign'],config['target'],self.net.sendto,clock)
            self.bridge=Bridge(config['source'],config['target'],codec,self.peer.voice,self.play,clock,config.get('ran',1))
            self.peer.start()
        except Exception:
            codec.close()
            for sock in self.sockets:sock.close()
            self.selector.close();raise
    def play(self,key,pcm):
        if pcm:pcm=gain(pcm,self.rx_gain)
        self.audio.sendto(USRP.pack(b'USRP',self.sequence,0,int(key),0,0,0,0)+pcm,('127.0.0.1',self.ports[1]))
        self.sequence=(self.sequence+1)&0xffffffff
    def step(self,timeout=.01):
        if self.done:return
        try:
            for event,_ in self.selector.select(timeout):
                data,source=event.fileobj.recvfrom(2048)
                if event.data=='net':
                    voice=self.peer.receive(data,source)
                    if voice is not None:self.bridge.receive(voice)
                elif event.data=='control':self.control_input(data,source)
                elif source==('127.0.0.1',self.ports[1]) and len(data) in (32,352) and self.peer.state=='connected':
                    eye,seq,memory,key,tg,kind,mpx,reserved=USRP.unpack(data[:32])
                    if eye==b'USRP' and key in (0,1) and not kind:
                        self.bridge.pcm(bool(key),gain(data[32:],self.tx_gain) if len(data)==352 else b'')
            self.peer.tick()
            if self.peer.state=='failed':
                self.note='NXDN peer timed out';self.done=True;self.bridge.close()
            elif self.peer.state=='connected':self.bridge.tick()
        except Exception:
            self.note='NXDN processing failed; no fallback';self.done=True;self.bridge.close();raise
    def status(self):
        return dict(state=self.peer.state,connected=self.peer.state=='connected' and not self.done,
                    authenticated=False,active='software' if not self.done else None,
                    busy=self.bridge.busy,note=self.note,profile='NXDN4800',target=self.config['target'],
                    interoperability_verified=False)
    def control_input(self,data,source):
        if source[0]!='127.0.0.1' or len(data)<2 or data[0]!=5 or data[1]!=len(data)-2:return
        try:
            key,value=data[2:].decode('ascii').split('=',1)
            if key in ('usrpGain','tlvGain'):
                amount=float(value)
                if not math.isfinite(amount) or not .25<=amount<=4:raise ValueError()
                if key=='usrpGain':self.rx_gain=amount
                else:self.tx_gain=amount
            # txTg is consumed through the shared validated target file by main.
        except (UnicodeError,ValueError):self.note='Rejected invalid NXDN control request'
    def close(self):
        if self.done and not self.sockets:return
        self.bridge.close()
        try:self.peer.close()
        finally:
            for sock in self.sockets:sock.close()
            self.sockets=[];self.selector.close();self.done=True

def gain(pcm,amount):
    if len(pcm)!=320:raise ValueError('Invalid PCM length')
    return struct.pack('<160h',*(max(-32768,min(32767,round(x*amount))) for x in struct.unpack('<160h',pcm)))

def main():
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    import codec_selection,nxdn_native,digital
    base=validate(codec_selection.read('nxdn-native.json'))
    selected=codec_selection.desired()
    if selected['backend']!='software':raise ValueError('NXDN external hardware unsupported; no fallback')
    target=int(digital.load('digital-targets.json',{}).get('NXDN',base['target']))
    config=nxdn_native.for_target(base,target)
    def construct(c):
        endpoint=socket.getaddrinfo(c['host'],c['port'],socket.AF_INET,socket.SOCK_DGRAM)[0][4]
        return Worker(c,endpoint,(34004,32004,33100))
    def stop(*_):raise SystemExit()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    worker=construct(config);last=0
    print('Starting USRP: NXDN4800 software; reflector interoperability unverified',flush=True)
    try:
        while not worker.done:
            worker.step()
            now=time.monotonic()
            if now-last>=.25:
                selected=codec_selection.desired()
                requested_target=int(digital.load('digital-targets.json',{}).get('NXDN',base['target']))
                queued=selected['backend']!='software' or requested_target!=config['target']
                if queued and not worker.bridge.busy:
                    worker.close()
                    if selected['backend']!='software':
                        worker.note='Selected NXDN hardware unsupported; software stopped without fallback'
                        break
                    config=nxdn_native.for_target(base,requested_target);worker=construct(config)
                state=worker.status();state.update(pid=os.getpid(),updated=time.time(),requested=selected['backend'],queued=queued)
                codec_selection.write('nxdn-native-status.json',state);last=now
    finally:
        worker.close()
        state=worker.status();state.update(pid=os.getpid(),updated=time.time(),connected=False,active=None,requested=selected['backend'],queued=False)
        codec_selection.write('nxdn-native-status.json',state)

if __name__=='__main__':main()
