"""Node display metadata only; all remote IO is mocked, never station/RF actions."""
import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch
import directory_api as d
import test_server


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = time.time()

    def seed(self, **updates):
        value = dict(updated=self.now, attempt=self.now, rows=[{'target': '516228', 'name': 'Existing cache'}])
        value.update(updates)
        (self.root / 'directory-AllStar.json').write_text(json.dumps(value))

    def wait(self, cache):
        end = time.monotonic() + 2
        while cache.refreshing and time.monotonic() < end:
            time.sleep(.005)
        self.assertFalse(cache.refreshing)

    def test_schema_missing_duplicates_and_plain_text(self):
        rows = d.parse(b'516228|K1TEST|Hub|Town\n516228|DUP|Duplicate|Elsewhere\n12345|||\n23456||Hub only|\n34567|<img src=x onerror=alert(1)>||City\x00name\n999||bad\n00000|BAD|x|x\nhttp://x|BAD|x|x')
        self.assertEqual([r['target'] for r in rows], ['516228', '12345', '23456', '34567'])
        self.assertEqual(rows[0]['name'], 'K1TEST · Hub · Town')
        self.assertEqual(rows[1]['name'], '')
        self.assertEqual(rows[2]['name'], 'Hub only')
        self.assertEqual(rows[3]['location'], 'City name')
        # Stored as data, no lossy HTML entity double-escaping. UI tests assert sinks.
        self.assertIn('<img', rows[3]['name'])
        self.assertEqual(d.text('x'*1000), 'x'*120)
        for raw in (b'', b'<html>failure</html>', b'12345|wrong|schema'):
            with self.assertRaises(ValueError): d.parse(raw)

    def test_existing_cache_reused_and_unknown_is_absent(self):
        self.seed()
        with patch.object(d, 'download') as get:
            cache = d.AllStarCache(self.root)
            result = cache.snapshot(['516228', '12345'])
            self.assertEqual(result['rows'][0]['name'], 'Existing cache')
            self.assertEqual(result['rows'][0]['location'], '')
            self.assertEqual(len(result['rows']), 1)
            self.assertFalse(result['stale'])
            get.assert_not_called()

    def test_stale_while_refreshing_and_singleflight(self):
        self.seed(updated=self.now-1000, attempt=self.now-1000)
        entered, release = threading.Event(), threading.Event()
        def fetch():
            entered.set()
            release.wait(2)
            return b'516228|New|Hub|Town'
        with patch.object(d, 'download', side_effect=fetch) as get:
            cache = d.AllStarCache(self.root)
            result = cache.snapshot(['516228'])
            self.assertTrue(entered.wait(1))
            self.assertTrue(result['refreshing'])
            self.assertTrue(result['stale'])
            self.assertEqual(result['rows'][0]['name'], 'Existing cache')
            for _ in range(20): self.assertTrue(cache.snapshot()['refreshing'])
            get.assert_called_once()
            release.set(); self.wait(cache)
            self.assertEqual(cache.snapshot()['rows'][0]['callsign'], 'New')
            self.assertFalse(cache.snapshot()['stale'])

    def test_failure_backoff_stale_expiry_and_disk_error(self):
        self.seed(updated=self.now-1000, attempt=self.now-1000)
        with patch.object(d, 'download', side_effect=OSError('offline')) as get, patch.object(d, 'atomic', side_effect=PermissionError('read only')):
            cache = d.AllStarCache(self.root)
            cache.snapshot(); self.wait(cache)
            for _ in range(5): self.assertEqual(cache.snapshot()['rows'][0]['name'], 'Existing cache')
            get.assert_called_once()
            self.assertTrue(cache.snapshot()['error'])
            cache.updated = self.now-d.MAX_STALE-1
            self.assertEqual(cache.snapshot()['rows'], [])

    def test_corrupt_future_empty_cache_and_bad_response(self):
        self.seed(updated=self.now+99999, attempt=self.now+99999)
        with patch.object(d, 'download', return_value=b'<html>error</html>') as get:
            cache = d.AllStarCache(self.root)
            self.assertEqual(cache.snapshot()['rows'], [])
            self.wait(cache); get.assert_called_once()
            self.assertTrue(cache.snapshot()['error'])
        (self.root/'directory-AllStar.json').write_text('[]')
        with patch.object(d, 'download', side_effect=TimeoutError()):
            cache = d.AllStarCache(self.root); cache.snapshot(); self.wait(cache)
            self.assertEqual(cache.snapshot()['rows'], [])

    def test_validation_and_dedup(self):
        self.seed()
        with patch.object(d, 'download') as get:
            for targets in ([], [''], ['00001'], ['123'], ['1234567'], ['１２３４５'], ['http://127.0.0.1'], ['12345']*101, '12345'):
                with self.assertRaises(ValueError): d.node_names(self.root, targets)
            self.assertEqual(len(d.node_names(self.root, ['516228', '516228'])['rows']), 1)
            get.assert_not_called()

    def test_fetch_fixed_origin_size_timeout_and_redirects(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read1.side_effect = [b'12345|C|D|L', b'']
        opener = Mock(); opener.open.return_value=response
        with patch.object(d.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(d.download(), b'12345|C|D|L')
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, 'https://allmondb.allstarlink.org/allmondb.php')
            self.assertEqual(opener.open.call_args.kwargs, {'timeout': 5})
        with self.assertRaises(ValueError): d.NoRedirect().redirect_request(None,None,302,'',{},'http://127.0.0.1/')
        response.read1.side_effect = [b'x'*5]
        with patch.object(d.urllib.request, 'build_opener', return_value=opener), patch.object(d,'MAX_BYTES',4):
            with self.assertRaises(ValueError): d.download()


    def test_observed_root_301_is_rejected_but_pinned_direct_feed_works(self):
        # Pi4 observed this exact same-origin canonicalization on 2026-11-01.
        # Exercise urllib's actual redirect dispatch, never the public network.
        import io
        from email.message import Message
        from urllib.response import addinfourl
        root_url = 'https://allmondb.allstarlink.org/'
        direct_url = 'https://allmondb.allstarlink.org/allmondb.php'
        calls = []
        class FixtureHTTPS(d.urllib.request.HTTPSHandler):
            def https_open(self, request):
                calls.append(request.full_url)
                headers = Message()
                if request.full_url == root_url:
                    headers['Location'] = direct_url
                    response = addinfourl(io.BytesIO(b''), headers, root_url, 301)
                    response.msg = 'Moved Permanently'
                else:
                    self_outer.assertEqual(request.full_url, direct_url)
                    headers['Content-Type'] = 'text/plain'
                    response = addinfourl(io.BytesIO(b'516228|K1TEST|Hub|Town\n'), headers, direct_url, 200)
                    response.msg = 'OK'
                return response
        self_outer = self
        build = d.urllib.request.build_opener
        opener = build(FixtureHTTPS(), d.NoRedirect())
        with self.assertRaisesRegex(ValueError, 'redirects are not permitted'):
            opener.open(root_url, timeout=5)
        self.assertEqual(calls, [root_url], 'The canonical redirect must not be followed')
        calls.clear()
        with patch.object(d.urllib.request, 'build_opener', side_effect=lambda *handlers: build(FixtureHTTPS(), *handlers)):
            rows = d.parse(d.download())
        self.assertEqual(calls, [direct_url], 'Exactly one pinned direct HTTPS request')
        self.assertEqual(rows, [dict(target='516228', callsign='K1TEST', description='Hub', location='Town', name='K1TEST · Hub · Town')])


class NodeNamesHTTPTests(unittest.TestCase):
    tearDown = test_server.HttpTests.tearDown
    request = test_server.HttpTests.request

    def setUp(self):
        test_server.HttpTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server.onboarding = types.SimpleNamespace(path=self.root/'onboarding.json')
        (self.root/'directory-AllStar.json').write_text(json.dumps(dict(updated=time.time(),attempt=time.time(),rows=[dict(target='516228',name='Known node')])) )

    def test_get_is_authenticated_read_only_and_validates(self):
        before = self.server.controller.snapshot()
        with patch.object(d, 'download') as get:
            status, raw = self.request('GET','/api/node-names?nodes=516228,516228,12345')
            self.assertEqual(status, 200)
            self.assertEqual(len(json.loads(raw)['rows']),1)
            for query in ('','nodes=','nodes=123','nodes=516228&nodes=12345','nodes=516228&url=http://127.0.0.1','nodes=..%2Fsecret'):
                self.assertEqual(self.request('GET','/api/node-names?'+query)[0],400)
            self.server.auth = Mock(unclaimed=False); self.server.auth.valid.return_value=False
            self.assertEqual(self.request('GET','/api/node-names?nodes=516228')[0],401)
            get.assert_not_called()
        self.assertEqual(self.server.controller.snapshot()['target'],before['target'])
        self.assertEqual(self.server.controller.snapshot()['connected'],before['connected'])
