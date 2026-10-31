# SPDX-License-Identifier: GPL-2.0-or-later
import unittest
from dstar import make_wav
from parrot import Parrot

class ParrotTests(unittest.TestCase):
    def setUp(self):
        self.now=0.; self.jobs=[]; self.calls=[]
        def process(pcm): self.calls.append(pcm); return make_wav(pcm)
        self.p=Parrot(processor=process,clock=lambda:self.now,launch=self.jobs.append)
    def ready(self):
        self.p.enable(2); self.p.record(); self.p.complete(bytes(320)); self.jobs.pop()()
    def test_record_then_play_local(self):
        self.ready(); self.assertEqual(self.p.state()['phase'],'ready')
        self.assertEqual(self.p.playback(),make_wav(bytes(320)))
        with self.assertRaises(ValueError): self.p.record()
        self.p.finished(); self.assertEqual(self.p.phase,'idle'); self.assertIsNone(self.p.wav)
        self.assertFalse(self.p.state()['network_tx']); self.assertFalse(self.p.state()['rf_tx'])
    def test_disable_at_each_phase(self):
        for phase in ['recording','processing','ready','playing']:
            self.setUp(); self.p.enable(); self.p.record()
            if phase!='recording': self.p.complete(bytes(320))
            if phase in ('ready','playing'): self.jobs.pop()()
            if phase=='playing': self.p.playback()
            self.p.disable()
            for job in self.jobs: job()
            self.assertEqual(self.p.phase,'disabled'); self.assertIsNone(self.p.wav)
    def test_cancel_inflight_and_repeated_clicks(self):
        self.p.enable(); self.p.enable(); self.p.record()
        with self.assertRaises(ValueError): self.p.record()
        self.p.complete(bytes(320)); self.p.stop(); self.jobs.pop()()
        self.assertEqual(self.p.phase,'idle'); self.assertIsNone(self.p.wav)
        self.p.stop(); self.p.disable(); self.p.disable()
    def test_duration_and_disconnect_timeout(self):
        self.p.enable(1); self.p.record(); self.now=4; self.p.tick(); self.assertEqual(self.p.phase,'idle')
        self.p.record(); self.now=21; self.p.tick(); self.assertEqual(self.p.phase,'idle')
        self.assertIsNone(self.p.wav)
    def test_playback_timeout(self):
        self.ready(); self.p.playback(); self.now=91; self.p.heartbeat(); self.p.tick()
        self.assertEqual(self.p.phase,'idle'); self.assertIsNone(self.p.wav)
    def test_pending_hardware_and_unavailable(self):
        self.ready(); self.p.select('hardware'); self.assertTrue(self.p.queued); self.assertEqual(self.p.active,'software')
        self.p.playback(); self.p.finished(); self.assertIsNone(self.p.active)
        with self.assertRaises(RuntimeError): self.p.record()
        self.p.select('software'); self.p.record(); self.assertEqual(self.p.phase,'recording')
    def test_processing_failure_no_fallback(self):
        self.p.processor=lambda _: (_ for _ in ()).throw(OSError('codec missing'))
        self.p.enable(); self.p.record(); self.p.complete(bytes(320)); self.jobs.pop()()
        self.assertEqual(self.p.error,'codec missing'); self.assertIsNone(self.p.wav)
    def test_bounded_input(self):
        for bad in [b'',b'x',bytes(16002)]:
            self.p.enable(1); self.p.record()
            with self.assertRaises(ValueError): self.p.complete(bad)
            self.assertEqual(self.p.phase,'idle')

if __name__=='__main__': unittest.main()
