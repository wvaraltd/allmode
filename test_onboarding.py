import copy
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode
from onboarding import Onboarding, GROUPS
from web_auth import Auth
from server import Handler, Controller
from sa818_hardware import Hardware


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.setup = Onboarding(self.tmp.name)
        self.data = {g:{k:default for k,label,kind,default in rows} for g,rows in GROUPS.items()}
        self.data['station']['callsign'] = 'W1AW'
        self.data['allstar'].update(enabled=True, node='12345', password='test-node-secret')

    def test_secrets_redacted_and_preserved(self):
        reply = self.setup.save(self.data)
        self.assertNotIn('test-node-secret', json.dumps(reply))
        self.data['allstar']['password'] = ''
        self.setup.save(self.data)
        self.assertEqual(self.setup.read()['allstar']['password'], 'test-node-secret')
        self.assertEqual(reply['activation'], 'pending')

    def test_order_partial_save_and_resume(self):
        networks={g:v for g,v in self.data.items() if g!='station'}
        with self.assertRaisesRegex(ValueError,'station identity'):
            self.setup.save_section('networks',networks)
        reply=self.setup.save_section('station',{'station':self.data['station']})
        self.assertEqual(reply['workflow']['next_step'],'networks')
        self.assertFalse(reply['workflow']['steps'][2]['available'])
        reply=self.setup.save_section('networks',networks)
        self.assertEqual(reply['workflow']['next_step'],'radio')
        self.assertFalse(reply['workflow']['ready'])
        self.assertEqual(Onboarding(self.tmp.name).snapshot()['workflow'],reply['workflow'])

    def test_incomplete_radio_write_cannot_unlock_audio(self):
        self.setup.save(self.data)
        path=Path(self.tmp.name)/'program.json'
        record=dict(state='incomplete',settings={},acknowledged=['AT+DMOSETGROUP'])
        path.write_text(json.dumps(record))
        self.assertFalse(self.setup.snapshot()['workflow']['steps'][3]['available'])
        record.update(state='acknowledged-not-verified',acknowledged=['AT+DMOSETGROUP','AT+DMOSETVOLUME','AT+SETFILTER','AT+SETTAIL'])
        path.write_text(json.dumps(record))
        reply=self.setup.snapshot()
        self.assertTrue(reply['workflow']['steps'][3]['available'])
        self.assertFalse(reply['workflow']['ready'])
        record['state']='incomplete';path.write_text(json.dumps(record))
        self.assertFalse(self.setup.snapshot()['workflow']['steps'][3]['available'])

    def test_edit_station_keeps_network_credentials_and_review(self):
        self.setup.save(self.data)
        self.data['station']['name']='New operator'
        self.setup.save_section('station',{'station':self.data['station']})
        self.assertEqual(self.setup.read()['allstar']['password'],'test-node-secret')
        self.assertTrue(self.setup.snapshot()['workflow']['steps'][1]['complete'])

    def test_dmr_networks_keep_separate_passwords(self):
        self.data['dmr'].update(id='1234567', essid='01')
        for group in ('brandmeister','tgif'):
            self.data[group].update(enabled=True,password=group+'-secret')
        reply=self.setup.save(self.data)
        self.assertNotIn('-secret', json.dumps(reply))
        self.assertNotEqual(self.setup.read()['brandmeister']['password'], self.setup.read()['tgif']['password'])

    def test_invalid_inputs_never_replace_valid_file(self):
        self.setup.save(self.data)
        before=self.setup.path.read_bytes()
        for group,key,value in [('allstar','node','123;bad'),('dmr','color_code',16),('station','callsign',''),('station','name','bad\nline')]:
            data=copy.deepcopy(self.data);data[group][key]=value
            with self.assertRaises(ValueError): self.setup.save(data)
            self.assertEqual(self.setup.path.read_bytes(),before)


class AuthHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        path=Path(self.tmp.name)/'auth.json';salt=b'test-salt'
        path.write_text(json.dumps(dict(salt=salt.hex(),hash=hashlib.pbkdf2_hmac('sha256',b'test-login',salt,600000).hex())))
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.auth=Auth(path)
        self.server.onboarding=Onboarding(self.tmp.name)
        self.server.hardware=Hardware(enabled=False)
        self.server.controller=Controller()
        self.server.public_origin='https://pi.local'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def request(self,method,path,body=None,cookie='',origin='https://pi.local',kind='application/x-www-form-urlencoded'):
        c=HTTPConnection('127.0.0.1',self.server.server_port)
        c.request(method,path,body,{'Origin':origin,'Cookie':cookie,'Content-Type':kind})
        r=c.getresponse();result=(r.status,dict(r.getheaders()),r.read());c.close();return result

    def test_login_pages_secret_api_and_logout(self):
        for path in ('/','/setup','/hardware'):
            self.assertEqual(self.request('GET',path)[0],303)
        self.assertEqual(self.request('GET','/api/onboarding')[0],401)
        self.assertEqual(self.request('POST','/login',urlencode(dict(username='admin',password='wrong')))[1]['Location'],'/login?error=1')
        status,headers,_=self.request('POST','/login',urlencode(dict(username='admin',password='test-login')))
        self.assertEqual(status,303);self.assertEqual(headers['Location'],'/setup')
        cookie=headers['Set-Cookie'];self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie)
        cookie=cookie.split(';')[0]
        for path in ('/','/setup','/hardware','/api/onboarding','/first-run.js','/api/status','/api/destinations'):
            self.assertEqual(self.request('GET',path,cookie=cookie)[0],200,path)
        self.assertEqual(self.request('POST','/api/onboarding','{}',cookie=cookie,origin='https://evil.invalid',kind='application/json')[0],403)
        self.assertEqual(self.request('POST','/logout',cookie=cookie)[0],303)
        self.assertEqual(self.request('GET','/api/onboarding',cookie=cookie)[0],401)


if __name__=='__main__': unittest.main()
