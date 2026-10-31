import math, struct, unittest
from speech_filter import SpeechFilter

class SpeechFilterTests(unittest.TestCase):
    def level(self,frequency):
        filter=SpeechFilter();output=[]
        for frame in range(100):
            pcm=struct.pack('<160h',*(round(6000*math.sin(2*math.pi*frequency*(frame*160+i)/8000)) for i in range(160)))
            result=struct.unpack('<160h',filter.process(pcm))
            if frame>20:output.extend(result)
        return math.sqrt(sum(v*v for v in output)/len(output))/(6000/math.sqrt(2))
    def test_rejects_pl_preserves_speech(self):
        self.assertLess(self.level(100),.001)
        self.assertLess(self.level(250),.08)
        self.assertGreater(self.level(500),.99)
        self.assertGreater(self.level(1000),.99)
    def test_silence_and_reset(self):
        filter=SpeechFilter();self.assertEqual(filter.process(bytes(320)),bytes(320))
        filter.process(struct.pack('<160h',*([10000]*160)));filter.reset()
        self.assertEqual(filter.process(bytes(320)),bytes(320))
