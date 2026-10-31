import unittest
from unittest.mock import patch
import radio_readback as radio

class RadioReadbackTests(unittest.TestCase):
    def test_supported_and_invalid_replies(self):
        self.assertEqual(radio.parse_rssi(b'RSSI=042\r\n'),42)
        self.assertEqual(radio.parse_rssi(b'RSSI:120\r\n'),120)
        for reply in (b'ERROR\r\n',b'RSSI=999\r\n',b'RSSI=-42\r\n'):
            self.assertIsNone(radio.parse_rssi(reply))
    def test_expired_value_is_not_shown(self):
        with patch.object(radio,'_thread',object()),patch.object(radio,'_state',{'value':42,'updated':10}),patch.object(radio.time,'monotonic',return_value=16):
            self.assertIsNone(radio.snapshot()['value'])
