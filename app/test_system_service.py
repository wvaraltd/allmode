import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import system_service as service
from onboarding import GROUPS
class SystemTests(unittest.TestCase):
 def setUp(self):
  self.config={g:{k:d for k,_,_,d in rows} for g,rows in GROUPS.items()}
  self.config['station']['callsign']='W1AW'
  self.config['allstar'].update(enabled=True,node='12345',password='node-test')
  self.templates={name:'[general]\n\n[node-main](!)\n\n[1999](node-main)\nrxchannel=SimpleUSB/1999\n' for name in service.FILES}
  self.templates['modules.conf']='[modules]\nnoload = chan_echolink.so\nnoload = chan_usrp.so\n'
 def test_hub_check_never_selects_radio(self):
  node,files=service.render(self.config,self.templates)
  self.assertEqual(node,'12345');self.assertIn('rxchannel = Local/pseudo',files['rpt.conf'])
  self.assertNotIn('SimpleUSB/',files['rpt.conf'])
  self.assertIn('12345:node-test@register.allstarlink.org',files['rpt_http_registrations.conf'])
  self.assertIn('noload = chan_echolink.so',files['modules.conf'])
 def test_radio_and_identity_are_consistent(self):
  _,files=service.render(self.config,self.templates,True)
  self.assertIn('[12345](node-main)',files['rpt.conf']);self.assertIn('SimpleUSB/12345',files['rpt.conf'])
  self.assertIn('[12345](node-main)',files['simpleusb.conf']);self.assertIn('rxmixerset=650',files['simpleusb.conf'])
  self.assertNotIn('[1999]',files['rpt.conf'])
 def test_injection_and_reserved_nodes_rejected(self):
  for group,key,value in [('station','name','bad;directive'),('allstar','password','pass@host'),('allstar','node','1994')]:
   c=copy.deepcopy(self.config);c[group][key]=value
   with self.assertRaises(ValueError):service.render(c,self.templates)
 def test_external_ambe_validation(self):
  self.config['dstar'].update(enabled=True,host='192.0.2.10',port=2460)
  self.assertEqual(service.normalized(self.config)['dstar']['host'],'192.0.2.10')
  self.config['dstar']['port']=0
  with self.assertRaises(ValueError):service.normalized(self.config)
 def test_failed_start_restores_every_config(self):
  import contextlib
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);etc=root/'etc';etc.mkdir();state=root/'state'
   for name,text in self.templates.items():(etc/name).write_text(text)
   def execute(argv,**kw):
    if argv==['systemctl','start','asterisk']:raise ValueError('startup failed')
    return ''
   def write(path,text,*args):path.write_text(text)
   with patch.object(service,'runtime_config'),patch.object(service,'RUN',root/'runtime'),patch.object(service,'ETC',etc),patch.object(service,'STATE',state),patch.object(service,'active',return_value=False),patch.object(service,'run',side_effect=execute),patch.object(service,'radio_lock',contextlib.nullcontext),patch.object(service,'atomic',side_effect=write):
    with self.assertRaisesRegex(ValueError,'restored'):service.install_config(self.config)
   self.assertEqual({n:(etc/n).read_text() for n in service.FILES},self.templates)
   self.assertFalse((state/'state.json').exists())
 def test_late_failure_restores_private_state_and_runtime(self):
  import contextlib
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);etc=root/'etc';etc.mkdir();state=root/'state';state.mkdir();runtime=root/'runtime';runtime.mkdir()
   for name,text in self.templates.items():(etc/name).write_text(text)
   prior={'node':'54321','radio':False}
   (state/'state.json').write_text(json.dumps(prior));(state/'config.json').write_text('old config')
   (runtime/'digital-modes.json').write_text('[]')
   def execute(argv,**kw):
    if argv==['systemctl','enable','asterisk']:raise ValueError('late failure')
    return ''
   def runtime_write(config):(runtime/'digital-modes.json').write_text('["D-STAR"]')
   def write(path,text,*args):path.write_text(text)
   with patch.object(service,'ETC',etc),patch.object(service,'STATE',state),patch.object(service,'RUN',runtime),patch.object(service,'active',return_value=False),patch.object(service,'run',side_effect=execute),patch.object(service,'cli',return_value='STATISTICS'),patch.object(service,'runtime_config',side_effect=runtime_write),patch.object(service,'radio_lock',contextlib.nullcontext),patch.object(service,'atomic',side_effect=write):
    with self.assertRaisesRegex(ValueError,'restored'):service.install_config(self.config)
   self.assertEqual(json.loads((state/'state.json').read_text()),prior)
   self.assertEqual((state/'config.json').read_text(),'old config')
   self.assertEqual((runtime/'digital-modes.json').read_text(),'[]')
   self.assertEqual({n:(etc/n).read_text() for n in service.FILES},self.templates)
 def test_detects_external_config_change(self):
  import hashlib
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);file=root/'rpt.conf';file.write_bytes(b'original')
   state={'config_hashes':{'rpt.conf':hashlib.sha256(b'original').hexdigest()}}
   with patch.object(service,'ETC',root):
    self.assertEqual(service.config_drift(state),[])
    file.write_bytes(b'changed')
    self.assertEqual(service.config_drift(state),['rpt.conf'])
if __name__=='__main__':unittest.main()
