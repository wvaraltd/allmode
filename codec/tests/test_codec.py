# SPDX-License-Identifier: GPL-2.0-or-later
import concurrent.futures
import ctypes as C
import math
import os
import platform
from pathlib import Path
import random
import struct
import time
import unittest
from dstar import Stream,ROOT,encode_pcm,decode_container,parse_wav,timing,Result

DLL=ROOT/'build'/('allmode_dstar.dll' if os.name=='nt' else 'liballmode_dstar.so')
def fixture(frames=35,seed=4):
    r=random.Random(seed)
    return [struct.pack('<160h',*[int(4000*math.sin((f*160+i)*.13)+r.uniform(-2000,2000)) for i in range(160)]) for f in range(frames)]

@unittest.skipUnless(DLL.exists(),'Native codec not built: requires C compiler')
class Codec(unittest.TestCase):
    def test_roundtrip_padding_empty_and_silence(self):
        for pcm in [b'',bytes(2),bytes(318),bytes(320),b''.join(fixture())]:
            encoded,_=encode_pcm(pcm); wav,status,_=decode_container(encoded)
            expected=((len(pcm)//2+159)//160+1)*320 if pcm else 0
            self.assertEqual(len(parse_wav(wav)),expected)
            self.assertTrue(all(s['errors']==0 for s in status))
        encoded,_=encode_pcm(bytes(320*30)); wav,_,_=decode_container(encoded)
        values=struct.unpack('<'+'h'*(len(parse_wav(wav))//2),parse_wav(wav))
        self.assertLess(max(map(abs,values)),1000) # quiet voice, not fabricated zero payload
    def test_stream_independence_and_errors(self):
        a=fixture(); b=fixture(seed=7)
        def sequence(frames):
            with Stream(7) as s: return [s.encode(f) for f in frames]
        ea,eb=sequence(a),sequence(b)
        with Stream(7) as sa,Stream(7) as sb:
            for fa,fb,pa,pb in zip(a,b,ea,eb):
                self.assertEqual(sa.encode(fa),pa); self.assertEqual(sb.encode(fb),pb)
        # Include corrupt frames to exercise comfort-noise TLS isolation.
        ea+= [bytes([255]*9),bytes(9)]*15
        eb+= [bytes(9),bytes([255]*9)]*15
        def decoded(frames):
            with Stream(7) as s: return [s.decode(f) for f in frames]
        da,db=decoded(ea),decoded(eb)
        with Stream(7) as sa,Stream(7) as sb:
            for pa,pb,oa,ob in zip(ea,eb,da,db):
                self.assertEqual(sa.decode(pa),oa); self.assertEqual(sb.decode(pb),ob)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(list(pool.map(decoded,[ea,eb])),[da,db])
    def test_c_validation_reset_and_loss(self):
        with Stream() as s:
            pcm=(C.c_int16*160)(*([123]*160)); payload=(C.c_uint8*9)(); result=Result()
            self.assertEqual(s.lib.ad_encode(s.handle,pcm,159,payload,9),-1)
            self.assertEqual(s.lib.ad_decode(s.handle,payload,8,pcm,160,C.byref(result)),-1)
            self.assertEqual(list(pcm),[0]*160)
            self.assertEqual(s.lib.ad_encode(None,pcm,160,payload,9),-1)
            self.assertEqual(s.lost(),bytes(320))
            frame=fixture(1)[0]; first=s.encode(frame); s.encode(frame); s.reset(); self.assertEqual(s.encode(frame),first)
    def test_timing_and_random_payloads(self):
        frames=fixture(150); enc=[]; dec=[]
        with Stream() as s:
            for frame in frames:
                t=time.perf_counter_ns(); p=s.encode(frame); enc.append(time.perf_counter_ns()-t)
                t=time.perf_counter_ns(); s.decode(p); dec.append(time.perf_counter_ns()-t)
            r=random.Random(100)
            for _ in range(300):
                pcm,status=s.decode(r.randbytes(9)); self.assertEqual(len(pcm),320)
        import json
        report={'encode':timing(enc),'decode':timing(dec),'note':platform.system()+' '+platform.machine()+' measurement; no real-time guarantee'}
        (ROOT/'build/timing.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report))

if __name__=='__main__': unittest.main()
