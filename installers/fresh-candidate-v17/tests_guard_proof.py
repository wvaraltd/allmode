import hashlib,json,os,pathlib,tempfile,time,unittest
from unittest.mock import patch
import guard_proof as g
class GuardProof(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name);self.owner=os.getuid();self.calls=[];self.action=None;self.result='no'
  for path in ('run/systemd/system','usr/lib/systemd/system/mmdvm_bridge.service.d','etc/allmode','proc/sys/kernel/random'):(self.root/path).mkdir(parents=True,exist_ok=True)
  (self.root/'proc/sys/kernel/random/boot_id').write_text('11111111-2222-3333-4444-555555555555\n')
  self.fragment='/usr/lib/systemd/system/mmdvm_bridge.service';self.drop=self.fragment+'.d/ara-allmode-owner.conf'
  (self.root/self.fragment[1:]).write_text('[Unit]\nRequires=netcheck.service\nAfter=netcheck.service\n[Service]\nExecStart=/opt/MMDVM_Bridge/MMDVM_Bridge\n')
  (self.root/self.drop[1:]).write_text('[Unit]\nConditionPathExists='+g.MARKER+'\n')
 def runner(self,argv,**kw):
  self.calls.append((argv,kw))
  if argv[0]=='busctl':
   if 'GetUnit' in argv:return json.dumps({'type':'o','data':['/org/freedesktop/systemd1/unit/'+argv[-1].replace('.','_2e')]})
   return json.dumps({'type':'a(sbbsi)','data':[['ConditionPathExists',False,False,g.MARKER,(-1 if 'guard-proof' in argv[4] else 0)]]})
  if argv[:2]==['systemctl','start']:
   if self.action and '-proof-' in argv[-1]:self.action(argv[-1])
   return ''
  if '--value' in argv:
   field=next(value.split('=',1)[1] for value in argv if value.startswith('--property='));unit=argv[-1]
   if unit==g.STOCK:return {'LoadState':'loaded','ActiveState':'inactive','MainPID':'0','FragmentPath':self.fragment,'DropInPaths':self.drop}[field]
   if '-anchor-' in unit:return {'LoadState':'not-found','ActiveState':'active','SubState':'exited','MainPID':'0'}[field]
   return {'LoadState':'not-found','ConditionResult':self.result,'ConditionTimestampMonotonic':'123','ActiveState':'inactive','MainPID':'0','ExecMainStartTimestampMonotonic':'0'}[field]
  return ''
 def prove(self):return g.prove(self.root,self.runner,self.owner)
 def test_success_is_distinct_semantic_proof_and_no_dependency_actions(self):
  proof=self.prove();g.validate(proof,g.snapshot(self.root,self.runner,self.owner))
  self.assertEqual(proof['kind'],'harmless-condition-semantics-not-stock-startup');self.assertEqual(list((self.root/'run/systemd/system').iterdir()),[])
  for argv,kw in self.calls:
   if argv[:2] in (['systemctl','start'],['systemctl','stop']):self.assertRegex(argv[-1],r'^ara-allmode-guard-(proof|anchor)-[0-9a-f]{32}\.service$');self.assertEqual(kw,{'timeout':20})
  self.assertNotIn(b'Requires=',g.FRAGMENT);self.assertNotIn(b'After=',g.FRAGMENT);self.assertIn(b'DefaultDependencies=no',g.FRAGMENT)
  self.assertNotIn('ConditionResult',proof['stock']);self.assertEqual(len(proof['stock']['config_sha256']),2)
 def test_false_proof_refuses_and_cleans_owned_file(self):
  self.result='yes'
  with self.assertRaisesRegex(ValueError,'did not skip'):self.prove()
  self.assertEqual(list((self.root/'run/systemd/system').iterdir()),[])
 def test_changed_probe_file_never_removed_or_stopped(self):
  self.action=lambda unit:(self.root/'run/systemd/system'/unit).write_text('changed')
  with self.assertRaisesRegex(ValueError,'file changed'):self.prove()
  self.assertEqual(len(list((self.root/'run/systemd/system').iterdir())),1)
  self.assertFalse(any(argv[:2]==['systemctl','stop'] and '-proof-' in argv[-1] for argv,_ in self.calls))
 def test_existing_file_collision_preserved(self):
  unit='ara-allmode-guard-proof-'+'a'*32+'.service';target=self.root/'run/systemd/system'/unit;target.write_text('existing')
  with patch.object(g.secrets,'token_hex',return_value='a'*32):
   with self.assertRaises(FileExistsError):self.prove()
  self.assertEqual(target.read_text(),'existing');self.assertFalse(any(argv[:2]==['systemctl','start'] for argv,_ in self.calls))
 def test_existing_dropin_collision_preserved(self):
  target=self.root/'run/systemd/system'/('ara-allmode-guard-proof-'+'a'*32+'.service.d');target.mkdir()
  with patch.object(g.secrets,'token_hex',return_value='a'*32):
   with self.assertRaisesRegex(ValueError,'drop-in collision'):self.prove()
  self.assertTrue(target.is_dir())
 def test_changed_actual_stock_configuration_refuses(self):
  self.action=lambda unit:(self.root/self.drop[1:]).write_text('[Unit]\nConditionPathExists='+g.MARKER+'\n#changed\n')
  with self.assertRaisesRegex(ValueError,'Stock state/config changed'):self.prove()
  self.assertEqual(list((self.root/'run/systemd/system').iterdir()),[])
 def test_marker_and_symlink_configuration_refuse(self):
  marker=self.root/g.MARKER[1:];marker.touch()
  with self.assertRaises(ValueError):self.prove()
  marker.unlink();target=self.root/self.drop[1:];target.unlink();target.symlink_to(self.root/self.fragment[1:])
  with self.assertRaises(OSError):self.prove()
 def test_proof_binding_freshness_semantics_and_cleanup_enforced(self):
  proof=self.prove();current=g.snapshot(self.root,self.runner,self.owner)
  for change in ({'created_at':time.time()-3601},{'kind':'stock-startup'},{'cleanup_complete':False},{'stock':{}},{'probe_unit':'mmdvm_bridge.service'},{'probe':{'ConditionResult':'no'}}):
   with self.assertRaises(ValueError):g.validate(dict(proof,**change),current)
 def test_anchor_retains_probe_without_pulling_other_units(self):
  proof=self.prove();starts=[argv[-1] for argv,_ in self.calls if argv[:2]==['systemctl','start']]
  self.assertEqual(starts,[proof['anchor_unit'],proof['probe_unit']])
  fragment=g.anchor_fragment(proof['probe_unit'])
  self.assertIn(('After='+proof['probe_unit']).encode(),fragment)
  for unsafe in (b'Wants=',b'Requires=',b'mmdvm_bridge',b'netcheck',b'asterisk',b'Install'):self.assertNotIn(unsafe,fragment)
  self.assertIn(b'RemainAfterExit=yes',fragment);self.assertIn(b'ExecStart=/usr/bin/true',fragment)
 def test_anchor_collision_preserved_and_probe_cleaned(self):
  token='b'*32;target=self.root/'run/systemd/system'/('ara-allmode-guard-anchor-'+token+'.service');target.write_text('existing-anchor')
  with patch.object(g.secrets,'token_hex',return_value=token):
   with self.assertRaises(FileExistsError):self.prove()
  self.assertEqual(target.read_text(),'existing-anchor');self.assertEqual(len(list(target.parent.iterdir())),1)
 def test_anchor_evidence_required(self):
  proof=self.prove()
  for change in ({'anchor_unit':'mmdvm_bridge.service'},{'anchor_state':{}},{'anchor_fragment_sha256':'wrong'}):
   with self.assertRaises(ValueError):g.validate(dict(proof,**change),proof['stock'])
 def test_prior_boot_proof_refused(self):
  proof=self.prove();(self.root/'proc/sys/kernel/random/boot_id').write_text('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n')
  with self.assertRaises(ValueError):g.validate(proof,g.snapshot(self.root,self.runner,self.owner))
 def test_unevaluated_default_or_gc_state_refused(self):
  proof=self.prove()
  for timestamp,conditions in [('0',proof['probe_conditions']),('123',[['ConditionPathExists',False,False,g.MARKER,0]])]:
   changed=dict(proof,probe=dict(proof['probe'],ConditionTimestampMonotonic=timestamp),probe_conditions=conditions)
   with self.assertRaises(ValueError):g.validate(changed,proof['stock'])
 def test_fifo_refused_without_blocking(self):
  target=self.root/self.drop[1:];target.unlink();os.mkfifo(target,0o600)
  with self.assertRaisesRegex(ValueError,'Untrusted proof/config'):g.read(self.root,self.drop,self.owner)
 def test_bounded_read_rejects_growth_and_path_replacement(self):
  for replace in (False,True):
   target=self.root/self.drop[1:];target.write_bytes(b'original')
   original_fdopen=g.os.fdopen
   class ChangingReader:
    def __init__(inner,fd,mode):inner.stream=original_fdopen(fd,mode)
    def __enter__(inner):return inner
    def __exit__(inner,*args):inner.stream.close()
    def fileno(inner):return inner.stream.fileno()
    def read(inner,limit):
     self.assertEqual(limit,1024*1024+1);data=inner.stream.read(limit)
     if replace:target.unlink();target.write_bytes(b'original')
     else:
      with target.open('ab') as append:append.write(b'growth')
     return data
   with patch.object(g.os,'fdopen',side_effect=ChangingReader):
    with self.assertRaisesRegex(ValueError,'changed during bounded read'):g.read(self.root,self.drop,self.owner)
 def test_symlink_runtime_directory_refused(self):
  path=self.root/'run/systemd/system';path.rmdir();path.symlink_to(self.root/'etc/allmode','proc/sys/kernel/random')
  with self.assertRaises(OSError):self.prove()
 def test_start_exception_still_cleans_exact_owned_file(self):
  def fail(unit):raise RuntimeError('synthetic start failure')
  self.action=fail
  with self.assertRaisesRegex(RuntimeError,'synthetic'):self.prove()
  self.assertEqual(list((self.root/'run/systemd/system').iterdir()),[])
if __name__=='__main__':unittest.main(verbosity=2)
