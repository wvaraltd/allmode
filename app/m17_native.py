"""M17 local readiness is separate from reflector liveness/interoperability."""
from pathlib import Path
import time
WORKER=Path('/opt/allmode/native_m17/worker.py')
LIBRARY=Path('/usr/lib/aarch64-linux-gnu/libcodec2.so.1.2')
def installed():return WORKER.is_file() and LIBRARY.is_file()
def problem(station):
    other=station.get('other',{})
    if not (other.get('m17') or other.get('m17_host')):return None
    if not installed():return 'Native M17 Codec2 3200 component is not installed'
    from native_m17.config import from_station
    try:from_station(station)
    except ValueError as e:return str(e)
    return None
def configured():
    import codec_selection
    from native_m17.config import validate
    c=codec_selection.read('m17-native.json',{})
    if not c or c.get('disabled'):return False
    try:validate(c)
    except ValueError:return False
    return installed()
def status():
    import codec_selection
    s=codec_selection.read('m17-native-status.json',{})
    try:
        pid=int(s.get('pid',0))
        live=pid>1 and 'native_m17/worker.py' in Path('/proc',str(pid),'cmdline').read_text() and 0<=time.time()-s.get('updated',0)<3
    except (OSError,ValueError,TypeError):live=False
    if not live:return dict(state='stopped',connected=False,authenticated=False,active=None,note='M17 worker stopped or status stale')
    return s
def for_target(config,target):
    from native_m17.config import validate
    if target==config['target']:return validate(config)
    key=target.rsplit(' ',1)[0]
    try:lines=Path('/opt/allmode-dmr/hosts/M17Hosts.txt').read_text().splitlines()
    except OSError:lines=[]
    for line in lines:
        f=line.split()
        if len(f)>=3 and f[0]==key:
            return validate(dict(config,target=target,host=f[1],port=int(f[2])))
    raise ValueError('M17 destination is not in the downloaded directory')
