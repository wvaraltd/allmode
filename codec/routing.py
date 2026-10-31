# SPDX-License-Identifier: GPL-2.0-or-later
"""Backend selection at completed-stream boundaries; no device or RF operations."""
from dataclasses import dataclass
from enum import Enum
from dstar import Stream, parse_wav, read_bounded, make_wav, write_new

class Mode(str,Enum):
    DSTAR='DSTAR'; DMR='DMR'; YSF='YSF'; P25='P25'; M17='M17'; NXDN='NXDN'

class BackendError(RuntimeError): pass

@dataclass(frozen=True)
class Capability:
    mode: Mode
    profile: str
    sample_rate: int
    samples_per_frame: int
    payload_bytes: int
    codec_delay_samples: int | None = None

DSTAR = Capability(Mode.DSTAR,'AMBE-3600x2400-air-lsb',8000,160,9)

class Software:
    name='software'
    def capabilities(self): return (DSTAR,)
    def open(self,capability):
        if capability!=DSTAR: raise BackendError('Software mode/profile unsupported')
        return Stream()

class UnavailableHardware:
    name='hardware'
    def capabilities(self): return ()
    def open(self,capability): raise BackendError('Hardware adapter unavailable; no fallback')

class Router:
    """Adapter contract: capabilities(), open(cap)->encode/decode/close context.

    The host serializes calls. One context is active. request() during a stream
    queues a switch; end() closes old state before opening fresh requested state.
    Never call end() while an utterance/PTT is still active. begin/end are host
    stream events, not individual 20 ms frame events. Failure leaves no active
    backend; recovery requires another explicit request. No silent fallback.
    """
    def __init__(self,hardware=None):
        self.backends={'software':Software(),'hardware':hardware or UnavailableHardware()}
        self.requested='software'; self.active=None; self.queued=False; self.busy=False
        self.capability=DSTAR; self.context=None; self.error=None
        self._activate()
    def discovery(self):
        return {name:list(adapter.capabilities()) for name,adapter in self.backends.items()}
    def state(self):
        return dict(requested=self.requested,active=self.active,queued=self.queued,
                    stream_active=self.busy,error=self.error,mode=self.capability.mode.value,
                    profile=self.capability.profile)
    def request(self,backend,capability=None):
        if backend not in self.backends: raise BackendError('Unknown backend')
        self.requested=backend
        if capability is not None: self.pending_capability=capability
        else: self.pending_capability=self.capability
        if self.busy:
            self.queued=True
        else:
            self.capability=self.pending_capability
            self._activate()
    def _activate(self):
        self.close_context(); self.error=None; self.queued=False
        adapter=self.backends[self.requested]
        try:
            caps=adapter.capabilities()
            if not caps: raise BackendError(f'{self.requested} unavailable; no fallback')
            if self.capability not in caps: raise BackendError(f'{self.requested} mode/profile unsupported')
            self.context=adapter.open(self.capability)
            self.active=self.requested
        except Exception as exc:
            self.error=str(exc); self.active=None
            raise BackendError(self.error) from exc
    def close_context(self):
        context=self.context; self.context=None; self.active=None
        if context is not None: context.close()
    def begin(self):
        if self.busy: raise BackendError('Stream already active')
        if self.context is None: raise BackendError(self.error or 'No active codec')
        self.busy=True
    def end(self):
        if not self.busy: raise BackendError('No active stream')
        self.busy=False
        if self.queued: self.capability=self.pending_capability
        self._activate()  # fresh histories even if backend did not change
    def _call(self,method,data):
        if not self.busy or self.context is None: raise BackendError('No active stream')
        try: return getattr(self.context,method)(data)
        except Exception as exc:
            self.error=str(exc); self.close_context(); self.busy=False; self.queued=False
            raise BackendError(self.error) from exc
    def encode(self,pcm): return self._call('encode',pcm)
    def decode(self,payload): return self._call('decode',payload)
    def close(self):
        self.close_context(); self.busy=False; self.queued=False

def compare_recording(wav_path,output_prefix,hardware):
    """Sequential A/B. No normalization or AGC. Requires an actual injected adapter.

    Hardware must implement precisely the DSTAR profile, S16LE byte encode and
    (S16LE bytes,status dict) decode. Delay is reported as unknown unless measured
    by the adapter; output is not automatically time aligned. No hardware is
    discovered/opened by this prototype. Caller supplies a reviewed adapter.
    """
    pcm=parse_wav(read_bounded(wav_path))
    if DSTAR not in hardware.capabilities():
        raise BackendError('Hardware D-Star profile unavailable; no comparison performed')
    outputs={}
    for backend in (Software(),hardware):
        encoded=[]; decoded=[]
        encoder=backend.open(DSTAR)
        try:
            for p in range(0,len(pcm),320): encoded.append(encoder.encode(pcm[p:p+320].ljust(320,b'\0')))
            if pcm: encoded.append(encoder.encode(bytes(320)))
        finally: encoder.close()
        decoder=backend.open(DSTAR)
        try:
            for frame in encoded:
                samples,status=decoder.decode(frame)
                if len(samples)!=320: raise BackendError('Adapter returned invalid PCM frame')
                decoded.append(samples)
        finally: decoder.close()
        outputs[backend.name]=make_wav(b''.join(decoded))
    # No outputs until both runs complete. Refuse any existing destinations.
    from pathlib import Path
    paths={name:Path(str(output_prefix)+'.'+name+'.wav') for name in outputs}
    if any(p.exists() for p in paths.values()): raise FileExistsError('Comparison destination exists')
    for name,data in outputs.items(): write_new(paths[name],data)
    return {'files':{k:str(v) for k,v in paths.items()},'gain':'unchanged input; no normalization',
            'alignment':'not applied; measure each codec delay before blind listening',
            'hardware':'provided adapter, sequential run'}
