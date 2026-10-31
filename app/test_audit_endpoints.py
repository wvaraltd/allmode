"""Real loopback HTTP regression tests; no hardware or public peers."""
import json
import unittest
from unittest.mock import patch
import test_server

class EndpointFailures(unittest.TestCase):
    setUp=test_server.HttpTests.setUp
    tearDown=test_server.HttpTests.tearDown
    request=test_server.HttpTests.request

    def test_service_post_failures_return_unavailable(self):
        with patch('system_client.request',side_effect=OSError('offline')):
            for path,payload in (('/api/codec/select',{'backend':'software'}),('/api/radio-parrot/stop',{}),('/api/system',{'action':'maintenance'})):
                with self.subTest(path=path):
                    status,body=self.request('POST',path,payload)
                    self.assertEqual(status,503)
                    self.assertIn('error',json.loads(body))

    def test_service_get_success_preserves_payload(self):
        with patch('system_client.request',return_value={'audit':'success'}):
            for path in ('/api/digital-identities','/api/codec/state','/api/radio-parrot/state'):
                with self.subTest(path=path):
                    status,body=self.request('GET',path)
                    self.assertEqual(status,200)
                    self.assertEqual(json.loads(body),{'audit':'success'})

    def test_protected_route_inventory_requires_login(self):
        from unittest.mock import Mock
        self.server.auth=Mock(unclaimed=False)
        self.server.auth.valid.return_value=False
        paths=('/api/hardware','/api/onboarding','/api/profiles','/api/features','/api/network','/api/digital-identities','/api/directory','/api/system','/api/destinations','/api/setup','/api/status','/api/audio-meter','/api/codec/libraries','/api/codec/state','/api/radio-parrot/state','/api/parrot/state')
        for path in paths:
            with self.subTest(path=path):self.assertEqual(self.request('GET',path)[0],401)
        posts=('/api/command','/api/hardware','/api/onboarding','/api/system','/api/settings','/api/finish','/api/profiles','/api/password','/api/features','/api/codec/upload','/api/codec/select','/api/radio-parrot/arm','/api/radio-parrot/stop','/api/radio-parrot/heartbeat','/api/parrot/enable')
        for path in posts:
            with self.subTest(path=path):
                self.assertEqual(self.request('POST',path,{})[0],401)
                self.assertEqual(self.request('POST',path,{},origin=False)[0],403)
    def test_service_get_failures_return_json(self):
        with patch('system_client.request',side_effect=OSError('offline')):
            for path in ('/api/digital-identities','/api/codec/state','/api/radio-parrot/state'):
                with self.subTest(path=path):
                    status,body=self.request('GET',path)
                    self.assertEqual(status,503)
                    self.assertIn('error',json.loads(body))

    def test_claim_password_message_matches_minimum(self):
        import tempfile
        from pathlib import Path
        from web_auth import Auth
        with tempfile.TemporaryDirectory() as temp:
            self.server.auth=Auth(Path(temp)/'auth.json')
            status,body=self.request('POST','/api/claim',{'password':'abc'})
            self.assertEqual(status,400)
            self.assertIn('4-128',json.loads(body)['error'])
            self.assertEqual(self.request('POST','/api/claim',{'password':'abcd'})[0],200)

if __name__=='__main__':unittest.main()
