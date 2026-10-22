import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import digital
from server import LiveController
class DigitalTests(unittest.TestCase):
 def test_audio_is_saved_per_mode_and_only_sent_to_selected_adapter(self):
  node=LiveController('60670',True);node.snapshot=Mock(return_value={})
  with tempfile.TemporaryDirectory() as directory,patch.object(digital,'RUN',Path(directory)),patch.object(digital,'ready',return_value=True),patch.object(digital,'control') as control:
   digital.save('audio.json',{'receive':1.25,'transmit':1})
   node.command('audio',{'mode':'D-STAR','receive':2,'transmit':1.5})
   self.assertEqual(digital.audio('DMR'),{'receive':1.25,'transmit':1})
   self.assertEqual(digital.audio('D-STAR'),{'receive':2,'transmit':1.5})
   self.assertTrue(all(call.args[0]=='D-STAR' for call in control.call_args_list))
   node.command('audio',{'mode':'D-STAR','receive':1,'transmit':1})
   self.assertEqual(digital.audio('DMR')['receive'],1.25)
   before=digital.load('audio-modes.json',{})
   for value in [float('nan'),float('inf'),True,0.2,4.1]:
    with self.assertRaises(ValueError):node.command('audio',{'mode':'D-STAR','receive':value,'transmit':1})
   self.assertEqual(digital.load('audio-modes.json',{}),before)
 def test_legacy_gateway_command_is_normalised(self):
  from dmr_worker import gateway_command
  self.assertEqual(gateway_command(b'TalkGroup10'),b'TalkGroup 10')
  self.assertEqual(gateway_command(b'TalkGroup 3166'),b'TalkGroup 3166')
  self.assertIsNone(gateway_command(b'TalkGroup10;shutdown'))
 def test_p25_uses_encoder_and_normalising_relay(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(digital,'RUN',Path(directory)),patch.object(digital,'control') as control,patch.object(digital.socket,'socket') as socket:
   digital.tune('P25','10');control.assert_called_once_with('P25','txTg=10')
   socket.assert_not_called()
 def test_ysf_selection_does_not_send_invalid_numeric_tlv(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(digital,'RUN',Path(directory)),patch.object(digital,'control') as control,patch.object(digital.socket,'socket') as socket:
   digital.tune('YSF','03166')
   control.assert_not_called()
   socket.return_value.__enter__.return_value.sendto.assert_called_once_with(b'LinkYSF 03166',('127.0.0.1',6073))
 def test_ports_and_private_nodes_do_not_overlap(self):
  for key in ['node','tx','rx','tlv','mb']:
   values=[p[key] for p in digital.PROFILES.values()];self.assertEqual(len(values),len(set(values)))
 def test_bridge_stages_independent_selected_links(self):
  node=LiveController('60670',True);node.snapshot=Mock(return_value={})
  current={'targets':[],'pending':False,'modes':['AllStar','DMR']}
  with patch.object(digital,'forwarding') as forwarding,patch.object(digital,'save'),patch.object(digital,'request') as request:
   node.start_bridge({'enabled':True,'connections':[{'mode':'AllStar','target':'12345'},{'mode':'DMR','target':'30410'}]},current)
   forwarding.assert_called_once_with(node,True);request.assert_called_once_with(['DMR'])
  self.assertEqual([s['peer'] for s in node.stages],['12345','1999'])
 def test_destination_validation(self):
  for mode,target in [('AllStar','60670'),('AllStar','1998'),('AllStar','12345;shutdown'),('FCS','evil'),('DMR','0'),('NXDN','65536')]:
   with self.assertRaises(ValueError):digital.validate(mode,target,'60670')
  self.assertEqual(digital.validate('FCS','FCS00120','60670'),'00120')
 def test_reflector_must_exist_in_directory(self):
  with patch.object(digital,'catalog',return_value={'YSF':[{'target':'12345'}]}):
   self.assertEqual(digital.validate('YSF','12345','60670'),'12345')
   with self.assertRaises(ValueError):digital.validate('YSF','54321','60670')
 def test_bridge_validates_all_rows_before_enabling_forwarding(self):
  node=LiveController('60670',True);current={'targets':[],'pending':False,'modes':['AllStar','DMR']}
  with patch.object(digital,'forwarding') as enable:
   with self.assertRaises(ValueError):node.start_bridge({'enabled':True,'connections':[{'mode':'AllStar','target':'12345'},{'mode':'DMR','target':'bad'}]},current)
   enable.assert_not_called()
 def test_parrots_cannot_be_bridged(self):
  node=LiveController('60670',True);current={'targets':[],'pending':False,'modes':['DMR','NXDN']}
  with patch.object(digital,'catalog',return_value={'NXDN':[{'target':'10'}]}),patch.object(digital,'forwarding') as enable:
   with self.assertRaises(ValueError):node.start_bridge({'enabled':True,'connections':[{'mode':'DMR','target':'30410'},{'mode':'NXDN','target':'10'}]},current)
   enable.assert_not_called()
 def test_stop_disables_forwarding_before_disconnect(self):
  node=LiveController('60670',True);calls=[];node.run_cli=Mock(side_effect=lambda command:calls.append(command))
  with patch.object(digital,'bridging',return_value=True),patch.object(digital,'forwarding',side_effect=lambda *_:calls.append('forwarding off')),patch.object(digital,'request'),patch.object(digital,'unlink'):
   node.stop_bridge(['1999','12345'])
  self.assertEqual(calls[0],'forwarding off');self.assertIn('rpt cmd 60670 ilink 1 1999',calls)
if __name__=='__main__':unittest.main()
