"""DMR Homebrew client state machine; no sockets or implicit connections.

Wire format reference: HBLink-org/hblink3 hblink.py. GPL-3.0-or-later.
Caller owns endpoint resolution, socket, scheduling, and explicit user start.
"""
import hashlib
import ipaddress
import struct

def number(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Integer outside protocol range')
    return value

def configuration(peer, callsign, rx=0, tx=0, color=1):
    number(peer,1,0xffffffff);number(rx,0,999999999);number(tx,0,999999999);number(color,0,15)
    if not isinstance(callsign,str) or not 1<=len(callsign)<=8 or not all(c.isascii() and (c.isalnum() or c in '/-') for c in callsign):
        raise ValueError('Invalid callsign')
    # No location disclosure. These are network metadata, never radio programming.
    fields=[callsign.upper().ljust(8),f'{rx:09}',f'{tx:09}','00',f'{color:02}',
            '0.000000','0.0000000','000','ALLMODE'.ljust(20),'Local gateway'.ljust(19),'2',
            ''.ljust(124),'ALLMODE native prototype'.ljust(40),'ALLMODE'.ljust(40)]
    result=b'RPTC'+struct.pack('>I',peer)+''.join(fields).encode('ascii')
    assert len(result)==302
    return result

class Peer:
    def __init__(self,endpoint,peer,password,config,send,clock):
        ipaddress.ip_address(endpoint[0]);number(endpoint[1],1,65535);number(peer,1,0xffffffff)
        if not isinstance(password,bytes) or not password or len(password)>256:raise ValueError('Invalid credential length')
        self.id=struct.pack('>I',peer)
        if len(config)!=302 or config[:8]!=b'RPTC'+self.id:raise ValueError('Invalid repeater configuration')
        self.endpoint=endpoint;self.password=password;self.config=config;self.send=send;self.clock=clock
        self.state='stopped';self.deadline=0;self.ping_at=0;self.pong_at=0;self.note=None
    def emit(self,data):self.send(data,self.endpoint)
    def start(self):
        if self.state!='stopped':raise RuntimeError('Peer already started')
        self.state='login';self.deadline=self.clock()+10;self.emit(b'RPTL'+self.id)
    def fail(self,note):self.state='failed';self.note=note
    def receive(self,data,endpoint):
        if endpoint!=self.endpoint or not isinstance(data,bytes):return None
        if data==b'MSTNAK'+self.id:
            if self.state not in ('stopped','failed'):self.fail('Master rejected session')
            return None
        if self.state=='login' and len(data)==10 and data[:6]==b'RPTACK':
            self.emit(b'RPTK'+self.id+hashlib.sha256(data[6:]+self.password).digest())
            self.state='auth';self.deadline=self.clock()+10
        elif self.state=='auth' and data==b'RPTACK'+self.id:
            self.emit(self.config);self.state='config';self.deadline=self.clock()+10
        elif self.state=='config' and data==b'RPTACK'+self.id:
            self.state='connected';self.pong_at=self.clock();self.ping_at=self.clock()+5
        elif self.state=='connected':
            if data==b'MSTPONG'+self.id:self.pong_at=self.clock()
            elif data==b'MSTCL'+self.id:self.fail('Master closed session')
            elif len(data)==55 and data[:4]==b'DMRD' and data[11:15]==self.id:return data
        return None
    def tick(self):
        now=self.clock()
        if self.state in ('login','auth','config') and now>=self.deadline:self.fail('Handshake timed out')
        if self.state=='connected':
            if now-self.pong_at>=20:self.fail('Master heartbeat timed out')
            elif now>=self.ping_at:self.emit(b'RPTPING'+self.id);self.ping_at=now+5
    def voice(self,data):
        if self.state!='connected':raise RuntimeError('Master session is not authenticated')
        if len(data)!=55 or data[:4]!=b'DMRD' or data[11:15]!=self.id:raise ValueError('Invalid voice datagram')
        self.emit(data)
    def close(self):
        if self.state not in ('stopped','failed'):self.emit(b'RPTCL'+self.id)
        self.state='stopped';self.password=b''

def packet(seq,source,target,peer,slot,kind,stream,burst):
    number(seq,0,255);number(source,1,0xffffff);number(target,1,0xffffff)
    number(peer,1,0xffffffff);number(slot,1,2);number(stream,1,0xffffffff)
    if kind not in (0x10,1,2,3,4,5,0x21,0x22) or len(burst)!=33:raise ValueError('Invalid DMR burst')
    return b'DMRD'+bytes([seq])+source.to_bytes(3,'big')+target.to_bytes(3,'big')+peer.to_bytes(4,'big')+bytes([kind|(0x80 if slot==2 else 0)])+stream.to_bytes(4,'big')+burst+b'\0\0'

def unpack(data,peer,slot,target):
    if len(data)!=55 or data[:4]!=b'DMRD':raise ValueError('Invalid DMR datagram')
    flags=data[15];kind=flags&0x3f
    if int.from_bytes(data[11:15],'big')!=peer or (2 if flags&0x80 else 1)!=slot or flags&0x40:return None
    if int.from_bytes(data[8:11],'big')!=target or kind not in (0x10,1,2,3,4,5,0x21,0x22):return None
    source=int.from_bytes(data[5:8],'big');stream=int.from_bytes(data[16:20],'big')
    if not source or not stream:return None
    return dict(seq=data[4],source=source,target=target,stream=stream,kind=kind,burst=data[20:53])
