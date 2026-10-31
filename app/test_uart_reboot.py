import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import sa818_hardware as hw


class UartRebootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.marker = self.root / 'serial-reboot-required'
        self.boot = self.root / 'boot_id'
        self.stat = self.root / 'boot_stat'
        self.boot.write_text('boot-one\n')
        self.stat.write_text('btime 100\n')

    def status(self):
        return hw.uart_reboot_required(self.root, self.boot, self.stat)

    def test_no_change(self):
        self.assertIs(self.status(), False)

    def test_default_tone_and_existing_draft_preservation(self):
        self.assertEqual((hw.PRESET['rx_ctcss'], hw.PRESET['tx_ctcss']), ('100.0', '100.0'))
        h = hw.Hardware(self.root)
        saved = dict(hw.PRESET, rx='438.6750', tx='438.6750', rx_ctcss='91.5', tx_ctcss='67.0')
        h.write('draft.json', saved)
        snapshot = h.snapshot()
        self.assertEqual(snapshot['draft'], saved)
        self.assertEqual(snapshot['preset']['rx_ctcss'], '100.0')

    def test_current_boot_requires_reboot(self):
        self.marker.write_text('boot_id=boot-one\n')
        self.assertIs(self.status(), True)

    def test_completed_reboot_clears_status_without_deleting_marker(self):
        self.marker.write_text('boot_id=boot-one\n')
        self.boot.write_text('boot-two\n')
        self.assertIs(self.status(), False)
        self.assertTrue(self.marker.exists())

    def test_legacy_marker_before_and_after_boot(self):
        self.marker.write_text('')
        os.utime(self.marker, (150, 150))
        self.assertIs(self.status(), True)
        self.stat.write_text('btime 200\n')
        self.assertIs(self.status(), False)

    def test_unknown_status_does_not_claim_ready_or_pending(self):
        self.marker.write_text('boot_id=boot-one\n')
        self.boot.unlink()
        self.assertIsNone(self.status())
        self.marker.write_text('')
        self.stat.write_text('missing boot time')
        self.assertIsNone(self.status())

    def test_pending_blocks_probe_and_program_before_transport(self):
        transport = Mock()
        h = hw.Hardware(self.root, True, transport=transport, guard=Mock())
        settings = dict(hw.PRESET, rx='446.1000', tx='446.1000')
        with patch.object(hw, 'uart_reboot_required', return_value=True):
            for action in ('probe', 'program'):
                with self.assertRaisesRegex(ValueError, 'needs a reboot'):
                    h.action(dict(action=action, settings=settings, safe=True, confirm='PROGRAM', port='/dev/serial0'))
            h.action(dict(action='save', settings=settings))
            self.assertEqual(h.read('draft.json')['rx'], '446.1000')
        transport.assert_not_called()


if __name__ == '__main__':
    unittest.main()
