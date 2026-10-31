# SPDX-License-Identifier: GPL-3.0-or-later
"""DMR 72-bit voice payload binding; not a complete DMR burst/network packet."""
import ctypes as C
from pathlib import Path
import struct
class Result(C.Structure):_fields_=[('errors',C.c_int),('flags',C.c_uint)]
class Stream:
 def __init__(self,seed=1):
  self.lib=C.CDLL(str(Path(__file__).parent/'build/liballmode_2450.so'));l=self.lib
  l.a2450_create.argtypes=[C.c_uint32];l.a2450_create.restype=C.c_void_p
  l.a2450_destroy.argtypes=[C.c_void_p];l.a2450_destroy.restype=None
  l.a2450_reset.argtypes=[C.c_void_p,C.c_uint32]
  l.a2450_encode.argtypes=[C.c_void_p,C.POINTER(C.c_int16),C.c_size_t,C.POINTER(C.c_uint8),C.c_size_t]
  l.a2450_decode.argtypes=[C.c_void_p,C.POINTER(C.c_uint8),C.c_size_t,C.POINTER(C.c_int16),C.c_size_t,C.POINTER(Result)]
  self.handle=l.a2450_create(seed)
  if not self.handle:raise MemoryError('AMBE2450 allocation failed')
 def close(self):
  if self.handle:self.lib.a2450_destroy(self.handle);self.handle=None
 def reset(self,seed=1):
  if self.lib.a2450_reset(self.handle,seed)<0:raise ValueError('Closed stream')
 def encode(self,pcm):
  if len(pcm)!=320:raise ValueError('Expected 160 S16LE PCM samples')
  p=(C.c_int16*160)(*struct.unpack('<160h',pcm));v=(C.c_uint8*9)()
  if self.lib.a2450_encode(self.handle,p,160,v,9)<0:raise ValueError('AMBE2450 encode failed')
  return bytes(v)
 def decode(self,voice):
  if len(voice)!=9:raise ValueError('Expected nine DMR voice bytes')
  v=(C.c_uint8*9).from_buffer_copy(voice);p=(C.c_int16*160)();r=Result()
  if self.lib.a2450_decode(self.handle,v,9,p,160,C.byref(r))<0:raise ValueError('AMBE2450 decode failed')
  return struct.pack('<160h',*p),{'errors':r.errors,'flags':r.flags}
