import contextlib
import json
import tempfile
import unittest
from unittest.mock import patch, Mock
import sa818_hardware as hw


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = dict(hw.PRESET, rx='446.1000', tx='446.1000')
        self.port = Mock()
        self.port.read_until.side_effect = [b'+DMOCONNECT:0\r\n', b'+DMOSETGROUP:0\r\n',
                                          b'+DMOSETVOLUME:0\r\n', b'+DMOSETFILTER:0\r\n', b'+DMOSETTAIL:0\r\n']
        self.guard = Mock()
        self.hardware = hw.Hardware(self.temp.name, True, lambda p: contextlib.nullcontext(self.port), self.guard)
        self.payload = dict(action='program', settings=self.settings, port='/dev/serial0', safe=True, confirm='PROGRAM')
        self.detect = patch.object(hw, 'ports', return_value=[dict(path='/dev/serial0')])
        self.detect.start()
        self.addCleanup(self.detect.stop)

    def test_exact_protocol_and_tone_table(self):
        self.assertEqual(len(hw.TONES), 39)
        self.assertEqual(hw.commands(self.settings), [
            ('AT+DMOSETGROUP=1,446.1000,446.1000,0012,6,0012', '+DMOSETGROUP:0'),
            ('AT+DMOSETVOLUME=6', '+DMOSETVOLUME:0'), ('AT+SETFILTER=0,0,0', '+DMOSETFILTER:0'),
            ('AT+SETTAIL=0', '+DMOSETTAIL:0')])

    def test_tx_rx_order_and_disabled_filters(self):
        s = dict(self.settings, tx='446.125', rx_ctcss='0', tx_ctcss='250.3', reverse_burst=True,
                 emphasis=False, highpass=True, lowpass=False)
        cmds = hw.commands(s)
        self.assertIn('446.1250,446.1000,0038,6,0000', cmds[0][0])
        self.assertEqual(cmds[2][0], 'AT+SETFILTER=1,0,1')
        self.assertEqual(cmds[3][0], 'AT+SETTAIL=1')

    def test_reject_invalid(self):
        for key, value in [('rx','nan'),('tx','446.10001'),('rx','446.1001'),('rx','144.5000'),
                           ('tx','446.1\r\nAT+SETTAIL=1'),('band','auto'),('volume',0),('volume',True),
                           ('squelch',9),('bandwidth',2),('rx_ctcss','254.1'),('emphasis',1)]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                hw.validate(dict(self.settings, **{key:value}))

    def test_reverse_requires_ctcss(self):
        with self.assertRaises(ValueError):
            hw.validate(dict(self.settings, reverse_burst=True, tx_ctcss='0'))

    def test_preview_and_save_never_open_port(self):
        for action in ('preview','save'):
            self.hardware.action(dict(action=action, settings=self.settings))
        self.port.write.assert_not_called()
        self.guard.assert_not_called()
        self.assertEqual(self.hardware.read('draft.json'), self.settings)

    def test_success_is_not_readback(self):
        result = self.hardware.action(self.payload)
        self.assertEqual(result['last_program']['state'], 'acknowledged-not-verified')
        self.assertFalse(result['last_program']['verified_by_readback'])
        self.assertEqual(len(result['last_program']['acknowledged']), 4)
        self.assertEqual(self.guard.call_count, 6)

    def test_partial_write_persisted(self):
        self.port.read_until.side_effect = [b'+DMOCONNECT:0\r\n', b'+DMOSETGROUP:0\r\n', OSError('unplugged')]
        with self.assertRaises(OSError):
            self.hardware.action(self.payload)
        record = self.hardware.read('program.json')
        self.assertEqual(record['state'], 'incomplete')
        self.assertEqual(record['acknowledged'], ['AT+DMOSETGROUP'])
        self.assertEqual(self.port.write.call_count, 3)

    def test_refusal_before_serial(self):
        for change in [dict(safe=False),dict(confirm='yes'),dict(port='/etc/passwd')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.hardware.action(dict(self.payload, **change))
        self.port.write.assert_not_called()

    def test_disabled(self):
        self.hardware.enabled = False
        with self.assertRaises(ValueError):
            self.hardware.action(self.payload)
        self.port.write.assert_not_called()

    def test_busy(self):
        with self.hardware.lock, self.assertRaises(ValueError):
            self.hardware.action(self.payload)

    def test_guard_failure(self):
        self.guard.side_effect = ValueError('asterisk active')
        with self.assertRaises(ValueError):
            self.hardware.action(self.payload)
        self.port.write.assert_not_called()

    def test_service_start_between_guard_and_serial_open_is_denied(self):
        self.guard.side_effect=[None,ValueError('asterisk started')]
        with self.assertRaises(ValueError):self.hardware.action(self.payload)
        self.port.write.assert_not_called()

    def test_strict_ack(self):
        self.port.read_until.side_effect = [b'+DMOCONNECT:1\r\n'] * 16
        with self.assertRaises(ValueError):
            self.hardware.action(self.payload)
        self.assertIsNone(self.hardware.read('program.json'))

    def test_echo_is_ignored(self):
        self.port.read_until.side_effect = [b'AT+DMOCONNECT\r\n',b'+DMOCONNECT:0\r\n']
        self.assertEqual(self.hardware.exchange(self.port,'AT+DMOCONNECT','+DMOCONNECT:0'),'+DMOCONNECT:0')

    def test_maintenance_unknown_and_running_denied(self):
        for state, code in [('active\n',0),('activating\n',0),('',1),('',0)]:
            with patch.object(hw.subprocess,'run',return_value=Mock(stdout=state,returncode=code)), self.assertRaises(ValueError):
                hw.maintenance_guard()

    def test_probe_version_does_not_program(self):
        self.port.read_until.side_effect=[b'+DMOCONNECT:0\r\n',b'+VERSION:V4.2\r\n']
        result=self.hardware.action(dict(action='probe',port='/dev/serial0',safe=True))
        self.assertIn('V4.2',result['device']['version'])
        self.assertIsNone(result['last_program'])

if __name__ == '__main__':
    unittest.main()
