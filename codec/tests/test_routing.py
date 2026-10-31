# SPDX-License-Identifier: GPL-2.0-or-later
import unittest
from unittest.mock import patch
from routing import Router,Capability,Mode,DSTAR,BackendError

class FakeContext:
    def __init__(self): self.closed=False; self.calls=0; self.fail=False
    def encode(self,data):
        if self.fail: raise OSError('device disconnected')
        self.calls+=1; return b'123456789'
    def close(self): self.closed=True

class FakeHardware:
    name='hardware'
    def capabilities(self): return (DSTAR,)
    def open(self,cap): return FakeContext()

class Routing(unittest.TestCase):
    def setUp(self):
        self.mock=patch('routing.Stream',FakeContext); self.mock.start()
    def tearDown(self): self.mock.stop()
    def test_default_and_queued_switch(self):
        r=Router(FakeHardware()); self.assertEqual(r.active,'software')
        old=r.context; r.begin(); r.request('hardware')
        self.assertTrue(r.state()['queued']); self.assertEqual(r.active,'software')
        r.encode(bytes(320)); self.assertEqual(old.calls,1)
        r.end(); self.assertTrue(old.closed); self.assertEqual(r.active,'hardware')
        hardware=r.context; r.begin(); r.encode(bytes(320)); self.assertEqual(hardware.calls,1)
        self.assertEqual(old.calls,1); r.request('software'); r.end()
        self.assertTrue(hardware.closed); self.assertEqual(r.active,'software'); r.close()
    def test_unavailable_no_fallback(self):
        r=Router(); old=r.context
        with self.assertRaises(BackendError): r.request('hardware')
        self.assertTrue(old.closed); self.assertIsNone(r.active); self.assertEqual(r.requested,'hardware')
        self.assertIsNone(r.context); r.request('software'); r.close()
    def test_unsupported_profiles(self):
        for mode in Mode:
            if mode==Mode.DSTAR: continue
            r=Router()
            with self.assertRaises(BackendError): r.request('software',Capability(mode,'unspecified',8000,160,9))
            self.assertIsNone(r.active); r.close()
    def test_failure_does_not_fallback(self):
        r=Router(FakeHardware()); r.request('hardware'); r.begin(); r.context.fail=True
        with self.assertRaises(BackendError): r.encode(bytes(320))
        self.assertIsNone(r.active); self.assertIsNone(r.context); self.assertFalse(r.busy)
    def test_same_backend_resets_history_and_last_request_wins(self):
        r=Router(FakeHardware()); first=r.context; r.begin(); r.request('hardware'); r.request('software'); r.end()
        self.assertTrue(first.closed); self.assertIsNot(first,r.context); self.assertEqual(r.active,'software'); r.close()
    def test_frame_requires_stream(self):
        r=Router()
        with self.assertRaises(BackendError): r.encode(bytes(320))
        r.close()

if __name__=='__main__': unittest.main()
