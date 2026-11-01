import hashlib, importlib.util, json, os, pathlib, subprocess, tempfile, unittest
P=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('launch',P/'launch.py');launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)
class Packaging(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.addCleanup(self.tmp.cleanup)
 def config(self,c):
  f=self.root/'config.json';f.write_text(json.dumps(c));return launch.arguments(f)
 def test_generic_config(self):
  c=json.loads((P/'config.json').read_text());self.assertIn('--managed',self.config(c));self.assertNotIn('--auth-file',self.config(c))
 def test_two_independent_users(self):
  for origin,port in [('https://station-one.example',8788),('https://station-two.example',9898)]:
   c=json.loads((P/'config.json').read_text());c.update(public_origin=origin,port=port,auth_file='/var/lib/allmode/auth.json',lan_proxy=True)
   args=self.config(c);self.assertIn(origin,args);self.assertIn(str(port),args)
 def test_legacy_lan_origin_list_preserved(self):
  c=json.loads((P/'config.json').read_text());origin='https://station-one.local,https://station-one'
  c.update(public_origin=origin,port=8788,auth_file='/var/lib/allmode/auth.json',lan_proxy=True)
  self.assertIn(origin,self.config(c))
 def test_origin_list_rejects_any_unsafe_member(self):
  c=json.loads((P/'config.json').read_text());c.update(auth_file='/var/lib/allmode/auth.json',lan_proxy=True)
  for origin in ['https://good.local,http://remote.example','https://good.local,','https://good.local,https://u:p@host','https://good.local, https://host','https://good.local,https://host:99999']:
   with self.subTest(origin=origin),self.assertRaises(ValueError):self.config(dict(c,public_origin=origin))
 def test_invalid_configuration(self):
  base=json.loads((P/'config.json').read_text())
  for changes in [{'port':True},{'port':22},{'hardware':'yes'},{'public_origin':'http://remote.example'},{'auth_file':'/etc/shadow'},{'public_origin':'https://u:p@foo'},{'extra':'injection'}]:
   with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):self.config(dict(base,**changes))
 def scripts(self,active=''):
  bindir=self.root/'bin';bindir.mkdir(exist_ok=True);log=self.root/'calls'
  for name in ['systemctl','install','getent','id','addgroup','adduser','systemd-tmpfiles']:
   f=bindir/name;f.write_text('#!/bin/sh\necho "'+name+' $*" >> "$LOG"\n'+('if [ "$1" = is-active ]; then [ "$3" = "$ACTIVE" ]; else exit 0; fi\n' if name=='systemctl' else 'exit 0\n'));f.chmod(0o755)
  return dict(os.environ,PATH=str(bindir)+':/usr/bin:/bin',LOG=str(log),ACTIVE=active),log
 def isolated_preinst(self):
  # Only the test copy redirects host unit inspection; installed script unchanged.
  script=self.root/'preinst';script.write_text((P/'preinst').read_text().replace('/etc/systemd/system/',str(self.root/'systemd-units')+'/'));return script
 def test_idle_preinst_allows_install_and_upgrade(self):
  env,_=self.scripts()
  for action in ['install','upgrade']:subprocess.run(['sh',str(self.isolated_preinst()),action],env=env,check=True,capture_output=True)
 def test_active_preinst_refuses_without_stopping(self):
  for unit in ['asterisk','allmode-setup','allmode-system','allmode-digital']:
   env,log=self.scripts(unit+'.service');r=subprocess.run(['sh',str(self.isolated_preinst()),'upgrade'],env=env,capture_output=True)
   self.assertNotEqual(r.returncode,0);self.assertNotIn('stop',log.read_text())
 def test_legacy_shadow_unit_refused_in_isolated_fixture(self):
  env,_=self.scripts();units=self.root/'systemd-units';units.mkdir();(units/'allmode-setup.service').write_text('[Service]\n')
  r=subprocess.run(['sh',str(self.isolated_preinst()),'upgrade'],env=env,capture_output=True)
  self.assertNotEqual(r.returncode,0);self.assertIn(b'legacy',r.stderr)
 def test_postinst_preserves_upgrade_fixtures(self):
  # Real shell lifecycle, mocked privileged mutators; NEVER executes host installer.
  state=self.root/'state';state.mkdir()
  for name,value in {'favorites.json':{'schema':1,'revision':3,'items':['first']},'rf-memories.json':{'active':4,'revision':9},'program.json':{'frequency':'145.500','calibration':17},'credentials.json':{'password':'synthetic-only'},'second-user.json':{'node':'TEST-SECOND','frequency':'433.500'}}.items():(state/name).write_text(json.dumps(value))
  before={p.name:p.read_bytes() for p in state.iterdir()};env,log=self.scripts()
  for _ in range(2):subprocess.run(['sh','-c',(P/'postinst').read_text().replace('/usr/bin/python3 /usr/libexec/ara-allmode/secure-dirs.py','true'),'postinst','configure','0.7'],env=env,check=True,capture_output=True)
  self.assertEqual(before,{p.name:p.read_bytes() for p in state.iterdir()})
  calls=log.read_text();self.assertNotIn('systemctl start',calls);self.assertNotIn('systemctl restart',calls);self.assertNotIn('systemctl enable',calls)
 def test_lifecycle_contains_no_package_operations_or_destructive_writes(self):
  for name in ['preinst','postinst','postrm','prerm']:
   s=(P/name).read_text()
   for prohibited in ['apt-get ','apt upgrade','curl ','wget ','rm -rf','chown -R','install.sh']:self.assertNotIn(prohibited,s)
 def test_release_rejects_nonarm_host(self):
  if subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()=='arm64':self.skipTest('ARM host')
  r=subprocess.run(['python3',str(P/'build-package.py'),'--source',str(self.root),'--output',str(self.root/'out'),'--release'],capture_output=True)
  self.assertNotEqual(r.returncode,0);self.assertIn(b'native Debian 13 ARM64',r.stderr)

class Maintenance(unittest.TestCase):
 def test_transaction_is_strictly_allmode_only(self):
  spec=importlib.util.spec_from_file_location('maintenance',P/'maintenance-upgrade.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  self.assertEqual(module.transaction_allowed('Inst ara-allmode (0.8 example)\nConf ara-allmode',{'ara-allmode'}),['ara-allmode'])
  for output in ['Inst asl3-asterisk (new)\n','Remv ara-allmode [old]\n','Inst libc6 (new)\n']:
   with self.assertRaises(ValueError):module.transaction_allowed(output,{'ara-allmode'})
 def test_no_automatic_radio_stop_or_resume(self):
  text=(P/'maintenance-upgrade.py').read_text()
  self.assertNotIn("['systemctl','stop','asterisk",text)
  self.assertNotIn("['systemctl','start','asterisk",text)

 def test_durable_journal_replaces_complete_json_privately(self):
  spec=importlib.util.spec_from_file_location('maintenance',P/'maintenance-upgrade.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as directory:
   path=pathlib.Path(directory)/'journal.json'
   for phase in ['prepared','backed-up','installed','config-validated','console-restored-radio-stopped']:
    module.durable_json(path,{'phase':phase,'versions_before':{'ara-allmode':'installed old'}})
    self.assertEqual(json.loads(path.read_text())['phase'],phase)
    self.assertEqual(path.stat().st_mode&0o777,0o600)
   self.assertEqual(len(list(path.parent.iterdir())),1)

class SecureDirectories(unittest.TestCase):
 def helper(self):
  spec=importlib.util.spec_from_file_location('dirs',P/'secure-dirs.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
 def test_symlink_target_is_not_chowned_or_chmodded(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t);target=root/'private';target.mkdir(mode=0o700);link=root/'locks';link.symlink_to(target,target_is_directory=True)
   with self.assertRaises(OSError):self.helper().ensure_directory(str(link),os.getuid(),os.getgid(),0o755)
   self.assertEqual(target.stat().st_mode&0o777,0o700)
 def test_real_directory_setup_preserves_all_state_files(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t)/'state'
   self.helper().ensure_directory(str(root),os.getuid(),os.getgid(),0o750)
   for name in ['favorites.json','rf-isolation.json','credentials.json','program.json','calibration.json']:(root/name).write_text('synthetic-'+name)
   before={x.name:x.read_bytes() for x in root.iterdir()}
   for _ in range(2):self.helper().ensure_directory(str(root),os.getuid(),os.getgid(),0o750)
   self.assertEqual(before,{x.name:x.read_bytes() for x in root.iterdir()})

class DvSwitchGuard(unittest.TestCase):
 def test_removal_refuses_enabled_upstream_without_starting_or_stopping(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t)
   subprocess.run(['python3',str(P/'build-dvswitch-addon.py'),'--output',t],check=True,capture_output=True)
   script=root/'guard-stage/DEBIAN/prerm'
   bindir=root/'bin';bindir.mkdir();tool=bindir/'systemctl'
   tool.write_text('#!/bin/sh\necho "$*" >> "$LOG"\nif [ "$1" = is-enabled ] && [ "$ENABLED" = yes ]; then exit 0; fi\nexit 1\n');tool.chmod(0o755)
   for enabled,expected in [('yes',1),('no',0)]:
    env=dict(os.environ,PATH=str(bindir)+':/usr/bin:/bin',LOG=str(root/'calls'),ENABLED=enabled)
    r=subprocess.run(['sh',str(script),'remove'],env=env,capture_output=True)
    self.assertEqual(r.returncode,expected)
   calls=(root/'calls').read_text();self.assertNotIn('start ',calls);self.assertNotIn('stop ',calls)

if __name__=='__main__':unittest.main(verbosity=2)
