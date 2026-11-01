"""Station apply preserves reviewed RF configuration; no Asterisk or RF calls."""
import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import system_service as service
from favorites_store import Store
from rf_memories import Config, BEGIN
import test_system_service


class RFRegenerationTests(unittest.TestCase):
    def setUp(self):
        fixture=test_system_service.SystemTests();fixture.setUp()
        self.config=fixture.config;self.templates=fixture.templates
        self.templates['rpt.conf']='[node-main](!)\nfunctions=functions\nmacro=macro\n\n[functions]\n3=ilink,3\n5=macro\n\n[macro]\n99=*312345#\n\n#tryinclude "custom/*.conf"\n'
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.etc=root/'etc';self.etc.mkdir();self.state=root/'state';self.state.mkdir()
        self.runtime=root/'runtime';self.runtime.mkdir()
        self.enter(patch.object(service,'ETC',self.etc));self.enter(patch.object(service,'STATE',self.state));self.enter(patch.object(service,'RUN',self.runtime))
        node,rendered=service.render(self.config,self.templates)
        self.rendered=rendered
        for name,text in rendered.items():(self.etc/name).write_text(text)
        self.rf=Config(self.etc/'rpt.conf',node,lock=self.state/'rf-memories.lock')
        self.plan=self.rf.isolation_plan()
        self.rf.apply_isolation(self.plan['plan_digest'])
        (self.state/'rf-isolation.json').write_text(json.dumps(self.plan))
        self.store=Store(self.state/'favorites.json',transaction=lambda old,new:self.rf.transaction(new['favorites']))
        self.store.replace({'revision':0,'favorites':[{'mode':'AllStar','target':'12346','slot':'12','enabled':True}]})

    def enter(self,manager):
        result=manager.start();self.addCleanup(manager.stop);return result

    def test_reapply_preserves_reviewed_tables_macros_and_commands(self):
        output,extra=service.reconcile_rf_config('12345',self.rendered)
        text=output['rpt.conf']
        self.assertIn('functions=allmode-12345-local',text)
        self.assertIn('12=*D12D#',text)
        self.assertIn('99=*312345#',text)
        self.assertIn('3=ilink,3',text)
        self.assertIn('#tryinclude "custom/*.conf"',text)
        self.assertEqual(extra,{})
        (self.etc/'rpt.conf').write_text(text)
        self.assertTrue(self.rf.status(self.store.snapshot()['favorites'])['available'])

    def test_node_change_and_missing_approval_fail_before_live_writes(self):
        before=(self.etc/'rpt.conf').read_text()
        with self.assertRaises(ValueError):service.reconcile_rf_config('54321',self.rendered)
        (self.state/'rf-isolation.json').unlink()
        with self.assertRaises(ValueError):service.reconcile_rf_config('12345',self.rendered)
        self.assertEqual((self.etc/'rpt.conf').read_text(),before)

    def test_existing_include_is_preserved_and_conflicts_fail_closed(self):
        custom=self.etc/'custom';custom.mkdir();(custom/'extras.conf').write_text('[custom-note]\nvalue=unchanged\n')
        output,extra=service.reconcile_rf_config('12345',self.rendered)
        self.assertEqual(extra,{})
        self.assertEqual((custom/'extras.conf').read_text(),'[custom-note]\nvalue=unchanged\n')
        (custom/'extras.conf').write_text('[allmode-12345-local]\n1=ilink,1\n')
        with self.assertRaises(ValueError):service.reconcile_rf_config('12345',self.rendered)

    def test_included_physical_node_fails_closed_with_clear_limit(self):
        import re
        path=self.etc/'rpt.conf';text=path.read_text()
        pattern=r'(?ms)^\[12345\]\(node-main\)[^\n]*\n.*?(?=^\[|\Z)'
        node=re.search(pattern,text).group(0)
        included=self.etc/'station.conf';included.write_text(node)
        text=re.sub(pattern,'',text)+'\n#include "station.conf"\n'
        path.write_text(text)
        with self.assertRaisesRegex(ValueError,'physical station node is in an included file'):
            service.reconcile_rf_config('12345',self.rendered)
        self.assertEqual(path.read_text(),text)
        self.assertEqual(included.read_text(),node)

    def test_user_macro_edits_are_not_erased_by_regeneration(self):
        path=self.etc/'rpt.conf';text=path.read_text()
        text=text.replace('[allmode-12345-macro]\n','[allmode-12345-macro]\n88=*312346#\n')
        path.write_text(text)
        with self.assertRaisesRegex(ValueError,'owner-edited'):
            service.reconcile_rf_config('12345',self.rendered)
        self.assertEqual(path.read_text(),text)

    def test_failed_restart_restores_complete_preexisting_isolated_configuration(self):
        baseline=self.state/'baseline';baseline.mkdir()
        for name,text in self.templates.items():(baseline/name).write_text(text)
        before={name:(self.etc/name).read_text() for name in service.FILES}
        def execute(argv,**kw):
            if argv==['systemctl','start','asterisk']:raise ValueError('simulated failed restart')
            return ''
        def write(path,text,*args):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        with patch.object(service,'active',return_value=False),patch.object(service,'run',side_effect=execute),patch.object(service,'radio_lock',contextlib.nullcontext),patch.object(service,'atomic',side_effect=write),patch.object(service,'runtime_config'):
            with self.assertRaisesRegex(ValueError,'restored'):service.install_config(self.config)
        self.assertEqual({n:(self.etc/n).read_text() for n in service.FILES},before)
        self.assertIn(BEGIN,before['rpt.conf'])
        self.assertEqual(json.loads((self.state/'rf-isolation.json').read_text()),self.plan)
        self.assertTrue(self.store.snapshot()['favorites'][0]['enabled'])
