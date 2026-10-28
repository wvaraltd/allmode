import unittest
from email.message import Message
from types import SimpleNamespace
from lan_origin import allowed
from unittest.mock import patch
import lan_origin


class OriginTests(unittest.TestCase):
    configured = 'https://192.168.1.152,https://allmode.local,https://allmode'

    def check(self, host='192.168.0.231', origin='https://192.168.0.231', proto='https', peer='127.0.0.1', duplicate=None, addresses=None):
        headers = Message()
        for key, value in [('Host', host), ('Origin', origin), ('X-Forwarded-Proto', proto)]:
            if value is not None:
                headers[key] = value
        if duplicate:
            headers[duplicate] = headers[duplicate]
        request = SimpleNamespace(headers=headers, client_address=(peer, 12345))
        return allowed(request, self.configured, {'192.168.0.231'} if addresses is None else addresses)

    def test_new_dhcp_ip_and_configured_names(self):
        self.assertTrue(self.check())
        self.assertTrue(self.check(host='allmode.local', origin='https://allmode.local'))
        self.assertTrue(self.check(host='192.168.0.231:443', origin='https://192.168.0.231'))

    def test_stale_ip_and_arbitrary_host_rejected(self):
        self.assertFalse(self.check(host='192.168.1.152', origin='https://192.168.1.152'))
        self.assertFalse(self.check(host='evil.example', origin='https://evil.example'))
        self.assertFalse(self.check(addresses=set()))

    def test_cross_origin_and_bad_authorities(self):
        for origin in [None, 'null', 'http://192.168.0.231', 'https://192.168.1.152', 'https://evil.example', 'https://192.168.0.231:444', 'https://192.168.0.231/path', 'https://192.168.0.231?x', 'https://user@192.168.0.231', 'https://192.168.0.231,https://evil.example']:
            with self.subTest(origin=origin):
                self.assertFalse(self.check(origin=origin))
        self.assertFalse(self.check(host='192.168.0.231:444'))

    def test_proxy_trust_and_duplicates(self):
        for proto in [None, 'http', 'https,http']:
            self.assertFalse(self.check(proto=proto))
        self.assertFalse(self.check(peer='192.168.0.5'))
        for key in ['Host', 'Origin', 'X-Forwarded-Proto']:
            self.assertFalse(self.check(duplicate=key))

    def test_secondary_addresses_and_discovery_failure(self):
        result = SimpleNamespace(stdout='[{"addr_info":[{"family":"inet","local":"192.168.0.231"},{"family":"inet","local":"192.168.0.232"}]}]')
        with patch('lan_origin.subprocess.run', return_value=result):
            self.assertEqual(lan_origin.local_ipv4_addresses(), {'192.168.0.231', '192.168.0.232'})
        self.assertFalse(self.check(host='[::1]', origin='https://[::1]'))


if __name__ == '__main__':
    unittest.main()
