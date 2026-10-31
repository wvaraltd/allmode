# SPDX-License-Identifier: GPL-2.0-or-later
import http.client
import json
import re
import socket
import subprocess
import sys
import time
import unittest
from dstar import ROOT,parse_wav

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); cls.port=s.getsockname()[1]
        cls.proc=subprocess.Popen([sys.executable,str(ROOT/'serve.py'),'--port',str(cls.port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for _ in range(60):
            try:
                c=http.client.HTTPConnection('127.0.0.1',cls.port,timeout=1); c.request('GET','/')
                r=c.getresponse(); page=r.read().decode(); c.close()
                cls.token=re.search("const token='([^']+)'",page)[1]; return
            except (OSError,TypeError): time.sleep(.05)
        cls.proc.terminate(); raise RuntimeError('Local test server failed to start')
    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.communicate(timeout=5)
    def request(self,path,body=b'{}',token=True,origin=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        headers={}
        if token: headers['X-Parrot-Token']=self.token
        if origin: headers['Origin']=origin
        c.request('POST',path,body,headers); r=c.getresponse(); data=r.read(); status=r.status;c.close()
        return status,json.loads(data)
    def test_api_origin_and_token(self):
        self.assertEqual(self.request('/enable',token=False)[0],403)
        self.assertEqual(self.request('/enable',origin='https://example.invalid')[0],403)
        self.assertEqual(self.request('/enable',b'{"seconds":1}')[0],200)
        status,s=self.request('/record')
        dll=ROOT/'build'/('allmode_dstar.dll' if sys.platform=='win32' else 'liballmode_dstar.so')
        if dll.exists():
            self.assertEqual(status,200);self.assertEqual(s['phase'],'recording')
            self.assertEqual(self.request('/record')[0],400)
        else:
            self.assertEqual(status,400); self.assertIn('not built',s['error'])
        status,s=self.request('/stop');self.assertEqual(status,200);self.assertEqual(s['phase'],'idle')
        self.assertFalse(s['network_tx']);self.assertFalse(s['rf_tx'])
        self.assertEqual(self.request('/compare')[0],400)
        self.assertEqual(self.request('/disable')[1]['phase'],'disabled')
    def test_native_file_parrot(self):
        dll=ROOT/'build'/('allmode_dstar.dll' if sys.platform=='win32' else 'liballmode_dstar.so')
        if not dll.exists(): self.skipTest('Native codec unavailable')
        self.request('/disable'); self.request('/enable',b'{"seconds":1}')
        self.assertEqual(self.request('/record')[0],200)
        self.assertEqual(self.request('/complete',bytes(1600))[0],200)
        for _ in range(100):
            status,state=self.request('/heartbeat')
            if state['phase']=='ready': break
            time.sleep(.02)
        self.assertEqual(state['phase'],'ready',state)
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        c.request('POST','/play',b'{}',{'X-Parrot-Token':self.token})
        r=c.getresponse(); data=r.read(); c.close()
        self.assertEqual(r.status,200); self.assertEqual(len(parse_wav(data)),1920)
        self.assertEqual(self.request('/finished')[1]['phase'],'idle')
        self.request('/disable')

if __name__=='__main__': unittest.main()
