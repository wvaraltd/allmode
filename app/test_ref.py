import socket,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import digital
from dstar_worker import Bridge,usrp_packet,parse_usrp
from dstar_ref import CONNECT,PING,header,frame,crc
from test_dstar import FakeCodec

class RefTests(unittest.TestCase):
 def test_crc_and_terminal_identity(self):
  self.assertEqual(crc(b'123456789'),bytes.fromhex('6e90'))
  h=header('N0CAL','Z','REF030C',42)
  self.assertEqual(len(h),58);self.assertEqual(h[20:28],b'REF030 C')
  self.assertEqual(h[44:52],b'N0CAL  Z');self.assertEqual(h[56:58],crc(h[17:56]))
  self.assertEqual(len(frame(42,0,bytes(9))),29);self.assertEqual(len(frame(42,1,b'',True)),32)
 def test_login_module_filter_voice_and_read_only(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(digital,'RUN',Path(directory)):
   peer=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);peer.bind(('127.0.0.1',0));peer.settimeout(.3)
   sink=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sink.bind(('127.0.0.1',0));sink.settimeout(.3)
   b=Bridge('N0CAL',dict(tx=sink.getsockname()[1],rx=0,remote=0,tlv=0),FakeCodec(),terminal='Z')
   try:
    now=time.monotonic();b.target='REF030C';b.endpoint=peer.getsockname();b.next_ping=now+100
    b.on_network(CONNECT,peer.getsockname(),now);login,_=peer.recvfrom(2048)
    self.assertEqual(len(login),28);self.assertEqual(login[4:12],b'N0CAL\0\0\0')
    ack=bytes.fromhex('08c00400')+b'OKRO';b.on_network(ack,peer.getsockname(),now)
    self.assertTrue(b.confirmed);self.assertFalse(b.ref.writable)
    b.on_audio(usrp_packet(0,True,bytes(320)),now);self.assertFalse(b.tx_stream)
    b.on_network(header('W1TEST',' ','REF030B',42),peer.getsockname(),now);self.assertIsNone(b.rx_stream)
    b.on_network(header('W1TEST',' ','REF030C',42),peer.getsockname(),now)
    b.on_network(frame(42,0,bytes(9)),peer.getsockname(),now)
    b.on_network(frame(42,0,bytes(9)),peer.getsockname(),now);self.assertEqual(len(b.rx_queue),1)
    b.tick(now+.07);packet,_=sink.recvfrom(2048);self.assertEqual(parse_usrp(packet),(True,bytes(320)))
    b.on_network(frame(42,1,b'',True),peer.getsockname(),now+.1);b.tick(now+.11)
    packet,_=sink.recvfrom(2048);self.assertEqual(parse_usrp(packet),(False,b''))
    b.on_network(bytes.fromhex('08c00400')+b'OKRW',peer.getsockname(),now+.2)
    b.on_audio(usrp_packet(1,True,bytes(320)),now+.3)
    h,_=peer.recvfrom(2048);v,_=peer.recvfrom(2048);self.assertEqual(len(h),58);self.assertEqual(len(v),29)
    self.assertEqual(h[44:52],b'N0CAL  Z')
    b.on_audio(usrp_packet(2,False),now+.4);e,_=peer.recvfrom(2048);self.assertEqual(len(e),32)
   finally:b.close();peer.close();sink.close()
 def test_ref_requires_installed_host(self):
  with patch('dstar_worker.hosts',return_value={'REF030':'ref030.dstargateway.org'}):
   self.assertEqual(digital.validate('D-STAR','ref030c','60670'),'REF030C')
   with self.assertRaises(ValueError):digital.validate('D-STAR','REF999C','60670')

if __name__=='__main__':unittest.main()
