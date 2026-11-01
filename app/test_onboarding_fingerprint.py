"""Stable beta9 migration: one omitted default must not invent unapplied changes."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from onboarding import Onboarding, GROUPS, applied_fingerprint_matches
from system_service import fingerprint


class LegacyFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.data = {g: {k: d for k, _, _, d in fields} for g, fields in GROUPS.items()}
        self.data['station']['callsign'] = 'N0CALL'
        self.legacy = copy.deepcopy(self.data)
        del self.legacy['dmr']['dvswitch']

    def test_current_false_and_legacy_omitted_hashes_match(self):
        before = copy.deepcopy(self.data)
        for value in (self.data, self.legacy):
            self.assertTrue(applied_fingerprint_matches(self.data, fingerprint(value)))
        self.assertEqual(self.data, before)

    def test_missing_empty_or_unknown_applied_hash_does_not_match(self):
        for value in (None, '', 'unknown'):
            self.assertFalse(applied_fingerprint_matches(self.data, value))
        self.assertFalse(applied_fingerprint_matches({}, fingerprint(self.data)))

    def test_true_is_never_omitted_or_equivalent_to_false(self):
        enabled = copy.deepcopy(self.data)
        enabled['dmr']['dvswitch'] = True
        self.assertTrue(applied_fingerprint_matches(enabled, fingerprint(enabled)))
        self.assertFalse(applied_fingerprint_matches(enabled, fingerprint(self.legacy)))
        self.assertFalse(applied_fingerprint_matches(enabled, fingerprint(self.data)))
        self.assertFalse(applied_fingerprint_matches(self.data, fingerprint(enabled)))

    def test_other_fields_and_boolean_types_are_not_canonicalized(self):
        for group, key, value in [('station', 'name', 'Changed'), ('dmr', 'id', '7654321'),
                                  ('dmr', 'color_code', 2), ('dmr', 'dvswitch', 0)]:
            changed = copy.deepcopy(self.data)
            changed[group][key] = value
            self.assertFalse(applied_fingerprint_matches(changed, fingerprint(self.legacy)))
        old = copy.deepcopy(self.legacy)
        del old['dmr']['color_code']
        self.assertFalse(applied_fingerprint_matches(self.data, fingerprint(old)))

    def test_read_workflow_preserves_disk_audio_and_drift_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            setup = Onboarding(root, managed=True)
            raw = json.dumps(self.legacy)
            setup.path.write_text(raw)
            (Path(root)/'program.json').write_text(json.dumps(dict(
                state='acknowledged-not-verified',
                acknowledged=['AT+DMOSETGROUP','AT+DMOSETVOLUME','AT+SETFILTER','AT+SETTAIL'])))
            for audio in (False, True):
                runtime = dict(fingerprint=fingerprint(self.legacy), audio_verified=audio, config_drift=[])
                with patch('system_client.status', return_value=runtime):
                    result = setup.workflow(setup.read())
                self.assertTrue(result['applied'])
                self.assertEqual(result['audio_status'], 'verified' if audio else 'untested')
                self.assertEqual(result['runtime'], runtime)
                self.assertEqual(setup.path.read_text(), raw)
            for runtime in (
                dict(fingerprint=None, audio_verified=True, config_drift=['rpt.conf']),
                dict(fingerprint=fingerprint(self.legacy), audio_verified=True, config_drift=['rpt.conf']),
            ):
                with patch('system_client.status', return_value=runtime):
                    result = setup.workflow(setup.read())
                self.assertFalse(result['applied'])
                self.assertNotEqual(result['audio_status'], 'verified')
            changed = setup.read()
            changed['station']['name'] = 'Unsaved activation change'
            with patch('system_client.status', return_value=dict(
                    fingerprint=fingerprint(self.legacy), audio_verified=True, config_drift=[])):
                result = setup.workflow(changed)
            self.assertFalse(result['applied'])
            self.assertNotEqual(result['audio_status'], 'verified')
            self.assertEqual(setup.path.read_text(), raw)



class ActivationCompatibilityTests(unittest.TestCase):
    setUp = LegacyFingerprintTests.setUp
    def activate(self, applied, requested, *, confirm='ACTIVATE', drift=(), acknowledged=True):
        import os
        import system_service as service
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            raw = json.dumps(applied)
            (root/'config.json').write_text(raw)
            (root/'program.json').write_text(json.dumps(dict(
                state='acknowledged-not-verified' if acknowledged else 'incomplete',
                acknowledged=['a','b','c','d'] if acknowledged else [])))
            with patch.object(service, 'STATE', root), \
                 patch.object(service, 'load_state', return_value={'levels': {'rx': 1, 'txa': 2, 'txb': 3}}), \
                 patch.object(service, 'config_drift', return_value=list(drift)), \
                 patch.object(service, 'open_program_record', side_effect=lambda: os.open(root/'program.json', os.O_RDONLY)), \
                 patch.object(service, 'install_config', return_value={'ok': True}) as install, \
                 patch.object(service, 'run', side_effect=AssertionError('No system/radio operations allowed')), \
                 patch.object(service, 'cli', side_effect=AssertionError('No Asterisk calls allowed')):
                try:
                    result = service.handle(dict(action='activate', confirm=confirm, fingerprint=fingerprint(requested)))
                except ValueError:
                    install.assert_not_called()
                    self.assertEqual((root/'config.json').read_text(), raw)
                    raise
                install.assert_called_once_with(applied, True, {'rx': 1, 'txa': 2, 'txb': 3})
                self.assertEqual((root/'config.json').read_text(), raw)
                return result

    def test_actual_activate_accepts_both_default_representations(self):
        for applied in (self.data, self.legacy):
            for requested in (self.data, self.legacy):
                self.assertEqual(self.activate(applied, requested), {'ok': True})

    def test_actual_activate_rejects_true_other_changes_types_and_gates(self):
        for group, key, value in [('dmr','dvswitch',True), ('dmr','dvswitch',0),
                                  ('station','name','Changed'), ('dmr','color_code',2)]:
            changed = copy.deepcopy(self.data)
            changed[group][key] = value
            with self.assertRaises(ValueError): self.activate(self.legacy, changed)
            with self.assertRaises(ValueError): self.activate(changed, self.legacy)
        for options in ({'confirm':''}, {'drift':['rpt.conf']}, {'acknowledged':False}):
            with self.assertRaises(ValueError): self.activate(self.legacy, self.data, **options)


if __name__ == '__main__':
    unittest.main()
