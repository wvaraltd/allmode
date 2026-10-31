# SPDX-License-Identifier: GPL-3.0-or-later
"""M17 reflector UDP stream, clear Codec2 3200 only (type=5 + CAN).

Strict full IP-payload CRC, as official pyM17 IPFrame.calculate_crc.
No legacy zero/LSF-only CRC bypass, encryption, signatures or packet mode.
"""
import re,time
ALPHABET=' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/.'
def address(call):
    if not isinstance(call,str) or not 1<=len(call)<=9 or not call.strip() or any(c not in ALPHABET for c in call):raise ValueError('M17 callsign must be 1..9 uppercase M17 characters')
    value=0
    for c in reversed(call):value=value*40+ALPHABET.index(c)
    return value.to_bytes(6,'big')
def decode_address(data):
    if len(data)!=6:raise ValueError('Invalid M17 address')
    value=int.from_bytes(data,'big')
    if not 0<value<40**9:raise ValueError('Reserved or broadcast source address')
    result=''
    while value:value,i=divmod(value,40);result+=ALPHABET[i]
    return result
def destination(target):
    if not isinstance(target,str) or not re.fullmatch(r'M17-[A-Z0-9]{3} [A-Z]',target):raise ValueError('Enter M17 reflector and module, e.g. M17-ABC A')
    return address(target[:7].ljust(8)+target[-1])
def crc(data):
    value=0xffff
    for b in data:
        value^=b<<8
        for _ in range(8):value=((value<<1)^ (0x5935 if value&0x8000 else 0))&0xffff
    return value
def lsf(source,target,can=0):
    if type(can) is not int or not 0<=can<=15:raise ValueError('Invalid M17 CAN')
    return destination(target)+address(source)+((can<<7)|5).to_bytes(2,'big')+bytes(14)
def packet(source,target,stream,sequence,payload,can=0,end=False):
    if type(stream) is not int or not 1<=stream<=65535 or type(sequence) is not int or not 0<=sequence<32768:raise ValueError('Invalid M17 stream/sequence')
    if not isinstance(payload,bytes) or len(payload)!=16 or type(end) is not bool:raise ValueError('Invalid M17 payload')
    body=lsf(source,target,can)+(sequence|(0x8000 if end else 0)).to_bytes(2,'big')+payload
    return b'M17 '+stream.to_bytes(2,'big')+body+crc(body).to_bytes(2,'big')
def parse(data,target,can=0):
    if not isinstance(data,bytes) or len(data)!=54 or data[:4]!=b'M17 ' or crc(data[6:52])!=int.from_bytes(data[52:],'big'):return None
    try:
        if data[6:12] not in (destination(target),b'\xff'*6) or int.from_bytes(data[18:20],'big')!=(can<<7)|5 or any(data[20:34]):return None
        source=decode_address(data[12:18]);stream=int.from_bytes(data[4:6],'big');fn=int.from_bytes(data[34:36],'big')
        if not stream:return None
        return dict(source=source,stream=stream,sequence=fn&32767,end=bool(fn&32768),payload=data[36:52],lsf=data[6:34])
    except ValueError:return None
class Peer:
    def __init__(self,endpoint,call,target,send,clock=time.monotonic):
        destination(target);self.endpoint=endpoint;self.call=address(call);self.send=send;self.clock=clock
        self.request=b'CONN'+self.call+target[-1].encode();self.state='stopped';self.last=0;self.note=None
    def start(self):
        if self.state!='stopped':raise ValueError('Create a fresh M17 peer')
        self.state='connecting';self.last=self.clock();self.send(self.request,self.endpoint)
    def receive(self,data,endpoint):
        if endpoint!=self.endpoint or self.state not in ('connecting','connected'):return None
        if data==b'NACK':self.state='failed';self.note='M17 reflector refused connection'
        elif data==b'ACKN' and self.state=='connecting':self.state='connected';self.last=self.clock()
        elif data==b'DISC':self.state='failed';self.note='M17 reflector disconnected'
        elif data[:4]==b'PING' and len(data)==10 and self.state=='connected':
            try:decode_address(data[4:])
            except ValueError:return None
            self.last=self.clock();self.send(b'PONG'+self.call,self.endpoint)
        elif self.state=='connected' and len(data)==54 and data[:4]==b'M17 ':return data
        return None
    def tick(self):
        if self.state in ('connecting','connected') and self.clock()-self.last>=(10 if self.state=='connecting' else 30):self.state='failed';self.note='M17 peer timed out'
    def voice(self,data):
        if self.state!='connected' or len(data)!=54 or data[:4]!=b'M17 ':raise ValueError('M17 peer unavailable or invalid frame')
        self.send(data,self.endpoint)
    def close(self):
        if self.state in ('connecting','connected'):self.send(b'DISC'+self.call,self.endpoint)
        self.state='stopped'
