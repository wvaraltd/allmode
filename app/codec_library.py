"""Inventory and non-executing inspection of administrator-uploaded codec libraries."""
from pathlib import Path
import hashlib,json,os,struct,subprocess,tempfile,time,threading
ROOT=Path('/var/lib/allmode/codec-uploads')
MAX=16*1024*1024
LOCK=threading.Lock()
COMPONENT=Path('/opt/allmode-vocoder-prototype/current')
PROFILES={
 'dstar':('D-STAR','ARA AllMode D-STAR software',COMPONENT/'build/liballmode_dstar.so',{'ad_create','ad_destroy','ad_reset','ad_encode','ad_decode','ad_lost','ad_thread_cleanup'}),
 'ambe2450':('DMR / YSF V/D2 / NXDN','ARA AllMode AMBE2450 software',COMPONENT/'ambe2450/build/liballmode_2450.so',{'a2450_create','a2450_destroy','a2450_reset','a2450_encode','a2450_decode','mbe_decodeAmbe3600x2450Frame','mbe_encodeAmbe3600x2450Frame'}),
 'p25':('P25 Phase 1','ARA AllMode IMBE (DroidStar source)',Path('/opt/allmode/native_p25/build/liballmode_p25.so'),{'p25_create','p25_destroy','p25_encode','p25_decode'}),
 'm17':('M17','Codec2 1.2 — 3200 bit/s',Path('/usr/lib/aarch64-linux-gnu/libcodec2.so.1.2'),{'codec2_create','codec2_destroy','codec2_encode','codec2_decode','codec2_samples_per_frame','codec2_bits_per_frame'})}
def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory():
 rows=[]
 for key,(modes,name,path,symbols) in PROFILES.items():
  rows.append(dict(profile=key,modes=modes,name=name,file=path.name,installed=path.is_file(),sha256=fingerprint(path) if path.is_file() else None))
 uploads=[]
 for p in sorted(ROOT.glob('*.json'),reverse=True):
  try:uploads.append(json.loads(p.read_text()))
  except (OSError,ValueError):pass
 return dict(installed=rows,uploads=uploads)
def inspect(path,profile):
 if profile not in PROFILES:raise ValueError('Choose a codec profile')
 with path.open('rb') as f:header=f.read(64)
 if len(header)<64 or header[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<HH',header,16)!=(3,183):raise ValueError('Expected a 64-bit ARM Linux shared library (.so) for this Pi')
 result=subprocess.run(['/usr/bin/readelf','--dyn-syms','--wide',str(path)],capture_output=True,text=True,timeout=10,check=False)
 if result.returncode:raise ValueError('Cannot read library symbols')
 symbols={parts[7].split('@')[0] for line in result.stdout.splitlines() if len(parts:=line.split())>=8 and parts[6]!='UND' and parts[4] in ('GLOBAL','WEAK')}
 missing=PROFILES[profile][3]-symbols
 if missing:raise ValueError('Library does not match the '+profile+' interface; missing '+', '.join(sorted(missing)))
 return 'ARM64 and required exported symbols checked; runtime compatibility has not been tested'
def upload(profile,name,body):
 if not isinstance(name,str) or not name.lower().endswith('.so') or len(name)>128 or any(ord(c)<32 for c in name):raise ValueError('Choose a .so codec library')
 if not 0<len(body)<=MAX:raise ValueError('Codec must be between 1 byte and 16 MiB')
 with LOCK:
  ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
  if len(list(ROOT.glob('*.json')))>=10:raise ValueError('Upload storage is full (10 libraries)')
  fd,temp=tempfile.mkstemp(dir=ROOT,suffix='.upload');path=Path(temp)
  try:
   with os.fdopen(fd,'wb') as f:f.write(body)
   checks=inspect(path,profile);digest=fingerprint(path);key=profile+'-'+digest
   dest=ROOT/(key+'.so');os.replace(path,dest);dest.chmod(0o600)
   item=dict(profile=profile,name=name.replace('\\','/').rsplit('/',1)[-1],sha256=digest,size=len(body),uploaded=time.time(),status='Uploaded — not active',checks=checks)
   metadata=ROOT/(key+'.json');metadata.write_text(json.dumps(item));metadata.chmod(0o600)
   return item
  finally:path.unlink(missing_ok=True)
