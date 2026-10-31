# SPDX-License-Identifier: GPL-2.0-or-later
"""Strict offline WAV/container tooling and the ctypes integration binding."""
import argparse
import ctypes as C
import io
import json
import os
import platform
from pathlib import Path
import struct
import time
import wave

ROOT = Path(__file__).resolve().parent
MAX_SAMPLES = 8000*600  # Prototype file limit: ten minutes.
HEADER = struct.Struct('<8sIHHQQII')
MAGIC = b'ADSTAR01'

class Result(C.Structure):
    _fields_ = [('errors', C.c_int), ('flags', C.c_uint)]

class Stream:
    def __init__(self, seed=1):
        path = ROOT/'build'/('allmode_dstar.dll' if os.name=='nt' else 'liballmode_dstar.so')
        self.lib = C.CDLL(str(path))
        lib=self.lib
        lib.ad_create.argtypes=[C.c_uint32]; lib.ad_create.restype=C.c_void_p
        lib.ad_destroy.argtypes=[C.c_void_p]; lib.ad_destroy.restype=None
        lib.ad_reset.argtypes=[C.c_void_p,C.c_uint32]; lib.ad_reset.restype=C.c_int
        lib.ad_encode.argtypes=[C.c_void_p,C.POINTER(C.c_int16),C.c_size_t,C.POINTER(C.c_uint8),C.c_size_t]
        lib.ad_decode.argtypes=[C.c_void_p,C.POINTER(C.c_uint8),C.c_size_t,C.POINTER(C.c_int16),C.c_size_t,C.POINTER(Result)]
        lib.ad_lost.argtypes=[C.c_void_p,C.POINTER(C.c_int16),C.c_size_t]
        lib.ad_thread_cleanup.argtypes=[]; lib.ad_thread_cleanup.restype=None
        self.handle=lib.ad_create(seed)
        if not self.handle: raise MemoryError('Cannot allocate D-Star codec')
    def close(self):
        if self.handle:
            self.lib.ad_destroy(self.handle); self.handle=None
            self.lib.ad_thread_cleanup()
    def __enter__(self): return self
    def __exit__(self,*exc): self.close()
    def reset(self,seed=1):
        if self.lib.ad_reset(self.handle,seed)<0: raise ValueError('Closed stream')
    def encode(self,pcm):
        if len(pcm)!=320: raise ValueError('Expected exactly 320 PCM bytes')
        samples=(C.c_int16*160)(*struct.unpack('<160h',pcm)); out=(C.c_uint8*9)()
        if self.lib.ad_encode(self.handle,samples,160,out,9)<0: raise ValueError('Codec encode failed')
        return bytes(out)
    def decode(self,payload):
        if len(payload)!=9: raise ValueError('Expected exactly nine voice bytes')
        inp=(C.c_uint8*9).from_buffer_copy(payload); out=(C.c_int16*160)(); result=Result()
        if self.lib.ad_decode(self.handle,inp,9,out,160,C.byref(result))<0: raise ValueError('Codec decode failed')
        return struct.pack('<160h',*out), {'errors':result.errors,'flags':result.flags}
    def lost(self):
        out=(C.c_int16*160)()
        if self.lib.ad_lost(self.handle,out,160)<0: raise ValueError('Closed stream')
        return struct.pack('<160h',*out)

def read_bounded(path):
    with open(path,'rb') as f:
        data=f.read(MAX_SAMPLES*2+1024*1024+1)
    if len(data)>MAX_SAMPLES*2+1024*1024: raise ValueError('Input exceeds prototype file limit')
    return data

def parse_wav(data):
    if len(data)<12 or data[:4]!=b'RIFF' or data[8:12]!=b'WAVE': raise ValueError('Expected RIFF/WAVE')
    if struct.unpack_from('<I',data,4)[0]!=len(data)-8: raise ValueError('RIFF length mismatch')
    pos=12; fmt=None; pcm=None
    while pos<len(data):
        if pos+8>len(data): raise ValueError('Truncated chunk header')
        tag=data[pos:pos+4]; size=struct.unpack_from('<I',data,pos+4)[0]; pos+=8
        end=pos+size
        if end+(size&1)>len(data): raise ValueError('Truncated chunk')
        if tag==b'fmt ':
            if fmt is not None or size<16: raise ValueError('Duplicate/short format')
            fmt=struct.unpack_from('<HHIIHH',data,pos)
            if fmt!=(1,1,8000,16000,2,16): raise ValueError('Requires mono PCM S16LE, 8000 Hz')
        elif tag==b'data':
            if fmt is None or pcm is not None or size%2: raise ValueError('Invalid/duplicate PCM data')
            pcm=data[pos:end]
        pos=end+(size&1)
    if pcm is None: raise ValueError('Missing PCM data')
    if len(pcm)//2>MAX_SAMPLES: raise ValueError('WAV exceeds ten minutes')
    return pcm

def make_wav(pcm):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setparams((1,2,8000,0,'NONE','not compressed')); w.writeframes(pcm)
    return out.getvalue()

def parse_container(data):
    if len(data)<HEADER.size: raise ValueError('Truncated ADSTAR header')
    magic,rate,samples,size,original,count,flags,reserved=HEADER.unpack_from(data)
    expected=(original+159)//160+1 if original else 0
    if (magic,rate,samples,size,flags,reserved)!=(MAGIC,8000,160,9,1,0): raise ValueError('Unsupported container header')
    if original>MAX_SAMPLES or count!=expected or len(data)!=HEADER.size+count*9: raise ValueError('Container length/count mismatch')
    return original,[data[p:p+9] for p in range(HEADER.size,len(data),9)]

def encode_pcm(pcm):
    if len(pcm)%2 or len(pcm)//2>MAX_SAMPLES: raise ValueError('Invalid PCM length')
    frames=[]; times=[]
    with Stream() as s:
        for pos in range(0,len(pcm),320):
            t=time.perf_counter_ns(); frames.append(s.encode(pcm[pos:pos+320].ljust(320,b'\0'))); times.append(time.perf_counter_ns()-t)
        if pcm:
            t=time.perf_counter_ns(); frames.append(s.encode(bytes(320))); times.append(time.perf_counter_ns()-t)
    return HEADER.pack(MAGIC,8000,160,9,len(pcm)//2,len(frames),1,0)+b''.join(frames), times

def decode_container(data):
    original,frames=parse_container(data); pcm=[]; statuses=[]; times=[]
    with Stream() as s:
        for frame in frames:
            t=time.perf_counter_ns(); out,status=s.decode(frame); times.append(time.perf_counter_ns()-t)
            pcm.append(out); statuses.append(status)
    return make_wav(b''.join(pcm)),statuses,times

def write_new(path,data):
    # Refuse overwrites. Validation and processing complete before opening output.
    with open(path,'xb') as f: f.write(data)

def timing(times):
    if not times: return {'frames':0}
    ms=sorted(t/1e6 for t in times)
    return {'frames':len(ms),'mean_ms':sum(ms)/len(ms),'p95_ms':ms[min(len(ms)-1,int(.95*len(ms)))],
            'max_ms':max(ms),'over_20ms':sum(x>20 for x in ms),
            'platform':platform.system(),'machine':platform.machine(),'realtime_guarantee':False}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['encode','decode','roundtrip'])
    ap.add_argument('input',type=Path); ap.add_argument('output',type=Path)
    args=ap.parse_args()
    try:
        data=read_bounded(args.input)
        if args.action=='decode':
            output,status,times=decode_container(data)
        else:
            output,times=encode_pcm(parse_wav(data)); status=[]
            if args.action=='roundtrip': output,status,dt=decode_container(output)
        write_new(args.output,output)
        report={'action':args.action,'timing':timing(times),'corrected_errors':sum(s['errors'] for s in status)}
        if args.action=='roundtrip': report['decode_timing']=timing(dt)
        print(json.dumps(report,indent=2))
    except (OSError,ValueError,MemoryError) as exc:
        ap.exit(2,f'error: {exc}\n')

if __name__=='__main__': main()
