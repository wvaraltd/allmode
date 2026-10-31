"""Strict production D-Star selection. No file-error-to-software fallback."""
import json,os,time,uuid
from pathlib import Path
RUN=Path('/var/lib/asterisk/allmode')
DRAFT=Path('/var/lib/allmode/station-setup.json')
def read(name,default=None):
    try:
        value=json.loads((RUN/name).read_text())
    except FileNotFoundError:return default
    except (OSError,ValueError) as e:raise ValueError('Cannot read codec configuration: '+name) from e
    if not isinstance(value,dict):raise ValueError('Invalid codec configuration: '+name)
    return value
def desired():
    explicit=read('dstar-backend-request.json')
    if explicit is not None and (explicit.get('backend') not in ('software','hardware') or not isinstance(explicit.get('id'),str)):
        raise ValueError('Invalid backend request')
    try:draft=json.loads(DRAFT.read_text())
    except FileNotFoundError:draft={}
    except (OSError,ValueError) as e:raise ValueError('Cannot read shared saved codec selection') from e
    if draft:
        flag=draft.get('dstar',{}).get('enabled',False)
        if type(flag) is not bool:raise ValueError('Invalid saved codec selection')
        backend='hardware' if flag else 'software'
        if explicit and explicit['backend']==backend:return explicit
        return {'backend':backend,'id':'wizard-'+str(DRAFT.stat().st_mtime_ns)+'-'+backend,'origin':'shared saved wizard selection'}
    if explicit:return explicit
    cfg=read('dstar-codec.json',{})
    kind=cfg.get('type','software')
    if kind not in ('software','hardware','disabled'):raise ValueError('Unknown configured codec type')
    return {'backend':'hardware' if kind=='hardware' else 'software','id':'initial-'+kind,'origin':'applied hardware selection' if kind=='hardware' else 'software default'}

def write(name,value):
    path=RUN/name;tmp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    tmp.write_text(json.dumps(value));tmp.chmod(0o600);os.replace(tmp,path)
def hardware_config():
    cfg=read('dstar-codec.json',{})
    if not isinstance(cfg.get('host'),str) or not cfg['host'] or not isinstance(cfg.get('port',2460),int):raise ValueError('Apply valid external AMBE settings before selecting hardware')
    return cfg
def request(backend):
    if backend not in ('software','hardware'):raise ValueError('Unsupported backend')
    if backend=='hardware':
        hardware_config()
        try:modes=json.loads((RUN/'digital-modes.json').read_text())
        except FileNotFoundError:modes=[]
        if isinstance(modes,list) and len(set(modes)&{'D-STAR','DMR'})>1:raise ValueError('Disconnect one digital mode before selecting a shared external vocoder')
    from setup_lock import setup_lock
    with setup_lock(DRAFT):
        try:draft=json.loads(DRAFT.read_text())
        except FileNotFoundError:draft={}
        if draft:
            draft.setdefault('dstar',{})['enabled']=backend=='hardware'
            st=DRAFT.stat();temp=DRAFT.with_name('.codec-choice-'+uuid.uuid4().hex)
            temp.write_text(json.dumps(draft,indent=2));temp.chmod(0o600)
            if os.geteuid()==0:os.chown(temp,st.st_uid,st.st_gid)
            os.replace(temp,DRAFT)
        item={'backend':backend,'id':uuid.uuid4().hex,'origin':'shared explicit codec selection'}
        write('dstar-backend-request.json',item)
        import pwd
        a=pwd.getpwnam('allmode')
        if os.geteuid()==0:os.chown(RUN/'dstar-backend-request.json',a.pw_uid,a.pw_gid)
    return snapshot()

def snapshot():
    wanted=desired();state=read('dstar-codec-state.json',{})
    live=False
    try:
        pid=int(state.get('pid',0))
        live=pid>1 and 'dstar_worker.py' in Path('/proc',str(pid),'cmdline').read_text() and 0<=time.time()-state.get('updated',0)<3
    except (OSError,ValueError,TypeError):pass
    applied=read('dstar-codec.json',{})
    return {'mode':'DSTAR','default':'software','applied_selection':applied.get('type','software'),
            'saved_selection':wanted['backend'],'requested':wanted['backend'],'active':state.get('active') if live else None,
            'queued':live and state.get('request_id')!=wanted['id'],
            'worker_running':live,'busy':bool(live and state.get('busy')),
            'note':state.get('note') if live else 'Worker stopped or status stale; selection takes effect on next start',
            'selection_origin':wanted.get('origin','explicit production selection'),
            'profiles':{'YSF':['VD2'],'NXDN':['NXDN4800'],'P25':['PHASE1'],'M17':['CODEC2_3200']},
            'capabilities':{'DSTAR':['software','hardware'],'DMR':(['software','hardware'] if __import__('dmr_native').hardware_supported() else ['software']) if __import__('dmr_native').installed() else [],'YSF':['software'] if __import__('ysf_native').installed() else [],'P25':['software'] if __import__('p25_native').installed() else [],'M17':['software'] if __import__('m17_native').installed() else [],'NXDN':['software'] if __import__('nxdn_native').installed() else []}}

class Router:
    def __init__(self,factory=None,get=desired,publish=None):
        self.factory=factory or self.make;self.get=get;self.publisher=publish or (lambda s:write('dstar-codec-state.json',s))
        self.codec=None;self.active=None;self.request_id=None;self.requested=None;self.note=None;self.last_publish=0;self.last_poll=0;self.busy=False
        self.poll(False,force=True)
    @property
    def available(self):return self.codec is not None
    @staticmethod
    def make(backend):
        if backend=='software':
            from allmode_dstar_adapter import SourceCodec
            return SourceCodec()
        from dstar_hardware import HardwareCodec
        c=hardware_config();return HardwareCodec(c['host'],c.get('port',2460))
    def emit(self):
        self.publisher(dict(pid=os.getpid(),updated=time.time(),requested=self.requested,request_id=self.request_id,active=self.active,busy=self.busy,note=self.note))
        self.last_publish=time.monotonic()
    def drop(self):
        old=self.codec;self.codec=None;self.active=None
        if old is not None:old.close()
    def poll(self,busy,force=False):
        self.busy=busy;now=time.monotonic()
        if force or now-self.last_poll>=.25:
            self.last_poll=now
            try:
                req=self.get();self.requested=req['backend']
                if req['id']!=self.request_id and not busy:
                    self.drop();self.request_id=req['id'];self.note=None
                    try:self.codec=self.factory(self.requested);self.active=self.requested
                    except Exception as e:self.note='Selected codec unavailable: '+type(e).__name__
            except (OSError,ValueError,KeyError) as e:
                self.drop();self.note='Codec selection unreadable; processing stopped'
            self.emit()
        elif now-self.last_publish>=1:self.emit()
    def invoke(self,method,*args):
        if self.codec is None:raise OSError(self.note or 'Selected codec unavailable')
        try:return getattr(self.codec,method)(*args)
        except Exception:
            self.drop();self.note='Selected codec failed; processing stopped, no fallback';self.emit();raise OSError(self.note) from None
    def encode(self,*args):return self.invoke('encode',*args)
    def decode(self,*args):return self.invoke('decode',*args)
    def reset_tx(self):
        if self.codec is not None and hasattr(self.codec,'reset_tx'):self.codec.reset_tx()
    def reset_rx(self):
        if self.codec is not None and hasattr(self.codec,'reset_rx'):self.codec.reset_rx()
    def close(self):self.drop();self.note='Worker stopped';self.emit()
