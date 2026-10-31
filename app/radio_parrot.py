"""Bounded analog SHARI parrot, owned by the fixed-operation system service.

No socket audio, codec plugins, or reflector clients. COP operations are fixed.
The operator must explicitly arm this RF operation; construction never arms it.
"""
import json
from pathlib import Path
import re
import threading
import time

FLAGS={'Incoming connections':(49,50),'User linking commands':(12,11),
       'Scheduler':(16,15),'Autopatch':(10,9),'User functions':(18,17)}

class RadioParrot:
    def __init__(self,cli,lease,clock=time.monotonic,sleep=time.sleep,capture_factory=None):
        self.cli=cli;self.lease=Path(lease);self.clock=clock
        self.sleep=sleep
        self.capture_factory=capture_factory;self.capture=None;self.mode="analog"
        self.tx_before=None;self.tx_observed=False
        self.lock=threading.RLock();self.record=None;self.phase='disabled';self.error=None
        self.started=0;self.rx_start=None;self.replay_end=None;self.heartbeat=0
    @property
    def active(self):return self.record is not None or self.lease.exists()
    def status(self):
        return dict(active=self.active,phase=self.phase,note=self.error,
                    audio='Handheld / SHARI only',codec={'analog':'analog bypass','dstar':'D-Star software roundtrip','ab':'Original then D-Star (one-second gap)','hardware':'External hardware D-Star roundtrip','software-hardware':'Software then external hardware D-Star (one-second gap)'}[self.mode],
                    dstar_roundtrip=self.mode!="analog",tx_observed=self.tx_observed,max_record_seconds=5 if self.mode in ('hardware','software-hardware') else 10,session_seconds=40)
    @staticmethod
    def tx_milliseconds(s):
        value=s.get('TX time today','')
        if not re.fullmatch(r'[0-9]+:[0-9]{2}:[0-9]{2}:[0-9]{3}',value):return None
        h,m,sec,ms=map(int,value.split(':'));return ((h*60+m)*60+sec)*1000+ms
    def stats(self,node):
        output=self.cli('rpt stats '+node)
        if 'STATISTICS' not in output:raise ValueError('Radio status unavailable')
        return {k.rstrip('. '):v.strip() for line in output.splitlines() if ':' in line for k,v in [line.split(':',1)]}
    def cop(self,n):
        out=self.cli('rpt cmd '+self.record['node']+' cop '+str(n)+' 0')
        if any(x in out.lower() for x in ('failed','not ready','unknown','usage:')):raise ValueError('Radio command rejected')
        # app_rpt accepts commands asynchronously. Pace flush operations and
        # require observable state acknowledgement for all state transitions.
        self.sleep(.15)
        expected={3:('System','DISABLED'),2:('System','ENABLED'),21:('Parrot Mode','ENABLED'),22:('Parrot Mode','DISABLED')}
        for name,(off,on) in FLAGS.items():expected[off]=(name,'DISABLED');expected[on]=(name,'ENABLED')
        if n in expected:
            name,value=expected[n]
            for _ in range(20):
                if self.stats(self.record['node']).get(name)==value:return
                self.sleep(.05)
            raise ValueError('Radio command state was not confirmed')
    @staticmethod
    def idle(s):
        if s.get('Nodes currently connected to us')!='<NONE>' or s.get('Signal on input')!='NO':
            raise ValueError('Disconnect every link and wait for radio RX idle before arming')
        if s.get('Autopatch state')!='DOWN' or s.get('Reverse patch/IAXRPT connected')!='DOWN':
            raise ValueError('A phone or reverse-patch session is active')
    def arm(self,node,confirm,mode="analog"):
        if mode not in ("analog","dstar","ab","hardware","software-hardware"):raise ValueError("Unsupported radio test mode")
        with self.lock:
            if confirm!='RADIO READY':raise ValueError('Confirm the radio channel and RF load before arming')
            if self.active:raise ValueError('Radio test already active; Stop before starting another')
            if not re.fullmatch('[0-9]{4,10}',str(node)):raise ValueError('Invalid configured radio node')
            if mode in ('hardware','software-hardware'):
                import codec_selection
                codec_selection.hardware_config()
                if codec_selection.snapshot()['worker_running']:raise ValueError('Stop the production D-Star worker before hardware comparison')
            s=self.stats(node);self.idle(s)
            if s.get('Parrot Mode')!='DISABLED' or s.get('System')!='ENABLED' or s.get('Time out timer')!='ENABLED':
                raise ValueError('Radio system, parrot or timeout state is unsuitable')
            if any(s.get(k) not in ('ENABLED','DISABLED') for k in FLAGS):raise ValueError('Unknown radio isolation state')
            self.mode=mode
            self.tx_before=None;self.tx_observed=False
            self.record={'mode':mode,'node':node,'flags':{k:s[k] for k in FLAGS}}
            self.lease.parent.mkdir(parents=True,exist_ok=True)
            self.lease.write_text(json.dumps(self.record));self.lease.chmod(0o600)
            self.phase='isolating';self.error=None
            try:
                for off,_ in FLAGS.values():self.cop(off)
                s=self.stats(node);self.idle(s)
                if any(s.get(k)!='DISABLED' for k in FLAGS):raise ValueError('Radio isolation did not confirm')
                if mode=='analog':self.cop(21)
                else:
                    if self.capture_factory is None:
                        from radio_codec_audio import Capture
                        self.capture=Capture(self.cli)
                    else:self.capture=self.capture_factory()
                    self.record['capture_pending']=True
                    self.lease.write_text(json.dumps(self.record))
                    self.capture.start(node)
                    self.record['capture_id']=self.capture.monitor_id
                    self.lease.write_text(json.dumps(self.record))
                self.started=self.heartbeat=self.clock();self.rx_start=None;self.replay_end=None
                self.phase='armed'
            except Exception:
                self.stop('Arming failed');raise
            return self.status()
    def ping(self):
        with self.lock:self.heartbeat=self.clock();return self.status()
    def stop(self,reason=None):
        with self.lock:
            if self.record is None and self.lease.exists():self.record=json.loads(self.lease.read_text())
            if self.record is None:return self.status()
            try:
                # Cut TX first, then discard recordings/queued playback before restoring.
                self.cop(3)
                if self.capture is not None:self.capture.stop()
                elif self.record.get('capture_pending'):
                    # Recovery stops only the recorder owned by this test lease.
                    channel='SimpleUSB/'+self.record['node']
                    ident=self.record.get('capture_id')
                    if ident:self.cli('mixmonitor stop '+channel+' '+ident)
                    else:self.cli('mixmonitor stop '+channel)
                self.cop(22);self.cop(23);self.cop(24)
                for name,(off,on) in FLAGS.items():self.cop(on if self.record['flags'][name]=='ENABLED' else off)
                self.cop(24);self.cop(2)
            except Exception:
                self.phase='cleanup-required';self.error='Radio cleanup failed; test locked until cleanup succeeds'
                raise
            self.capture=None;self.record=None;self.lease.unlink(missing_ok=True);self.phase='disabled';self.error=reason
            return self.status()
    def replay(self,duration,path):
        if not isinstance(duration,(int,float)) or not 0<duration<=22:raise ValueError('Replay duration outside bounds')
        if self.clock()+duration+2>self.started+40:raise ValueError('Not enough session time remains for full replay; test cancelled')
        latest=self.stats(self.record['node']);self.idle(latest)
        if any(latest.get(k)!='DISABLED' for k in FLAGS):raise ValueError('Isolation changed during processing')
        if self.clock()-self.heartbeat>5:raise ValueError('Heartbeat expired during processing')
        self.tx_before=self.tx_milliseconds(latest)
        # PLAYBACK is required for simplex TX; all links remain inhibited.
        self.cli('rpt playback '+self.record['node']+' '+path)
        self.replay_end=self.clock()+duration+2;self.phase='replay-window'
    def tick(self):
        with self.lock:
            if self.record is None:return
            now=self.clock()
            try:
                if now-self.heartbeat>5:return self.stop('Browser disconnected or heartbeat expired')
                if now-self.started>=40:return self.stop('Session timeout')
                s=self.stats(self.record['node'])
                if s.get('Nodes currently connected to us')!='<NONE>' or any(s.get(k)!='DISABLED' for k in FLAGS):
                    return self.stop('Isolation changed; test cancelled')
                rx=s.get('Signal on input')
                if rx not in ('YES','NO'):return self.stop('Radio input state unavailable')
                if self.phase=='processing':
                    if rx=='YES':return self.stop('New RX during processing; test cancelled')
                    result=self.capture.poll()
                    if result is not None:self.replay(*result)
                    return
                if rx=='YES':
                    if self.replay_end is not None:return self.stop('New RX during replay window; cancelled to prevent loops')
                    if self.rx_start is None:self.rx_start=now;self.phase='recording'
                    limit=5 if self.mode in ('hardware','software-hardware') else 10
                    if now-self.rx_start>=limit:return self.stop('Recording limit exceeded ('+str(limit)+' seconds); audio discarded')
                elif self.rx_start is not None and self.replay_end is None:
                    # Built-in parrot waits the configured 1s then replays. This is
                    # a bounded replay window, not a claim of measured RF TX state.
                    if self.mode=='analog':self.replay_end=now+(now-self.rx_start)+2
                    else:
                        self.phase='processing'
                        if self.mode in ('hardware','software-hardware'):
                            self.capture.begin(self.rx_start,now,self.mode)
                            return
                        duration,path=self.capture.finish(self.rx_start,now,self.mode)
                        self.replay(duration,path)
                    self.phase='replay-window' 
                if self.replay_end is not None and self.mode!='analog':
                    tx_now=self.tx_milliseconds(s)
                    if self.tx_before is not None and tx_now is not None and tx_now!=self.tx_before:self.tx_observed=True
                if self.replay_end is not None and now>=self.replay_end:
                    note=None if self.mode=='analog' or self.tx_observed else 'Replay ended without observed TX activity; radio output is not confirmed'
                    return self.stop(note)
            except Exception as exc:
                import logging
                logging.exception('Radio parrot failed during %s',self.phase)
                if self.phase!='cleanup-required':
                    detail=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                    self.stop('Radio test failed: '+detail)
                raise

def make_manager(cli):return RadioParrot(cli,'/var/lib/allmode-system/radio-parrot-lease.json')
