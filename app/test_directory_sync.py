import sys,tempfile,unittest
from pathlib import Path

import directory_sync as d
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();d.CACHE=Path(self.tmp.name)/'cache';d.HOSTS=Path(self.tmp.name)/'hosts'
 def tearDown(self):self.tmp.cleanup()
 def test_formats(self):
  samples={'YSF':'32592;AmericaLink;Global;example.org;42000;000;', 'NXDN':'123 example.org 41400', 'P25':'123 example.org 41000', 'M17':'M17-ABC example.org 17000', 'DCS':'DCS001 example.org', 'REF':'REF001 example.org L', 'XLX':'001;example.org;4004', 'TGIF':'123;0;Example;TG123', 'BrandMeister':'{"91":"Worldwide"}'}
  for name,sample in samples.items():
   with self.subTest(name=name):
    result=d.refresh_one(name,lambda url:sample.encode());self.assertIsNone(result['error']);self.assertEqual(len(result['rows']),1)
  self.assertEqual(d.cached('XLX')['rows'][0]['port'],30051)
  self.assertEqual(len(d.listing('D-STAR')['rows']),3)
 def test_failure_retains_files(self):
  original=d.refresh_one('YSF',lambda url:b'123;name;desc;example.org;42000;')
  before=(d.HOSTS/'YSFHosts.txt').read_bytes()
  bad=d.refresh_one('YSF',lambda url:b'<html>error</html>')
  self.assertTrue(bad['error']);self.assertEqual(bad['rows'],original['rows']);self.assertEqual(bad['updated'],original['updated']);self.assertEqual((d.HOSTS/'YSFHosts.txt').read_bytes(),before)
 def test_invalid(self):
  self.assertEqual(d.parse('YSF','1;x;y;bad host;42000'),[])
  self.assertEqual(d.parse('TGIF','1;2;private;TG1'),[])
  self.assertEqual(d.parse('NXDN','999999 example.org 41400'),[])
  self.assertEqual(d.parse('REF','XRF001 example.org'),[])
if __name__ == "__main__": unittest.main()
