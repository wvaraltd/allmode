import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from onboarding import Onboarding, GROUPS
import operator_store


class OptionalAudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ob = Onboarding(self.root, managed=True)
        self.saved = {g:{k:d for k,_,_,d in fields} for g,fields in GROUPS.items()}
        self.saved['station']['callsign'] = 'N0CALL'
        self.saved['_networks_reviewed'] = True
        operator_store.atomic(self.ob.path, self.saved)
        operator_store.atomic(self.root/'program.json', dict(state='acknowledged-not-verified',
            acknowledged=['AT+DMOSETGROUP','AT+DMOSETVOLUME','AT+SETFILTER','AT+SETTAIL'], settings={'rx':'438.6750'}))
        self.runtime = dict(fingerprint='fixture', radio_enabled=False, audio_verified=False)
        p = patch('system_client.status', side_effect=lambda:dict(self.runtime))
        p.start(); self.addCleanup(p.stop)
        p = patch('system_service.fingerprint', return_value='fixture')
        p.start(); self.addCleanup(p.stop)

    def test_untested_audio_optional_without_activation(self):
        flow = self.ob.snapshot()['workflow']
        self.assertTrue(flow['ready'])
        self.assertEqual(flow['audio_status'], 'untested')
        audio = next(s for s in flow['steps'] if s['id']=='audio')
        self.assertTrue(audio['optional'])
        self.assertFalse(audio['complete'])

    def test_skip_finish_reload_never_confirms_or_activates(self):
        with patch('system_client.request') as requests:
            operator_store.skip_audio(self.ob)
            operator_store.skip_audio(self.ob)
            operator_store.finish(self.ob)
            resumed = Onboarding(self.root, managed=True)
            self.assertTrue(operator_store.completed(resumed))
            self.assertEqual(resumed.snapshot()['workflow']['audio_status'], 'skipped')
            self.assertFalse(self.runtime['audio_verified'])
            self.assertFalse(self.runtime['radio_enabled'])
            requests.assert_not_called()
        self.assertEqual(json.loads((self.root/'setup-complete.json').read_text())['audio_status'], 'skipped')

    def test_skip_cannot_bypass_mandatory_radio_or_apply(self):
        operator_store.skip_audio(self.ob)
        self.runtime['fingerprint'] = 'old'
        with self.assertRaises(ValueError):
            operator_store.finish(self.ob)
        self.runtime['fingerprint'] = 'fixture'
        (self.root/'program.json').unlink()
        with self.assertRaises(ValueError):
            operator_store.finish(self.ob)

    def test_later_real_confirmation_supersedes_skip(self):
        operator_store.skip_audio(self.ob)
        self.runtime.update(audio_verified=True, radio_enabled=True)
        flow = self.ob.snapshot()['workflow']
        self.assertEqual(flow['audio_status'], 'verified')
        self.assertTrue(next(s for s in flow['steps'] if s['id']=='audio')['complete'])


if __name__ == '__main__':
    unittest.main()
