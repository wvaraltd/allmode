"""HTTP and RF dispatch isolation tests. Never contact Asterisk or transmit RF."""
import json
import tempfile
import threading
import types
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import Mock, patch
import favorites_api
import test_server
from favorites_store import Store


class FavoritesHTTPTests(unittest.TestCase):
    tearDown = test_server.HttpTests.tearDown
    request = test_server.HttpTests.request

    def setUp(self):
        test_server.HttpTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server.favorites_store = Store(Path(self.temp.name) / 'favorites.json')

    def raw(self, body, content_type='application/json'):
        connection = HTTPConnection('127.0.0.1', self.port)
        connection.request('POST', '/api/favorites', body,
                           {'Origin': f'http://127.0.0.1:{self.port}', 'Content-Type': content_type})
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_owner_auth_and_same_origin(self):
        self.server.auth = Mock(unclaimed=False)
        self.server.auth.valid.return_value = False
        self.assertEqual(self.request('GET', '/api/favorites')[0], 401)
        for path in ('/api/favorites', '/api/favorites/import'):
            self.assertEqual(self.request('POST', path, {})[0], 401)
            self.assertEqual(self.request('POST', path, {}, origin=False)[0], 403)
        self.assertEqual(self.server.favorites_store.snapshot()['revision'], 0)

    def test_malformed_size_and_content_type(self):
        for body, kind in [('{bad', 'application/json'), ('[]', 'application/json'), ('{}', 'text/plain'), (' ' * (favorites_api.MAX_BODY + 1), 'application/json')]:
            self.assertEqual(self.raw(body, kind)[0], 400)
        self.assertEqual(self.server.favorites_store.snapshot()['revision'], 0)

    def test_save_reload_stale_and_import(self):
        status, raw = self.request('POST', '/api/favorites', {'revision': 0, 'favorites': [{'mode': 'AllStar', 'target': '12345', 'slot': '12'}]})
        self.assertEqual(status, 200)
        state = json.loads(raw)
        self.assertFalse(state['rf']['available'])
        self.assertEqual(json.loads(self.request('GET', '/api/favorites')[1]), state)
        self.assertEqual(self.request('POST', '/api/favorites', {'revision': 0, 'favorites': []})[0], 409)
        self.assertEqual(self.request('POST', '/api/favorites/import', {'revision': 1, 'favorites': [{'mode': 'EchoLink', 'target': '456'}]})[0], 200)
        self.assertEqual(len(self.server.favorites_store.snapshot()['favorites']), 2)

    def test_full_size_unicode_list_round_trips(self):
        rows = [{'mode': 'AllStar', 'target': str(10000+i), 'note': '😀'*500} for i in range(100)]
        status, raw = self.request('POST', '/api/favorites', {'revision': 0, 'favorites': rows})
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(raw)['favorites']), 100)
        self.assertEqual(json.loads(self.request('GET', '/api/favorites')[1])['favorites'][0]['note'], '😀'*500)

    def test_service_errors_are_structured_and_recall_not_http(self):
        del self.server.favorites_store
        with patch('system_client.request', side_effect=OSError('offline')):
            self.assertEqual(self.request('GET', '/api/favorites')[0], 503)
            self.assertEqual(self.request('POST', '/api/favorites', {})[0], 503)
        with patch('system_client.request', side_effect=favorites_api.system_client.SystemConflictError('changed')):
            status, raw = self.request('POST', '/api/favorites', {})
            self.assertEqual(status, 409)
            self.assertEqual(json.loads(raw)['code'], 'conflict')
        self.assertEqual(self.request('POST', '/api/favorites/recall', {'slot': '1'})[0], 404)


class FavoritesRecallTests(unittest.TestCase):
    def setUp(self):
        self.controller = Mock()
        self.controller.lock = threading.RLock()
        self.controller.node = '60670'
        self.current = {'modes': ['AllStar', 'EchoLink', 'DMR', 'YSF', 'NXDN', 'P25', 'M17', 'D-STAR']}
        self.controller.snapshot.side_effect = lambda: self.current
        self.server = types.SimpleNamespace(controller=self.controller)
        self.rows = [{'id': 'saved', 'mode': 'AllStar', 'target': '12345', 'slot': '1', 'enabled': True}]
        self.state = {'favorites': self.rows, 'rf': {'available': True}}
        self.connect = Mock()
        self.enter(patch.dict('sys.modules', {'rf_memories': types.SimpleNamespace(generation=lambda rows: 'verified')}))
        self.enter(patch('favorites_api.operation', side_effect=lambda *a: self.state))
        self.parrot = self.enter(patch('parrot_integration.STATE.state', return_value={'enabled': False}))
        self.radio = self.enter(patch('system_client.request', return_value={'active': False}))

    def enter(self, manager):
        result = manager.start()
        self.addCleanup(manager.stop)
        return result

    def recall(self, slot='1', digest='verified', connect=None):
        return favorites_api.recall(self.server, slot, digest, connect or self.connect)

    def rejected(self, **kwargs):
        with self.assertRaises((ValueError, OSError)):
            self.recall(**kwargs)
        self.connect.assert_not_called()

    def test_all_modes_route_only_saved_destination_without_bridge(self):
        for mode in self.current['modes']:
            self.rows[0].update(mode=mode, network='TGIF' if mode == 'DMR' else None, source_id='1234567')
            self.connect.reset_mock()
            self.assertEqual(self.recall()['status'], 'requested')
            self.connect.assert_called_once_with(self.controller, mode, '12345', allow_bridge=False,
                                                 network='TGIF' if mode == 'DMR' else None, source_id='1234567')

    def test_bad_slots_disabled_deleted_and_changed_generation(self):
        for slot in ['0', '01', '1000', '1;sh', '*51', 1, None, '2']:
            self.rejected(slot=slot)
        self.rejected(digest='stale')
        self.rows[0]['enabled'] = False
        self.rejected()
        self.rows.clear()
        self.rejected()

    def test_readonly_pending_simulation_unavailable_and_duplicates(self):
        for key in ['readonly', 'pending', 'simulation']:
            self.current[key] = True
            self.rejected()
            del self.current[key]
        self.current['unavailable_modes'] = {'AllStar': 'offline'}
        self.rejected()
        del self.current['unavailable_modes']
        self.current['modes'] = []
        self.rejected()
        self.current['modes'] = ['AllStar']
        self.state['rf']['available'] = False
        self.rejected()
        self.state['rf']['available'] = True
        self.rows.append(dict(self.rows[0]))
        self.rejected()

    def test_parrot_failures_prevent_connect(self):
        self.parrot.return_value = {'enabled': True}
        self.rejected()
        self.parrot.return_value = {}
        self.rejected()
        self.parrot.return_value = {'enabled': False}
        for state in [{'active': True}, {}]:
            self.radio.return_value = state
            self.rejected()
        self.radio.side_effect = OSError('offline')
        self.rejected()

    def test_quick_modes_use_shared_preparation_despite_inactive_worker(self):
        for mode in ('YSF', 'NXDN', 'P25', 'M17'):
            self.rows[0]['mode'] = mode
            self.current.update(modes=['AllStar'], quick_connect_modes=[mode], unavailable_modes={mode: 'Worker is not running'})
            self.connect.reset_mock()
            self.assertEqual(self.recall()['status'], 'requested')
            self.connect.assert_called_once()

    def test_busy_controller_does_not_queue_recall(self):
        held = threading.Event()
        release = threading.Event()
        def hold():
            with self.controller.lock:
                held.set()
                release.wait(2)
        thread = threading.Thread(target=hold)
        thread.start()
        try:
            self.assertTrue(held.wait(1))
            self.rejected()
        finally:
            release.set()
            thread.join()

    def test_own_node_rejected_by_shared_dispatcher_before_disconnect(self):
        from server import connect_destination
        self.rows[0]['target'] = '60670'
        self.current['connected'] = True
        self.rejected(connect=connect_destination)
        self.controller.stop_bridge.assert_not_called()
        self.controller.command.assert_not_called()
