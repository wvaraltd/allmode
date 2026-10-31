"""Resolve public destinations at Connect time using the applied station identity."""
import copy,importlib,json
MODES=('YSF','NXDN','P25','M17')
def prepare(mode,target,source_id,station,previous,remembered,lookup):
 if mode not in MODES:raise ValueError('Unsupported automatic digital configuration')
 if not isinstance(target,str):raise ValueError('Choose a destination')
 target=target.strip().upper()
 if mode=='M17':
  from native_m17.protocol import destination
  destination(target)
 elif not target.isascii() or not target.isdigit():raise ValueError('Enter a numeric destination')
 else:target=str(int(target)).zfill(5) if mode=='YSF' else str(int(target))
 row=lookup(mode,target)
 # Retain explicitly configured private endpoints, but prefer directory updates.
 if row is None and str(previous.get('target'))==str(int(target) if mode=='YSF' else target) and not previous.get('disabled'):
  row={'host':previous.get('host'),'port':previous.get('port')}
 if row is None:raise ValueError('Destination is not in the downloaded directory. Enter a custom server in Settings if needed.')
 s=copy.deepcopy(station);o=s.setdefault('other',{});key=mode.lower()
 o.update({key:target,key+'_host':row['host'],key+'_port':row['port']})
 if mode in ('NXDN','P25'):
  saved=remembered.get(mode,{})
  identity=source_id or (saved.get('id') if saved.get('callsign')==s['station']['callsign'] else o.get(key+'_id') or (previous.get('source') if previous.get('callsign')==s['station']['callsign'] else None))
  if not identity:raise ValueError('Enter your '+mode+' ID in Settings > Digital IDs.')
  o[key+'_id']=str(identity)
 if mode=='M17':
  saved=remembered.get('M17',{})
  if saved.get('callsign')==s['station']['callsign'] and saved.get('id'):s['station']['callsign']=saved['id']
 return importlib.import_module('native_'+key+'.config').from_station(s)
