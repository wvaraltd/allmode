"""Passive SimpleUSB audiohook meters. FIFO streams; no audio recordings retained."""
import os, math, struct, time, threading, re, pwd
from pathlib import Path
ROOT=Path('/run/allmode-audio-meter')

def measure(data):
    data=data[:len(data)//2*2]
    if not data:return dict(rms_db=-96.0,peak_db=-96.0,clipping=False)
    values=struct.unpack('<%dh'%(len(data)//2),data)
    peak=max(abs(v) for v in values)
    rms=math.sqrt(sum(v*v for v in values)/len(values))
    db=lambda n:round(max(-96,20*math.log10(n/32768)),1) if n else -96.0
    return dict(rms_db=db(rms),peak_db=db(peak),clipping=peak>=32760)

class Meter:
    def __init__(self,cli):
        self.cli=cli;self.lock=threading.RLock();self.ident=None;self.channel=None
        self.fds={};self.values={};self.lease=0;self.running=False;self.checked=0;self.peaks={};self.sequence=0
    def stop(self):
        with self.lock:
            if self.ident:
                self.cli('mixmonitor stop '+self.channel+' '+self.ident)
                self.ident=None
            for fd in self.fds.values():os.close(fd)
            self.fds={};self.values={};self.peaks={}
    def start(self,node):
        if not re.fullmatch('[0-9]{4,10}',str(node)):raise ValueError('Radio node unavailable')
        self.channel='SimpleUSB/'+str(node)
        if self.channel not in self.cli('core show channels concise'):raise ValueError('Start the radio to see live audio levels')
        self.cli('module load app_mixmonitor.so')
        self.cli('module load format_allmode_meter.so')
        if 'allmode_meter' not in self.cli('core show file formats'):
            raise ValueError('Live meter format unavailable; reload matching ASL meter module')
        for line in self.cli('mixmonitor list '+self.channel).splitlines():
            if str(ROOT) in line:
                match=re.search(r'0x[0-9a-fA-F]+',line)
                if match:self.cli('mixmonitor stop '+self.channel+' '+match.group())
        before=set(re.findall(r'0x[0-9a-fA-F]+',self.cli('mixmonitor list '+self.channel)))
        ROOT.mkdir(mode=0o750,parents=True,exist_ok=True)
        a=pwd.getpwnam('asterisk');os.chown(ROOT,a.pw_uid,a.pw_gid)
        try:
            for key in ('rx','tx','mixed'):
                path=ROOT/(key+'.ameter');path.unlink(missing_ok=True);os.mkfifo(path,0o600);os.chown(path,a.pw_uid,a.pw_gid)
                self.fds[key]=os.open(path,os.O_RDWR|os.O_NONBLOCK)
            self.cli('mixmonitor start '+self.channel+' '+str(ROOT/'mixed.ameter')+',r('+str(ROOT/'rx.ameter')+')t('+str(ROOT/'tx.ameter')+')')
            after=set(re.findall(r'0x[0-9a-fA-F]+',self.cli('mixmonitor list '+self.channel)))
            ids=after-before
            if len(ids)!=1:raise ValueError('Audio meter could not attach to the radio')
            self.ident=ids.pop()
        except Exception:
            self.stop();raise
        if not self.running:
            self.running=True;threading.Thread(target=self.loop,daemon=True).start()
    def snapshot(self,node):
        with self.lock:
            if self.ident and self.channel!='SimpleUSB/'+str(node):self.stop()
            if self.ident and time.monotonic()-self.checked>5:
                self.checked=time.monotonic()
                if self.ident not in self.cli('mixmonitor list '+self.channel):self.stop()
            self.lease=time.monotonic()+8
            if not self.ident:self.start(node)
            now=time.monotonic();result={}
            for key in ('rx','tx'):
                val,stamp=self.values.get(key,(measure(b''),0))
                age=max(0,now-stamp)
                fresh=bool(stamp) and age<.35
                result[key]=dict(val if fresh else measure(b''),available=fresh,
                                 age_ms=round(age*1000,1) if stamp else None)
            return dict(active=True,**result,sequence=self.sequence,
                        refresh_ms=100,stale_ms=350,window_ms=100,
                        deviation='Not calibrated',point='SimpleUSB PCM, before radio hardware')

    def drain_once(self):
        """Bound each read; use only the latest <=100ms, never an old RMS batch.

        age_ms is time since delivery, not a hardware capture timestamp.
        The dedicated FIFO writer is immediate and nonblocking. No bytes persist.
        """
        for key,fd in self.fds.items():
            data=bytearray()
            while len(data)<65536:
                try:chunk=os.read(fd,8192)
                except BlockingIOError:break
                if not chunk:break
                data.extend(chunk)
            if data and key!='mixed':
                if len(data)>=65536:
                    # A large backlog is not live: drain, but do not label it fresh.
                    self.values.pop(key,None)
                    continue
                self.values[key]=(measure(bytes(data[-1600:])),time.monotonic())
                self.sequence+=1

    def loop(self):
        while True:
            time.sleep(.05)
            with self.lock:
                if not self.ident:continue
                if time.monotonic()>self.lease:
                    try:self.stop()
                    except Exception:pass
                    continue
                self.drain_once()
