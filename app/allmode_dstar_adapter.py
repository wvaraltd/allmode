# SPDX-License-Identifier: GPL-2.0-or-later
"""ALLMODE D-Star codec boundary. No plugin binaries or network side effects."""
import math
import os
from pathlib import Path
import struct
import sys
COMPONENT=Path(os.environ.get('ALLMODE_VOCODER_ROOT','/opt/allmode-vocoder-prototype/current'))
if str(COMPONENT) not in sys.path: sys.path.insert(0,str(COMPONENT))
from dstar import Stream

class SourceCodec:
    def __init__(self,root=None):
        # root remains accepted for the former worker's constructor contract.
        self.tx=Stream(); self.rx=None
        try:self.rx=Stream()
        except Exception:self.tx.close();raise
    @staticmethod
    def gain(pcm,gain):
        if len(pcm)!=320 or not isinstance(gain,(int,float)) or not math.isfinite(gain) or not 0<=gain<=10:
            raise ValueError('Invalid PCM frame or gain')
        return struct.pack('<160h',*(max(-32768,min(32767,round(v*gain))) for v in struct.unpack('<160h',pcm)))
    def encode(self,data,gain): return self.tx.encode(self.gain(data,gain))
    def decode(self,voice,gain): return self.gain(self.rx.decode(voice)[0],gain)
    def reset_tx(self): self.tx.reset()
    def reset_rx(self): self.rx.reset()
    def close(self):
        if self.tx:self.tx.close();self.tx=None
        if self.rx:self.rx.close();self.rx=None
