"""Software D-STAR / USRP bridge. Initial networking support: DCS reflectors.

Wire layouts checked against nostar/DroidStar dcs.cpp and AllStar chan_usrp.h.
The plugin runs locally; there is no external vocoder service.
"""
import ctypes, json, os, re, secrets, selectors, signal, socket, struct, time
from collections import deque
from pathlib import Path
import digital
from speech_filter import SpeechFilter

HEADER=struct.Struct('!4s7I')
PCM=ctypes.c_int16*160
VOICE=ctypes.c_uint8*9
END_VOICE=bytes.fromhex('dc8e0a40adedad396e')

def hosts(path=None):
    result={}
    for filename in ([path] if path else [digital.ROOT/'hosts/DCSHosts.txt',digital.ROOT/'hosts/XLXHosts.txt',digital.ROOT/'hosts/REFHosts.txt']):
        if not filename.exists():continue
        for line in filename.read_text().splitlines():
            fields=line.split()
            if len(fields)>=2 and re.fullmatch(r'(?:DCS|XLX|REF)[0-9]{3}',fields[0]):result[fields[0]]=fields[1]
    return result

def split_target(target):
    if not re.fullmatch(r'(?:DCS|XLX|REF)[0-9]{3}[A-Z]',target):raise ValueError('Use a reflector and module, such as REF030C, DCS001C or XLX681A.')
    return target[:6],target[6]

def connect_packet(call,module):
    return call.encode().ljust(8,b' ')+module.encode()*2+b'\x0b'+bytes(508)

def voice_packet(call,target,stream,number,voice,end=False):
    reflector,module=split_target(target);packet=bytearray(100);packet[:4]=b'0001'
    packet[7:15]=('DCS'+reflector[3:]+' '+module).encode()
    packet[15:23]=(call.ljust(7)+module).encode()
    packet[23:31]=b'CQCQCQ  ';packet[31:39]=call.encode().ljust(8,b' ');packet[39:43]=b'ALMD'
    packet[43:45]=struct.pack('!H',stream);packet[45]=number%21|(0x40 if end else 0)
    packet[46:55]=END_VOICE if end else voice
    packet[55:58]=b'\x55\x2d\x16' if number%21==0 else b'\x16\x29\xf5'
    packet[58:61]=(number&0xffffff).to_bytes(3,'little');packet[61]=1
    return bytes(packet)

def usrp_packet(sequence,key,pcm=b''):
    return HEADER.pack(b'USRP',sequence&0xffffffff,0,int(key),0,0,0,0)+pcm

def parse_usrp(data):
    if len(data) not in (32,352):return None
    eye,seq,memory,key,tg,kind,mpx,reserved=HEADER.unpack(data[:32])
    if eye!=b'USRP' or kind!=0 or key not in (0,1):return None
    return bool(key),data[32:]

class Codec:
    def __init__(self,root=None):
        root=root or digital.ROOT/'DStar';self.lib=ctypes.CDLL(str(root/'liballmode_dstar.so'))
        self.lib.allmode_codec_open.argtypes=[ctypes.c_char_p];self.lib.allmode_codec_open.restype=ctypes.c_void_p
        self.lib.allmode_codec_encode.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int16),ctypes.POINTER(ctypes.c_uint8)]
        self.lib.allmode_codec_decode.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(ctypes.c_int16)]
        self.lib.allmode_codec_close.argtypes=[ctypes.c_void_p]
        self.handle=self.lib.allmode_codec_open(os.fsencode(root/'vocoder_plugin.linux.arm64'))
        if not self.handle:raise RuntimeError('D-STAR software codec could not load')
    def encode(self,data,gain):
        samples=struct.unpack('<160h',data);pcm=PCM(*(max(-32768,min(32767,round(v*gain))) for v in samples));voice=VOICE()
        if self.lib.allmode_codec_encode(self.handle,pcm,voice):raise RuntimeError('D-STAR encode failed')
        return bytes(voice)
    def decode(self,voice,gain):
        pcm=PCM();frame=VOICE.from_buffer_copy(voice)
        if self.lib.allmode_codec_decode(self.handle,frame,pcm):raise RuntimeError('D-STAR decode failed')
        return struct.pack('<160h',*(max(-32768,min(32767,round(v*gain))) for v in pcm))
    def close(self):
        if self.handle:self.lib.allmode_codec_close(self.handle);self.handle=None

class Bridge:
    def __init__(self,call,profile=None,codec=None,terminal=' '):
        if not re.fullmatch(r'[A-Z0-9]{3,7}',call):raise ValueError('Invalid gateway callsign')
        self.call=call;self.p=profile or digital.PROFILES['D-STAR'];self.codec=codec or Codec()
        self.speech_filter=SpeechFilter()
        self.selector=selectors.DefaultSelector();self.sockets=[]
        for name,port in [('audio',self.p['rx']),('remote',self.p['remote']),('control',self.p['tlv']),('network',0)]:
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1' if name!='network' else '0.0.0.0',port));sock.setblocking(False)
            self.sockets.append(sock);setattr(self,name,sock);self.selector.register(sock,selectors.EVENT_READ,name)
        self.target=None;self.endpoint=None;self.confirmed=False;self.status='Unlinked'
        self.tx_stream=0;self.tx_number=0;self.tx_since=0;self.last_tx=0;self.tx_blocked=False
        self.rx_queue=deque();self.rx_stream=None;self.rx_counter=None;self.rx_key=False;self.sequence=0
        self.last_network=0;self.last_rx=0;self.next_ping=0;self.next_retry=0;self.next_audio=0
        self.receive_gain=1.;self.transmit_gain=1.;self.done=False;self.last_status=None
        from dstar_ref import RefProtocol
        self.ref=RefProtocol(self,terminal)
    def is_ref(self):return bool(self.target and self.target.startswith('REF'))
    def publish(self):
        if self.last_status!=self.status:
            digital.save('dstar-status.json',{'network':self.status,'target':self.target,'confirmed':self.confirmed})
            print(self.status,flush=True);self.last_status=self.status
    def send_usrp(self,key,pcm=b''):
        self.audio.sendto(usrp_packet(self.sequence,key,pcm),('127.0.0.1',self.p['tx']));self.sequence+=1;self.rx_key=key
    def end_tx(self):
        if self.tx_stream and self.confirmed:
            if self.is_ref():self.ref.transmit(b'',True)
            else:self.network.sendto(voice_packet(self.call,self.target,self.tx_stream,self.tx_number,b'',True),self.endpoint)
        self.tx_stream=0;self.tx_number=0
    def unlink(self):
        self.end_tx()
        if self.endpoint and self.target:
            from dstar_ref import DISCONNECT
            packet=DISCONNECT if self.is_ref() else self.call.encode().ljust(8,b' ')+self.target[-1].encode()+b' \0'
            self.network.sendto(packet,self.endpoint)
        if self.rx_key:self.send_usrp(False)
        self.rx_queue.clear();self.rx_stream=None;self.rx_counter=None
        self.target=None;self.endpoint=None;self.confirmed=False;self.status='Unlinked';self.publish()
    def link(self,target):
        reflector,module=split_target(target);host=hosts().get(reflector)
        if not host:raise ValueError('Reflector is not in the installed DCS directory')
        endpoint=(socket.gethostbyname(host),20001 if reflector.startswith('REF') else 30051)
        self.unlink();self.target=target;self.endpoint=endpoint;self.status='Waiting for REF login' if self.is_ref() else 'Waiting for DCS handshake';self.tx_blocked=False
        if self.is_ref():self.ref.connect()
        else:self.network.sendto(connect_packet(self.call,module),endpoint)
        now=time.monotonic();self.last_network=now;self.next_retry=now+5;self.next_ping=now+1;self.publish()
    def on_network(self,data,source,now):
        if source!=self.endpoint or not self.target:return
        if self.is_ref():self.ref.network(data,now);return
        if len(data)==14:
            if data[:8]!=self.call.encode().ljust(8,b' ') or data[9:10]!=self.target[-1:].encode():return
            if data[10:13]==b'ACK':self.confirmed=True;self.status='Reflector handshake confirmed';self.last_network=now;self.publish()
            elif data[10:13]==b'NAK':self.unlink();self.status='DCS reflector rejected the connection';self.publish()
        elif self.confirmed and len(data)==22:self.last_network=now
        elif self.confirmed and len(data)==100 and data[:4]==b'0001':
            # The connected reflector routes its selected module. Forwarded
            # streams can retain their originating RPT2 callsign; accept them
            # from the already-validated endpoint, as DroidStar does.
            self.last_network=now
            if self.tx_stream or data[31:39].rstrip()==self.call.encode():return
            stream=data[43:45];counter=int.from_bytes(data[58:61],'little')
            if stream==self.rx_stream and self.rx_counter is not None and counter<=self.rx_counter:return
            if self.rx_stream not in (None,stream) and now-self.last_rx<1:return
            if stream!=self.rx_stream:self.rx_queue.clear();self.rx_stream=stream;self.rx_counter=None;self.next_audio=now+.06
            self.rx_counter=counter;self.last_rx=now
            if len(self.rx_queue)>=25:self.rx_queue.clear();self.next_audio=now
            self.rx_queue.append(None if data[45]&0x40 else bytes(data[46:55]))
    def on_audio(self,data,now):
        parsed=parse_usrp(data)
        if parsed is None:return
        keyed,pcm=parsed
        if not keyed:self.end_tx();self.tx_blocked=False;return
        if not self.confirmed or self.tx_blocked or len(pcm)!=320:return
        if self.is_ref() and not self.ref.writable:return
        if not self.tx_stream:
            if self.rx_key:self.send_usrp(False)
            self.rx_queue.clear();self.rx_stream=None;self.rx_counter=None
            self.tx_stream=secrets.randbelow(65535)+1;self.tx_since=now
            self.speech_filter.reset()
        if now-self.tx_since>=180:self.end_tx();self.tx_blocked=True;return
        # USRP speech is already at normal PCM levels. Apply only the saved
        # transmit gain, with peak headroom; avoid an additional hidden boost.
        pcm=self.speech_filter.process(pcm)
        peak=max(abs(v) for v in struct.unpack('<160h',pcm))
        gain=min(self.transmit_gain,30000/peak) if peak else self.transmit_gain
        voice=self.codec.encode(pcm,gain)
        if self.is_ref():self.ref.transmit(voice)
        else:self.network.sendto(voice_packet(self.call,self.target,self.tx_stream,self.tx_number,voice),self.endpoint)
        self.tx_number+=1;self.last_tx=now
    def on_control(self,data):
        if len(data)<2 or data[0]!=5 or len(data)!=data[1]+2:return
        text=data[2:].decode('ascii',errors='strict')
        if text.startswith(('usrpGain=','tlvGain=')):
            key,value=text.split('=',1);gain=float(value)
            if not .25<=gain<=4:return
            if key=='usrpGain':self.receive_gain=gain
            else:self.transmit_gain=gain
    def tick(self,now):
        if self.target:
            if not self.confirmed and now>=self.next_retry:
                if now-self.last_network>30:self.unlink();self.status='D-STAR handshake timed out';self.publish()
                else:
                    if self.is_ref():self.ref.connect()
                    else:self.network.sendto(connect_packet(self.call,self.target[-1]),self.endpoint)
                    self.next_retry=now+5
            elif self.confirmed:
                if now-self.last_network>20:self.unlink();self.status='D-STAR keepalive lost';self.publish()
                elif now>=self.next_ping:
                    ping=self.call.encode().ljust(7,b' ')+self.target[-1:].encode()+b'\0'+('DCS'+self.target[3:6]).encode()+b'\0'+self.target[-1:].encode()
                    from dstar_ref import PING
                    self.network.sendto(PING if self.is_ref() else ping,self.endpoint);self.next_ping=now+(1 if self.is_ref() else 2)
        if self.tx_stream and now-self.last_tx>.5:self.end_tx()
        if self.rx_queue and now>=self.next_audio:
            voice=self.rx_queue.popleft();self.next_audio+=.02
            if now-self.next_audio>.06:self.next_audio=now+.02
            if voice is None:
                if self.rx_key:self.send_usrp(False)
                self.rx_stream=None;self.rx_counter=None
            else:self.send_usrp(True,self.codec.decode(voice,self.receive_gain))
        elif self.rx_key and now-self.last_rx>1:
            self.send_usrp(False);self.rx_queue.clear();self.rx_stream=None;self.rx_counter=None
    def run(self):
        print('Starting USRP D-STAR software adapter',flush=True);self.publish()
        try:
            while not self.done:
                # Wake at the audio deadline rather than adding a polling delay
                # to every 20 ms frame. Keep the deadline independent of decode.
                wait=max(0,min(.01,self.next_audio-time.monotonic())) if self.rx_queue else .01
                for key,_ in self.selector.select(wait):
                    data,source=key.fileobj.recvfrom(2048);now=time.monotonic()
                    try:
                        if key.data=='network':self.on_network(data,source,now)
                        elif key.data=='audio':self.on_audio(data,now)
                        elif key.data=='control':self.on_control(data)
                        elif key.data=='remote':
                            text=data.decode('ascii')
                            if text=='UnLink':self.unlink()
                            elif text.startswith('Link '):self.link(text[5:])
                    except (ValueError,UnicodeError,OSError) as error:
                        self.status='D-STAR request failed: '+type(error).__name__;self.publish()
                self.tick(time.monotonic())
        finally:self.close()
    def close(self):
        try:self.unlink()
        finally:
            self.selector.close()
            for sock in self.sockets:sock.close()
            self.codec.close()

def main():
    import configparser
    settings=configparser.ConfigParser();settings.read(digital.ROOT/'MMDVM_Bridge/allmode-tgif.ini')
    identity=digital.load('dstar-identity.json',{})
    codec_settings=digital.load('dstar-codec.json',{})
    codec=None
    if codec_settings.get('type')=='hardware':
        from dstar_hardware import HardwareCodec
        codec=HardwareCodec(codec_settings['host'],codec_settings.get('port',2460))
    bridge=Bridge(settings.get('General','Callsign').upper(),codec=codec,terminal=identity.get('terminal',' '))
    def stop(*_):bridge.done=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);bridge.run()

if __name__=='__main__':main()
