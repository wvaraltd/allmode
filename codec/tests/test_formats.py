# SPDX-License-Identifier: GPL-2.0-or-later
import struct
import unittest
from dstar import HEADER,MAGIC,parse_container,parse_wav,make_wav

class Formats(unittest.TestCase):
    def test_wav_valid_empty_and_partial(self):
        for n in [0,1,159,160,161,1000]:
            pcm=bytes(2*n); self.assertEqual(parse_wav(make_wav(pcm)),pcm)
    def test_wav_malformed(self):
        good=make_wav(bytes(320))
        cases=[b'',good[:10],good[:-1],good+b'x',b'RIFX'+good[4:]]
        for offset,value in [(20,3),(22,2),(24,48000),(28,1),(32,4),(34,8),(40,321)]:
            bad=bytearray(good); struct.pack_into('<I' if offset in (24,28,40) else '<H',bad,offset,value); cases.append(bad)
        for data in cases:
            with self.subTest(data=bytes(data[:44])):
                with self.assertRaises(ValueError): parse_wav(data)
    def test_chunks_and_duplicates(self):
        def riff(body): return b'RIFF'+struct.pack('<I',len(body)+4)+b'WAVE'+body
        good=make_wav(bytes(320)); body=good[12:]
        self.assertEqual(parse_wav(riff(b'JUNK\x01\0\0\0x\0'+body)),bytes(320))
        for bad in [body+body[:24],body+body[24:],body[24:]+body[:24],body+b'x']:
            with self.assertRaises(ValueError): parse_wav(riff(bad))
    def test_container(self):
        good=HEADER.pack(MAGIC,8000,160,9,160,2,1,0)+bytes(18)
        self.assertEqual(parse_container(good)[0],160)
        cases=[b'',good[:39],good[:-1],good+b'x']
        for offset in [0,8,12,14,20,24,32,36]:
            bad=bytearray(good); bad[offset]^=0x80; cases.append(bad)
        for data in cases:
            with self.assertRaises(ValueError): parse_container(data)

if __name__=='__main__': unittest.main()
