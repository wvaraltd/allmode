# SPDX-License-Identifier: GPL-3.0-or-later
"""Two independent AMBE2450 streams; no external codec fallback."""
import importlib.util
from pathlib import Path

class Codec:
    def __init__(self,root=Path('/opt/allmode-vocoder-prototype/current/ambe2450')):
        spec=importlib.util.spec_from_file_location('allmode_native_2450',Path(root)/'codec.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.tx=module.Stream();self.rx=None
        try:self.rx=module.Stream()
        except Exception:self.tx.close();raise
    def reset_tx(self):self.tx.reset()
    def reset_rx(self):self.rx.reset()
    def encode(self,pcm):return self.tx.encode(pcm)
    def decode(self,frame):return self.rx.decode(frame)[0]
    def close(self):
        if self.tx:self.tx.close();self.tx=None
        if self.rx:self.rx.close();self.rx=None
