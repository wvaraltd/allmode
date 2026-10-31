import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from onboarding import Onboarding,GROUPS
from operator_store import update_group,profiles,finish,completed
from operator_features import Features
from server import Controller
from web_auth import Auth

class OperatorTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.ob=Onboarding(self.root)
  update_group(self.ob,'station',dict(callsign='N0CALL',name='',location='',email=''))
 def test_independent_section_preserves_secrets(self):
  update_group(self.ob,'allstar',dict(enabled=True,node='123456',password='private-value'))
  result=update_group(self.ob,'allstar',dict(enabled=True,node='123457',password=''))
  self.assertEqual(self.ob.read()['allstar']['password'],'private-value')
  self.assertNotIn('private-value',json.dumps(result))
 def test_profile_restore_does_not_apply_services(self):
  profiles(self.ob,dict(action='save',name='Station A'))
  update_group(self.ob,'station',dict(callsign='N1TEST',name='',location='',email=''))
  profiles(self.ob,dict(action='restore',name='Station A'))
  self.assertEqual(self.ob.read()['station']['callsign'],'N0CALL')
  self.assertEqual(len(profiles(self.ob)['profiles']),2)
  with self.assertRaises(ValueError):profiles(self.ob,dict(action='save',name='../escape'))
 def test_completion_requires_evidence_and_persists(self):
  with self.assertRaises(ValueError):finish(self.ob)
  with patch.object(self.ob,'snapshot',return_value={'workflow':{'steps':[{'complete':True}]}}):finish(self.ob)
  self.assertTrue(completed(Onboarding(self.root)))
 def test_first_owner_claim_is_one_time(self):
  auth=Auth(self.root/'auth.json');self.assertTrue(auth.unclaimed)
  auth.claim('test-password-123');self.assertFalse(auth.unclaimed)
  with self.assertRaises(ValueError):auth.claim('another-password')
  self.assertNotIn('test-password',auth.path.read_text())
  auth.sessions['test']=1
  auth.change('test-password-123','replacement-password')
  self.assertFalse(auth.sessions)
 def test_profile_without_radio_clears_previous_draft_and_keeps_backup(self):
  from operator_store import atomic
  from sa818_hardware import PRESET
  profiles(self.ob,dict(action='save',name='No radio'))
  draft=dict(PRESET,rx='440.1000',tx='440.1000')
  atomic(self.root/'draft.json',draft)
  profiles(self.ob,dict(action='restore',name='No radio'))
  self.assertFalse((self.root/'draft.json').exists())
  backup=next((self.root/'profiles').glob('before-restore-*.json'))
  self.assertEqual(json.loads(backup.read_text())['radio'],draft)
 def test_first_owner_failure_keeps_claim_available(self):
  auth=Auth(self.root/'auth.json')
  (self.root/'os-owner-pending').touch()
  with patch('web_auth.OWNER_PENDING',self.root/'os-owner-pending'), patch('system_client.request',side_effect=OSError('unavailable')):
   with self.assertRaises(OSError):auth.claim('test-password-123')
  self.assertTrue(auth.unclaimed)
  self.assertFalse(auth.path.exists())
 def test_password_rejects_line_breaks(self):
  auth=Auth(self.root/'auth.json')
  with self.assertRaises(ValueError):auth.claim('password\nsecondline')
 def test_schedule_does_not_repeat_after_restart(self):
  controller=Controller();features=Features(self.root,controller)
  now=dt.datetime(2026,10,22,18,30,tzinfo=dt.timezone.utc)
  features.action(dict(action='add',label='Test net',timezone='UTC',time='18:30',days=[3],mode='AllStar',target='123456',operation='connect'))
  rule=features.snapshot()['rules'][0]
  self.assertFalse(rule['enabled'])
  features.action(dict(action='toggle',id=rule['id'],enabled=True));features.tick(now)
  self.assertEqual(controller.target,'123456')
  controller.command('disconnect',None)
  Features(self.root,controller).tick(now)
  self.assertIsNone(controller.target)
 def test_schedule_leaves_existing_link_alone(self):
  controller=Controller();controller.command('connect','654321')
  features=Features(self.root,controller)
  features.action(dict(action='add',label='Test',timezone='UTC',time='18:30',days=[3],mode='AllStar',target='123456',operation='connect'))
  rule=features.snapshot()['rules'][0];features.action(dict(action='toggle',id=rule['id'],enabled=True))
  features.tick(dt.datetime(2026,10,22,18,30,tzinfo=dt.timezone.utc))
  self.assertEqual(controller.target,'654321')

if __name__=='__main__':unittest.main()
