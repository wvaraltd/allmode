import os, sys, time, struct, unittest, threading, platform
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import audio_meter as m

class MeterTests(unittest.TestCase):
    def meter(self):
        obj=m.Meter(lambda command:'0x1234')
        obj.ident='0x1234';obj.channel='SimpleUSB/12345';obj.checked=time.monotonic()
        return obj
    def test_pcm(self):
        self.assertEqual(m.measure(b'')['rms_db'],-96)
        self.assertEqual(m.measure(bytes(320))['rms_db'],-96)
        self.assertAlmostEqual(m.measure(struct.pack('<h',16384)*160)['rms_db'],-6,places=1)
        self.assertTrue(m.measure(struct.pack('<h',-32768))['clipping'])
        self.assertEqual(m.measure(bytes(321)),m.measure(bytes(320)))
    def test_latest_window_and_stream_independence(self):
        obj=self.meter();r,w=os.pipe();t,u=os.pipe();os.set_blocking(r,False);os.set_blocking(t,False)
        obj.fds={'rx':r,'tx':t}
        try:
            os.write(w,struct.pack('<h',30000)*800+bytes(1600))
            os.write(u,struct.pack('<h',16384)*160)
            obj.drain_once();s=obj.snapshot('12345')
            self.assertEqual(s['rx']['rms_db'],-96)
            self.assertEqual(s['tx']['rms_db'],-6)
            self.assertEqual(s['sequence'],2)
            # Two consumers see the same independent snapshot, not consumed peaks.
            self.assertEqual(obj.snapshot('12345')['tx']['peak_db'],s['tx']['peak_db'])
            obj.drain_once();self.assertEqual(obj.sequence,2)
        finally:obj.stop();os.close(w);os.close(u)
    def test_stale(self):
        obj=self.meter();obj.values['rx']=(m.measure(struct.pack('<h',20000)),time.monotonic()-.4)
        s=obj.snapshot('12345');self.assertFalse(s['rx']['available']);self.assertEqual(s['rx']['rms_db'],-96)
        self.assertIsNone(s['tx']['age_ms'])
    def test_bad_node_and_missing_format(self):
        calls=[]
        obj=m.Meter(lambda c:calls.append(c) or 'SimpleUSB/12345')
        with self.assertRaises(ValueError):obj.start('bad;node')
        self.assertEqual(calls,[])
        with self.assertRaisesRegex(ValueError,'format unavailable'):obj.start('12345')
        self.assertFalse(any(c.startswith('mixmonitor start') for c in calls))
    def test_backlog_not_fresh(self):
        obj=self.meter();obj.fds={'rx':7}
        with patch.object(m.os,'read',return_value=bytes(8192)):obj.drain_once()
        self.assertNotIn('rx',obj.values)
    def test_synthetic_cadence(self):
        obj=self.meter();r,w=os.pipe();os.set_blocking(r,False);obj.fds={'rx':r}
        finish=threading.Event();t0=time.monotonic();sent=[]
        def collect():
            while not finish.wait(.05):
                with obj.lock:obj.drain_once()
        def produce():
            for i in range(60):
                loud=i>=20
                if i==20:sent.append(time.monotonic())
                os.write(w,struct.pack('<h',16000 if loud else 0)*160)
                time.sleep(.02)
        c=threading.Thread(target=collect);p=threading.Thread(target=produce);c.start();p.start()
        seen=None;updates=0;seq=-1
        try:
            while time.monotonic()-t0<1.3:
                s=obj.snapshot('12345')
                if s['sequence']!=seq:updates+=1;seq=s['sequence']
                if s['rx']['rms_db']>-20 and seen is None:seen=time.monotonic()
                time.sleep(.1)
        finally:
            p.join();finish.set();c.join();obj.stop();os.close(w)
        self.assertIsNotNone(seen);latency=(seen-sent[0])*1000
        self.assertLess(latency,250);self.assertGreaterEqual(updates,10)
        print(f'SYNTHETIC {platform.system()}/{platform.machine()} collector + 100ms consumer (not a hardware guarantee): onset {latency:.1f}ms; {updates} distinct snapshots in 1.3s')

if __name__=='__main__':unittest.main(verbosity=2)
