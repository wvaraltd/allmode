"""Coupled controller -> request transport -> real helper whitelist -> mocked OS.
Run with bash .github/ci/run-regressions.sh (ordinary user, disposable checkout).
No network sockets, Asterisk processes, radio operations, or installed files.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server
import system_service as service
import system_client
import digital
import codec_selection


class ManagedStatusContract(unittest.TestCase):
    def test_actual_controller_uses_only_helper_accepted_status_commands(self):
        commands=[]
        def os_run(argv, **kwargs):
            if argv == ['systemctl','is-active','asterisk']:
                return 'active\n'
            if argv[:2] != ['/usr/sbin/asterisk','-rx']:
                raise AssertionError('Unexpected OS operation: '+repr(argv))
            command=argv[2]
            commands.append(command)
            replies={
                'rpt show registrations':'Registered\n',
                'rpt stats 12345':'STATISTICS\nNodes currently connected to us: 23456\nSignal on input: NO\nSystem: Synthetic\n',
                'rpt xnode 12345':'23456 192.0.2.1 0 IN 00:00:01 ESTABLISHED\nRPT_ALINKS=1,23456TK\n',
                'module show like chan_echolink.so':'0 modules loaded\n',
            }
            if command not in replies:
                raise AssertionError('Unexpected or mutating Asterisk command: '+command)
            return replies[command]

        # Substitute only the socket transport, not request validation/dispatch.
        def in_process_request(action, **values):
            return service.handle(dict(action=action, **values))

        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'state.json').write_text(json.dumps({'node':'12345','radio':False,'config_hashes':{}}))
            with patch.object(service,'STATE',root), patch.object(service,'ETC',root), \
                 patch.object(service,'RUN',root), patch.object(digital,'RUN',root), \
                 patch.object(digital,'ROOT',root), patch.object(server,'AUDIO_FILE',root/'audio.json'), \
                 patch.object(codec_selection,'DRAFT',root/'station-setup.json'), \
                 patch.object(codec_selection,'RUN',root), patch.object(service,'run',side_effect=os_run), \
                 patch.object(system_client,'request',side_effect=in_process_request):
                c=server.ManagedController()
                result=c.snapshot()
                self.assertFalse(result['simulation'])
                self.assertEqual(result['node'],'12345')
                self.assertTrue(result['connected'])
                self.assertEqual(result['active_connections'][0]['target'],'23456')
                self.assertEqual(result['current_speaker']['identity'],'Via node 23456')
                self.assertTrue(result['current_speaker']['active'])
                c.snapshot()  # shared xnode cache, no per-browser extra CLI
                self.assertEqual(commands.count('rpt xnode 12345'),1)
                # Same real helper path must still reject a different node.
                with self.assertRaisesRegex(ValueError,'not permitted'):
                    c.run_cli('rpt xnode 54321')
                self.assertNotIn('rpt xnode 54321',commands)
        print('COUPLED PASS: actual ManagedController + real status/CLI dispatcher and whitelist; OS boundary only mocked')


if __name__=='__main__':
    unittest.main()
