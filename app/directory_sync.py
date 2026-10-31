"""Public digital directories. Refresh without changing active radio connections."""
import json,os,re,time,urllib.request
from pathlib import Path
CACHE=Path('/var/lib/allmode/directories')
HOSTS=Path('/opt/allmode-dmr/hosts')
BASE='https://www.pistar.uk/downloads/'
SOURCES={'YSF':BASE+'YSF_Hosts.txt','NXDN':BASE+'NXDN_Hosts.txt','P25':BASE+'P25_Hosts.txt','M17':BASE+'M17_Hosts.txt','DCS':BASE+'DCS_Hosts.txt','REF':BASE+'DPlus_Hosts.txt','XLX':BASE+'XLXHosts.txt','BrandMeister':'https://api.brandmeister.network/v2/talkgroup','TGIF':'https://tgif.network/tglist.php'}
FILES={'YSF':'YSFHosts.txt','NXDN':'NXDNHosts.txt','P25':'P25Hosts.txt','M17':'M17Hosts.txt','DCS':'DCSHosts.txt','REF':'REFHosts.txt','XLX':'XLXHosts.txt'}

def host(value):
    return bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',value))

def parse(source,text):
    rows={}
    if source=='BrandMeister':
        data=json.loads(text)
        if not isinstance(data,dict):raise ValueError('Unexpected talkgroup format')
        return sorted([{'target':k,'name':v[:200]} for k,v in data.items() if k.isascii() and k.isdigit() and 1<=int(k)<=16777215 and isinstance(v,str)],key=lambda r:int(r['target']))
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        f=[v.strip() for v in (line.split(';') if source in ('YSF','XLX','TGIF') else line.split())]
        try:
            if source=='TGIF':
                if len(f)<3 or f[1]!='0' or not f[0].isascii() or not f[0].isdigit() or not 1<=int(f[0])<=16777215:continue
                row={'target':str(int(f[0])),'name':f[2][:200]}
            elif source=='YSF':
                if len(f)<5 or not re.fullmatch(r'[0-9]{1,5}',f[0]):continue
                row={'target':f[0].zfill(5),'name':f[1][:100]+' / '+f[2][:100],'host':f[3],'port':int(f[4])}
            elif source in ('NXDN','P25','M17'):
                if len(f)<3:continue
                if source=='M17':
                    if not re.fullmatch(r'M17-[A-Z0-9]{3}',f[0]):continue
                    target=f[0]
                else:
                    if not f[0].isascii() or not f[0].isdigit() or not 1<=int(f[0])<=(65535 if source=='NXDN' else 16777215):continue
                    target=str(int(f[0]))
                row={'target':target,'name':f[3][:200] if len(f)>3 else f[1],'host':f[1],'port':int(f[2])}
            else:
                if len(f)<2:continue
                target='XLX'+f[0] if source=='XLX' else f[0]
                if not re.fullmatch(r'(?:DCS|REF|XLX)[0-9]{3}',target):continue
                row={'target':target,'name':target,'host':f[1],'port':20001 if source=='REF' else 30051}
            if 'host' in row and (not host(row['host']) or not 1<=row['port']<=65535):continue
            rows[row['target']]=row
        except (ValueError,IndexError):continue
    return sorted(rows.values(),key=lambda r:r['target'])

def atomic(path,text):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(text,encoding='utf-8');tmp.chmod(0o644);os.replace(tmp,path)

def cached(source):
    try:return json.loads((CACHE/(source+'.json')).read_text())
    except (OSError,ValueError):return {'source':source,'rows':[],'updated':None,'error':'No downloaded directory yet.'}

def listing(source):
    if source=='D-STAR':
        parts=[cached(s) for s in ('DCS','REF','XLX')]
        return {'source':source,'rows':list({r['target']:r for p in parts for r in p['rows']}.values()), 'updated':min((p['updated'] for p in parts if p.get('updated')),default=None),'error':'; '.join(p['source']+': '+p['error'] for p in parts if p.get('error')) or None,'attribution':'Pi-Star host files / reflector operators'}
    if source not in SOURCES:raise ValueError('Unsupported digital directory')
    d=cached(source);d['attribution']='Pi-Star / DVRef reflector directory' if source in ('YSF','NXDN','P25','M17') else source+' public directory';return d

def endpoint(source,target):
    key=target.rsplit(' ',1)[0] if source=='M17' else str(target).zfill(5) if source=='YSF' else str(target)
    return next((r for r in listing(source)['rows'] if r['target']==key),None)

def refresh_one(source,fetch=None):
    previous=cached(source)
    try:
        if fetch is None:
            req=urllib.request.Request(SOURCES[source],headers={'User-Agent':'ARA-AllMode directory updater/1.0'})
            with urllib.request.urlopen(req,timeout=25) as response:raw=response.read(8*1024*1024+1)
        else:raw=fetch(SOURCES[source])
        if len(raw)>8*1024*1024:raise ValueError('Oversized directory')
        rows=parse(source,raw.decode('utf-8-sig'))
        if not rows or (len(previous['rows'])>100 and len(rows)<len(previous['rows'])//2):raise ValueError('Empty or unexpectedly incomplete directory')
        if source in FILES:
            lines=[]
            for r in rows:
                if source=='YSF':lines.append(f"{r['target']};{r['name'].replace(';',' ')};;{r['host']};{r['port']};000;")
                else:lines.append(f"{r['target']} {r['host']} {r['port']}")
            atomic(HOSTS/FILES[source],'# ARA AllMode public directory; source: '+SOURCES[source]+'\n'+'\n'.join(lines)+'\n')
        result={'source':source,'url':SOURCES[source],'rows':rows,'updated':time.time(),'error':None}
    except (OSError,ValueError) as exc:
        result=previous.copy();result['error']='Refresh failed ('+type(exc).__name__+'); last working list retained.'
    result['attempt']=time.time();atomic(CACHE/(source+'.json'),json.dumps(result));return result

if __name__=='__main__':
    import fcntl
    CACHE.mkdir(parents=True,exist_ok=True,mode=0o755)
    with (CACHE/'refresh.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for source in SOURCES:
            result=refresh_one(source);print(source,len(result['rows']),result.get('error') or 'updated',flush=True)
