"""Installer marker may affect only a genuinely fresh unsaved station."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import onboarding
from onboarding import Onboarding,GROUPS
import operator_store

class FreshDVSwitchProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.profile=self.root/'install-profile.json';self.applied=self.root/'config.json';self.binary=self.root/'MMDVM_Bridge'
        for name,path in [('INSTALL_PROFILE',self.profile),('APPLIED_CONFIG',self.applied),('MMDVM_BINARY',self.binary)]:
            p=patch.object(onboarding,name,path);p.start();self.addCleanup(p.stop)
        self.station=Onboarding(self.root/'draft')
        self.profile.write_text(json.dumps({'version':1,'dvswitch_dmr_default':True}));self.binary.write_text('test fixture, not executed')
    def value(self):
        return next(f['value'] for g in self.station.snapshot()['groups'] if g['id']=='dmr' for f in g['fields'] if f['key']=='dvswitch')
    def station_values(self):return dict(callsign='N0TEST',name='',location='',email='')
    def test_fresh_marker_and_binary_default_true_but_not_saved(self):
        self.assertTrue(self.value());self.assertEqual(self.station.read(),{});self.assertFalse(self.station.snapshot()['saved']);self.assertFalse(self.station.path.exists())
        defaults=self.station.effective_defaults()
        for mode in ('allstar','echolink','brandmeister','tgif','dstar'):self.assertFalse(defaults[mode]['enabled'])
        self.assertEqual(defaults['dmr']['id'],'');self.assertEqual(defaults['brandmeister']['password'],'');self.assertEqual(defaults['tgif']['password'],'')
    def test_no_marker_retains_native_default(self):
        self.profile.unlink();self.assertFalse(self.value())
    def test_missing_binary_retains_native_default(self):
        self.binary.unlink();self.assertFalse(self.value())
    def test_invalid_or_disabled_marker_retains_native(self):
        for marker in ({'version':True,'dvswitch_dmr_default':True},{'version':1,'dvswitch_dmr_default':'yes'},{'version':2,'dvswitch_dmr_default':True},{'version':1,'dvswitch_dmr_default':False},[]):
            self.profile.write_text(json.dumps(marker));self.assertFalse(self.value())
        self.profile.write_text('not JSON');self.assertFalse(self.value())
    def write_draft(self,data):
        self.station.path.parent.mkdir();self.station.path.write_text(json.dumps(data));return self.station.path.read_bytes()
    def test_old_draft_missing_field_stays_native_unchanged(self):
        original=self.write_draft({'station':self.station_values(),'dmr':{'id':'1234567'}})
        self.assertFalse(self.value());self.assertFalse(self.station.read()['dmr']['dvswitch']);self.assertEqual(self.station.path.read_bytes(),original)
    def test_existing_explicit_false_preserved(self):
        original=self.write_draft({'station':self.station_values(),'dmr':{'dvswitch':False}})
        self.assertFalse(self.value());self.assertEqual(self.station.path.read_bytes(),original)
    def test_existing_empty_draft_not_treated_as_fresh(self):
        self.write_draft({});self.assertFalse(self.value())
    def test_applied_config_without_draft_blocks_preset(self):
        self.applied.write_text('{}');self.assertFalse(self.value());self.assertFalse(self.station.path.exists())
    def test_unreadable_presence_fails_closed(self):
        with patch.object(onboarding,'no_applied_config',return_value=False):self.assertFalse(self.value())
    def test_protected_applied_state_requires_explicit_helper_absence(self):
        original=type(self.applied).lstat
        def lstat(path,*args,**kwargs):
            if path==self.applied:raise PermissionError('root-only state')
            return original(path,*args,**kwargs)
        with patch.object(type(self.applied),'lstat',lstat):
            for state,expected in [({'applied_config':False,'applied_state':False},True),({'applied_config':True,'applied_state':False},False),({'applied_config':False,'applied_state':True},False),({},False),({'applied_config':0,'applied_state':0},False)]:
                with patch('system_client.request',return_value=state) as request:
                    self.assertEqual(self.value(),expected);request.assert_called_once_with('installation-state')
            with patch('system_client.request',side_effect=OSError('unavailable')):self.assertFalse(self.value())
    def test_missing_marker_never_asks_privileged_helper(self):
        self.profile.unlink()
        with patch('system_client.request',side_effect=AssertionError('unexpected helper')):self.assertFalse(self.value())
    def test_installation_state_helper_is_fixed_and_read_only(self):
        import system_service
        with patch.object(system_service,'STATE',self.root),patch.object(system_service,'run',side_effect=AssertionError('no CLI')):
            self.assertEqual(system_service.handle({'action':'installation-state'}),{'applied_config':False,'applied_state':False})
            self.applied.write_text('private credentials not read')
            result=system_service.handle({'action':'installation-state','path':'/etc/shadow'})
            self.assertEqual(result,{'applied_config':True,'applied_state':False})
            (self.root/'state.json').write_text('private state not read')
            self.assertEqual(system_service.handle({'action':'installation-state'}),{'applied_config':True,'applied_state':True})
    def test_station_first_section_save_retains_fresh_choice_only(self):
        self.station.save_section('station',{'station':self.station_values()})
        saved=self.station.read();self.assertTrue(saved['dmr']['dvswitch'])
        self.profile.unlink();self.binary.unlink();self.assertTrue(self.value())
        for mode in ('allstar','echolink','brandmeister','tgif','dstar'):self.assertFalse(saved[mode]['enabled'])
    def test_ui_first_group_save_retains_choice_without_network_activation(self):
        operator_store.update_group(self.station,'station',self.station_values())
        saved=self.station.read();self.assertTrue(saved['dmr']['dvswitch'])
        for mode in ('allstar','echolink','brandmeister','tgif','dstar'):self.assertFalse(saved[mode]['enabled'])
    def test_existing_state_without_config_is_not_fresh(self):
        self.applied.with_name('state.json').write_text('{}')
        self.assertFalse(self.value())
    def test_explicit_native_submission_remains_native(self):
        data={g:{k:d for k,_,_,d in fields} for g,fields in GROUPS.items()};data['station']=self.station_values()
        self.station.save(data);self.assertFalse(self.value());self.assertFalse(self.station.read()['dmr']['dvswitch'])

if __name__=='__main__':unittest.main()
