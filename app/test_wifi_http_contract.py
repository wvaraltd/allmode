"""Authenticated HTTP -> real helper dispatch. Only OS writes/commands are mocked."""
import configparser,json,os
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
import unittest
import system_client
import system_service as service
import test_onboarding


class WiFiHTTPContractTests(unittest.TestCase):
    request=test_onboarding.AuthHttpTests.request
    tearDown=test_onboarding.AuthHttpTests.tearDown

    def setUp(self):
        test_onboarding.AuthHttpTests.setUp(self)
        status,headers,_=self.request('POST','/login',urlencode(dict(username='admin',password='test-login')))
        self.assertEqual(status,303);self.cookie=headers['Set-Cookie'].split(';')[0]
        self.root=Path(self.tmp.name)/'profiles';self.root.mkdir()
        self.forwarded=[];self.writes=[]
        def transport(action,**fields):
            self.forwarded.append(dict(action=action,**fields))
            return service.handle(dict(action=action,**fields))
        def atomic(path,text,*args):
            path.write_text(text);path.chmod(0o600);self.writes.append(path)
        for context in (patch.object(system_client,'request',side_effect=transport),
                        patch.object(service,'WIFI_PROFILES',self.root),
                        patch.object(service,'WIFI_ROOT_UID',os.geteuid()),
                        patch.object(service,'atomic',side_effect=atomic),
                        patch.object(service.shutil,'which',side_effect=lambda name:'/usr/bin/'+name)):
            context.start();self.addCleanup(context.stop)
        context=patch.object(service,'run',return_value='')
        self.run=context.start();self.addCleanup(context.stop)

    def post(self,body,**options):
        status,headers,raw=self.request('POST','/api/system',json.dumps(body),cookie=options.pop('cookie',self.cookie),kind='application/json',**options)
        return status,json.loads(raw)

    def profile(self):
        result=configparser.RawConfigParser();result.read(self.writes[-1]);return result

    def test_real_http_personal_hidden_connect_reaches_real_scheduler(self):
        body=dict(action='wifi-save',ssid='Synthetic Hidden',password='test-only-password',security='wpa-psk',hidden=True,connect=True)
        status,result=self.post(body)
        self.assertEqual(status,200);self.assertEqual(self.forwarded,[body])
        self.assertTrue(result['scheduled']);self.assertFalse(result['connected'])
        self.assertEqual(self.profile()['wifi']['hidden'],'true')
        self.assertEqual(self.profile()['wifi-security']['psk'],'test-only-password')
        calls=[call.args[0] for call in self.run.call_args_list]
        self.assertEqual([call[1:3] for call in calls[:2]],[['connection','load'],['connection','modify']])
        self.assertEqual(calls[2][:3],['/usr/bin/systemd-run','--quiet','--on-active=3s'])
        self.assertNotIn(body['password'],json.dumps(calls));self.assertNotIn(body['password'],json.dumps(result))

    def test_real_http_open_connect_preserves_security_not_legacy_wpa_default(self):
        body=dict(action='wifi-save',ssid='Synthetic Open',password='',security='open',hidden=False,connect=True)
        status,result=self.post(body)
        self.assertEqual(status,200);self.assertTrue(result['scheduled'])
        self.assertEqual(self.forwarded,[body]);self.assertFalse(self.profile().has_section('wifi-security'))

    def test_legacy_request_is_save_only_with_explicit_defaults(self):
        body=dict(action='wifi-save',ssid='Synthetic Legacy',password='test-only-password')
        status,result=self.post(body)
        self.assertEqual(status,200);self.assertFalse(result['scheduled'])
        self.assertEqual(self.forwarded,[dict(body,security='wpa-psk',hidden=False,connect=False)])
        self.assertEqual(self.run.call_count,1)

    def test_flags_security_and_arbitrary_keys_fail_before_helper(self):
        base=dict(action='wifi-save',ssid='Synthetic',password='test-only-password')
        for changes in ({'connect':'true'},{'hidden':1},{'security':'wpa-eap'},
                        {'security':None},{'command':'arbitrary'},{'config':{}},{'id':'foreign'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(dict(base,**changes))[0],400)
        self.assertEqual(self.post(dict(action='wifi-save',ssid='Synthetic'))[0],400)
        self.assertEqual(self.forwarded,[]);self.assertEqual(self.writes,[]);self.run.assert_not_called()

    def test_auth_and_origin_still_block_helper(self):
        body=dict(action='wifi-save',ssid='Synthetic',password='test-only-password',connect=True)
        self.assertEqual(self.post(body,cookie='')[0],401)
        self.assertEqual(self.post(body,origin='https://untrusted.invalid')[0],403)
        self.assertEqual(self.forwarded,[]);self.run.assert_not_called()

    def test_helper_validation_and_tool_failure_return_http_error_without_write(self):
        base=dict(action='wifi-save',ssid='Synthetic',password='',security='wpa-psk',hidden=False,connect=True)
        self.assertEqual(self.post(base)[0],400);self.assertEqual(self.writes,[])
        with patch.object(service.shutil,'which',return_value=None):
            status,result=self.post(dict(base,password='test-only-password'))
        self.assertEqual(status,400);self.assertIn('nmcli',result['error'])
        self.assertEqual(self.writes,[]);self.run.assert_not_called()


if __name__=='__main__':unittest.main()
