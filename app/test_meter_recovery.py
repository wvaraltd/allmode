import os,struct,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import audio_meter as module


class MeterRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'meter'
        self.root_patch=patch.object(module,'ROOT',self.root);self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.commands=[];self.loaded=False;self.hooks={};self.starts=0
        self.meter=module.Meter(self.cli);self.meter.running=True
        self.addCleanup(self.meter.forget)
        self.addCleanup(patch.stopall)
        patch.object(module.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())).start()
        patch.object(module.os,'chown').start()

    def cli(self,command):
        self.commands.append(command)
        if command=='core show channels concise':return 'SimpleUSB/12345'
        if command.startswith('module load '):self.loaded=True;return 'Loaded'
        if command=='core show file formats':return 'allmode_meter'
        if command.startswith('mixmonitor list '):
            if not self.loaded:raise ValueError('Asterisk command failed: No such command')
            return '\n'.join(key+' '+value for key,value in self.hooks.items())
        if command.startswith('mixmonitor stop '):
            self.hooks.pop(command.split()[-1],None);return 'Stopped'
        if command.startswith('mixmonitor start '):
            self.starts+=1;self.hooks['0xdef']='\t'.join(str(self.root/key) for key in ('mixed','rx','tx'));return 'Started'
        raise AssertionError('Unexpected command: '+command)

    def stale(self):
        fd=os.open('/dev/null',os.O_RDONLY)
        self.meter.ident='0xabc';self.meter.channel='SimpleUSB/12345';self.meter.checked=0
        self.meter.fds={'rx':fd};self.meter.values={'rx':({'rms_db':-1},time.monotonic())}
        return fd

    def test_asterisk_restart_missing_mixmonitor_recovers_passively(self):
        oldfd=self.stale()
        result=self.meter.snapshot('12345')
        self.assertTrue(result['active']);self.assertEqual(self.meter.ident,'0xdef')
        self.assertEqual(self.starts,1)
        self.assertNotIn('mixmonitor stop SimpleUSB/12345 0xabc',self.commands)
        self.assertIn('module load app_mixmonitor.so',self.commands)
        self.assertIn('module load format_allmode_meter.so',self.commands)
        self.assertNotIn('0xabc',self.hooks)
        # A new FIFO descriptor may reuse the numeric fd; it cannot still be /dev/null.
        self.assertNotEqual(os.readlink('/proc/self/fd/'+str(oldfd)),'/dev/null')
        os.write(self.meter.fds['tx'],struct.pack('<h',16384)*160)
        self.meter.drain_once();result=self.meter.snapshot('12345')
        self.assertTrue(result['tx']['available']);self.assertEqual(result['tx']['rms_db'],-6)
        self.assertFalse(result['rx']['available'])

    def test_reused_id_foreign_recording_is_not_stopped_or_adopted(self):
        self.loaded=True;self.hooks={'0xabc':'/private/foreign.wav'}
        self.stale();self.meter.snapshot('12345')
        self.assertEqual(self.hooks['0xabc'],'/private/foreign.wav')
        self.assertEqual(self.meter.ident,'0xdef')
        self.assertNotIn('mixmonitor stop SimpleUSB/12345 0xabc',self.commands)
        self.meter.stop()
        self.assertEqual(self.hooks,{'0xabc':'/private/foreign.wav'})

    def test_stop_failure_always_releases_own_descriptors(self):
        fd=self.stale()
        with self.assertRaises(ValueError):self.meter.stop()
        self.assertIsNone(self.meter.ident);self.assertFalse(self.meter.fds);self.assertFalse(self.meter.values)
        with self.assertRaises(OSError):os.fstat(fd)

    def test_stop_reused_foreign_id_does_not_signal_it(self):
        self.loaded=True;self.hooks={'0xabc':'/private/foreign.wav'}
        self.stale();self.meter.stop()
        self.assertEqual(self.hooks,{'0xabc':'/private/foreign.wav'})
        self.assertFalse(any(c.startswith('mixmonitor stop ') for c in self.commands))

    def test_failed_module_or_channel_retries_are_bounded(self):
        def failed(command):self.commands.append(command);raise ValueError('Asterisk unavailable')
        self.meter.cli=failed
        with self.assertRaisesRegex(ValueError,'Passive audio meter unavailable'):self.meter.snapshot('12345')
        count=len(self.commands)
        with self.assertRaises(ValueError):self.meter.snapshot('12345')
        self.assertEqual(len(self.commands),count)
        self.meter.retry_at=0;self.meter.cli=self.cli
        self.assertTrue(self.meter.snapshot('12345')['active'])

    def test_actual_cli_extensionless_triple_and_exact_ownership(self):
        real='0x7f14000f10\t'+'\t'.join(str(self.root/key) for key in ('mixed','rx','tx'))
        self.assertEqual(self.meter.owned_ids(real),{'0x7f14000f10'})
        named='0xabc '+' '.join(str(self.root/(key+'.ameter')) for key in ('mixed','rx','tx'))
        self.assertEqual(self.meter.owned_ids(named),{'0xabc'})
        for invalid in (real+'.foreign',real.replace('/rx','/foreign'),real.replace('0x7f14000f10','0x7f14000f10junk'),
                        '0xabc '+str(self.root/'mixed'),real+' extra'):
            self.assertEqual(self.meter.owned_ids(invalid),set())


if __name__=='__main__':unittest.main()
