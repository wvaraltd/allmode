# SPDX-License-Identifier: GPL-2.0-or-later
"""Local file/microphone parrot state machine. Deliberately has no TX adapter."""
import threading
import time
from dstar import encode_pcm,decode_container,parse_wav,ROOT
import os
from routing import BackendError

def software_roundtrip(pcm):
    encoded,_=encode_pcm(pcm)
    wav,_,_=decode_container(encoded)
    return wav

class Parrot:
    def __init__(self,processor=software_roundtrip,clock=time.monotonic,launch=None):
        self.lock=threading.RLock(); self.clock=clock; self.processor=processor
        self.software_available=(processor is not software_roundtrip or
            (ROOT/'build'/('allmode_dstar.dll' if os.name=='nt' else 'liballmode_dstar.so')).is_file())
        self.launch=launch or (lambda fn: threading.Thread(target=fn,daemon=True).start())
        self.enabled=False; self.phase='disabled'; self.limit=30
        self.requested='software'; self.active='software'; self.queued=False
        self.error=None; self.wav=None; self.generation=0
        self.in_flight=False
        self.started=clock(); self.heartbeat_at=clock()
    def _clear(self):
        self.generation+=1; self.wav=None; self.phase='idle' if self.enabled else 'disabled'
    def _apply(self):
        self.queued=False; self.active=self.requested
        if self.requested=='hardware':
            self.active=None; self.error='Hardware adapter unavailable; no software fallback'
        elif not self.software_available:
            self.active=None; self.error='Software codec not built: C compiler required'
        else: self.error=None
    def heartbeat(self):
        with self.lock: self.heartbeat_at=self.clock()
    def tick(self):
        with self.lock:
            now=self.clock()
            if self.phase in ('recording','processing','ready','playing'):
                timeout=(self.limit+2 if self.phase=='recording' else 90)
                if now-self.started>timeout or now-self.heartbeat_at>15:
                    self._clear(); self._apply(); self.error='Session timed out; audio cleared'
    def state(self):
        self.tick()
        with self.lock:
            return dict(enabled=self.enabled,phase=self.phase,max_seconds=self.limit,
                        requested=self.requested,active=self.active,queued=self.queued,error=self.error,
                        local_only=True,network_tx=False,rf_tx=False,hardware_available=False,
                        software_available=self.software_available)
    def enable(self,seconds=30):
        if type(seconds) is not int or not 1<=seconds<=60: raise ValueError('Duration must be 1..60 seconds')
        with self.lock:
            if self.enabled: return self.state()  # repeated click is idempotent
            self.enabled=True; self.limit=seconds; self._clear(); self._apply(); self.heartbeat()
            return self.state()
    def disable(self):
        with self.lock:
            self.enabled=False; self._clear(); self._apply(); return self.state()
    def stop(self):
        with self.lock:
            self._clear(); self._apply(); return self.state()
    def select(self,name):
        if name not in ('software','hardware'): raise ValueError('Unknown backend')
        with self.lock:
            self.requested=name
            if self.phase in ('recording','processing','ready','playing'): self.queued=True
            else: self._apply()
            return self.state()
    def record(self):
        with self.lock:
            self.tick()
            if not self.enabled or self.phase!='idle': raise ValueError('Enable parrot and finish or clear the current session first')
            if self.in_flight: raise ValueError('Previous canceled codec job is still finishing')
            if self.active is None: raise BackendError(self.error)
            self.wav=None; self.error=None; self.phase='recording'; self.started=self.clock(); self.heartbeat()
            return self.state()
    def complete(self,pcm):
        with self.lock:
            self.tick()
            if self.phase!='recording': raise ValueError('No recording active')
            if not pcm or len(pcm)%2 or len(pcm)>self.limit*16000:
                self.stop(); raise ValueError('Invalid or over-limit S16LE recording')
            self.phase='processing'; self.started=self.clock(); generation=self.generation
            self.in_flight=True
            def work():
                try:
                    wav=self.processor(pcm)
                    decoded=parse_wav(wav)
                    if len(decoded)>(self.limit+2)*16000: raise ValueError('Invalid processor output duration')
                    with self.lock:
                        if generation==self.generation and self.enabled:
                            self.wav=wav; self.phase='ready'; self.started=self.clock()
                except Exception as exc:
                    with self.lock:
                        if generation==self.generation:
                            self._clear(); self._apply(); self.error=str(exc)
                finally:
                    with self.lock: self.in_flight=False
            self.launch(work)
            return self.state()
    def playback(self):
        with self.lock:
            self.tick()
            if self.phase!='ready' or self.wav is None: raise ValueError('No playback ready')
            self.phase='playing'; self.started=self.clock(); return self.wav
    def finished(self):
        with self.lock:
            if self.phase!='playing': raise ValueError('No playback active')
            return self.stop()
