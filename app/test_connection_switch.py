import ast,re,threading,time,types,unittest
from pathlib import Path
from unittest.mock import Mock
source=(Path(__file__).parent/'server.py').read_text(encoding='utf-8');tree=ast.parse(source)
f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='connect_destination')
class Tests(unittest.TestCase):
 def setUp(self):
  self.d=types.SimpleNamespace(PROFILES={'D-STAR':{},'DMR':{}},PRIVATE={},validate=lambda m,v,n:v,request=Mock(),forwarding=Mock(),save=Mock(),peer=lambda m,v:v)
  ns=dict(re=re,time=time,digital=self.d,system_client=Mock());exec(compile(ast.Module(body=[f],type_ignores=[]),'switch','exec'),ns);self.go=ns['connect_destination']
  self.c=Mock();self.c.lock=threading.RLock();self.c.node='518581';self.state=dict(modes=['AllStar','D-STAR','DMR'],connected=True,targets=['529740'],active_connections=[{'mode':'AllStar','target':'529740'}],pending=False)
  self.c.snapshot.side_effect=[self.state,dict(self.state,connected=False,targets=[]),dict(self.state,connected=False,targets=[])]
 def test_replace(self):
  self.go(self.c,'AllStar','2000');self.c.stop_bridge.assert_called_once_with(['529740']);self.assertEqual(self.c.command.call_args_list[-1].args,('connect','2000'))
 def test_invalid_preserves(self):
  with self.assertRaises(ValueError):self.go(self.c,'AllStar','bad')
  self.c.stop_bridge.assert_not_called()
 def test_bridge_keeps_links(self):
  self.go(self.c,'AllStar','2000',allow_bridge=True);self.c.stop_bridge.assert_not_called();self.d.forwarding.assert_called_once_with(self.c,True);self.assertEqual(self.c.stages[0]['target'],'2000')
 def test_disconnect_timeout(self):
  self.c.snapshot.side_effect=None;self.c.snapshot.return_value=self.state
  with self.assertRaises(ValueError):self.go(self.c,'AllStar','2000',timeout=0)
  self.c.command.assert_not_called()
 def test_same_digital_rejected(self):
  self.state['active_connections']=[{'mode':'D-STAR','target':'REF030C'}]
  with self.assertRaises(ValueError):self.go(self.c,'D-STAR','REF001C',allow_bridge=True)
  self.d.forwarding.assert_not_called()
 def test_network_checked_before_disconnect(self):
  self.go.__globals__['system_client'].request.side_effect=ValueError('disabled')
  with self.assertRaises(ValueError):self.go(self.c,'DMR','91',network='BrandMeister')
  self.c.stop_bridge.assert_not_called()
if __name__ == "__main__": unittest.main()
