import json,math,platform,struct,time,unittest
from pathlib import Path
from codec import Stream
class Tests(unittest.TestCase):
 def frames(self):return [struct.pack('<160h',*(round(5000*math.sin(2*math.pi*137*(i*160+j)/8000)) for j in range(160))) for i in range(100)]
 def test_roundtrip_timing(self):
  s=Stream();times=[]
  try:
   for f in self.frames():
    t=time.perf_counter_ns();v=s.encode(f);p,r=s.decode(v);times.append((time.perf_counter_ns()-t)/1e6)
    self.assertEqual(len(p),320);self.assertEqual(r['errors'],0)
   result={'platform':platform.system(),'machine':platform.machine(),'realtime_guarantee':False,'frames':len(times),'encode_decode_mean_ms':sum(times)/len(times),'max_ms':max(times)}
   (Path(__file__).parent/'build/timing.json').write_text(json.dumps(result,indent=2));print(result)
  finally:s.close()
 def test_known_dmr_silence(self):
  s=Stream()
  try:p,r=s.decode(bytes.fromhex('acaa40200044408080'));self.assertEqual(r['errors'],0);self.assertEqual(len(p),320)
  finally:s.close()
 def test_interleaved_streams_and_reset(self):
  a,b,c=Stream(1),Stream(2),Stream(1)
  try:
   for f in self.frames():
    x=a.encode(f);b.decode(b.encode(bytes(320)));y=c.encode(f);self.assertEqual(x,y);self.assertEqual(a.decode(x),c.decode(y))
   a.reset();c.reset();self.assertEqual(a.encode(bytes(320)),c.encode(bytes(320)))
  finally:a.close();b.close();c.close()
 def test_malformed_closed(self):
  s=Stream()
  for f in [b'',bytes(319),bytes(321)]:
   with self.assertRaises(ValueError):s.encode(f)
  for f in [b'',bytes(8),bytes(10)]:
   with self.assertRaises(ValueError):s.decode(f)
  s.close()
  with self.assertRaises(ValueError):s.encode(bytes(320))
if __name__=='__main__':unittest.main(verbosity=2)
