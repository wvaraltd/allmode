"""Private first-run station/network configuration; never returns saved secrets."""
import json
import os
import re
import threading
from pathlib import Path

# key, label, input type, default. Disabled networks may be left empty.
GROUPS = {
 'station': [('callsign','Station callsign','text',''),('name','Operator name','text',''),('location','Location / QTH','text',''),('email','Email','email','')],
 'allstar': [('enabled','Enable AllStar','checkbox',False),('node','AllStar node number','text',''),('password','AllStar node password (not website password)','password','')],
 'echolink': [('enabled','Enable EchoLink','checkbox',False),('callsign','Validated EchoLink callsign, including -L or -R','text',''),('node','EchoLink node number','text',''),('password','EchoLink password','password',''),('name','Operator name','text',''),('location','Location / QTH','text',''),('email','Email','email','')],
 'dmr': [('id','Seven-digit DMR ID','text',''),('essid','Hotspot suffix / ESSID (00–99)','text','00'),('color_code','Color code (0–15)','number',1)],
 'brandmeister': [('enabled','Configure BrandMeister','checkbox',False),('master','Master hostname','text','3102.master.brandmeister.network'),('password','BrandMeister hotspot security password','password',''),('talkgroup','Initial talkgroup','text','9')],
 'tgif': [('enabled','Configure TGIF','checkbox',False),('master','Master hostname','text','tgif.network'),('password','TGIF hotspot security password','password',''),('talkgroup','Initial talkgroup','text','9')],
 'other': [('ysf','YSF reflector (optional)','text',''),('nxdn_id','NXDN ID (optional)','text',''),('nxdn','NXDN talkgroup (optional)','text',''),('p25','P25 talkgroup (optional)','text',''),('dstar','D-STAR reflector and module (optional)','text',''),('m17','M17 reflector and module (optional)','text','')]
}
TITLES={'station':'1. Station identity','allstar':'2. AllStar','echolink':'3. EchoLink','dmr':'4. DMR identity','brandmeister':'5. BrandMeister','tgif':'6. TGIF','other':'7. Other digital networks'}

class Onboarding:
    def __init__(self, root='/var/lib/allmode'):
        self.path=Path(root)/'station-setup.json'
        self.lock=threading.RLock()

    def read(self):
        try: return json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError: return {}

    def snapshot(self):
        with self.lock:
            saved=self.read()
        groups=[]
        for group, fields in GROUPS.items():
            rows=[]
            for key,label,kind,default in fields:
                value=saved.get(group,{}).get(key,default)
                rows.append(dict(key=key,label=label,type=kind,value='' if kind=='password' else value,saved=bool(value) if kind=='password' else False))
            groups.append(dict(id=group,title=TITLES[group],fields=rows))
        return dict(groups=groups, saved=bool(saved), activation='pending', workflow=self.workflow(saved),
                    note=('Configuration saved privately. ' if saved else 'Configuration has not been saved yet. ') + ' Network services are not activated by saving. AllStar/EchoLink service configuration and digital bridge installation are still required before live use.')

    def workflow(self, saved):
        """Derive progress from evidence; a saved credential is never activation."""
        try:
            program=json.loads((self.path.parent/'program.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            program={}
        radio_ok=(program.get('state')=='acknowledged-not-verified' and
                  program.get('acknowledged')==['AT+DMOSETGROUP','AT+DMOSETVOLUME','AT+SETFILTER','AT+SETTAIL'])
        station_ok=bool(saved.get('station',{}).get('callsign'))
        networks_ok=station_ok and saved.get('_networks_reviewed',bool(saved)) is True
        steps=[
            dict(id='station', title='Station', complete=station_ok, available=True),
            dict(id='networks', title='Networks', complete=networks_ok, available=station_ok),
            dict(id='radio', title='Radio', complete=radio_ok, available=networks_ok),
            dict(id='audio', title='Audio', complete=False, available=networks_ok and radio_ok),
            dict(id='review', title='Review', complete=False, available=networks_ok)]
        blockers=[]
        if not station_ok: blockers.append('Save your station callsign.')
        if not networks_ok: blockers.append('Save your network choices; unused networks can stay off.')
        if not radio_ok: blockers.append('Complete radio programming; all four commands must be acknowledged.')
        blockers.extend(['Applying saved credentials to live services is not implemented in this build.',
                         'Audio calibration and live network checks are still required.'])
        return dict(steps=steps, next_step=next(s['id'] for s in steps if not s['complete'] and s['available']),
                    ready=False, blockers=blockers, radio=program.get('settings') if radio_ok else None,
                    radio_note='Serial acknowledgements are not RF readback or an audio test.')

    def save_section(self, section, values):
        selected=['station'] if section=='station' else [g for g in GROUPS if g!='station'] if section=='networks' else []
        if not selected or not isinstance(values,dict) or set(values)!=set(selected):
            raise ValueError('Supply the fields for the selected setup step.')
        with self.lock:
            old=self.read()
            if section=='networks' and not old.get('station',{}).get('callsign'):
                raise ValueError('Save station identity before network choices.')
            data={g:old.get(g,{k:default for k,label,kind,default in rows}) for g,rows in GROUPS.items()}
            data.update(values)
            reviewed=True if section=='networks' else old.get('_networks_reviewed',bool(old))
            return self.save(data, networks_reviewed=reviewed)

    def save(self, data, networks_reviewed=True):
        if not isinstance(data,dict) or set(data)!=set(GROUPS): raise ValueError('Supply all setup sections.')
        with self.lock:
            old=self.read(); result={}
            for group, fields in GROUPS.items():
                values=data[group]
                if not isinstance(values,dict) or set(values)!={f[0] for f in fields}: raise ValueError('Invalid setup fields.')
                result[group]={}
                for key,label,kind,default in fields:
                    value=values[key]
                    if kind=='checkbox':
                        if type(value) is not bool: raise ValueError(label+': choose on or off.')
                    elif kind=='number':
                        if type(value) is not int or not 0<=value<=15: raise ValueError('Color code must be 0–15.')
                    else:
                        if not isinstance(value,str) or len(value)>128 or any(ord(c)<32 for c in value): raise ValueError(label+': invalid value.')
                        value=value.strip() if kind!='password' else value
                        if kind=='password' and not value: value=old.get(group,{}).get(key,'')
                    result[group][key]=value
            call=result['station']['callsign'].upper()
            if not re.fullmatch(r'[A-Z0-9]{3,12}(?:/[A-Z0-9]{1,4})?',call) or not any(c.isdigit() for c in call): raise ValueError('Enter your station callsign.')
            result['station']['callsign']=call
            for group in ('allstar','echolink'):
                if result[group]['enabled']:
                    node=result[group]['node']
                    if not re.fullmatch(r'[0-9]{4,6}' if group=='allstar' else r'[0-9]{1,7}',node) or int(node)==0: raise ValueError(group+': enter a valid node number.')
                    if not result[group]['password']: raise ValueError(group+': enter its password.')
            if result['echolink']['enabled']:
                if not re.fullmatch(r'[A-Za-z0-9]{3,12}-[LR]',result['echolink']['callsign']): raise ValueError('EchoLink requires your validated -L or -R callsign.')
                for key in ('name','location','email'):
                    if not result['echolink'][key]: raise ValueError('Complete EchoLink name, location and email.')
            for group in ('brandmeister','tgif'):
                if result[group]['enabled']:
                    if not re.fullmatch(r'[0-9]{7}',result['dmr']['id']): raise ValueError('Enter your seven-digit DMR ID.')
                    if not re.fullmatch(r'[0-9]{2}',result['dmr']['essid']): raise ValueError('ESSID must be two digits, 00–99.')
                    if not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',result[group]['master']): raise ValueError('Enter a valid DMR master hostname.')
                    tg=result[group]['talkgroup']
                    if not tg.isascii() or not tg.isdigit() or not 1<=int(tg)<=16777215: raise ValueError('Enter a valid DMR talkgroup.')
                    if not result[group]['password']: raise ValueError(group+': enter its hotspot password.')
            result['_networks_reviewed']=networks_reviewed
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.tmp')
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(result,f,indent=2); f.flush(); os.fsync(f.fileno())
            os.replace(temp,self.path)
        return self.snapshot()
