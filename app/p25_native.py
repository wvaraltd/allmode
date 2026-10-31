"""P25 local readiness is separate from reflector liveness/interoperability."""
from pathlib import Path
import time
WORKER=Path('/opt/allmode/native_p25/worker.py')
LIBRARY=Path('/opt/allmode/native_p25/build/liballmode_p25.so')
def installed():return WORKER.is_file() and LIBRARY.is_file()
def problem(station):
    other=station.get('other',{})
    if not (other.get('p25') or other.get('p25_host')):return None
    if not installed():return 'Native P25 Phase 1 component is not installed'
    from native_p25.config import from_station
    try:from_station(station)
    except ValueError as e:return str(e)
    return None
def configured():
    import codec_selection
    from native_p25.config import validate
    c=codec_selection.read('p25-native.json',{})
    if not c or c.get('disabled'):return False
    try:validate(c)
    except ValueError:return False
    return installed()
def status():
    import codec_selection
    s=codec_selection.read('p25-native-status.json',{})
    try:
        pid=int(s.get('pid',0))
        live=pid>1 and 'native_p25/worker.py' in Path('/proc',str(pid),'cmdline').read_text() and 0<=time.time()-s.get('updated',0)<3
    except (OSError,ValueError,TypeError):live=False
    if not live:return dict(state='stopped',connected=False,authenticated=False,active=None,note='P25 worker stopped or status stale')
    return s
def for_target(config,target):
    from native_p25.config import validate
    target=int(target)
    if target==config['target']:return validate(config)
    import digital
    try:lines=(digital.ROOT/'hosts/P25Hosts.txt').read_text().splitlines()
    except FileNotFoundError:lines=[]
    for line in lines:
        fields=line.split()
        if len(fields)>=3 and fields[0].isdigit() and int(fields[0])==target:
            return validate(dict(config,target=target,host=fields[1],port=int(fields[2])))
    raise ValueError('P25 destination has no configured reflector endpoint')
