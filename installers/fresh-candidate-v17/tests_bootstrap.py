import importlib.util,json,os,pathlib,tempfile,unittest
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bootstrap',P/'bootstrap.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
def fake_apt(versions,calls,architecture='arm64'):
 def runner(argv):
  calls.append(argv)
  if '-s' in argv:return ''.join(f'Inst {name} ({version} repo)\n' for name,version in versions.items())
  if '--download-only' in argv:
   folder=pathlib.Path(next(x.split('=',1)[1] for x in argv if x.startswith('Dir::Cache::archives=')))
   for name,version in versions.items():(folder/(name+'.deb')).write_text(json.dumps({'Package':name,'Version':version,'Architecture':architecture}))
  if argv[:2]==['dpkg-deb','-f']:return ''.join(k+': '+v+'\n' for k,v in json.loads(pathlib.Path(argv[2]).read_text()).items())
  if argv[:2]==['dpkg-query','-W']:return ''.join(name+'\t'+version+'\tinstalled\n' for name,version in sorted(versions.items()))
  if argv[:2]==['apt-cache','policy']:return 'Candidate: '+versions[argv[-1]]+'\n'
  return ''
 return runner

class Bootstrap(unittest.TestCase):
 def test_legacy_two_distinct_users_preserve_list_and_port(self):
  for name,port in [('station-one',8788),('station-two',9898)]:
   text=f'[Service]\nExecStart=/usr/bin/python3 /opt/allmode/server.py --managed --hardware\n[Service]\nExecStart=\nExecStart=/usr/bin/python3 /opt/allmode/server.py --managed --hardware --port {port} --auth-file /var/lib/allmode/auth.json --lan-proxy --public-origin https://{name}.local,https://{name}\n'
   c=b.legacy_config(text);self.assertEqual(c['port'],port);self.assertEqual(c['public_origin'],f'https://{name}.local,https://{name}')
   with tempfile.NamedTemporaryFile(mode='w') as f:json.dump(c,f);f.flush();args=b.launcher.arguments(f.name)
   self.assertIn(c['public_origin'],args)
 def test_generated_tunnel_uses_actual_ssh_destination(self):
  text=b.initial_access({'SUDO_USER':'operator','SSH_CONNECTION':'192.0.2.1 123 192.0.2.2 2222'})
  self.assertIn('operator@192.0.2.2',text);self.assertIn('ssh -p 2222',text);self.assertIn('http://127.0.0.1:8787/setup',text)
  self.assertNotIn('evil;',b.initial_access({'SUDO_USER':'evil;','SSH_CONNECTION':'192.0.2.1 123 192.0.2.2 2222'}))
 def test_resume_binds_all_executable_bundle_inputs(self):
  identity=b.bundle_identity();self.assertEqual(set(identity),{'bootstrap.py','provision-fresh-profile.py','verify-dvswitch-loopback.py','packaging/launch.py','guard_proof.py'});self.assertTrue(all(len(value)==64 for value in identity.values()))
 def test_release_manifest_matches_split_runtime_pins(self):
  packages=json.loads((P/'release-manifest.json').read_text())['packages']
  for name,version in {'ara-allmode':b.CORE,'ara-allmode-dvswitch':b.ADDON,'ara-allmode-dvswitch-guard':b.GUARD_PACKAGE,'ara-allmode-meter':b.METER,'dbus':b.DBUS}.items():self.assertEqual(packages[name]['version'],version)
  self.assertEqual(packages['ara-allmode']['sha256'],'0e97bd421ae0525d498a0cf44b87e68ae7b37425559f8df5e6b7cb81e4bba291')
 def test_asl_public_key_uses_commit_pinned_official_source(self):
  self.assertEqual(b.KEYS['allstarlink'],(b.ASL_KEY_URL,'F2AF416869932ABB39E165E5409D50181BD84509'))
  self.assertEqual(b.ASL_KEY_URL,'https://raw.githubusercontent.com/AllStarLink/asl-apt-repos/32d4dd6af2baf2d313ce15b6b27023cfafcc8030/allstarlink.gpg')
  self.assertEqual(b.ASL_KEY_SHA,'af652e0473ed95d73345a8c6912cb38ac29001b67c30ea767fa99fa7cbd5e9de')
  self.assertEqual(b.CORE,'0.8.0~beta9-7');self.assertEqual(b.ADDON,'0.8.0~beta9-2');self.assertEqual(b.GUARD_PACKAGE,'0.8.0~beta9-2')
 def test_trust_downloads_pinned_asl_key_without_deb_or_ua_change(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder)/'root';work=pathlib.Path(folder)/'work';root.mkdir();work.mkdir();downloads=[];commands=[]
   def get(url,target,sha=None):downloads.append((url,sha));pathlib.Path(target).write_bytes(b'public-key-fixture')
   def runner(command):
    commands.append(command)
    if '--show-keys' in command:
     name=pathlib.Path(command[-1]).stem;return 'pub:-:::::::::\nfpr:::::::::'+b.KEYS[name][1]+':\n'
    return ''
   def write(path,data,*args,**kwargs):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
   with patch.object(b,'get',side_effect=get),patch.object(b,'atomic_new',side_effect=write):b.trust(root,work,runner)
   self.assertIn((b.ASL_KEY_URL,b.ASL_KEY_SHA),downloads)
   self.assertFalse(any('.deb' in url for url,_ in downloads));self.assertFalse(any(command[0]=='dpkg-deb' for command in commands))
 def test_packaged_legacy_install_refused(self):
  for status in ('installed','unpacked','half-configured'):
   with self.assertRaises(ValueError):b.reject_packaged_migration(0,status)
  b.reject_packaged_migration(1,'');b.reject_packaged_migration(0,'config-files')
 def test_explicit_apt_authentication(self):
  calls=[];b.install({'ara-allmode':b.CORE},fake_apt({'ara-allmode':b.CORE},calls))
  for command in calls:
   if command[0]=='apt-get':
    self.assertIn('APT::Get::AllowUnauthenticated=false',command);self.assertIn('Acquire::AllowInsecureRepositories=false',command)
 def test_resume_rejects_unrecorded_partial_packages(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaises(ValueError):b.resume_pending_check(pathlib.Path(folder),lambda command:'unrelated\t1\thalf-configured\tarm64\n')
 def test_complex_or_unknown_legacy_options_refused(self):
  for args in ['--managed --bad x','--managed --port ${PORT}','--managed --port 8 --port 9']:
   with self.assertRaises(ValueError):b.legacy_config('[Service]\nExecStart=/usr/bin/python3 /opt/allmode/server.py '+args)
 def test_plan_refuses_removal_unrelated_upgrade_wrong_asl(self):
  for text in ['Remv unrelated [1]\n','Inst libc6 [old] (new stable)\n','Inst asl3-asterisk (wrong repo)\n']:
   with self.assertRaises(ValueError):b.solve(text,{})
 def test_install_pins_entire_simulated_closure_and_no_remove(self):
  calls=[];b.install({'ara-allmode':b.CORE},fake_apt({'ara-allmode':b.CORE,'python3-serial':'3.5-2'},calls))
  actual=next(c for c in calls if '--no-download' in c)
  self.assertIn('python3-serial=3.5-2',actual);self.assertIn('--no-remove',actual);self.assertFalse(any('upgrade' in c for c in calls))
  self.assertEqual(sum('-s' in c for c in calls),2)
 def test_downloaded_wrong_architecture_refused_before_install(self):
  calls=[]
  with self.assertRaises(ValueError):b.install({'ara-allmode':b.CORE},fake_apt({'ara-allmode':b.CORE},calls,'amd64'))
  self.assertFalse(any('--no-download' in c for c in calls))
 def test_revised_solver_closure_refused_before_download(self):
  calls=[]
  def runner(argv):
   calls.append(argv);return 'Inst ara-allmode (0.8.0~beta9-1 repo)\n'+('Inst added (1 repo)\n' if len(calls)>1 else '')
  with self.assertRaises(ValueError):b.install({'ara-allmode':b.CORE},runner)
  self.assertFalse(any('--download-only' in c for c in calls))
 def test_guard_rejects_trigger_negated_reset_unknown_conditions(self):
  marker='/etc/allmode/consent'
  b.guard_condition_json(json.dumps({'type':'a(sbbsi)','data':[['ConditionPathExists',False,False,marker,0]]}),marker)
  for data in [[],[['ConditionPathExists',True,False,marker,0]],[['ConditionPathExists',False,True,marker,0]],[['ConditionPathExists',False,False,'other',0]]]:
   with self.assertRaises(ValueError):b.guard_condition_json(json.dumps({'type':'a(sbbsi)','data':data}),marker)
  with self.assertRaises(ValueError):b.guard_condition_json('{}',marker)
 def test_exclusive_bootstrap_lock(self):
  with tempfile.TemporaryDirectory() as t:
   path=pathlib.Path(t)/'lock';fd=b.acquire_lock(path,os.getuid())
   try:
    with self.assertRaises(BlockingIOError):b.acquire_lock(path,os.getuid())
   finally:os.close(fd)
   fd=b.acquire_lock(path,os.getuid());os.close(fd)
 def test_missing_verifier_is_pinned_from_existing_system_repos(self):
  calls=[]
  with patch.object(b.shutil,'which',return_value=None),patch.object(b.pathlib.Path,'is_file',return_value=True):b.ensure_bootstrap_tools(fake_apt({'gpg':'2.4.7-1'},calls))
  self.assertEqual(calls[0][-1],'update');self.assertTrue(any('gpg=2.4.7-1' in c for c in calls))
 def test_only_known_legacy_enablement_link_is_retargeted(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t)/'root';work=pathlib.Path(t)/'private';work.mkdir()
   folder=root/'etc/systemd/system/multi-user.target.wants';folder.mkdir(parents=True)
   unit=root/'usr/lib/systemd/system/allmode-setup.service';unit.parent.mkdir(parents=True);unit.write_text('[Unit]\n')
   link=folder/'allmode-setup.service';link.symlink_to('/etc/systemd/system/allmode-setup.service')
   unrelated=folder/'custom.service';unrelated.symlink_to('/opt/custom.service')
   b.normalize_enablement_links(root,work,os.getuid())
   self.assertEqual(os.readlink(link),'/usr/lib/systemd/system/allmode-setup.service');self.assertEqual(os.readlink(unrelated),'/opt/custom.service')
   self.assertEqual(len(json.loads((work/'enablement-links.json').read_text())),1)
   b.normalize_enablement_links(root,work,os.getuid());self.assertEqual(len(json.loads((work/'enablement-links.json').read_text())),1)
 def test_snapshot_preserves_group_writable_data_and_detects_mode_change(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t);folder=root/'var/lib/allmode';folder.mkdir(parents=True);file=folder/'favorites.json';file.write_text('fixture');file.chmod(0o660)
   before=b.state_hashes(root);item=before['var/lib/allmode/favorites.json'];self.assertEqual(item['mode'],0o660);self.assertEqual(item['uid'],os.getuid());self.assertEqual(item['gid'],os.getgid())
   file.chmod(0o600);self.assertNotEqual(before,b.state_hashes(root))
 def test_native_wrapper_readable_under_private_umask(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t);validation=root/'validation';validation.mkdir();work=root/'work';work.mkdir();safe=b.atomic_new
   def runner(argv):
    if argv[:2]==['id','-u']:return str(os.getuid())
    if argv[:2]==['id','-g']:return str(os.getgid())
    self.assertEqual((validation/'source').stat().st_mode&0o777,0o755)
    result=validation/'result';result.mkdir();(result/'loopback-results.json').write_text('[]');return ''
   old=os.umask(0o077)
   try:
    with patch.object(b.tempfile,'mkdtemp',return_value=str(validation)),patch.object(b.os,'chown'),patch.object(b,'atomic_new',side_effect=lambda path,data,mode:safe(path,data,mode,owner=os.getuid())):report=b.native_validation(work,runner)
   finally:os.umask(old)
   self.assertTrue(report.exists());self.assertFalse(validation.exists())
 def test_primary_fingerprint_only(self):
  text='pub:-:::::::::\nfpr:::::::::PRIMARY:\nsub:-:::::::::\nfpr:::::::::SUBKEY:\n'
  self.assertEqual(b.fingerprints(text),['PRIMARY'])
 def test_atomic_file_refuses_symlink_and_preserves_other_content(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t);p=root/'key';b.atomic_new(p,b'key',owner=os.getuid());b.atomic_new(p,b'key',owner=os.getuid())
   with self.assertRaises(ValueError):b.atomic_new(p,b'other',owner=os.getuid())
   p.unlink();target=root/'target';target.write_text('unchanged');p.symlink_to(target)
   with self.assertRaises(OSError):b.atomic_new(p,b'new',owner=os.getuid())
   self.assertEqual(target.read_text(),'unchanged')
 def test_migrate_code_preserves_state_and_rf_cleanup(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t)/'root';work=pathlib.Path(t)/'backup';work.mkdir()
   for name in ['opt/allmode','opt/allmode-vocoder-prototype','var/lib/allmode','etc/systemd/system/allmode-setup.service.d']:(root/name).mkdir(parents=True,exist_ok=True)
   (root/'opt/allmode/old.py').write_text('old');(root/'var/lib/allmode/auth.json').write_text('synthetic-secret')
   for name in ['lan.conf','runtime.conf','rf-memories.conf']:(root/'etc/systemd/system/allmode-setup.service.d'/name).write_text(name)
   before=b.state_hashes(root);b.migrate_code(root,work)
   self.assertEqual(before,b.state_hashes(root));self.assertTrue((work/'legacy/opt/allmode/old.py').exists());self.assertTrue((root/'etc/systemd/system/allmode-setup.service.d/rf-memories.conf').exists())
   self.assertFalse((root/'opt/allmode').exists())
 def test_journal_is_private_and_phase_updates(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t)
   for phase in ['prepared','backed-up','failed-radio-not-resumed']:b.write_journal(root,{'phase':phase});self.assertEqual(json.loads((root/'journal.json').read_text())['phase'],phase)
   self.assertEqual((root/'journal.json').stat().st_mode&0o777,0o600)
class SystemBus(unittest.TestCase):
 def test_available_bus_is_read_only(self):
  calls=[];b.ensure_system_bus(lambda argv:calls.append(argv) or '')
  self.assertEqual(len(calls),1);self.assertEqual(calls[0][-1],'Ping');self.assertIn('--system',calls[0])
 def test_existing_broken_bus_is_not_restarted_or_reinstalled(self):
  calls=[]
  def runner(argv):
   calls.append(argv)
   if argv[0]=='busctl':raise RuntimeError('missing transport')
   return 'dbus\tinstalled\n'
  with self.assertRaisesRegex(ValueError,'repair its service explicitly'):b.ensure_system_bus(runner)
  self.assertEqual([argv[0] for argv in calls],['busctl','dpkg-query'])
 def test_missing_bus_installs_exact_signed_bounded_prerequisite_then_checks(self):
  calls=[];probes=0
  def runner(argv):
   nonlocal probes
   calls.append(argv)
   if argv[0]=='busctl':
    probes+=1
    if probes==1:raise RuntimeError('missing transport')
   return ''
  with patch.object(b,'install') as install:b.ensure_system_bus(runner)
  install.assert_called_once_with({'dbus':'1.16.2-2'},runner,allowed_new=b.DBUS_NEW)
  self.assertEqual(probes,2)
  start=['systemctl','start','dbus.socket','dbus.service'];self.assertEqual(calls.count(start),1)
  self.assertLess(calls.index(start),len(calls)-1);self.assertEqual(calls[-1][-1],'Ping')
  self.assertFalse(any('restart' in c or 'enable' in c or 'unmask' in c for c in calls))
  update=next(argv for argv in calls if argv[0]=='apt-get');self.assertIn('APT::Get::AllowUnauthenticated=false',update)
 def test_bus_install_failure_does_not_start_any_service(self):
  calls=[]
  def runner(argv):
   calls.append(argv)
   if argv[0]=='busctl':raise RuntimeError('missing transport')
   return ''
  with patch.object(b,'install',side_effect=ValueError('rejected closure')):
   with self.assertRaisesRegex(ValueError,'rejected closure'):b.ensure_system_bus(runner)
  self.assertFalse(any(c[0]=='systemctl' for c in calls))
 def test_new_bus_install_start_ping_exact_order(self):
  events=[];probes=0
  def runner(argv):
   nonlocal probes
   events.append(argv)
   if argv[0]=='busctl':
    probes+=1
    if probes==1:raise RuntimeError('missing transport')
   return ''
  with patch.object(b,'install',side_effect=lambda *args,**kwargs:events.append(['OWN_AUTHENTICATED_INSTALL'])):b.ensure_system_bus(runner)
  self.assertEqual(events[-3:],[['OWN_AUTHENTICATED_INSTALL'],['systemctl','start','dbus.socket','dbus.service'],['busctl','--system','--timeout=15s','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.DBus.Peer','Ping']])
 def test_install_does_not_silently_repair_unavailable_bus(self):
  def runner(argv):
   if argv[0]=='busctl':raise RuntimeError('missing transport')
   return ''
  with patch.object(b,'install'):
   with self.assertRaisesRegex(ValueError,'no guards changed'):b.ensure_system_bus(runner)
 def test_unrelated_dependency_and_existing_upgrade_refused(self):
  for plan in ('Inst unrelated (1 repo)\n','Inst libc6 [2.41-1] (2.41-2 repo)\n'):
   calls=[]
   def runner(argv):calls.append(argv);return plan
   with self.assertRaises(ValueError):b.install({'dbus':b.DBUS},runner,allowed_new=b.DBUS_NEW)
   self.assertEqual(len(calls),1);self.assertIn('-s',calls[0])
 def test_missing_bus_failure_precedes_app_stop_backup_and_guard_mutation(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder)/'root';root.mkdir();work=pathlib.Path(folder)/'private';work.mkdir();calls=[]
   def runner(argv):calls.append(argv);return 'inactive\n'
   with patch.object(b,'ensure_system_bus',side_effect=ValueError('missing bus')),patch.object(b,'atomic_new') as write,patch.object(b,'backup') as backup:
    with self.assertRaisesRegex(ValueError,'missing bus'):b.orchestrate(root,work,'fresh',runner=runner)
   write.assert_not_called();backup.assert_not_called()
   self.assertFalse(any('stop' in argv or 'start' in argv or 'daemon-reload' in argv for argv in calls))
   self.assertFalse(any(root.rglob('*.conf')))
   journal=json.loads((work/'journal.json').read_text());self.assertEqual(journal['failed_phase'],'prepared');self.assertFalse(journal['radio_resumed'])

class Orchestration(unittest.TestCase):
 def fixture(self,mode,fail=False):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=pathlib.Path(temp.name)/'root';work=pathlib.Path(temp.name)/'private';root.mkdir();work.mkdir()
  (root/'etc/allmode').mkdir(parents=True)
  events=[]
  def runner(argv):
   events.append(('command',argv))
   if argv[0]=='busctl':
    if 'call' in argv:return json.dumps({'type':'o','data':['/org/freedesktop/systemd1/unit/'+argv[-1].replace('.','_2e')]})
    marker='/etc/allmode/permit-asterisk-during-bootstrap' if 'asterisk' in argv[4] else '/etc/allmode/allow-upstream-mmdvm-service'
    return json.dumps({'type':'a(sbbsi)','data':[['ConditionPathExists',False,False,marker,0]]})
   if '--property=LoadState' in argv:return 'not-found\n'
   if '--property=ActiveState' in argv:return 'inactive\n'
   if '--property=ConditionResult' in argv:return 'no\n'
   return ''
  def install(packages,runner):
   events.append(('install',dict(packages)))
   if 'ara-allmode-dvswitch-guard' in packages:
    file=root/'usr/lib/systemd/system/mmdvm_bridge.service.d/ara-allmode-owner.conf';file.parent.mkdir(parents=True);file.write_text('[Unit]\nConditionPathExists=/etc/allmode/allow-upstream-mmdvm-service\n')
   if fail and 'ara-allmode' in packages:raise RuntimeError('Synthetic package failure')
  def write(path,data,*args,**kwargs):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
  config=dict(schema=1,port=8788,public_origin='https://example.local,https://example',auth_file='/var/lib/allmode/auth.json',hardware=True,lan_proxy=True)
  with patch.object(b.guard_proof,'prove',return_value={'test_only_mock':True}),patch.object(b,'ensure_bootstrap_tools'),patch.object(b,'trust',side_effect=lambda *args:events.append(('trust',None))),patch.object(b,'backup',side_effect=lambda *args:events.append(('backup',None))),patch.object(b,'install',side_effect=install),patch.object(b,'atomic_new',side_effect=write),patch.object(b,'native_validation',return_value=work/'report.json'),patch.object(b,'normalize_enablement_links'),patch.object(b.profile,'regular_bytes',side_effect=lambda path,owner:(path.read_bytes(),None)):
   if fail:
    with self.assertRaises(RuntimeError):b.orchestrate(root,work,mode,config,runner)
   else:b.orchestrate(root,work,mode,config,runner)
  return root,work,events
 def test_fresh_transaction_order_and_no_radio_resume(self):
  root,work,events=self.fixture('fresh')
  ping=next(i for i,e in enumerate(events) if e[0]=='command' and e[1][-1]=='Ping');self.assertLess(ping,events.index(('backup',None)))
  installs=[e[1] for e in events if e[0]=='install'];self.assertEqual(list(installs[0]),['ara-allmode-dvswitch-guard']);self.assertEqual(installs[1],b.UPSTREAM);self.assertIn('ara-allmode',installs[2])
  self.assertLess(events.index(('backup',None)),events.index(('trust',None)))
  commands=[e[1] for e in events if e[0]=='command'];self.assertIn(['systemctl','disable','asterisk.service'],commands)
  self.assertFalse((root/'etc/systemd/system/asterisk.service.d/00-allmode-provisioning.conf').exists())
  self.assertNotIn(['systemctl','start','mmdvm_bridge.service'],commands);self.assertNotIn(['systemctl','start','netcheck.service'],commands)
  self.assertTrue(any('provision-fresh-profile.py' in ' '.join(c) for c in commands));self.assertFalse(json.loads((work/'journal.json').read_text())['radio_resumed'])
 def test_exact_final_package_sets_and_bus_order_for_both_modes(self):
  for mode in ('fresh','legacy-migrate'):
   root,work,events=self.fixture(mode)
   installs=[e[1] for e in events if e[0]=='install']
   self.assertEqual(installs[0],{'ara-allmode-dvswitch-guard':'0.8.0~beta9-2'})
   self.assertEqual(installs[-1],{'ara-allmode':'0.8.0~beta9-7','ara-allmode-meter':'0.8.0~beta9+abid1486d408855-1','ara-allmode-dvswitch':'0.8.0~beta9-2'})
   commands=[e[1] for e in events if e[0]=='command']
   ping=next(i for i,c in enumerate(commands) if c[0]=='busctl' and c[-1]=='Ping')
   for i,c in enumerate(commands):
    if c[0]=='busctl' and c[-1]!='Ping':self.assertGreater(i,ping)
   self.assertLess(ping,next(i for i,c in enumerate(commands) if c[:2]==['systemctl','daemon-reload']))
   calls=[];b.install(installs[-1],fake_apt(installs[-1],calls))
   simulations=[c for c in calls if c[0]=='apt-get' and '-s' in c]
   for command in simulations:
    self.assertIn('ara-allmode=0.8.0~beta9-7',command)
    self.assertIn('ara-allmode-dvswitch=0.8.0~beta9-2',command)
    self.assertNotIn('ara-allmode-dvswitch=0.8.0~beta9-7',command)
 def test_migration_never_creates_fresh_preset_or_starts_asterisk(self):
  root,work,events=self.fixture('legacy-migrate');commands=[e[1] for e in events if e[0]=='command']
  self.assertFalse(any('provision-fresh-profile.py' in ' '.join(c) for c in commands));self.assertNotIn(['systemctl','start','asterisk.service'],commands)
  self.assertEqual(json.loads((root/'etc/allmode/service.json').read_text())['port'],8788)
 def test_failure_records_phase_and_does_not_start_console(self):
  root,work,events=self.fixture('legacy-migrate',True);journal=json.loads((work/'journal.json').read_text());self.assertEqual(journal['phase'],'failed-radio-not-resumed');self.assertEqual(journal['failed_phase'],'legacy-code-saved')
  for unit in b.RADIO:self.assertEqual((root/('etc/systemd/system/'+unit+'.d/00-allmode-provisioning.conf')).read_text(),b.GUARD)
  commands=[e[1] for e in events if e[0]=='command'];self.assertFalse(any(c[:3]==['systemctl','start','allmode-system.service'] for c in commands))

if __name__=='__main__':unittest.main(verbosity=2)
