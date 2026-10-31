"""Real HTTP login regressions, with temporary auth and mocked interface state."""
import hashlib
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from server import Handler, Controller
from web_auth import Auth


class LanHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name)/'auth.json'
        salt = b'unit-test-salt-only'
        path.write_text(json.dumps({'salt': salt.hex(), 'hash': hashlib.pbkdf2_hmac('sha256', b'test-password', salt, 600000).hex()}))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.auth = Auth(path)
        self.server.controller = Controller()
        self.server.public_origin = 'https://192.168.1.152,https://allmode.local'
        self.server.lan_proxy = True
        self.addresses = {'192.168.0.231', '192.168.0.232'}
        self.mock = patch('lan_origin.local_ipv4_addresses', side_effect=lambda: self.addresses)
        self.mock.start()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.mock.stop()
        self.temp.cleanup()

    def request(self, method='POST', path='/login', host='192.168.0.231', origin='https://192.168.0.231', proto='https', extra=(), body='username=admin&password=test-password'):
        conn = HTTPConnection(*self.server.server_address)
        conn.putrequest(method, path, skip_host=True)
        for key, value in [('Host', host), ('Origin', origin), ('X-Forwarded-Proto', proto)]:
            if value is not None:
                conn.putheader(key, value)
        for key, value in extra:
            conn.putheader(key, value)
        conn.putheader('Content-Length', str(len(body)))
        conn.putheader('Content-Type', 'application/x-www-form-urlencoded')
        conn.endheaders(body.encode())
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_get_login_needs_no_origin_and_successful_login_keeps_secure_cookie(self):
        status, _, body = self.request(method='GET', origin=None, proto=None, body='')
        self.assertEqual(status, 200)
        self.assertIn(b'<form', body)
        status, headers, _ = self.request()
        self.assertEqual(status, 303)
        self.assertEqual(headers['Location'], '/setup')
        for attribute in ['Secure', 'HttpOnly', 'SameSite=Strict']:
            self.assertIn(attribute, headers['Set-Cookie'])

    def test_cross_site_missing_origin_and_spoofed_proxy_headers(self):
        for origin in [None, 'null', 'https://evil.example', 'https://192.168.1.152', 'http://192.168.0.231']:
            self.assertEqual(self.request(origin=origin)[0], 403)
        self.assertEqual(self.request(host='evil.example', origin='https://evil.example')[0], 403)
        self.assertEqual(self.request(proto=None)[0], 403)
        self.assertEqual(self.request(proto='http')[0], 403)
        for header in ['Origin', 'Host', 'X-Forwarded-Proto']:
            self.assertEqual(self.request(extra=[(header, 'https')])[0], 403)
        self.assertEqual(len(self.server.auth.sessions), 0)

    def test_dhcp_change_rejects_removed_ip_and_accepts_secondary_and_hostname(self):
        self.assertEqual(self.request(host='192.168.0.232', origin='https://192.168.0.232')[0], 303)
        self.addresses = {'10.0.0.42'}
        self.assertEqual(self.request()[0], 403)
        self.assertEqual(self.request(host='192.168.1.152', origin='https://192.168.1.152')[0], 403)
        self.assertEqual(self.request(host='10.0.0.42', origin='https://10.0.0.42')[0], 303)
        self.assertEqual(self.request(host='allmode.local', origin='https://allmode.local')[0], 303)

    def test_default_port_equivalence_and_other_ports_rejected(self):
        self.assertEqual(self.request(host='192.168.0.231:443')[0], 303)
        self.assertEqual(self.request(origin='https://192.168.0.231:443')[0], 303)
        self.assertEqual(self.request(host='192.168.0.231:444', origin='https://192.168.0.231:444')[0], 403)
        self.assertEqual(self.request(origin='https://192.168.0.231:444')[0], 403)

    def test_protected_post_requires_auth_and_csrf_even_after_login(self):
        self.assertEqual(self.request(path='/api/command')[0], 401)
        _, headers, _ = self.request()
        cookie = headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request(path='/api/command', origin='https://evil.example', extra=[('Cookie', cookie)])[0], 403)
        self.assertEqual(self.request(path='/logout', extra=[('Cookie', cookie)])[0], 303)
        self.assertEqual(len(self.server.auth.sessions), 0)

    def test_discovery_fails_closed_and_legacy_mode_unchanged(self):
        with patch('lan_origin.local_ipv4_addresses', side_effect=OSError('unavailable')):
            self.assertEqual(self.request()[0], 403)
        self.server.lan_proxy = False
        self.assertEqual(self.request()[0], 403)
        self.assertEqual(self.request(host='192.168.1.152', origin='https://192.168.1.152', proto=None)[0], 303)


class InstallerRegressionTests(unittest.TestCase):
    def test_portable_installer_proxy_contract(self):
        installer = Path(__file__).resolve().parent.parent/'enable-lan.sh'
        # Source-only test: some deployments contain app files but no installer.
        if not installer.exists():
            self.skipTest('Installer not present in app-only deployment')
        script = installer.read_text()
        self.assertIn('return 302 https://\\$server_addr\\$request_uri;', script)
        self.assertIn('proxy_set_header Host \\$host;', script)
        self.assertIn('proxy_set_header X-Forwarded-Proto https;', script)
        self.assertIn('--lan-proxy --public-origin https://$host.local,https://$host', script)
        self.assertNotIn('--public-origin https://$ip', script)


if __name__ == '__main__':
    unittest.main()
