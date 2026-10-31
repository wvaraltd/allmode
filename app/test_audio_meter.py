import sys, math, struct, unittest
from pathlib import Path

from audio_meter import measure
class AudioMeterTests(unittest.TestCase):
    def test_silence(self):
        self.assertEqual(measure(bytes(320)),dict(rms_db=-96.0,peak_db=-96.0,clipping=False))
    def test_half_scale_sine(self):
        signal=struct.pack('<800h',*[int(16384*math.sin(2*math.pi*1000*n/8000)) for n in range(800)])
        reading=measure(signal)
        self.assertAlmostEqual(reading['rms_db'],-9.0,delta=.1)
        self.assertAlmostEqual(reading['peak_db'],-6.0,delta=.1)
        self.assertFalse(reading['clipping'])
    def test_clip_both_polarities(self):
        for sample in (-32768,32767):self.assertTrue(measure(struct.pack('<h',sample))['clipping'])
if __name__=='__main__':unittest.main()
