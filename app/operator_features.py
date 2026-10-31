"""Local schedules and observed receive activity. Never runs shell input."""
import datetime as dt
import json
import re
import threading
import time
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from operator_store import atomic

class Features:
    def __init__(self,root,controller):
        self.path=root/'operator-features.json';self.controller=controller
        self.lock=threading.RLock();self.last_rx=None
        try:self.data=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.data={'rules':[],'history':[],'airtime':{}}
    def save(self):atomic(self.path,self.data)
    def snapshot(self):
        with self.lock:return json.loads(json.dumps(self.data))
    def action(self,p):
        with self.lock:
            if p.get('action')=='delete':
                self.data['rules']=[r for r in self.data['rules'] if r['id']!=p.get('id')]
            elif p.get('action')=='toggle':
                rule=next((r for r in self.data['rules'] if r['id']==p.get('id')),None)
                if rule is None or type(p.get('enabled')) is not bool:raise ValueError('Invalid rule.')
                rule['enabled']=p['enabled']
            elif p.get('action')=='add':
                if len(self.data['rules'])>=30:raise ValueError('Maximum 30 rules.')
                label=p.get('label','');zone=p.get('timezone','');clock=p.get('time','');days=p.get('days',[])
                if not isinstance(label,str) or not 1<=len(label)<=60:raise ValueError('Enter a label of 1–60 characters.')
                try:ZoneInfo(zone)
                except (ZoneInfoNotFoundError,TypeError,ValueError):raise ValueError('Choose a valid IANA time zone.') from None
                if not isinstance(clock,str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',clock):raise ValueError('Choose a time.')
                if not isinstance(days,list) or not days or any(type(d) is not int or not 0<=d<=6 for d in days):raise ValueError('Choose at least one day.')
                mode=p.get('mode');target=p.get('target','');op=p.get('operation')
                if mode not in ('AllStar','EchoLink','DMR','YSF','NXDN','P25','M17','D-STAR'):raise ValueError('Unknown mode.')
                if op not in ('connect','disconnect'):raise ValueError('Choose connect or disconnect.')
                if not isinstance(target,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _./#-]{0,47}',target):raise ValueError('Enter a destination.')
                self.data['rules'].append(dict(id=uuid.uuid4().hex,label=label,timezone=zone,time=clock,days=sorted(set(days)),mode=mode,target=target,operation=op,enabled=False,last_run=None,last_result='Not run'))
            else:raise ValueError('Unknown schedule operation.')
            self.save();return self.snapshot()
    def tick(self,now=None):
        now=now or dt.datetime.now(dt.timezone.utc)
        with self.lock:
            for rule in self.data['rules']:
                local=now.astimezone(ZoneInfo(rule['timezone']))
                key=local.strftime('%Y-%m-%d %H:%M')
                if not rule['enabled'] or local.weekday() not in rule['days'] or local.strftime('%H:%M')!=rule['time'] or rule['last_run']==key:continue
                # Persist before dispatch: a restart cannot repeat the same local minute.
                rule['last_run']=key;rule['last_result']='Dispatching';self.save()
                try:
                    with self.controller.lock:
                        s=self.controller.snapshot()
                        if s.get('pending') or s.get('readonly') or s.get('bridge_enabled'):raise ValueError('Station busy or controls unavailable.')
                        if not s.get('simulation') and not s.get('runtime',{}).get('radio_enabled'):raise ValueError('Radio is stopped. Rule skipped.')
                        if rule['operation']=='connect':
                            if s.get('connected'):raise ValueError('An existing connection is active. Rule skipped.')
                            if rule['mode'] not in s.get('modes',[]):raise ValueError('Mode is unavailable.')
                            self.controller.command('mode',rule['mode'])
                            self.controller.command('connect',rule['target'])
                            result='Connection requested; check live status for confirmation.'
                        else:
                            if not s.get('connected') or s.get('mode')!=rule['mode'] or str(s.get('target'))!=rule['target']:raise ValueError('Target is not the current connection. Rule skipped.')
                            self.controller.command('disconnect',None);result='Disconnect requested.'
                except Exception as error:result=str(error)
                rule['last_result']=result
                self.data['history'].insert(0,dict(time=now.isoformat(),label=rule['label'],result=result))
                self.data['history']=self.data['history'][:100];self.save()
            with self.controller.lock:s=self.controller.snapshot()
            if s.get('simulation'):return
            mode=s.get('mode','Unknown');stamp=now.timestamp()
            if s.get('receiving'):
                key=now.strftime('%Y-%m')
                bucket=self.data['airtime'].setdefault(key,{})
                row=bucket.setdefault(mode,{'seconds':0,'count':0})
                if self.last_rx is None:row['count']+=1
                else:row['seconds']+=max(0,min(4,stamp-self.last_rx))
                self.last_rx=stamp;self.save()
            else:self.last_rx=None
            # Retain 13 monthly buckets, no personal callsigns.
            for key in sorted(self.data['airtime'])[:-13]:del self.data['airtime'][key]
