import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock
from rf_memories import Config, UnixMemoryServer, generation, slot, decode_request

BASE='''[base](!)
functions=local
macro=macro
link_functions=remote
phone_functions=remote
dphone_functions=remote
[60670](base)
rxchannel=SimpleUSB/60670
[local]
3=ilink,3
5=macro
[remote]
3=ilink,3
[macro]
'''
ROW={'id':'one','mode':'AllStar','target':'12345','network':None,'slot':'1','enabled':True}

class RFMemoriesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'rpt.conf';self.path.write_text(BASE)
        self.reload=Mock();self.config=Config(self.path,'60670',self.reload,self.root/'lock')
    def test_apply_and_disable_preserve_config(self):
        with self.config.transaction([ROW]):pass
        text=self.path.read_text()
        self.assertIn('1=*D1D#',text);self.assertIn('3=ilink,3',text);self.assertIn('5=macro',text)
        self.assertNotIn('*501',text)
        self.assertEqual(self.path.with_name('rpt.conf.allmode-rf-backup').read_text(),BASE)
        with self.config.transaction([]):pass
        self.assertEqual(self.path.read_text(),BASE)
    def test_rollback_store_failure(self):
        with self.assertRaisesRegex(ValueError,'store failed'):
            with self.config.transaction([ROW]):raise ValueError('store failed')
        self.assertEqual(self.path.read_text(),BASE);self.assertEqual(self.reload.call_count,2)
    def test_reload_failure_rolls_back(self):
        self.reload.side_effect=[ValueError('reload failed'),None]
        with self.assertRaises(ValueError):
            with self.config.transaction([ROW]):pass
        self.assertEqual(self.path.read_text(),BASE)
    def test_remote_shared_fails_closed(self):
        self.path.write_text(BASE.replace('link_functions=remote','link_functions=local'))
        self.assertFalse(self.config.status()['available'])
        with self.assertRaises(ValueError):self.config.plan([ROW])
    def test_remote_macro_even_in_distinct_table_fails(self):
        self.path.write_text(BASE.replace('[remote]','[remote]\n5=macro'))
        self.assertIn('macro/cmd',self.config.status()['reason'])
    def test_conflicts_both_directions(self):
        for existing,new in [('1','12'),('12','1'),('1','1')]:
            self.path.write_text(BASE+existing+'=*312345#\n')
            with self.assertRaisesRegex(ValueError,'overlap'):self.config.plan([dict(ROW,slot=new)])
    def test_proposed_prefix_conflict(self):
        with self.assertRaises(ValueError):self.config.plan([ROW,dict(ROW,id='two',slot='12')])
    def test_function_conflict(self):
        self.path.write_text(BASE.replace('[local]','[local]\n51=cop,1'))
        with self.assertRaises(ValueError):self.config.plan([ROW])
    def test_helper_conflict(self):
        self.path.write_text(BASE.replace('[local]','[local]\nD=ilink,1'))
        with self.assertRaises(ValueError):self.config.plan([ROW])
    def test_isolation_plan_is_read_only_and_preserves_commands(self):
        self.path.write_text(BASE.replace('link_functions=remote','link_functions=local').replace('phone_functions=remote','phone_functions=local').replace('dphone_functions=remote','dphone_functions=local'))
        before=self.path.read_text();plan=self.config.isolation_plan()
        self.assertEqual(self.path.read_text(),before)
        self.assertEqual(plan['removed_remote_macro_commands']['link_functions'],{'5':'macro'})
        self.assertIn('3=ilink,3',plan['new_sections'])
        self.assertTrue(plan['requires_owner_approval'])
        # Materialize the explicit owner-reviewed plan only in this fixture.
        text=before.replace('[60670](base)','[60670](base)\n'+'\n'.join(k+'='+v for k,v in plan['node_overrides'].items()))
        self.path.write_text(text+'\n'+plan['new_sections'])
        self.assertTrue(self.config.status()['available'])
    def test_apply_reviewed_isolation_and_stale_guard(self):
        self.path.write_text(BASE.replace('link_functions=remote','link_functions=local'))
        plan=self.config.isolation_plan();original=self.path.read_text()
        with self.assertRaises(ValueError):self.config.apply_isolation('0'*64)
        self.assertEqual(self.path.read_text(),original)
        result=self.config.apply_isolation(plan['plan_digest'])
        self.assertTrue(result['applied']);self.assertTrue(self.config.status()['available'])
        self.assertEqual(Path(result['backup']).read_text(),original)
        self.assertIn('3=ilink,3',self.path.read_text())
    def test_isolation_rollback_on_reload_failure(self):
        original=self.path.read_text();plan=self.config.isolation_plan()
        self.reload.side_effect=[ValueError('reload'),None]
        with self.assertRaises(ValueError):self.config.apply_isolation(plan['plan_digest'])
        self.assertEqual(self.path.read_text(),original)
    def test_extra_macro_alias_needs_new_review(self):
        self.path.write_text(BASE.replace('[remote]','[remote]\n7=macro'))
        with self.assertRaisesRegex(ValueError,'aliases'):self.config.isolation_plan()
    def test_alternate_control_requires_review(self):
        self.path.write_text(BASE.replace('[60670](base)','[60670](base)\nalt_functions=remote'))
        self.assertFalse(self.config.status()['available'])
    def test_case_insensitive_helper_conflict(self):
        self.path.write_text(BASE.replace('[local]','[local]\nd1d=ilink,1'))
        with self.assertRaises(ValueError):self.config.plan([ROW])
    def test_privileged_auth_requires_review(self):
        self.path.write_text(BASE.replace('[60670](base)','[60670](base)\nauth_users=auth.conf'))
        self.assertFalse(self.config.status()['available'])
    def test_missing_phone_source_preserves_no_commands(self):
        self.path.write_text(BASE.replace('dphone_functions=remote\n',''))
        plan=self.config.isolation_plan()
        name=plan['node_overrides']['dphone_functions']
        self.assertIn('['+name+']\n\n',plan['new_sections'])
        self.assertEqual(plan['removed_remote_macro_commands']['dphone_functions'],{})
    def test_slot_validation(self):
        for value in ('0','01','1000','-1','1;id',1,None):
            with self.assertRaises(ValueError):slot(value)
    def test_includes_and_optional_glob(self):
        (self.root/'parts').mkdir();(self.root/'parts'/'one.conf').write_text(BASE)
        self.path.write_text('#include parts/*.conf\n#tryinclude optional.conf\n')
        self.assertTrue(self.config.status()['available'])
        with self.config.transaction([ROW]):pass
        self.assertIn('1=*D1D#',(self.root/'parts'/'one.conf').read_text())
    def test_missing_required_or_exec_fail_closed(self):
        for text in ('#include missing.conf\n','#exec echo\n'):
            self.path.write_text(text);self.assertFalse(self.config.status()['available'])
    def test_disabled_save_when_config_unavailable(self):
        self.path.unlink()
        with self.config.transaction([]):pass
    def test_generation_identity_and_source(self):
        digest=generation([ROW])
        for change in ({'target':'45678'},{'source_id':'123'},{'id':'two'},{'network':'TGIF'},{'slot':'2'}):
            self.assertNotEqual(digest,generation([dict(ROW,**change)]))
    def test_request_decoder_auth_and_malformed_inputs(self):
        valid=json.dumps({'slot':'1','generation':generation([ROW])}).encode()
        self.assertEqual(decode_request(valid,100,100),('1',generation([ROW])))
        for raw,peer in [(valid,101),(b'[]',100),(b'{',100),(b'x'*257,100),(b'{"slot":"1","generation":null}',100)]:
            with self.assertRaises(ValueError):decode_request(raw,peer,100)
    def test_socket_validates_shape_and_peer(self):
        calls=[];path=self.root/'recall.sock'
        try:server=UnixMemoryServer(lambda s,d:calls.append((s,d)) or {'ok':True},path,os.getuid()).start()
        except PermissionError:self.skipTest('Execution sandbox denies Unix sockets; integration not exercised.')
        self.addCleanup(server.close)
        def request(data):
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                client.settimeout(2);client.connect(str(path));client.sendall(json.dumps(data).encode()+b'\n')
                return json.loads(client.makefile('rb').readline())
        self.assertTrue(request({'slot':'1','generation':generation([ROW])})['requested'])
        self.assertIn('error',request({'slot':'01','generation':generation([ROW])}))
        self.assertEqual(len(calls),1)
    def test_unauthorized_socket_peer(self):
        calls=[];path=self.root/'denied.sock'
        try:server=UnixMemoryServer(lambda *args:calls.append(args),path,os.getuid()+1).start()
        except PermissionError:self.skipTest('Execution sandbox denies Unix sockets; integration not exercised.')
        self.addCleanup(server.close)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.connect(str(path));self.assertEqual(client.recv(1),b'')
        self.assertFalse(calls)

class RFDurabilityFailureTests(unittest.TestCase):
    def test_postrename_directory_failure_rolls_back_config(self):
        import stat
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'rpt.conf';path.write_text(BASE)
            reload=Mock();config=Config(path,'60670',reload,root/'lock')
            real=os.fsync;directories=0
            def fsync(fd):
                nonlocal directories
                if stat.S_ISDIR(os.fstat(fd).st_mode):
                    directories+=1
                    if directories==2:raise OSError(5,'injected postrename failure')
                return real(fd)
            with patch('os.fsync',side_effect=fsync), self.assertRaises(OSError):
                with config.transaction([ROW]):self.fail('Failed apply must not commit store')
            self.assertEqual(path.read_text(),BASE)
            reload.assert_called_once()

    def test_store_postrename_failure_rolls_back_both_files(self):
        import stat
        from unittest.mock import patch
        from favorites_store import Store
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'rpt.conf';path.write_text(BASE)
            config=Config(path,'60670',Mock(),root/'lock')
            store=Store(root/'favorites.json',transaction=lambda old,new:config.transaction(new['favorites']))
            real=os.fsync;directories=0
            def fsync(fd):
                nonlocal directories
                if stat.S_ISDIR(os.fstat(fd).st_mode):
                    directories+=1
                    if directories==3:raise OSError(5,'injected store postrename failure')
                return real(fd)
            row={k:v for k,v in ROW.items() if k!='id'}
            with patch('os.fsync',side_effect=fsync),self.assertRaises(OSError):
                store.replace({'revision':0,'favorites':[row]})
            self.assertEqual(path.read_text(),BASE)
            self.assertFalse(store.path.exists())
            self.assertEqual(store.snapshot(),{'revision':0,'favorites':[]})
