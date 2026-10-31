"""Private station profiles and durable setup completion."""
import json
import os
import re
import time
import tempfile
from pathlib import Path
from onboarding import GROUPS

def atomic(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        Path(temp).unlink(missing_ok=True)


def update_group(onboarding, group, values):
    if group not in GROUPS:raise ValueError('Unknown settings section.')
    with onboarding.lock:
        old=onboarding.read()
        data={g:old.get(g,{k:d for k,_,_,d in fields}) for g,fields in GROUPS.items()}
        data[group]=values
        return onboarding.save(data,networks_reviewed=True)

def completed(onboarding):
    return (onboarding.path.parent/'setup-complete.json').is_file()

def finish(onboarding):
    snapshot=onboarding.snapshot()
    if not all(s['complete'] for s in snapshot['workflow']['steps'] if not s.get('optional')):
        raise ValueError('Complete station/network setup, program the radio and apply configuration before finishing setup.')
    atomic(onboarding.path.parent/'setup-complete.json',{'completed_at':time.time(), 'audio_status':snapshot['workflow'].get('audio_status','untested')})
    return {'ok':True,'complete':True}

def skip_audio(onboarding):
    # An explicit choice, never an audio confirmation or radio activation.
    with onboarding.lock:
        atomic(onboarding.path.parent/'audio-test-choice.json', {'status':'skipped','chosen_at':time.time()})
    return {'ok':True,'audio_status':'skipped','message':'Audio test skipped for now; audio remains unverified.'}


def profiles(onboarding, payload=None):
    root=onboarding.path.parent/'profiles'
    with onboarding.lock:
        if payload:
            name=payload.get('name','')
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,47}',name):
                raise ValueError('Use a profile name with 1–48 letters, numbers, spaces, hyphens or underscores.')
            path=root/(name+'.json');action=payload.get('action')
            if action=='save':
                config=onboarding.read()
                if not config:raise ValueError('Save station settings first.')
                if path.exists():raise ValueError('That profile already exists. Choose a new name.')
                radio=onboarding.path.parent/'draft.json'
                atomic(path,{'config':config,'radio':json.loads(radio.read_text()) if radio.exists() else None,'created':time.time()})
            elif action=='restore':
                if not path.is_file():raise ValueError('Profile not found.')
                saved=json.loads(path.read_text(encoding='utf-8'))
                radio_path=onboarding.path.parent/'draft.json'
                radio=saved.get('radio')
                if radio is not None:
                    from sa818_hardware import validate
                    radio=validate(radio)
                previous=onboarding.read()
                if previous:atomic(root/('before-restore-'+str(time.time_ns())+'.json'),{'config':previous,'radio':json.loads(radio_path.read_text()) if radio_path.exists() else None,'created':time.time()})
                # Replace rather than retain another station's blank passwords.
                oldpath=onboarding.path
                data={g:saved['config'].get(g,{k:d for k,_,_,d in fields}) for g,fields in GROUPS.items()}
                snapshot=onboarding.save(data)
                clean=onboarding.read()
                for g,fields in GROUPS.items():
                    for key,_,kind,_ in fields:
                        if kind=='password':clean[g][key]=data[g][key]
                atomic(oldpath,clean)
                if radio is not None:atomic(radio_path,radio)
                else:radio_path.unlink(missing_ok=True)
                return {'ok':True,'message':'Profile recalled into saved settings. Review and apply; radio programming is a separate action.'}
            else:raise ValueError('Unknown profile operation.')
        return {'profiles':[{'name':p.stem,'modified':p.stat().st_mtime} for p in sorted(root.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)]}
