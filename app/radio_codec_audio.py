"""Receive-only SHARI recording and local D-Star file processing.

Only the configured external codec is contacted for explicit hardware comparison.
No reflector client, browser audio, automatic gain, or hardware fallback.
Caller must isolate the radio before start and authorize local replay separately.
"""
from pathlib import Path
import os,pwd,re,time,wave,json,subprocess,sys

ROOT=Path('/var/spool/asterisk/monitor/allmode-radio-codec')

def read_pcm(path):
    if path.stat().st_size>700000:raise ValueError('Recording exceeds size bound')
    with wave.open(str(path),'rb') as f:
        if (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getcomptype())!=(1,2,8000,'NONE'):
            raise ValueError('Recording must be mono 8 kHz signed PCM')
        return f.readframes(320001)

def write_pcm(path,data):
    with wave.open(str(path),'wb') as f:
        f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(data)
    path.chmod(0o640)

def roundtrip(pcm,factory):
    codec=factory();decoded=bytearray()
    try:
        for offset in range(0,len(pcm),320):
            frame=pcm[offset:offset+320].ljust(320,b'\0')
            result=codec.decode(codec.encode(frame,1.0),1.0)
            if len(result)!=320:raise ValueError('Invalid codec output')
            decoded.extend(result)
    finally:codec.close()
    return bytes(decoded[:len(pcm)])

def hardware_factory():
    import codec_selection
    if codec_selection.snapshot()['worker_running']:raise ValueError('Stop the production D-Star worker before hardware comparison')
    c=codec_selection.hardware_config()
    from dstar_hardware import HardwareCodec
    return HardwareCodec(c['host'],c.get('port',2460))

def process(raw,start,stop,mode,root=ROOT,factory=None,hardware=None):
    if mode not in ('dstar','ab','hardware','software-hardware'):raise ValueError('Unsupported radio comparison mode')
    if not 0<=start<stop<=41 or stop-start>10.5:raise ValueError('Recording duration outside bounds')
    pcm=read_pcm(raw)
    pcm=pcm[max(0,int((start-.2)*8000))*2:min(len(pcm),int(stop*8000)*2)]
    if not 1600<=len(pcm)<=168000 or not any(pcm):raise ValueError('No usable receive audio was captured')
    write_pcm(root/'original.wav',pcm)
    (root/'replay.wav').unlink(missing_ok=True)
    actual=[]
    if mode!='hardware':
        if factory is None:
            from allmode_dstar_adapter import SourceCodec
            factory=SourceCodec
        decoded=roundtrip(pcm,factory);write_pcm(root/'dstar.wav',decoded);actual.append('software')
    if mode in ('hardware','software-hardware'):
        try:external=roundtrip(pcm,hardware or hardware_factory)
        except Exception as exc:raise ValueError('External D-Star codec unavailable or failed; no fallback and no replay') from exc
        write_pcm(root/'hardware.wav',external);actual.append('hardware')
    replay=external if mode=='hardware' else decoded if mode=='dstar' else pcm+bytes(16000)+decoded if mode=='ab' else decoded+bytes(16000)+external
    write_pcm(root/'replay.wav',replay)
    (root/'result.json').write_text(json.dumps(dict(mode=mode,backends=actual,samples=len(pcm)//2,gain=1.0,completed_utc=time.time())))
    (root/'result.json').chmod(0o600)
    return len(replay)/16000

class Capture:
    def __init__(self,cli,root=ROOT,clock=time.monotonic):
        self.cli=cli;self.root=Path(root);self.clock=clock;self.channel=None;self.monitor_id=None;self.owned=False;self.process_job=None
    def start(self,node):
        if not re.fullmatch('[0-9]{4,10}',str(node)):raise ValueError('Invalid radio node')
        if 'app_mixmonitor.so' not in self.cli('module show like app_mixmonitor.so'):
            self.cli('module load app_mixmonitor.so')
        self.channel='SimpleUSB/'+str(node)
        listing=self.cli('mixmonitor list '+self.channel)
        self.existing_meter_ids=set(re.findall(r'0x[0-9a-fA-F]+',listing)) if '/run/allmode-audio-meter/' in listing else set()
        if self.existing_meter_ids:listing='\n'.join(line for line in listing.splitlines() if '/run/allmode-audio-meter/' not in line)
        if re.search(r'0x[0-9a-fA-F]+',listing):raise ValueError('An existing radio recorder is active')
        self.root.mkdir(parents=True,exist_ok=True)
        account=pwd.getpwnam('asterisk');os.chown(self.root,account.pw_uid,account.pw_gid);self.root.chmod(0o750)
        self.clear()
        self.started=self.clock()
        self.owned=True
        self.cli('mixmonitor start '+self.channel+' '+str(self.root/'mixed.wav')+',r('+str(self.root/'receive.wav')+')')
        listing=self.cli('mixmonitor list '+self.channel)
        ids=[i for i in re.findall(r'0x[0-9a-fA-F]+',listing) if i not in self.existing_meter_ids]
        if len(set(ids))!=1:raise ValueError('Recording did not confirm')
        self.monitor_id=ids[0]
        # The CLI can report an audiohook even when opening its file failed.
        # Check the real output, not merely the presence of the hook.
        for _ in range(20):
            if (self.root/'receive.wav').is_file() and (self.root/'mixed.wav').is_file():break
            time.sleep(.05)
        else:
            self.stop()
            raise ValueError('SHARI recorder could not create its audio files')
        return self.started
    def stop(self):
        if self.process_job is not None:
            if self.process_job.poll() is None:
                self.process_job.terminate()
                try:self.process_job.wait(timeout=1)
                except subprocess.TimeoutExpired:self.process_job.kill();self.process_job.wait(timeout=1)
            self.process_job=None
        if self.owned and self.monitor_id is None:
            self.cli('mixmonitor stop '+self.channel)
            if re.search(r'0x[0-9a-fA-F]+',self.cli('mixmonitor list '+self.channel)):raise ValueError('Recorder did not stop')
            self.owned=False
        if self.monitor_id is not None:
            self.cli('mixmonitor stop '+self.channel+' '+self.monitor_id)
            if self.monitor_id in self.cli('mixmonitor list '+self.channel):raise ValueError('Recorder did not stop')
            self.monitor_id=None;self.owned=False
    def clear(self):
        for name in ('mixed.wav','receive.wav','original.wav','dstar.wav','hardware.wav','replay.wav','result.json'):
            (self.root/name).unlink(missing_ok=True)
    def finish(self,start,stop,mode):
        self.stop() # StopMixMonitor closes files before processing/playback.
        duration=process(self.root/'receive.wav',start-self.started,stop-self.started,mode,self.root)
        account=pwd.getpwnam('asterisk')
        for p in self.root.glob('*.wav'):os.chown(p,account.pw_uid,account.pw_gid)
        return duration,str(self.root/'replay')

    def begin(self,start,stop,mode):
        self.stop()
        self.process_deadline=self.clock()+20
        self.process_job=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),mode,str(start-self.started),str(stop-self.started)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    def poll(self):
        if self.process_job is None:raise ValueError('Codec processing was cancelled')
        if self.clock()>self.process_deadline:
            self.stop();raise ValueError('Codec processing timed out; no replay')
        if self.process_job.poll() is None:return None
        job=self.process_job;self.process_job=None;out,err=job.communicate()
        if job.returncode:
            import logging
            logging.error('Codec subprocess failed: %s',err[-4000:])
            detail='External D-Star codec unavailable or processing failed'
            try:detail=json.loads(out.splitlines()[-1]).get('error',detail)
            except (ValueError,IndexError,TypeError):pass
            raise ValueError(detail+'; no fallback or replay')
        result=json.loads(out.splitlines()[-1])
        return result['duration'],str(self.root/'replay')

if __name__=='__main__':
    try:
        if len(sys.argv)!=4 or sys.argv[1] not in ('hardware','software-hardware'):raise ValueError('Unsupported processor request')
        duration=process(ROOT/'receive.wav',float(sys.argv[2]),float(sys.argv[3]),sys.argv[1])
        a=pwd.getpwnam('asterisk')
        for p in ROOT.glob('*.wav'):os.chown(p,a.pw_uid,a.pw_gid)
        print(json.dumps({'duration':duration}))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        cause=exc
        while cause.__cause__ is not None and not (isinstance(cause,TimeoutError) and str(cause).startswith('AMBE hardware')):cause=cause.__cause__
        detail=type(cause).__name__+': '+str(cause)[:200]
        print(json.dumps({'error':detail}))
        sys.exit(1)
