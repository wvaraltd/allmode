"""Ephemeral current-playout identity, never a last-heard or directory lookup.

Workers publish only already accepted stream metadata while keyed PCM is being
played. Active means an active transmission, not syllable/VAD detection: the
existing packet-gap unkey watchdog clears after 600 ms on native/DVSwitch paths
and 1 second on D-STAR. Explicit end/reset clears with normal playout unkey.
Readers also require a fresh report, its live worker and a matching
currently connected destination. This module never connects or starts audio.
"""
import math
import re
import time
from pathlib import Path

TTL=1.5
REPORTS={
 'D-STAR':('dstar-status.json','dstar_worker.py'),
 'DMR':('dmr-native-status.json','native_dmr/worker.py'),
 'YSF':('ysf-native-status.json','native_ysf/worker.py'),
 'NXDN':('nxdn-native-status.json','native_nxdn/worker.py'),
 'P25':('p25-native-status.json','native_p25/worker.py'),
 'M17':('m17-native-status.json','native_m17/worker.py'),
}


def identity(mode,value):
    if mode in ('DMR','NXDN','P25'):
        limit=65535 if mode=='NXDN' else 0xffffff
        if type(value) is int and 1<=value<=limit:return mode+' ID '+str(value)
        return None
    if isinstance(value,bytes):
        try:value=value.decode('ascii')
        except UnicodeError:return None
    if not isinstance(value,str):return None
    value=value.strip()
    return value if re.fullmatch(r'[A-Z0-9][A-Z0-9 /.-]{0,15}',value) else None


def playout(engine,mode,valid=True):
    """Header receipt or a queued frame alone is not active speaker evidence."""
    active=bool(valid and getattr(engine,'rx_key' if mode=='D-STAR' else 'keyed',False))
    value=getattr(engine,'rx_identity',None)
    if mode=='DMR' and not hasattr(engine,'rx_identity'):
        value=getattr(engine,'rx',None)
        value=value[0] if isinstance(value,tuple) else None
    return dict(active=active,identity=identity(mode,value) if active else None)


def target_key(mode,value):
    if mode in ('DMR','YSF','NXDN','P25'):
        text=str(value)
        return str(int(text)) if text.isascii() and text.isdigit() else None
    return value if isinstance(value,str) else None


def live_process(pid,script):
    if type(pid) is not int or pid<=1:return False
    try:return script in Path('/proc',str(pid),'cmdline').read_text()
    except (OSError,ValueError):return False


def blank(connected,reason=None):
    return dict(active=False,identity=None,mode=None,state='listening' if connected else 'disconnected',expires_in_ms=0,reason=reason)


def current(connections,connected,read,now=None,alive=live_process,requested=None,rf_active=False,rf_age=TTL,link_report=None):
    if not connected:return blank(False)
    now=time.time() if now is None else now
    rows=list(link_report['rows']) if isinstance(link_report,dict) and link_report.get('known') is True else []
    if rf_active and 0<=rf_age<TTL:
        rows.append(dict(active=True,identity=None,mode='RF',state='active',expires_in_ms=max(0,int((TTL-rf_age)*1000)),reason='Local RF input has no sender identity metadata'))
    for connection in connections:
        mode=connection.get('mode')
        if mode not in REPORTS or (requested is not None and mode not in requested):continue
        name,script=REPORTS[mode]
        transport=read('dvswitch.json',{}) if mode=='DMR' else {}
        if mode=='DMR' and isinstance(transport,dict) and transport.get('dmr_transport')=='dvswitch':
            name,script='dvswitch-worker-status.json','dvswitch_worker.py'
        report=read(name,{})
        if not isinstance(report,dict):continue
        updated=report.get('updated');speaker=report.get('speaker')
        if type(updated) not in (int,float) or not math.isfinite(updated) or not 0<=now-updated<TTL:continue
        if not alive(report.get('pid'),script):continue
        target=target_key(mode,connection.get('target'))
        if target is None or target_key(mode,report.get('target'))!=target:continue
        if not isinstance(speaker,dict) or speaker.get('active') is not True:continue
        # The worker has already normalized its identity. Validate the public
        # value again without deriving a callsign from the connected node.
        name=speaker.get('identity')
        if not isinstance(name,str) or not re.fullmatch(r'[A-Z0-9][A-Za-z0-9 /.-]{0,31}',name):name=None
        rows.append(dict(active=True,identity=name,mode=mode,state='active',expires_in_ms=max(0,int((TTL-(now-updated))*1000)),reason=None if name else 'Active audio; sender identity unavailable'))
    if len(rows)==1:return rows[0]
    if len(rows)>1:return dict(active=True,identity=None,mode=None,state='active',expires_in_ms=min(row['expires_in_ms'] for row in rows),reason='Multiple active inputs; a single speaker cannot be identified')
    unsupported=any(row.get('mode') in ('AllStar','EchoLink') for row in connections) and not (isinstance(link_report,dict) and link_report.get('known') is True)
    return blank(True,'Live speaker telemetry unavailable for this network' if unsupported else None)


def linked_audio(text,connections,age):
    """ASL rpt xnode RPT_ALINKS: adjacent node + link mode + K/U.

    Official rpt_link.c USE_FORMAT_RPT_ALINK exports lastrx1 as K or U.
    This identifies the receiving *link*, not a talker's originating callsign.
    Correlate to both current confirmed connections and xnode ESTABLISHED rows.
    """
    unknown=dict(known=False,rows=[])
    if not isinstance(text,str) or len(text)>262144 or not 0<=age<TTL:return unknown
    lines=re.findall(r'^RPT_ALINKS=(.*)$',text,re.M)
    if len(lines)!=1:return unknown
    fields=lines[0].strip().split(',')
    if not fields[0].isascii() or not fields[0].isdigit():return unknown
    count=int(fields[0]);tokens=fields[1:]
    if not 0<=count<=1024 or count!=len(tokens):return unknown
    parsed={}
    for token in tokens:
        match=re.fullmatch(r'([1-9][0-9]{3,9})([TRLC])([KU])',token)
        if not match or match[1] in parsed:return unknown
        parsed[match[1]]=(match[2],match[3])
    established={cols[0] for line in text.splitlines() if len(cols:=line.split())>=6 and cols[0].isdigit() and cols[-1]=='ESTABLISHED'}
    rows=[]
    for c in connections:
        mode=c.get('mode');peer=str(c.get('peer') or c.get('target',''))
        if mode not in ('AllStar','EchoLink') or peer not in established:continue
        if parsed.get(peer,(None,None))[0] in ('T','R','L') and parsed[peer][1]=='K':
            label='Via node '+peer if mode=='AllStar' else 'Via EchoLink node '+str(c.get('target',''))
            rows.append(dict(active=True,identity=label,mode=mode,state='active',expires_in_ms=max(0,int((TTL-age)*1000)),reason='Receiving link only; originating speaker identity is not supplied through a hub'))
    return dict(known=True,rows=rows)
