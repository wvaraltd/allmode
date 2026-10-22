import unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
import setup_api as setup
class SetupTests(unittest.TestCase):
 def test_rejects_injection_and_unbounded_fields(self):
  for group,value in [('allstar',{'idrecording':'WV8CH\n[evil]'}),('usb',{'rxmixerset':1000}),('dmr',{'BMPassword':'x\nId=0'}),('allstar',{'file':'/etc/passwd'}),('radio',{'frequency':'nan'})]:
   with self.assertRaises(ValueError):setup.validate(group,value)
 def test_preserves_blank_password(self):
  self.assertEqual(setup.validate('dmr',{'TGIFPassword':'','BMPassword':''}),{})
 def test_dmr_network_passwords_are_separate(self):
  import digital
  node=Mock();node.node='60670';node.snapshot.return_value={'targets':[],'pending':False,'receiving':False}
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'MMDVM_Bridge').mkdir()
   (root/'MMDVM_Bridge/allmode-tgif.ini').write_text('[General]\nCallsign=WV8CH\nId=315401099\n[DMR]\nColorCode=1\n[DMR Network]\nPassword=old-tgif\n')
   with patch.object(setup,'DMR',root),patch.object(setup,'RUN',root),patch.object(digital,'RUN',root):
    with self.assertRaises(ValueError):setup.save(node,{'group':'dmr','values':{'Network':'BrandMeister'}})
    self.assertFalse((root/'dmr-networks.json').exists())
    setup.save(node,{'group':'dmr','values':{'Network':'BrandMeister','BMPassword':'new-bm'}})
    setup.save(node,{'group':'dmr','values':{'Network':'TGIF','TGIFPassword':'','BMPassword':''}})
    account=digital.load('dmr-networks.json',{})
    self.assertEqual(account['TGIFPassword'],'old-tgif');self.assertEqual(account['BMPassword'],'new-bm');self.assertEqual(account['Network'],'TGIF')
 def test_writes_only_selected_section_and_backs_up(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);p=root/'rpt.conf';original='[node-main](!)\ntotime = 180000\n[60670](node-main)\nhangtime = 100\n[1999](node-main)\nhangtime = 0\n';p.write_text(original)
   with patch.object(setup,'RUN',root):setup.write_section(p,'60670',{'hangtime':'200','totime':'240000'})
   self.assertEqual(setup.section(p.read_text(),'60670')['totime'],'240000')
   self.assertEqual(setup.section(p.read_text(),'1999')['hangtime'],'0')
   self.assertEqual(next((root/'backups').iterdir()).read_text(),original)
 def test_connected_node_blocks_config_changes(self):
  node=Mock();node.snapshot.return_value={'targets':['1999'],'pending':False,'receiving':False}
  with self.assertRaises(ValueError):setup.save(node,{'group':'usb','values':{'rxmixerset':'500'}})
  node.run_cli.assert_not_called()
 def test_usb_uses_fixed_cli_and_persists(self):
  node=Mock();node.node='60670';node.snapshot.return_value={'targets':[],'pending':False,'receiving':False}
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'simpleusb.conf').write_text('[60670]\nrxmixerset=650\n')
   with patch.object(setup,'RUN',root),patch.object(setup,'AST',root):setup.save(node,{'group':'usb','values':{'rxmixerset':'650'}})
  self.assertEqual([c.args[0] for c in node.run_cli.call_args_list],['susb active 60670','susb tune rx 650','susb tune save'])
 def test_radio_requires_hardware_acknowledgement(self):
  node=Mock();node.snapshot.return_value={'targets':[],'pending':False,'receiving':False}
  request={'group':'radio','values':{'frequency':'433.5','tone':'100.0','squelch':'4','bandwidth':'1'}}
  from contextlib import nullcontext
  with patch('radio_readback.serial_lock',side_effect=nullcontext),patch.object(setup.subprocess,'run',return_value=Mock(returncode=0,stdout='',stderr='SA818 programming error')):
   with self.assertRaises(ValueError):setup.save(node,request)
 def test_choice_values_are_allowlisted(self):
  self.assertEqual(setup.validate('usb-options',{'carrierfrom':'usbinvert'})['carrierfrom'],'usbinvert')
  with self.assertRaises(ValueError):setup.validate('usb-options',{'carrierfrom':'unknown'})
if __name__=='__main__':unittest.main()
