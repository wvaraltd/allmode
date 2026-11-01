# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit-start software PCM/DMR TLV adapter. Binds only IPv4 loopback.

MMDVM_Bridge owns network authentication. This worker never resolves or contacts
an Internet host and never starts Analog_Bridge or an emulator.
"""
import json,math,os,selectors,signal,socket,struct,time
from pathlib import Path
from dvswitch_tlv import Bridge,parse
from dvswitch_config import validate
HEADER=struct.Struct('!4s7I')


def gain(pcm,amount):
    if len(pcm)!=320 or not math.isfinite(amount) or not .25<=amount<=4:raise ValueError('Invalid PCM gain')
    return struct.pack('<160h',*(max(-32768,min(32767,round(x*amount))) for x in struct.unpack('<160h',pcm)))


class Worker:
    def __init__(self,station,transport,codec,clock=time.monotonic,owner=lambda source:False):
        from native_dmr.managed_config import validate as station_validate
        station_validate(station);self.config=validate(transport);self.clock=clock
        self.selector=selectors.DefaultSelector();self.sockets=[];self.engine=None
        self.owner=owner;self.sequence=0;self.done=False;self.rx_gain=1.;self.tx_gain=1.
        try:
            for name,key in (('audio','usrp_receive'),('tlv','tlv_receive')):
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sockets.append(sock)
                sock.bind(('127.0.0.1',self.config[key]));sock.setblocking(False)
                setattr(self,name,sock);self.selector.register(sock,selectors.EVENT_READ,name)
            n=station['networks'][station['selected']]
            self.engine=Bridge(station['source'],station['peer'],n['talkgroup'],station['slot'],station['color'],codec,self.send_tlv,self.send_audio,clock)
        except Exception:
            codec.close()
            for sock in self.sockets:sock.close()
            self.selector.close();raise
    def send_tlv(self,data):self.tlv.sendto(data,('127.0.0.1',self.config['tlv_send']))
    def send_audio(self,key,pcm):
        if pcm:pcm=gain(pcm,self.rx_gain)
        self.audio.sendto(HEADER.pack(b'USRP',self.sequence,0,int(key),0,0,0,0)+pcm,('127.0.0.1',self.config['usrp_send']))
        self.sequence=(self.sequence+1)&0xffffffff
    def audio_input(self,data,source):
        if source!=('127.0.0.1',self.config['usrp_send']) or len(data) not in (32,352):return
        eye,seq,memory,key,tg,kind,mpx,reserved=HEADER.unpack(data[:32])
        if eye!=b'USRP' or kind or key not in (0,1):return
        self.engine.pcm(bool(key),gain(data[32:],self.tx_gain) if len(data)==352 else b'')
    def control(self,data):
        if len(data)<2 or data[0]!=5 or data[1]!=len(data)-2:return False
        try:
            key,value=data[2:].decode('ascii').split('=',1)
            if key=='txTg':
                target=int(value)
                if not 1<=target<=0xffffff or self.engine.busy:raise ValueError('Busy or invalid destination')
                self.engine.target=target
            elif key in ('usrpGain','tlvGain'):
                amount=float(value)
                if not math.isfinite(amount) or not .25<=amount<=4:raise ValueError('Invalid gain')
                if key=='usrpGain':self.rx_gain=amount
                else:self.tx_gain=amount
        except (UnicodeError,ValueError):pass
        return True
    def step(self,timeout=.01):
        for event,_ in self.selector.select(timeout):
            data,source=event.fileobj.recvfrom(2048)
            if event.data=='audio':self.audio_input(data,source)
            elif source[0]=='127.0.0.1':
                if self.control(data):continue
                if not self.owner(source):continue
                try:parse(data)
                except ValueError:continue
                self.engine.network(data)
        self.engine.tick()
    def close(self):
        try:self.engine.close()
        finally:
            for sock in self.sockets:sock.close()
            self.selector.close()


def owned_udp(pid,source):
    """Verify the actual exporting socket belongs to the supervised MB child.

    MB's exporter binds port zero, separate from its fixed TLV receiving socket.
    Re-read ownership rather than trusting or pinning the first incoming sender.
    """
    if type(pid) is not int or pid<=1 or source[0]!='127.0.0.1':return False
    try:
        sockets=set()
        for p in Path('/proc',str(pid),'fd').iterdir():
            try:sockets.add(p.readlink().name)
            except FileNotFoundError:continue
        for line in Path('/proc/net/udp').read_text().splitlines()[1:]:
            fields=line.split();address,port=fields[1].split(':')
            if int(port,16)==source[1] and address in ('00000000','0100007F') and 'socket:['+fields[9]+']' in sockets:return True
    except (OSError,ValueError,IndexError):return False
    return False


def main():
    import codec_selection,digital,dvswitch_config
    from speaker_status import playout
    from native_dmr.native2450 import Codec
    selection=codec_selection.desired()
    if selection['backend']!='software':raise ValueError('DVSwitch TLV route requires software; disconnect and select native for optional hardware')
    cfg=codec_selection.read('dmr-native.json');transport=dvswitch_config.load()
    if transport['dmr_transport']!='dvswitch':raise ValueError('DVSwitch route not selected')
    pid=int(os.environ['ALLMODE_MMDVM_PID'])
    worker=Worker(cfg,transport,Codec(),owner=lambda source:owned_udp(pid,source));last=0
    signal.signal(signal.SIGTERM,lambda *_:setattr(worker,'done',True));signal.signal(signal.SIGINT,lambda *_:setattr(worker,'done',True))
    print('Starting USRP; local DVSwitch DMR software selected',flush=True)
    try:
        while not worker.done:
            # Never open a second codec or silently fallback on a selection change.
            if codec_selection.desired()['id']!=selection['id']:
                if not worker.engine.busy:break
            worker.step()
            if time.monotonic()-last>.25:
                digital.save('dvswitch-worker-status.json',dict(speaker=playout(worker.engine,'DMR'),target=worker.engine.target,pid=os.getpid(),updated=time.time(),active='software',busy=worker.engine.busy,transport='dvswitch',note='Local adapter running; network authentication belongs to MMDVM_Bridge'))
                last=time.monotonic()
    finally:
        worker.close();digital.save('dvswitch-worker-status.json',dict(pid=os.getpid(),updated=time.time(),active=None,busy=False,transport='dvswitch',note='Stopped'))
if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('DVSwitch adapter stopped: '+type(exc).__name__,flush=True);raise SystemExit(1)
