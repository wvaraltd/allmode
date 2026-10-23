import socket,threading,struct,unittest
from dstar_hardware import HardwareCodec
class AmbeUDPTests(unittest.TestCase):
 def test_real_udp_handshake_and_silent_frame_exchange(self):
  sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',0));sock.settimeout(2)
  seen=[];errors=[]
  def serve():
   try:
    for _ in range(5):
     data,peer=sock.recvfrom(2048);seen.append(data)
     if data[3]==0:
      command=data[4];payload=(b'\x30AMBE3000\0' if command==0x30 else bytes([command,0]));kind=0
     elif data[3]==2:payload=b'\x01\x48'+bytes(9);kind=1
     else:payload=b'\x00\xa0'+bytes(320);kind=2
     sock.sendto(b'\x61'+len(payload).to_bytes(2,'big')+bytes([kind])+payload,peer)
   except Exception as error:errors.append(error)
  thread=threading.Thread(target=serve);thread.start()
  try:
   codec=HardwareCodec('127.0.0.1',sock.getsockname()[1])
   try:self.assertEqual(codec.decode(codec.encode(bytes(320),1),1),bytes(320))
   finally:codec.close()
  finally:thread.join(3);sock.close()
  self.assertEqual(errors,[]);self.assertEqual(len(seen),5)
if __name__=='__main__':unittest.main()
