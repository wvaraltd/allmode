"""Cached read-only signal queries, serialized with radio programming."""
import re, threading, time, os
from pathlib import Path
from contextlib import contextmanager
import digital
_thread=None
_state={}
_allowed=False
_start_lock=threading.Lock()

def directory():
    return Path(os.environ.get('ALLMODE_SERIAL_LOCK_DIR', str(digital.RUN)))

@contextmanager
def serial_lock(blocking=False):
    import fcntl
    with (directory()/'radio-serial.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try: yield
        finally: fcntl.flock(lock,fcntl.LOCK_UN)

def paused():
    return (directory()/'rssi-paused').exists()

def set_paused(value):
    global _state
    if type(value) is not bool:
        raise ValueError('paused must be true or false')
    with serial_lock(blocking=True):
        flag=directory()/'rssi-paused'
        if value: flag.touch()
        else: flag.unlink(missing_ok=True)
        _state={}
    return {'paused':value}

def parse_rssi(reply):
    match=re.search(rb'RSSI\s*[:=]\s*([0-9]{1,3})(?:\r|\n|$)',reply)
    return int(match[1]) if match and int(match[1])<=255 else None

def poll_once():
    global _state
    if not _allowed or paused(): return
    import serial
    with serial_lock():
        if not _allowed or paused(): return
        with serial.Serial('/dev/serial0',9600,timeout=.25,write_timeout=.25,exclusive=True) as port:
            port.reset_input_buffer();port.write(b'RSSI?\r\n');port.flush()
            reply=port.read_until(b'\n',64)
        value=parse_rssi(reply)
        if value is not None: _state={'value':value,'updated':time.monotonic()}

def _poll():
    while True:
        try: poll_once()
        except (OSError,ImportError): pass
        time.sleep(1)

def snapshot(active=True):
    global _thread,_allowed
    enabled=os.environ.get('ALLMODE_ENABLE_RSSI') != '0'
    _allowed=bool(active and enabled)
    is_paused=paused()
    with _start_lock:
        if _allowed and not is_paused and _thread is None:
            _thread=threading.Thread(target=_poll,daemon=True,name='radio-rssi');_thread.start()
    state=_state.copy()
    fresh=time.monotonic()-state.get('updated',0)<5
    return {'value':state.get('value') if _allowed and not is_paused and fresh else None,
            'unit':'relative','enabled':enabled,'paused':is_paused,'active':_allowed}
