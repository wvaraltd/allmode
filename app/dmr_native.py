"""Shared truthful native DMR readiness and configuration boundary."""
from pathlib import Path
import importlib.util,json,time
COMPONENT=Path('/opt/allmode-vocoder-prototype/current/ambe2450')
WORKER=Path('/opt/allmode/native_dmr/worker.py')

def installed():
    return WORKER.is_file() and (COMPONENT/'build/liballmode_2450.so').is_file() and importlib.util.find_spec('bitarray') is not None
def problem(station):
    if not any(station.get(g,{}).get('enabled') for g in ('brandmeister','tgif')):return None
    if station.get('dmr',{}).get('dvswitch') and not Path('/opt/MMDVM_Bridge/MMDVM_Bridge').is_file():return 'Local MMDVM_Bridge is not installed'
    if not installed():return 'Native DMR transport or source-built AMBE2450 codec is not installed'
    if station.get('dstar',{}).get('enabled') and not hardware_supported(station['dstar']):return 'External DMR capability is not verified for this device; select software or verify the configured hardware'
    from native_dmr.managed_config import from_station
    try:from_station(station)
    except (KeyError,TypeError,ValueError):return 'Complete the DMR identity and enabled network credentials'
    return None
def configured():
    import codec_selection
    from native_dmr.managed_config import validate
    c=codec_selection.read('dmr-native.json')
    if not c or c.get('disabled'):return False
    try:validate(c)
    except ValueError:return False
    return installed()
def status():
    import codec_selection
    if __import__('dvswitch_config').enabled():
        s=codec_selection.read('dvswitch-network-status.json',{})
        worker=codec_selection.read('dvswitch-worker-status.json',{})
        try:
            pid=int(worker.get('pid',0));live=pid>1 and 'dvswitch_worker.py' in Path('/proc',str(pid),'cmdline').read_text() and 0<=time.time()-worker.get('updated',0)<3 and 0<=time.time()-s.get('updated',0)<5
        except (OSError,ValueError,TypeError):live=False
        if not live:return dict(authenticated=False,state='stopped',active=None,note='DVSwitch worker or supervisor stopped or status stale')
        return dict(s,active=worker.get('active'),busy=worker.get('busy'),network='DVSwitch DMR',note='Local DVSwitch transport; voice interoperability unverified')
    s=codec_selection.read('dmr-native-status.json',{})
    live=False
    try:
        pid=int(s.get('pid',0));live=pid>1 and 'native_dmr/worker.py' in Path('/proc',str(pid),'cmdline').read_text() and 0<=time.time()-s.get('updated',0)<3
    except (OSError,ValueError,TypeError):pass
    if not live:return dict(authenticated=False,state='stopped',active=None,note='Native DMR worker stopped or status stale')
    return s

def hardware_supported(config=None):
    import codec_selection
    c=config if config is not None else codec_selection.read('dstar-codec.json',{})
    verified=codec_selection.read('ambe-capabilities.json',{})
    return bool(verified.get('passed') and 'DMR' in verified.get('profiles',[]) and all(c.get(k)==verified.get(k) for k in ('host','port')))
