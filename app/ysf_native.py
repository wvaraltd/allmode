"""YSF local readiness is separate from reflector liveness/interoperability."""
from pathlib import Path
import time
WORKER=Path('/opt/allmode/native_ysf/worker.py')
LIBRARY=Path('/opt/allmode-vocoder-prototype/current/ambe2450/build/liballmode_2450.so')
def installed():return WORKER.is_file() and LIBRARY.is_file() and (WORKER.parent/'build/liballmode_ysf.so').is_file() and Path('/opt/allmode/native_nxdn/raw_codec.py').is_file()
def problem(station):
    other=station.get('other',{})
    if not (other.get('ysf') or other.get('ysf_host')):return None
    if not installed():return 'Native YSF V/D2 component is not installed'
    from native_ysf.config import from_station
    try:from_station(station)
    except ValueError as e:return str(e)
    return None
def configured():
    import codec_selection
    from native_ysf.config import validate
    c=codec_selection.read('ysf-native.json',{})
    if not c or c.get('disabled'):return False
    try:validate(c)
    except ValueError:return False
    return installed()
def status():
    import codec_selection
    s=codec_selection.read('ysf-native-status.json',{})
    try:
        pid=int(s.get('pid',0))
        live=pid>1 and 'native_ysf/worker.py' in Path('/proc',str(pid),'cmdline').read_text() and 0<=time.time()-s.get('updated',0)<3
    except (OSError,ValueError,TypeError):live=False
    if not live:return dict(state='stopped',connected=False,authenticated=False,active=None,note='YSF worker stopped or status stale')
    return s
def for_target(config,target):
    from native_ysf.config import validate
    target=int(target)
    if target==config['target']:return validate(config)
    import digital
    try:lines=(digital.ROOT/'hosts/YSFHosts.txt').read_text().splitlines()
    except FileNotFoundError:lines=[]
    for line in lines:
        fields=line.split(';')
        if len(fields)>=5 and fields[0].isdigit() and int(fields[0])==target:
            return validate(dict(config,target=target,host=fields[3],port=int(fields[4])))
    raise ValueError('YSF destination has no configured reflector endpoint')
