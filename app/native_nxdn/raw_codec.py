# SPDX-License-Identifier: GPL-3.0-or-later
"""49-bit parameter boundary using the installed source-built AMBE2450 API.

FEC conversion bridges the existing 72-bit wrapper; no new binary dependency.
One independent native context per direction. Raw frames carry no FEC.
"""
import ctypes as C
import importlib.util
from pathlib import Path
if __package__:from .protocol import raw49
else:from protocol import raw49

W=(0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,2,0,2,0,2,0,2,0,2,0,2,0,2)
X=(23,10,22,9,21,8,20,7,19,6,18,5,17,4,16,3,15,2,14,1,13,0,12,10,11,9,10,8,9,7,8,6,7,5,6,4)
Y=(0,2,0,2,0,2,0,2,0,3,0,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3)
Z=(5,3,4,2,3,1,2,0,1,13,0,12,22,11,21,10,20,9,19,8,18,7,17,6,16,5,15,4,14,3,13,2,12,1,11,0)
SCHEDULE=tuple(p for i in range(36) for p in ((W[i],X[i]),(Y[i],Z[i])))
Plane=(C.c_char*24)*4

class Codec:
    def __init__(self, root=Path('/opt/allmode-vocoder-prototype/current/ambe2450')):
        spec=importlib.util.spec_from_file_location('nxdn_ambe_binding',Path(root)/'codec.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.tx=m.Stream();self.rx=None
        try:self.rx=m.Stream()
        except Exception:self.tx.close();raise
        self.lib=self.tx.lib
        self.lib.mbe_decodeAmbe3600x2450Frame.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p]
        self.lib.mbe_encodeAmbe3600x2450Frame.argtypes=[C.c_void_p,C.c_void_p]
    def reset_tx(self):self.tx.reset()
    def reset_rx(self):self.rx.reset()
    def encode(self,pcm):
        payload=self.tx.encode(pcm);plane=Plane();bits=(C.c_char*49)()
        for i,(r,c) in enumerate(SCHEDULE):plane[r][c]=bytes([(payload[i//8]>>(7-i%8))&1])
        if self.lib.mbe_decodeAmbe3600x2450Frame(plane,bits,None)!=0:raise ValueError('Native encoder produced invalid FEC')
        value=0
        for b in bits:value=(value<<1)|ord(b)
        return (value<<7).to_bytes(7,'big')
    def decode(self,raw):
        value=raw49(raw);bits=(C.c_char*49)(*[bytes([(value>>(48-i))&1]) for i in range(49)]);plane=Plane()
        if self.lib.mbe_encodeAmbe3600x2450Frame(bits,plane)<0:raise ValueError('Invalid raw AMBE frame')
        value=0
        for r,c in SCHEDULE:value=(value<<1)|ord(plane[r][c])
        return self.rx.decode(value.to_bytes(9,'big'))[0]
    def close(self):
        if self.tx:self.tx.close();self.tx=None
        if self.rx:self.rx.close();self.rx=None
