"""D-Plus dongle protocol, checked against nostar/DroidStar ref.cpp.
REF sends multiple modules; a validated header selects the requested module.
"""
import secrets, struct

CONNECT=bytes.fromhex('0500180001')
DISCONNECT=bytes.fromhex('0500180000')
PING=bytes.fromhex('036000')

def crc(data):
 value=0xffff
 for byte in data:
  value^=byte
  for _ in range(8):value=(value>>1)^0x8408 if value&1 else value>>1
 return ((~value)&0xffff).to_bytes(2,'little')

def prefix(length,kind,stream):
 return bytes([length,0x80])+b'DSVT'+bytes([kind,0,0,0,0x20,0,2,1])+struct.pack('!H',stream)

def header(call,terminal,target,stream):
 station=call.encode().ljust(7,b' ')+terminal.encode()
 body=b'\0\0\0'+(target[:6]+' '+target[-1]).encode()+station+b'CQCQCQ  '+station+b'ALMD'
 return prefix(58,0x10,stream)+b'\x80'+body+crc(body)

def frame(stream,number,voice,end=False):
 slow=b'\x55\x2d\x16' if number%21==0 else bytes.fromhex('1629f5')
 if end:return prefix(32,0x20,stream)+bytes([number%21|0x40])+bytes(9)+bytes.fromhex('55555555c87a')
 return prefix(29,0x20,stream)+bytes([number%21])+voice+slow

class RefProtocol:
 def __init__(self,bridge,terminal):
  if len(terminal)!=1 or terminal not in ' ABCDEFGHIJKLMNOPQRSTUVWXYZ':raise ValueError('Invalid D-STAR terminal suffix')
  self.b=bridge;self.terminal=terminal;self.writable=False;self.rx_sequence=None
 def send(self,data):self.b.network.sendto(data,self.b.endpoint)
 def connect(self):self.writable=False;self.rx_sequence=None;self.send(CONNECT)
 def transmit(self,voice,end=False):
  b=self.b
  if not self.writable:return
  if not end and b.tx_number%21==0:self.send(header(b.call,self.terminal,b.target,b.tx_stream))
  self.send(frame(b.tx_stream,b.tx_number,voice,end))
 def network(self,data,now):
  b=self.b
  if data==CONNECT:
   serial=('HS'+str(secrets.randbelow(900000)+100000)).encode()
   self.send(bytes.fromhex('1cc00400')+b.call.encode().ljust(8,b'\0')+bytes(8)+serial)
  elif len(data)==8 and data[:4]==bytes.fromhex('08c00400'):
   result=data[4:]
   if result in (b'OKRW',b'OKRO'):
    self.writable=result==b'OKRW';b.confirmed=True;b.last_network=now
    b.status='REF login confirmed'+(' (transmit enabled)' if self.writable else ' (receive only)');b.publish()
   else:
    b.unlink();b.status='REF login rejected: '+result.decode('ascii',errors='replace');b.publish()
  elif data==DISCONNECT:
   b.unlink();b.status='REF disconnected by server';b.publish()
  elif b.confirmed and data==PING:b.last_network=now
  elif b.confirmed and len(data) in (58,29,32) and data[1:6]==b'\x80DSVT':
   b.last_network=now
   if b.tx_stream:return
   stream=data[14:16]
   if len(data)==58:
    if data[6]!=0x10 or crc(data[17:56])!=data[56:58]:return
    target=(b.target[:6]+' '+b.target[-1]).encode()
    if target not in (data[20:28],data[28:36]):return
    station=b.call.encode().ljust(7,b' ')+self.terminal.encode()
    if data[44:52] in (station,b.call.encode().ljust(8,b' ')):return
    if b.rx_stream not in (None,stream) and now-b.last_rx<1:return
    if stream!=b.rx_stream:
     b.rx_queue.clear();b.rx_stream=stream;b.next_audio=now+.06;self.rx_sequence=None
     print('REF voice header received for '+b.target,flush=True)
    b.last_rx=now
   elif data[6]==0x20 and stream==b.rx_stream:
    sequence=data[16]&0x1f
    if sequence>20:return
    end=len(data)==32 or bool(data[16]&0x40)
    if sequence==self.rx_sequence and not end:return
    self.rx_sequence=sequence;b.last_rx=now
    if len(b.rx_queue)>=25:b.rx_queue.clear();b.next_audio=now
    b.rx_queue.append(None if end else data[17:26])
