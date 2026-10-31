# SPDX-License-Identifier: GPL-3.0-or-later
"""Codec2 3200 binding; separate bounded helper process per TX/RX stream.

Official Codec2 1.2.0 has process-global decoder noise RNG. Process isolation
preserves independent deterministic stream state without modifying the system lib.
"""
import ctypes as C,os,select,subprocess,sys,time
from pathlib import Path
LIBRARY='/usr/lib/aarch64-linux-gnu/libcodec2.so.1.2'
class Stream:
    def __init__(self):
        self.proc=None;self.reset()
    def reset(self):
        self.close()
        self.proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
        try:
            if self.read(1)!=b'K':raise RuntimeError('Codec2 helper initialization failed')
        except Exception:self.close();raise
    def read(self,size):
        result=b'';deadline=time.monotonic()+2
        while len(result)<size:
            left=deadline-time.monotonic()
            if left<=0 or not select.select([self.proc.stdout],[],[],left)[0]:raise RuntimeError('Codec2 helper timed out')
            data=os.read(self.proc.stdout.fileno(),size-len(result))
            if not data:raise RuntimeError('Codec2 helper stopped; no fallback')
            result+=data
        return result
    def call(self,command,data,size,expected):
        if not isinstance(data,bytes) or len(data)!=expected:raise ValueError('Invalid Codec2 frame size')
        if self.proc is None:raise RuntimeError('Codec2 stream closed')
        try:
            self.proc.stdin.write(command+data);return self.read(size)
        except Exception:self.close();raise
    def encode(self,pcm):return self.call(b'E',pcm,8,320)
    def decode(self,raw):return self.call(b'D',raw,320,8)
    def close(self):
        if self.proc is not None:
            p=self.proc;self.proc=None
            try:
                p.stdin.close();p.wait(timeout=.3)
            except (OSError,subprocess.TimeoutExpired):p.kill();p.wait(timeout=2)
            finally:p.stdout.close()
class Codec:
    def __init__(self):
        self.tx=Stream()
        try:self.rx=Stream()
        except Exception:self.tx.close();raise
    def encode(self,pcm):return self.tx.encode(pcm)
    def decode(self,raw):return self.rx.decode(raw)
    def reset_tx(self):self.tx.reset()
    def reset_rx(self):self.rx.reset()
    def close(self):self.tx.close();self.rx.close()
def worker():
    lib=C.CDLL(LIBRARY)
    lib.codec2_create.argtypes=[C.c_int];lib.codec2_create.restype=C.c_void_p
    lib.codec2_destroy.argtypes=[C.c_void_p]
    for n in ('codec2_samples_per_frame','codec2_bits_per_frame'):
        getattr(lib,n).argtypes=[C.c_void_p];getattr(lib,n).restype=C.c_int
    lib.codec2_encode.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p]
    lib.codec2_decode.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p]
    ctx=lib.codec2_create(0) # CODEC2_MODE_3200, verified official 1.2.0 codec2.h
    if not ctx:raise RuntimeError('Codec2 unavailable')
    try:
        assert lib.codec2_samples_per_frame(ctx)==160 and lib.codec2_bits_per_frame(ctx)==64
        sys.stdout.buffer.write(b'K');sys.stdout.buffer.flush()
        while True:
            command=sys.stdin.buffer.read(1)
            if not command:return
            if command not in (b'E',b'D'):return
            data=sys.stdin.buffer.read(320 if command==b'E' else 8)
            if len(data)!=(320 if command==b'E' else 8):return
            if command==b'E':
                pcm=(C.c_int16*160).from_buffer_copy(data);bits=(C.c_ubyte*8)();lib.codec2_encode(ctx,bits,pcm);out=bytes(bits)
            else:
                bits=(C.c_ubyte*8).from_buffer_copy(data);pcm=(C.c_int16*160)();lib.codec2_decode(ctx,pcm,bits);out=bytes(pcm)
            sys.stdout.buffer.write(out);sys.stdout.buffer.flush()
    finally:lib.codec2_destroy(ctx)
if __name__=='__main__' and sys.argv[1:]==['--worker']:worker()
