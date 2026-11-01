import sys,time,guard_proof,hashlib,importlib.util,json,os,pathlib,tempfile,unittest
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('profile',P/'provision-fresh-profile.py');profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
class FreshProfile(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name)
  for path in ['etc/allmode','opt/MMDVM_Bridge',*profile.STATE_DIRS]:(self.root/path).mkdir(parents=True,exist_ok=True)
  binary=self.root/'opt/MMDVM_Bridge/MMDVM_Bridge';binary.write_bytes(b'synthetic-binary');binary.chmod(0o755)
  self.report=self.root/'report.json';self.data=[dict(cycle=i,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),scope='loopback-only; no RF; architecture aarch64',pass_=True,authenticated=True,rx_voice_golden=True,tx_voice_matches_codec=True,owned_exporter=True) for i in range(2)];self.save()
  self.current={'test_only_actual_stock':'unchanged'};self.evidence={'schema':1,'kind':'harmless-condition-semantics-not-stock-startup','created_at':time.time(),'stock':self.current,'probe_unit':'ara-allmode-guard-proof-'+'a'*32+'.service','fragment_sha256':hashlib.sha256(guard_proof.FRAGMENT).hexdigest(),'probe_conditions':[['ConditionPathExists',False,False,guard_proof.MARKER,-1]],'probe':{'ConditionResult':'no','ConditionTimestampMonotonic':'123','ActiveState':'inactive','MainPID':'0','ExecMainStartTimestampMonotonic':'0'},'cleanup_complete':True,'anchor_unit':'ara-allmode-guard-anchor-'+'a'*32+'.service','anchor_fragment_sha256':hashlib.sha256(guard_proof.anchor_fragment('ara-allmode-guard-proof-'+'a'*32+'.service')).hexdigest(),'anchor_state':{'ActiveState':'active','SubState':'exited','MainPID':'0'}}
 def save(self):self.report.write_text(json.dumps(self.data));self.report.chmod(0o600)
 def call(self,apply=True,package=lambda n:'installed',service=None):
  service=service or (lambda u,f:{'ActiveState':'inactive','LoadState':'loaded','ConditionResult':'no'}[f])
  profile.provision(self.root,self.report,package,service,apply,owner=os.getuid(),guard_evidence=self.evidence,guard_snapshot=lambda:self.current)
 def test_cli_guard_proof_fifo_rejected_before_provisioning(self):
  folder=self.root/'proof';folder.mkdir();path=folder/'evidence.json';os.mkfifo(path,0o600)
  actual_read=guard_proof.read
  def read(root,absolute,owner):
   self.assertEqual(root,pathlib.Path('/'));self.assertEqual(absolute,str(path))
   return actual_read(self.root,'/proof/evidence.json',os.getuid())
  with patch.object(sys,'argv',['profile','--validation-report',str(self.report),'--guard-proof',str(path),'--apply']),patch.object(profile.os,'geteuid',return_value=0),patch.object(guard_proof,'read',side_effect=read),patch.object(profile,'provision') as provision:
   with self.assertRaisesRegex(SystemExit,'Untrusted proof/config'):profile.main()
  provision.assert_not_called();self.assertFalse((self.root/'etc/allmode/install-profile.json').exists())
 def test_cli_guard_proof_replacement_rejected_before_provisioning(self):
  folder=self.root/'proof';folder.mkdir();path=folder/'evidence.json';path.write_text('{}')
  actual_read=guard_proof.read;actual_fdopen=guard_proof.os.fdopen
  class ReplacingReader:
   def __init__(inner,fd,mode):inner.stream=actual_fdopen(fd,mode)
   def __enter__(inner):return inner
   def __exit__(inner,*args):inner.stream.close()
   def fileno(inner):return inner.stream.fileno()
   def read(inner,limit):
    data=inner.stream.read(limit);path.unlink();path.write_text('{}');return data
  def read(root,absolute,owner):return actual_read(self.root,'/proof/evidence.json',os.getuid())
  with patch.object(sys,'argv',['profile','--validation-report',str(self.report),'--guard-proof',str(path),'--apply']),patch.object(profile.os,'geteuid',return_value=0),patch.object(guard_proof,'read',side_effect=read),patch.object(guard_proof.os,'fdopen',side_effect=ReplacingReader),patch.object(profile,'provision') as provision:
   with self.assertRaisesRegex(SystemExit,'changed during bounded read'):profile.main()
  provision.assert_not_called();self.assertFalse((self.root/'etc/allmode/install-profile.json').exists())
 def test_guard_evidence_binding_failure_prevents_marker(self):
  for field,value in [('stock',{}),('cleanup_complete',False),('created_at',time.time()-3601),('kind','stockConditionResult')]:
   old=self.evidence[field];self.evidence[field]=value
   with self.assertRaises(ValueError):self.call()
   self.assertFalse((self.root/'etc/allmode/install-profile.json').exists());self.evidence[field]=old
 def test_fresh_atomic_creation_and_no_overwrite(self):
  self.call(False);target=self.root/'etc/allmode/install-profile.json';self.assertFalse(target.exists())
  self.call();self.assertEqual(json.loads(target.read_text()),dict(version=1,dvswitch_dmr_default=True));self.assertEqual(target.stat().st_mode&0o777,0o644)
  with self.assertRaises(ValueError):self.call()
 def test_existing_user_state_all_types_preserved(self):
  for filename in ['station-setup.json','program.json','favorites.json','auth.json']:
   path=self.root/'var/lib/allmode'/filename;path.write_text('existing-'+filename)
   with self.assertRaises(ValueError):self.call()
   self.assertEqual(path.read_text(),'existing-'+filename);path.unlink()
 def test_protected_applied_state_refuses(self):
  (self.root/'var/lib/allmode-system/config.json').write_text('{}')
  with self.assertRaises(ValueError):self.call()
 def test_symlink_marker_never_followed(self):
  outside=self.root/'private';outside.write_text('unchanged');(self.root/'etc/allmode/install-profile.json').symlink_to(outside)
  with self.assertRaises(ValueError):self.call()
  self.assertEqual(outside.read_text(),'unchanged')
 def test_incomplete_packages_or_running_services_refuse(self):
  with self.assertRaises(ValueError):self.call(package=lambda n:'unpacked')
  with self.assertRaises(ValueError):self.call(service=lambda u,f:'active')
 def test_failed_wrong_binary_and_wrong_arch_report_refuse(self):
  for field,value in [('pass_',False),('binary_sha256','wrong'),('scope','loopback-only; no RF; architecture x86_64')]:
   old=self.data[0][field];self.data[0][field]=value;self.save()
   with self.assertRaises(ValueError):self.call()
   self.data[0][field]=old;self.save()
 def test_symlink_state_directory_refuses(self):
  folder=self.root/'var/lib/allmode';folder.rmdir();folder.symlink_to(self.root/'etc/allmode',target_is_directory=True)
  with self.assertRaises(OSError):self.call()
if __name__=='__main__':unittest.main(verbosity=2)
