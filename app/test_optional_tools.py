import unittest
from unittest.mock import patch
import system_service as service


class OptionalToolTests(unittest.TestCase):
    def test_missing_nmcli_blocks_every_wifi_action_before_mutation(self):
        for action in ('wifi-scan','wifi-save','wifi-connect'):
            with self.subTest(action=action), patch.object(service.shutil,'which',return_value=None), \
                 patch.object(service,'atomic') as write, patch.object(service,'run') as run:
                with self.assertRaisesRegex(ValueError,'nmcli is unavailable'):
                    service.handle(dict(action=action,ssid='Synthetic',password='test-password',id='a'*36))
                write.assert_not_called()
                run.assert_not_called()

    def test_connect_requires_scheduler_before_modifying_autoconnect(self):
        with patch.object(service.shutil,'which',side_effect=lambda name: '/usr/bin/nmcli' if name=='nmcli' else None), \
             patch.object(service,'run') as run, patch.object(service,'atomic') as write:
            with self.assertRaisesRegex(ValueError,'systemd-run is unavailable'):
                service.handle(dict(action='wifi-connect',id='a'*36))
            run.assert_not_called()
            write.assert_not_called()

    def test_missing_diagnostics_are_not_empty_success_or_audio_test(self):
        with patch.object(service.shutil,'which',return_value=None), patch.object(service,'run') as run:
            result=service.handle(dict(action='network-status'))
        run.assert_not_called()
        self.assertIn('Unavailable: ip',result['output'])
        self.assertIn('Unavailable: nmcli',result['output'])
        self.assertIn('Unavailable ALSA',result['output'])
        self.assertFalse(result['audio_tested'])
        self.assertFalse(any(result['tools'].values()))

    def test_partial_diagnostics_run_only_present_tools(self):
        with patch.object(service.shutil,'which',side_effect=lambda name: '/usr/bin/ip' if name=='ip' else None), \
             patch.object(service,'run',return_value='synthetic interfaces') as run:
            result=service.handle(dict(action='network-status'))
        self.assertEqual([c.args[0] for c in run.call_args_list],[['ip','-brief','address'],['ip','route']])
        self.assertIn('synthetic interfaces',result['output'])
        self.assertFalse(result['audio_tested'])

    def test_save_still_saves_without_connecting_or_autoconnect(self):
        with patch.object(service.shutil,'which',return_value='/usr/bin/nmcli'), \
             patch.object(service,'atomic') as write, patch.object(service,'run') as run:
            result=service.handle(dict(action='wifi-save',ssid='Synthetic',password='test-password'))
        self.assertTrue(result['ok'])
        self.assertIn('autoconnect = false',write.call_args.args[1])
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.args[0][:3],['/usr/bin/nmcli','connection','load'])

    def test_present_audio_tools_are_not_executed_or_claimed_tested(self):
        with patch.object(service.shutil,'which',side_effect=lambda name: '/usr/bin/'+name), \
             patch.object(service,'run',return_value='synthetic status') as run:
            result=service.handle(dict(action='network-status'))
        self.assertEqual(run.call_count,3)
        self.assertFalse(result['audio_tested'])
        self.assertIn('have not been tested',result['output'])


if __name__=='__main__':
    unittest.main()
