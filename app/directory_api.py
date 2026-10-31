"""Read-only public directories, fixed sources and conservative caching."""
import json
import threading
import time
import urllib.request
from operator_store import atomic
LOCK=threading.Lock()
SOURCES={'AllStar':('https://allmondb.allstarlink.org/allmondb.php',900),'BrandMeister':('https://api.brandmeister.network/v2/talkgroup',86400)}
def directory(root,source):
 if source!='AllStar':
  import directory_sync
  return directory_sync.listing(source)
 if source not in SOURCES:raise ValueError('Directory source is not supported.')
 with LOCK:
  path=root/('directory-'+source+'.json');url,ttl=SOURCES[source]
  try:cached=json.loads(path.read_text(encoding='utf-8'))
  except (OSError,ValueError):cached={}
  if time.time()-cached.get('attempt',0)<ttl:return cached
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'ARA-AllMode/0.7 directory client','Accept':'application/json,text/plain'})
   with urllib.request.urlopen(req,timeout=15) as response:raw=response.read(8*1024*1024+1)
   if len(raw)>8*1024*1024:raise ValueError('Directory response too large.')
   if source=='AllStar':
    rows=[]
    for line in raw.decode('utf-8',errors='replace').splitlines():
     p=line.split('|')
     if len(p)>=3 and p[0].isdigit():rows.append({'target':p[0],'name':p[1]+' · '+p[2]})
   else:
    data=json.loads(raw)
    if not isinstance(data,dict):raise ValueError('Invalid directory response.')
    rows=[{'target':k,'name':str(v)[:200]} for k,v in data.items() if k.isdigit() and isinstance(v,str)]
   cached={'source':source,'url':url,'updated':time.time(),'rows':rows,'error':None}
  except (OSError,ValueError):cached.update(error='Directory refresh failed. Showing cached entries if available.',source=source,url=url)
  cached['attempt']=time.time();atomic(path,cached);return cached
