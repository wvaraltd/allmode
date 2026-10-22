import socket, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
import digital
from dstar_worker import Bridge, connect_packet, voice_packet, usrp_packet, parse_usrp

class FakeCodec:
 def encode(self,data,gain):return bytes(range(9))
 def decode(self,data,gain):return bytes(320)
 def close(self):pass

class DStarTests(unittest.TestCase):
 def test_radio_link_waits_for_matching_reflector_ack(self):
  from server import LiveController
  from unittest.mock import Mock
  node=LiveController('60670',True)
  node.run_cli=Mock(side_effect=lambda command:'STATISTICS\nNodes currently connected to us: <NONE>\n' if 'rpt stats' in command else '')
  stage=dict(mode='D-STAR',target='DCS001C',peer='1994',sent=False,deadline=time.monotonic()+60);node.stages=[stage]
  with patch.object(digital,'ready',return_value=True),patch.object(digital,'tune') as tune,patch.object(digital,'bridging',return_value=False),patch.object(digital,'available',return_value=['D-STAR']),patch.object(digital,'load',return_value={}):
   node.snapshot();self.assertFalse(stage['sent']);tune.assert_called_once()
   node.snapshot();tune.assert_called_once()
  with patch.object(digital,'ready',return_value=True),patch.object(digital,'bridging',return_value=False),patch.object(digital,'available',return_value=['D-STAR']),patch.object(digital,'load',side_effect=lambda name,default:{'confirmed':True,'target':'DCS001C'} if name=='dstar-status.json' else default):
   node.snapshot();self.assertTrue(stage['sent'])
  node.run_cli.assert_any_call('rpt cmd 60670 ilink 3 1994')
 def test_framing(self):
  self.assertEqual(len(connect_packet('WV8CH','C')),519)
  packet=voice_packet('WV8CH','DCS001C',123,21,bytes(9))
  self.assertEqual(len(packet),100);self.assertEqual(packet[7:15],b'DCS001 C')
  self.assertEqual(packet[43:45],b'\x00{');self.assertEqual(packet[45],0)
  self.assertEqual(voice_packet('WV8CH','XLX681A',123,0,bytes(9))[7:15],b'DCS681 A')
  self.assertEqual(parse_usrp(usrp_packet(1,True,bytes(320))),(True,bytes(320)))
  self.assertIsNone(parse_usrp(b'bad'))
 def test_ack_source_audio_and_unkey_watchdogs(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(digital,'RUN',Path(directory)):
   sink=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sink.bind(('127.0.0.1',0));sink.settimeout(.3)
   peer=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);peer.bind(('127.0.0.1',0));peer.settimeout(.3)
   bridge=Bridge('WV8CH',dict(tx=sink.getsockname()[1],rx=0,remote=0,tlv=0),FakeCodec())
   try:
    bridge.endpoint=peer.getsockname();bridge.target='DCS001C';now=time.monotonic()
    ack=b'WV8CH   CCACK\n'
    bridge.on_network(ack,('127.0.0.1',9999),now);self.assertFalse(bridge.confirmed)
    bridge.on_network(ack,peer.getsockname(),now);self.assertTrue(bridge.confirmed)
    bridge.next_ping=now+100
    bridge.transmit_gain=1.25
    with patch.object(bridge.codec,'encode',wraps=bridge.codec.encode) as encode:
     bridge.on_audio(usrp_packet(0,True,bytes(320)),now)
     self.assertEqual(encode.call_args.args[1],1.25)
    tx,_=peer.recvfrom(2048);self.assertEqual(tx[46:55],bytes(range(9)))
    bridge.tick(now+.6);end,_=peer.recvfrom(2048);self.assertTrue(end[45]&0x40)
    incoming=voice_packet('W1TEST','DCS001C',456,0,bytes(9))
    forwarded=bytearray(incoming);forwarded[7:15]=b'W1ABC  B'
    bridge.on_network(bytes(forwarded),('127.0.0.1',9999),now+1);self.assertEqual(len(bridge.rx_queue),0)
    incoming=bytes(forwarded)
    bridge.on_network(incoming,peer.getsockname(),now+1)
    bridge.on_network(incoming,peer.getsockname(),now+1);self.assertEqual(len(bridge.rx_queue),1)
    bridge.tick(now+1.07);audio,_=sink.recvfrom(2048);self.assertEqual(parse_usrp(audio),(True,bytes(320)))
    self.assertAlmostEqual(bridge.next_audio,now+1.08,places=5)
    bridge.tick(now+2.1);audio,_=sink.recvfrom(2048);self.assertEqual(parse_usrp(audio),(False,b''))
   finally:bridge.close();peer.close();sink.close()
 def test_dcs_validation_and_remote_selection(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(digital,'RUN',Path(directory)),patch('dstar_worker.hosts',return_value={'DCS001':'localhost'}),patch.object(digital.socket,'socket') as sock,patch.object(digital,'control') as control:
   self.assertEqual(digital.validate('D-STAR','dcs001 c','60670'),'DCS001C')
   for value in ['REF001C','DCS999C','DCS001;']:
    with self.assertRaises(ValueError):digital.validate('D-STAR',value,'60670')
   digital.tune('D-STAR','DCS001C');control.assert_not_called()
   sock.return_value.__enter__.return_value.sendto.assert_called_with(b'Link DCS001C',('127.0.0.1',6077))

if __name__=='__main__':unittest.main()
