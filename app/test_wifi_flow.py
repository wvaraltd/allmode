"""Wi-Fi save/connect behavior; every network command and privileged write mocked."""
import configparser,json,os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import system_service as s

class WiFiFlowTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.writes=[]
  def write(path,text,*args):path.parent.mkdir(exist_ok=True);path.write_text(text);path.chmod(0o600);self.writes.append((path,text))
  for p in (patch.object(s,'WIFI_PROFILES',self.root),patch.object(s,'WIFI_ROOT_UID',os.geteuid()),patch.object(s,'atomic',side_effect=write),patch.object(s.shutil,'which',side_effect=lambda n:'/usr/bin/'+n)):
   p.start();self.addCleanup(p.stop)
  self.runner=patch.object(s,'run',return_value='');self.run=self.runner.start();self.addCleanup(self.runner.stop)
 def save(self,**values):return s.handle(dict(action='wifi-save',ssid='Synthetic Network',password='test-only-password',**values))
 def profile(self,result):
  p=configparser.RawConfigParser();p.read(self.root/('ara-'+result['id']+'.nmconnection'));return p
 def test_scan_strict_security_and_escaped_names(self):
  self.run.return_value='Synthetic\\:One:81:WPA2\nSynthetic\\\\Path:63:WPA1 WPA2\nOpen synthetic:45:--\nHidden enterprise:88:WPA2 802.1X\nWep synthetic:11:WEP\nNew synthetic:90:WPA3\nUnknown synthetic:50:UNKNOWN\n:44:WPA2\nBad:101:WPA2\n'
  result=s.handle({'action':'wifi-scan'})['networks'];self.assertEqual(len(result),7)
  self.assertEqual(result[0]['ssid'],'Synthetic:One');self.assertEqual(result[1]['ssid'],'Synthetic\\Path')
  self.assertEqual([x['security_mode'] for x in result],['wpa-psk','wpa-psk','open',None,None,None,None])
  self.assertTrue(all(x['unsupported_reason'] for x in result[3:]));self.assertFalse(self.writes)
 def test_known_mixed_personal_and_open_only(self):
  for raw in ('WPA','WPA1','WPA2','WPA1 WPA2','WPA2 WPA3'):self.assertEqual(s.wifi_security(raw)[0],'wpa-psk')
  for raw in ('','--'):self.assertEqual(s.wifi_security(raw)[0],'open')
  for raw in ('WPA3','WPA2-EAP','WPA2 802.1X','WEP','SAE','OWE','NONE','WPA2 unknown'):self.assertIsNone(s.wifi_security(raw)[0])
 def test_legacy_default_save_is_wpa_only_no_autoconnect(self):
  result=self.save();p=self.profile(result)
  self.assertEqual(p['wifi-security']['key-mgmt'],'wpa-psk');self.assertEqual(p['connection']['autoconnect'],'false');self.assertEqual(p['wifi']['hidden'],'false')
  self.assertFalse(result['scheduled']);self.assertFalse(result['connected']);self.assertEqual(self.run.call_count,1)
  self.assertEqual(self.run.call_args.args[0][:3],['/usr/bin/nmcli','connection','load'])
 def test_open_has_no_security_section_or_secret(self):
  result=s.handle(dict(action='wifi-save',ssid='Synthetic Open',password='',security='open',hidden=False))
  self.assertFalse(self.profile(result).has_section('wifi-security'));self.assertNotIn('psk',self.writes[0][1])
 def test_hidden_and_exact_ssid_bytes(self):
  name=' 12;34;\\:雪 '
  result=s.handle(dict(action='wifi-save',ssid=name,password='test-password',hidden=True))
  p=self.profile(result);self.assertEqual(p['wifi']['hidden'],'true')
  self.assertEqual(bytes(int(x) for x in p['wifi']['ssid'].split(';') if x).decode('utf-8'),name)
 def test_keyfile_password_escape_and_no_argv_or_response_secret(self):
  secret=' test\\password '
  result=s.handle(dict(action='wifi-save',ssid='Synthetic',password=secret,security='wpa-psk',connect=True))
  self.assertEqual(self.profile(result)['wifi-security']['psk'],r'\stest\\password\s')
  self.assertNotIn(secret,repr(self.run.call_args_list));self.assertNotIn(secret,json.dumps(result))
  self.assertTrue(result['scheduled']);self.assertFalse(result['connected']);self.assertIn('not yet verified',result['message'])
  self.assertEqual(self.writes[0][0].stat().st_mode&0o777,0o600)
 def test_connect_preflight_missing_scheduler_no_profile_writes(self):
  with patch.object(s.shutil,'which',side_effect=lambda n:'/usr/bin/nmcli' if n=='nmcli' else None):
   with self.assertRaisesRegex(ValueError,'systemd-run is unavailable'):self.save(connect=True)
  self.assertFalse(self.writes);self.run.assert_not_called()
 def test_missing_nmcli_blocks_all_wifi_actions(self):
  for action in ('wifi-scan','wifi-save','wifi-connect'):
   with patch.object(s.shutil,'which',return_value=None):
    with self.assertRaisesRegex(ValueError,'nmcli is unavailable'):s.handle({'action':action})
  self.assertFalse(self.writes);self.run.assert_not_called()
 def test_unsupported_security_bad_flags_and_open_secret_rejected(self):
  cases=[dict(security='wpa-eap'),dict(security='sae'),dict(security='wep'),dict(security=None),dict(hidden='true'),dict(connect=1),dict(security='open')]
  for kw in cases:
   with self.subTest(kw=kw),self.assertRaises(ValueError):self.save(**kw)
  self.assertFalse(self.writes);self.run.assert_not_called()
 def test_bad_names_passwords_rejected(self):
  for name in ('','x'*33,'雪'*11,'bad\nSSID','bad\x00SSID','bad\x7fSSID'):
   with self.assertRaises(ValueError):s.handle(dict(action='wifi-save',ssid=name,password='test-only-password'))
  for secret in ('short','x'*64,'nonascii雪password','bad\npassword',None):
   with self.assertRaises(ValueError):s.handle(dict(action='wifi-save',ssid='Synthetic',password=secret))
  self.assertFalse(self.writes);self.run.assert_not_called()
 def test_hex_key_accepted(self):self.assertTrue(s.handle(dict(action='wifi-save',ssid='Synthetic',password='ab'*32))['ok'])
 def test_one_explicit_connect_fixed_scheduler_argv(self):
  result=self.save(connect=True);uid=result['id'];calls=[c.args[0] for c in self.run.call_args_list]
  self.assertEqual(calls[1],['/usr/bin/nmcli','connection','modify','uuid',uid,'connection.autoconnect','yes'])
  self.assertEqual(calls[2],['/usr/bin/systemd-run','--quiet','--on-active=3s','/usr/bin/nmcli','connection','up','uuid',uid])
  self.assertEqual(len(calls),3);self.assertIn('autoconnect = false',self.writes[0][1])
 def test_old_connect_uuid_only_and_preserves_existing_files(self):
  result=self.save();prior=self.writes[0][0].read_bytes();self.run.reset_mock()
  reply=s.handle(dict(action='wifi-connect',id=result['id']));self.assertTrue(reply['scheduled']);self.assertEqual(self.writes[0][0].read_bytes(),prior)
  for uid in ('../private','a'*36,'00000000-0000-0000-0000-000000000000'):
   with self.assertRaises(ValueError):s.handle(dict(action='wifi-connect',id=uid))
 def test_symlink_or_insecure_profile_rejected(self):
  result=self.save();path=self.writes[0][0];path.chmod(0o644)
  with self.assertRaises(ValueError):s.handle(dict(action='wifi-connect',id=result['id']))
  path.chmod(0o600);other=path.with_suffix('.saved');path.rename(other);path.symlink_to(other)
  with self.assertRaises(ValueError):s.handle(dict(action='wifi-connect',id=result['id']))
 def test_profile_collision_never_overwrites(self):
  uid=uuid.UUID('12345678-1234-4234-8234-123456789abc');path=self.root/('ara-'+str(uid)+'.nmconnection');path.write_text('existing-private-profile')
  with patch.object(uuid,'uuid4',return_value=uid):
   with self.assertRaisesRegex(ValueError,'collision'):self.save()
  self.assertEqual(path.read_text(),'existing-private-profile');self.assertFalse(self.writes);self.run.assert_not_called()
 def test_scheduler_failure_restores_prior_autoconnect(self):
  result=self.save();self.run.reset_mock()
  def fail(argv,**kw):
   if 'systemd-run' in argv[0]:raise ValueError('scheduler failed')
   return ''
  self.run.side_effect=fail
  with self.assertRaisesRegex(ValueError,'prior automatic-connection setting was restored'):s.handle(dict(action='wifi-connect',id=result['id']))
  self.assertEqual(self.run.call_args.args[0][-1],'no')
 def test_load_failure_does_not_schedule_or_enable(self):
  self.run.side_effect=ValueError('load failed')
  with self.assertRaisesRegex(ValueError,'profile was saved.*loading it was not confirmed'):self.save(connect=True)
  self.assertEqual(self.run.call_count,1);self.assertIn('autoconnect = false',self.writes[0][1])
 def test_scheduler_timeout_is_uncertain_not_false_failure_or_success(self):
  import subprocess
  result=self.save();self.run.reset_mock()
  def uncertain(argv,**kw):
   if 'systemd-run' in argv[0]:raise subprocess.TimeoutExpired(argv,3)
   return ''
  self.run.side_effect=uncertain
  with self.assertRaisesRegex(ValueError,'not confirmed.*queued switch may still occur'):s.handle(dict(action='wifi-connect',id=result['id']))
  self.assertEqual(self.run.call_count,3)
if __name__=='__main__':unittest.main()
