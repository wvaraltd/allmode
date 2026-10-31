# SPDX-License-Identifier: GPL-3.0-or-later
"""P25 reflector record protocol, Phase 1 clear group voice only; not RF framing.

Record templates follow G4KLX P25Clients Voice.cpp (GPL-2.0-or-later).
Clear algorithm byte follows DroidStar p25.cpp (GPL-3.0-or-later).
"""
import re,time
SILENCE=bytes.fromhex('040cfd7bfb7df27b3d9e44')
END=b'\x80'+bytes(16)
OFFSETS=(10,1,5,5,5,5,5,5,4,10,1,5,5,5,5,5,5,4)
LENGTHS=(22,14,17,17,17,17,17,17,16,22,14,17,17,17,17,17,17,16)
def callsign(call):
    if not isinstance(call,str) or not re.fullmatch(r'[A-Z0-9/ -]{1,10}',call) or not call.strip():raise ValueError('Invalid P25 callsign')
    return call.encode('ascii').ljust(10,b' ')
def identity(n):
    if type(n) is not int or not 1<=n<=0xffffff:raise ValueError('P25 ID must be 1..16777215')
    return n.to_bytes(3,'big')
def record(index,raw,source,target):
    identity(source);identity(target)
    if type(index) is not int or not 0<=index<18 or not isinstance(raw,bytes) or len(raw)!=11:raise ValueError('Invalid P25 voice frame')
    out=bytearray(LENGTHS[index]);out[0]=0x62+index
    if index in (0,9):out[1:10]=bytes.fromhex('02020c0b1264000080')
    elif index in (8,17):out[3]=2
    else:out[-1]=2
    metadata={3:identity(target),4:identity(source),5:bytes.fromhex('f09d6a'),6:bytes.fromhex('19d426'),7:bytes.fromhex('e0eb7b'),14:b'\x80\0\0',15:bytes.fromhex('acb8a4'),16:bytes.fromhex('9bdc75')}
    if index in metadata:out[1:4]=metadata[index]
    off=OFFSETS[index];out[off:off+11]=raw
    return bytes(out)
def valid_record(data):
    return isinstance(data,bytes) and bool(data) and ((0x62<=data[0]<=0x73 and len(data)==LENGTHS[data[0]-0x62]) or data==END)
def cycle(records,target):
    """Validate all metadata before releasing any of a 360-ms cycle to audio."""
    if len(records)!=18 or any(not valid_record(d) or d[0]!=0x62+i for i,d in enumerate(records)):raise ValueError('Incomplete or unordered P25 cycle')
    if records[2][1:4]!=bytes(3):raise ValueError('Only standard clear group voice is supported')
    if records[3][1:4]!=identity(target):raise ValueError('Wrong P25 target')
    source=int.from_bytes(records[4][1:4],'big');identity(source)
    if records[14][1:4]!=b'\x80\0\0' or any(any(records[i][1:4]) for i in (11,12,13)):raise ValueError('Encrypted/non-clear P25 voice unsupported')
    return source,[d[o:o+11] for d,o in zip(records,OFFSETS)]
class Peer:
    def __init__(self,endpoint,call,target,send,clock=time.monotonic):
        self.endpoint=endpoint;self.request=b'\xf0'+callsign(call);self.unlink=b'\xf1'+callsign(call)
        self.send=send;self.clock=clock;self.state='stopped';self.last=0;self.next=0
    def start(self):
        if self.state!='stopped':raise ValueError('Create a fresh P25 peer')
        self.state='connecting';self.last=self.clock();self.next=self.last+5;self.send(self.request,self.endpoint)
    def receive(self,data,endpoint):
        if endpoint!=self.endpoint or self.state not in ('connecting','connected'):return None
        if data==self.request:self.state='connected';self.last=self.clock()
        elif self.state=='connected' and valid_record(data):return data
        return None
    def tick(self):
        if self.state not in ('connecting','connected'):return
        now=self.clock()
        if now-self.last>=15:self.state='failed'
        elif now>=self.next:self.send(self.request,self.endpoint);self.next=now+5
    def voice(self,data):
        if self.state!='connected' or not valid_record(data):raise ValueError('P25 peer unavailable or invalid record')
        self.send(data,self.endpoint)
    def close(self):
        if self.state in ('connecting','connected'):self.send(self.unlink,self.endpoint)
        self.state='stopped'
