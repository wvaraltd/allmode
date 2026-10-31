# SPDX-License-Identifier: GPL-3.0-or-later
"""P25 Phase 1: 160 S16LE samples at 8 kHz / 11 raw IMBE bytes (no RF FEC)."""
import ctypes as C
from pathlib import Path
class Stream:
    def __init__(self):
        self.lib=C.CDLL(str(Path(__file__).resolve().parent/'build/liballmode_p25.so'))
        self.lib.p25_create.restype=C.c_void_p
        self.lib.p25_destroy.argtypes=[C.c_void_p]
        self.lib.p25_encode.argtypes=[C.c_void_p,C.c_void_p,C.c_int,C.c_void_p,C.c_int]
        self.lib.p25_decode.argtypes=[C.c_void_p,C.c_void_p,C.c_int,C.c_void_p,C.c_int]
        self.ctx=self.lib.p25_create()
        if not self.ctx:raise RuntimeError('IMBE initialization failed')
    def reset(self):
        fresh=self.lib.p25_create()
        if not fresh:raise RuntimeError('IMBE reset failed')
        self.close();self.ctx=fresh
    def encode(self,pcm):
        if not self.ctx or len(pcm)!=320:raise ValueError('Expected 160 S16LE samples')
        source=(C.c_int16*160).from_buffer_copy(pcm);out=(C.c_uint8*11)()
        if self.lib.p25_encode(self.ctx,source,160,out,11):raise ValueError('IMBE encoding failed')
        return bytes(out)
    def decode(self,raw):
        if not self.ctx or len(raw)!=11:raise ValueError('Expected 11 raw IMBE bytes')
        source=(C.c_uint8*11).from_buffer_copy(raw);out=(C.c_int16*160)()
        result=self.lib.p25_decode(self.ctx,source,11,out,160)
        if result<0:raise ValueError('IMBE decoding failed')
        return bytes(out)
    def close(self):
        if self.ctx:self.lib.p25_destroy(self.ctx);self.ctx=None
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
