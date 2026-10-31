import unittest
import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from server import Controller, Handler, LiveController, validate_audio
from unittest.mock import Mock
import sa818_hardware


class ControllerTests(unittest.TestCase):
    def test_switch_requires_disconnect(self):
        node = Controller()
        node.command('connect', '12345')
        with self.assertRaises(ValueError):
            node.command('mode', 'DMR')
        with self.assertRaises(ValueError):
            node.command('connect', '67890')
        self.assertEqual(node.snapshot()['target'], '12345')
        node.command('disconnect', None)
        node.command('mode', 'DMR')
        self.assertFalse(node.snapshot()['connected'])

    def test_invalid_commands_do_not_mutate(self):
        node = Controller()
        for action, value in [('mode', 'invalid'), ('connect', '123;shutdown'), ('connect', ''), ('connect', 'letters'), ('ptt', True)]:
            with self.assertRaises(ValueError):
                node.command(action, value)
        self.assertFalse(node.snapshot()['connected'])
        self.assertFalse(node.snapshot()['transmit_enabled'])

    def test_each_mode_can_be_simulated(self):
        node = Controller()
        for mode in node.snapshot()['modes']:
            node.command('mode', mode)
            node.command('connect', '12345')
            self.assertTrue(node.snapshot()['simulation'])
            self.assertFalse(node.snapshot()['transmit_enabled'])
            node.command('disconnect', None)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.controller = Controller()
        self.server.hardware = sa818_hardware.Hardware(enabled=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, data=None, origin=True):
        connection = HTTPConnection('127.0.0.1', self.port)
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = f'http://127.0.0.1:{self.port}'
        connection.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_first_run_claim_and_protected_pages(self):
        import tempfile
        from pathlib import Path
        from web_auth import Auth
        with tempfile.TemporaryDirectory() as root:
            self.server.auth=Auth(Path(root)/'auth.json')
            self.assertEqual(self.request('GET','/')[0],303)
            self.assertIn(b'Choose',self.request('GET','/setup')[1])
            self.assertEqual(self.request('POST','/api/claim',{'password':'local-test-password'},origin=False)[0],403)
            self.assertTrue(self.server.auth.unclaimed)
            self.assertEqual(self.request('POST','/api/claim',{'password':'local-test-password'})[0],200)
            self.assertFalse(self.server.auth.unclaimed)
            self.assertEqual(self.request('GET','/api/status')[0],401)
            self.assertEqual(self.request('POST','/api/claim',{'password':'other-password'})[0],401)

    def test_network_connect_is_single_request(self):
        status,body=self.request('POST','/api/command',{'action':'connect-network','mode':'DMR','value':'91'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['mode'],'DMR')
        self.assertEqual(json.loads(body)['target'],'91')
        self.assertEqual(self.request('POST','/api/command',{'action':'connect-network','mode':'AllStar','value':'12345'})[0],400)
        self.assertEqual(self.server.controller.target,'91')

    def test_assets_and_status(self):
        for path in ['/', '/app.js', '/style.css', '/api/status', '/hardware', '/hardware.js', '/hardware.css', '/api/hardware']:
            status, body = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertTrue(body)
        self.assertEqual(self.request('GET', '/../server.py')[0], 404)

    def test_command_validation_and_origin(self):
        self.assertEqual(self.request('POST', '/api/command', {'action': 'connect', 'value': '12345'}, origin=False)[0], 403)
        status, body = self.request('POST', '/api/command', {'action': 'connect', 'value': '12345'})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['connected'])
        self.assertEqual(self.request('POST', '/api/command', {'action': 'mode', 'value': 'DMR'})[0], 400)
        self.assertEqual(self.request('POST', '/api/command', [1, 2])[0], 400)

    def test_hardware_api_validation_and_csrf(self):
        body = dict(action='preview', settings=dict(sa818_hardware.PRESET,rx='446.1000',tx='446.1000'))
        self.assertEqual(self.request('POST','/api/hardware',body,origin=False)[0],403)
        status, data = self.request('POST','/api/hardware',body)
        self.assertEqual(status,200)
        self.assertEqual(len(json.loads(data)['commands']),4)
        self.assertEqual(self.request('POST','/api/hardware',dict(body,action='program'))[0],400)
        self.assertEqual(self.request('POST','/api/hardware',dict(action='ptt'))[0],400)


class LiveTests(unittest.TestCase):
    def test_audio_limits_reject_nonfinite_and_invalid_values(self):
        for value in [float('nan'), float('inf'), True, 0.49, 1.51, '1.0']:
            with self.assertRaises(ValueError):
                validate_audio({'receive':value,'transmit':1})
        self.assertEqual(validate_audio({'receive':0.85,'transmit':1.0})['receive'],0.85)
    def test_pending_link_is_not_established(self):
        node = LiveController('60670', True)
        node.run_cli = Mock(return_value='STATISTICS\nNodes currently connected to us....: 12345\nSystem....: ENABLED\n12345 127.0.0.1 0 OUT 00:00:00 CONNECTING')
        node.pending = ('connect', '12345', __import__('time').monotonic()+30)
        result = node.snapshot()
        self.assertFalse(result['connected'])
        self.assertTrue(result['pending'])

    def test_dmr_routes_only_to_private_node(self):
        from unittest.mock import patch
        node = LiveController('60670', True)
        node.run_cli = Mock(return_value='STATISTICS\nNodes currently connected to us....: <NONE>\nSystem....: ENABLED')
        with patch('digital.available', return_value=['DMR']), patch('server.Path.exists', return_value=True), patch('server.Path.write_text'), patch('server.socket.socket'), patch('digital.request'), patch('digital.tune'), patch('digital.ready', return_value=True):
            node.command('mode', 'DMR')
            result = node.command('connect', '31665')
            self.assertTrue(result['pending'])
            self.assertEqual(node.digital_target, '31665')
            self.assertIn(('rpt cmd 60670 ilink 3 1999',), [call.args for call in node.run_cli.call_args_list])

    def test_confirmation_and_validation(self):
        node = LiveController('60670', True)
        idle = 'STATISTICS\nNodes currently connected to us....: <NONE>\nSystem....: ENABLED'
        linked = idle.replace('<NONE>', '12345') + '\n12345 127.0.0.1 0 OUT 00:00:00 ESTABLISHED'
        node.run_cli = Mock(return_value=idle)
        with self.assertRaises(ValueError):
            node.command('connect', '12345; reboot')
        result = node.command('connect', '12345')
        self.assertTrue(result['pending'])
        self.assertFalse(result['connected'])
        self.assertIn(('rpt cmd 60670 ilink 3 12345',), [call.args for call in node.run_cli.call_args_list])
        node.run_cli.return_value = linked
        self.assertFalse(node.snapshot()['pending'])
        self.assertTrue(node.snapshot()['connected'])
        result = node.command('disconnect', None)
        self.assertTrue(result['pending'])
        node.run_cli.return_value = idle
        self.assertFalse(node.snapshot()['connected'])
        self.assertFalse(node.snapshot()['pending'])


if __name__ == '__main__':
    unittest.main()
