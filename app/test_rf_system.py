import contextlib
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import favorites_store
import rf_memories
import system_service
from test_rf_memories import BASE

class RFSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.etc=self.root/'etc';self.etc.mkdir();self.state=self.root/'state';self.state.mkdir()
        (self.etc/'rpt.conf').write_text(BASE)
        self.old={'node':'60670','radio':True,'config_hashes':{'rpt.conf':hashlib.sha256(BASE.encode()).hexdigest()}}
        (self.state/'state.json').write_text(json.dumps(self.old))
        self.socket=self.root/'socket';self.socket.touch()
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        for obj,key,val in [(system_service,'STATE',self.state),(system_service,'ETC',self.etc),(rf_memories,'SOCKET',str(self.socket))]:self.stack.enter_context(patch.object(obj,key,val))
        self.stack.enter_context(patch.object(system_service,'active',return_value=True))
        self.stack.enter_context(patch.object(system_service,'cli',return_value='Module successfully reloaded'))
        self.stack.enter_context(patch('stat.S_ISSOCK',return_value=True))
        self.stack.enter_context(patch('os.fchown'))
    def save(self):
        return system_service.handle({'action':'favorites-save','payload':{'revision':0,'favorites':[{'mode':'AllStar','target':'12345','slot':'1','enabled':True}]}})
    def test_hash_reconciled_and_no_drift(self):
        result=self.save();self.assertEqual(result['revision'],1)
        current=system_service.load_state();self.assertNotEqual(current['config_hashes'],self.old['config_hashes'])
        self.assertEqual(system_service.config_drift(current),[])
    def test_store_failure_rolls_back_config_and_hash(self):
        with patch.object(favorites_store.Store,'_write',side_effect=ValueError('disk full')):
            with self.assertRaises(ValueError):self.save()
        self.assertEqual((self.etc/'rpt.conf').read_text(),BASE)
        self.assertEqual(system_service.load_state(),self.old)
    def test_preexisting_drift_not_adopted(self):
        (self.etc/'rpt.conf').write_text(BASE+'; external edit\n')
        with self.assertRaisesRegex(ValueError,'drift'):self.save()
        self.assertEqual(system_service.load_state(),self.old)
    def test_reload_rejection_rolls_back(self):
        with patch.object(system_service,'cli',side_effect=['Module reload failed','Module successfully reloaded']):
            with self.assertRaises(ValueError):self.save()
        self.assertEqual((self.etc/'rpt.conf').read_text(),BASE)

    def test_isolation_wrong_digest_never_rewrites_state(self):
        import rf_memory_isolate
        with patch.object(system_service,'save_state') as save:
            with self.assertRaisesRegex(ValueError,'changed since review'):
                rf_memory_isolate.apply_reviewed('60670','0'*64)
        save.assert_not_called()
