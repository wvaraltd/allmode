# SPDX-License-Identifier: GPL-3.0-or-later
"""YSF V/D mode 2 only: five 49-bit voice frames per 155-byte datagram.
Derived layout from pinned G4KLX YSFClients and Doug McLain's DroidStar.
Full-rate voice/data, V/D mode 1, FCS and private calls are unsupported.
"""
import ctypes as C
from pathlib import Path
import re,time
WHITE=bytes.fromhex('93d751219c2f6cd0ef0ff83df1732094ed1e7cd8')
SYNC=bytes.fromhex('d471c9634d')
def callsign(s):
    if not isinstance(s,str) or not re.fullmatch(r'[A-Z0-9/-]{1,10}',s):raise ValueError('YSF callsign must fit ten ASCII characters')
    return s.ljust(10).encode('ascii')
def bits(b):return [(v>>(7-i))&1 for v in b for i in range(8)]
def packed(b):
    v=0
    for x in b:v=(v<<1)|x
    return (v<<((-len(b))%8)).to_bytes((len(b)+7)//8,'big')
def raw49(raw):
    if len(raw)!=7 or raw[6]&127:raise ValueError('Invalid 49-bit voice frame')
    return bits(raw)[:49]
def vch(raw):
    a=raw49(raw);repeat=[x for v in a[:27] for x in [v]*3]+a[27:]+[0]
    repeat=[x^y for x,y in zip(repeat,bits(WHITE))]
    return packed([repeat[(i%4)*26+i//4] for i in range(104)])
def unvch(data):
    if len(data)!=13:raise ValueError('Invalid voice channel')
    a=bits(data);a=[a[(i%26)*4+i//26]^bits(WHITE)[i] for i in range(104)]
    # Majority decoding of each triplet corrects one error per protected bit.
    raw=[int(sum(a[3*i:3*i+3])>=2) for i in range(27)]+a[81:103]
    return packed(raw)
class FEC:
    def __init__(self):
        self.lib=C.CDLL(str(Path(__file__).parent/'build/liballmode_ysf.so'))
        for n in ('ysf_fich_encode','ysf_fich_decode','ysf_data_encode','ysf_data_decode'):
            getattr(self.lib,n).argtypes=[C.c_void_p,C.c_uint,C.c_void_p,C.c_uint]
    def call(self,name,data,size):
        src=(C.c_uint8*len(data)).from_buffer_copy(data);dst=(C.c_uint8*size)()
        if getattr(self.lib,name)(src,len(data),dst,size)<0:raise ValueError('YSF FEC/CRC rejected frame')
        return bytes(dst)
_fec=None
def fec():
    global _fec
    if _fec is None:_fec=FEC()
    return _fec
def fich(fi,index=0,dgid=0):
    if not 0<=dgid<=99 or not 0<=index<=6 or fi not in (0,1,2):raise ValueError('Unsupported YSF FICH')
    return fec().call('ysf_fich_encode',bytes([(fi<<6)|0x20,(index<<3)|6,2,dgid]),25)
def envelope(source,seq,end=False):
    call=callsign(source)
    return b'YSFD'+call+call+b'ALL       '+bytes([((seq%128)<<1)|int(end)])
def header(source,target=None,ran=0,end=False,seq=0):
    call=callsign(source);a=fec().call('ysf_data_encode',b'**********'+call,45);b=fec().call('ysf_data_encode',call*2,45)
    payload=b''.join(a[i*9:i*9+9]+b[i*9:i*9+9] for i in range(5))
    return envelope(source,seq,end)+SYNC+fich(2 if end else 0,0,ran)+payload
def voice(source,target,frames,index,ran=0,frame_number=None):
    if len(frames)!=5 or type(index) is not int or not 0<=index<=127:raise ValueError('Expected five voice frames and sequence 0..127')
    fn=(index-1)%7 if frame_number is None else frame_number
    if type(fn) is not int or not 0<=fn<=6:raise ValueError('Invalid YSF frame number')
    call=callsign(source)
    dch=b'**********' if fn==0 else call if fn in (1,2,3) else bytes.fromhex('0122615f2b0311000000') if fn==6 else b' '*10
    encoded=fec().call('ysf_data_encode',dch,25)
    payload=b''.join(encoded[i*5:i*5+5]+vch(frames[i]) for i in range(5))
    return envelope(source,index)+SYNC+fich(1,fn,ran)+payload
def parse(data,target=None,ran=0):
    if not isinstance(data,bytes) or len(data)!=155 or data[:4]!=b'YSFD' or data[35:40]!=SYNC:return None
    try:
        source=data[14:24].decode('ascii').rstrip();callsign(source)
        raw=fec().call('ysf_fich_decode',data[40:65],4)
        fi=raw[0]>>6;fn=(raw[1]>>3)&7;dt=raw[2]&3;cm=(raw[0]>>2)&3
        if dt!=2 or cm!=0 or (raw[0]&3) or (raw[1]>>6) or raw[3]!=ran or fn>6:return None
        if data[24:34] not in (b'ALL       ',b'**********'):return None
        seq=data[34]>>1;end=bool(data[34]&1)
        if fi in (0,2):
            if end!=(fi==2):return None
            a=b''.join(data[65+i*18:74+i*18] for i in range(5));b=b''.join(data[74+i*18:83+i*18] for i in range(5))
            a=fec().call('ysf_data_decode',a,20);fec().call('ysf_data_decode',b,20)
            if a[10:]!=callsign(source):return None
            return dict(kind='end' if end else 'header',source=source,index=seq)
        if fi!=1 or end:return None
        dch=b''.join(data[65+i*18:70+i*18] for i in range(5))
        decoded=fec().call('ysf_data_decode',dch,10)
        if fn==1 and decoded!=callsign(source):return None
        return dict(kind='voice',source=source,index=seq,frames=tuple(unvch(data[70+i*18:83+i*18]) for i in range(5)))
    except (ValueError,UnicodeError):return None
class Peer:
    def __init__(self,endpoint,call,target,send,clock=time.monotonic):
        self.endpoint=endpoint;self.request=b'YSFP'+callsign(call);self.unlink=b'YSFU'+callsign(call)
        self.send=send;self.clock=clock;self.state='stopped';self.last=0;self.next=0
    def start(self):
        if self.state!='stopped':raise ValueError('Create a fresh YSF peer')
        self.state='connecting';self.last=self.clock();self.next=self.last+5;self.send(self.request,self.endpoint)
    def receive(self,data,endpoint):
        if endpoint!=self.endpoint or self.state not in ('connecting','connected'):return None
        # Reflectors identify themselves in YSFP; they need not echo our callsign.
        if len(data)==14 and data[:4]==b'YSFP':self.state='connected';self.last=self.clock()
        elif self.state=='connected' and len(data)==155 and data[:4]==b'YSFD':return data
        return None
    def tick(self):
        if self.state not in ('connecting','connected'):return
        now=self.clock()
        if now-self.last>=15:self.state='failed'
        elif now>=self.next:self.send(self.request,self.endpoint);self.next=now+5
    def voice(self,data):
        if self.state!='connected' or len(data)!=155 or data[:4]!=b'YSFD':raise ValueError('YSF peer unavailable or invalid datagram')
        self.send(data,self.endpoint)
    def close(self):
        if self.state in ('connecting','connected'):self.send(self.unlink,self.endpoint)
        self.state='stopped'
