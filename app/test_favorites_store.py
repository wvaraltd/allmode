import contextlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from favorites_store import Store, ConflictError


class FavoritesStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'favorites.json'
        self.store = Store(self.path)

    def row(self, **values):
        return dict(mode='AllStar', target='12345', **values)

    def save(self, rows, revision=0):
        return self.store.replace(dict(revision=revision, favorites=rows))

    def test_persistence_ids_and_delete_no_renumber(self):
        first = self.save([self.row(slot='11'), dict(mode='EchoLink', target='9876', slot='12')])
        second = self.save([first['favorites'][1]], 1)
        self.assertEqual(second['favorites'][0]['id'], first['favorites'][1]['id'])
        self.assertEqual(second['favorites'][0]['slot'], '12')
        self.assertEqual(Store(self.path).snapshot(), second)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_stale_revision_id_and_duplicate_atomic(self):
        state = self.save([self.row()])
        row = state['favorites'][0]
        for payload in [dict(revision=0, favorites=[]), dict(revision=1, favorites=[row, row])]:
            with self.assertRaises(ConflictError):
                self.store.replace(payload)
            self.assertEqual(self.store.snapshot(), state)
        self.save([], 1)
        with self.assertRaises(ConflictError):
            self.save([row], 2)

    def test_slots_reject_leading_zero_range_and_prefixes(self):
        for slot in ['0', '01', '1000', '', 1, True, '*51', '1;id']:
            with self.subTest(slot=slot), self.assertRaises(ValueError):
                self.save([self.row(slot=slot)])
        for slots in [('1', '12'), ('12', '1'), ('12', '12')]:
            with self.assertRaises(ConflictError):
                self.save([self.row(slot=slots[0]), dict(mode='EchoLink', target='123', slot=slots[1])])
        self.assertEqual(self.store.snapshot()['revision'], 0)

    def test_import_preserves_network_source_notes_and_deduplicates(self):
        row = dict(mode='DMR', target='91', network='BrandMeister', source_id='1234567', note='World')
        first = self.store.import_legacy(dict(revision=0, favorites=[row, row]))
        self.assertEqual(len(first['favorites']), 1)
        second = self.store.import_legacy(dict(revision=1, favorites=[row, dict(row, network='TGIF')]))
        self.assertEqual(len(second['favorites']), 2)
        self.assertEqual(first['favorites'][0], second['favorites'][0])
        self.assertFalse(second['favorites'][1]['enabled'])
        for change in [dict(note='Other'), dict(source_id='7654321')]:
            with self.assertRaises(ConflictError):
                self.store.import_legacy(dict(revision=2, favorites=[dict(row, **change)]))
        self.assertEqual(self.store.snapshot(), second)

    def test_import_missing_network_and_rf_assignment_fail(self):
        for row in [dict(mode='DMR', target='91'), self.row(slot='1'), self.row(enabled=True)]:
            with self.assertRaises(ValueError):
                self.store.import_legacy(dict(revision=0, favorites=[row]))
        self.assertFalse(self.path.exists())

    def test_malformed_requests_and_corrupt_state_not_reset(self):
        for value in [[], None, {}, {'revision': True, 'favorites': []}, {'revision': 0, 'favorites': 'bad'}]:
            with self.assertRaises(ValueError):
                self.store.replace(value)
        for value in ['{bad', '[]', '{"revision":false,"favorites":[]}']:
            self.path.write_text(value)
            with self.assertRaises(ValueError):
                self.store.snapshot()
            with self.assertRaises(ValueError):
                self.save([])
            self.assertEqual(self.path.read_text(), value)

    def test_enable_requires_adapter_and_valid_slot(self):
        for row in [self.row(enabled=True), self.row(slot='1', enabled=True), self.row(enabled=1)]:
            with self.assertRaises(ValueError):
                self.save([row])

    def test_adapter_rollback_on_write_failure(self):
        events = []
        @contextlib.contextmanager
        def transaction(old, new):
            events.append('apply')
            try:
                yield
            except Exception:
                events.append('rollback')
                raise
            events.append('commit')
        store = Store(self.path, transaction=transaction)
        with patch.object(store, '_write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                store.replace(dict(revision=0, favorites=[self.row(slot='1', enabled=True)]))
        self.assertEqual(events, ['apply', 'rollback'])
        self.assertFalse(self.path.exists())

    def test_concurrent_edit_exactly_one_wins(self):
        barrier = threading.Barrier(2)
        results = []
        def save():
            barrier.wait()
            try:
                Store(self.path).replace(dict(revision=0, favorites=[self.row()]))
                results.append('saved')
            except ConflictError:
                results.append('conflict')
        threads = [threading.Thread(target=save) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertCountEqual(results, ['saved', 'conflict'])

    def test_source_id_types_and_existing_note_length(self):
        for source in [False, 0, True, 1234567, '0', 'x']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.save([self.row(source_id=source)])
        result = self.save([self.row(note='n' * 500, source_id='1234567')])
        self.assertEqual(len(result['favorites'][0]['note']), 500)
        with self.assertRaises(ValueError):
            self.save([dict(result['favorites'][0], note='n' * 501)], 1)

    def test_safe_destination_validation(self):
        for row in [dict(mode='AllStar', target='123;touch x'), dict(mode='AllStar', target='0'), dict(mode='NXDN', target='999999'), dict(mode='Nope', target='1'), dict(mode='DMR', target='1', network='evil')]:
            with self.assertRaises(ValueError): self.save([row])


if __name__ == '__main__':
    unittest.main()

class DestinationFormatTests(unittest.TestCase):
    def test_uncallable_formats_rejected(self):
        from favorites_store import normalize
        for mode, target in [('D-STAR', 'INVALID'), ('M17', 'NOT-A-REFLECTOR'), ('AllStar', '00060670'), ('EchoLink', '0000001')]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                normalize({'mode': mode, 'target': target})
        for mode, target in [('D-STAR', 'REF030C'), ('D-STAR', 'DCS001 A'), ('M17', 'M17-M17 A')]:
            self.assertEqual(normalize({'mode': mode, 'target': target})['target'], target)

class StoreDurabilityFailureTests(unittest.TestCase):
    def test_directory_fsync_failure_restores_prior_bytes_or_absence(self):
        import os, stat
        from unittest.mock import patch
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/'favorites.json'
                store = Store(path)
                if existing:
                    store.replace({'revision':0,'favorites':[{'mode':'AllStar','target':'12345'}]})
                previous = path.read_bytes() if existing else None
                state = store.snapshot()
                real = os.fsync
                failed = False
                def fsync(fd):
                    nonlocal failed
                    if stat.S_ISDIR(os.fstat(fd).st_mode) and not failed:
                        failed = True
                        raise OSError(5, 'injected directory fsync failure')
                    return real(fd)
                with patch('os.fsync',side_effect=fsync), self.assertRaises(OSError):
                    store.replace({'revision':state['revision'],'favorites':[{'mode':'AllStar','target':'23456'}]})
                self.assertEqual(path.read_bytes() if path.exists() else None, previous)
                self.assertEqual(store.snapshot(),state)
                self.assertFalse(store.recovery_path.exists())

    def test_persistent_rollback_failure_blocks_future_instances(self):
        import os, stat
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'favorites.json';store=Store(path)
            store.replace({'revision':0,'favorites':[{'mode':'AllStar','target':'12345'}]})
            previous=path.read_text();real=os.fsync
            def fsync(fd):
                if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError(5,'persistent directory failure')
                return real(fd)
            with patch('os.fsync',side_effect=fsync), self.assertRaisesRegex(OSError,'rollback failed'):
                store.replace({'revision':1,'favorites':[]})
            self.assertEqual(json.loads(store.recovery_path.read_text())['previous'],previous)
            for instance in (store,Store(path)):
                with self.assertRaisesRegex(ValueError,'recovery'):instance.snapshot()
