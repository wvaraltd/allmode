import struct
import unittest
from unittest.mock import patch
from dstar_hardware import HardwareCodec


class HardwareTests(unittest.TestCase):
    def codec(self):
        return object.__new__(HardwareCodec)

    def test_encode_big_endian_and_voice_payload(self):
        codec = self.codec()
        with patch.object(codec, 'exchange', return_value=b'\x01\x48'+bytes(range(9))) as exchange:
            self.assertEqual(codec.encode(struct.pack('<160h', *([1000]*160)), .5), bytes(range(9)))
            self.assertEqual(exchange.call_args.args[0], bytes.fromhex('610143024000a0')+struct.pack('>160h', *([500]*160)))

    def test_decode_endian_gain_and_clipping(self):
        codec = self.codec()
        with patch.object(codec, 'exchange', return_value=b'\x00\xa0'+struct.pack('>160h', *([20000]*160))):
            self.assertEqual(struct.unpack('<160h', codec.decode(bytes(9), 2)), (32767,)*160)

    def test_reject_bad_hardware_responses(self):
        codec = self.codec()
        with patch.object(codec, 'exchange', return_value=bytes(11)):
            with self.assertRaises(OSError): codec.encode(bytes(320), 1)
            with self.assertRaises(OSError): codec.decode(bytes(9), 1)
