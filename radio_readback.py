"""Cached, read-only SA818 queries. Never program or key the radio."""
import re, threading, time, os
from pathlib import Path
from contextlib import contextmanager
import digital

_thread=None
_state={}

@contextmanager
def serial_lock():
    import fcntl
    directory = Path(os.environ.get('ALLMODE_SERIAL_LOCK_DIR', str(digital.RUN)))
    with (directory/'radio-serial.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)

def parse_rssi(reply):
    match=re.search(rb'RSSI\s*[:=]\s*([0-9]{1,3})(?:\r|\n|$)',reply)
    return int(match[1]) if match and int(match[1])<=255 else None

def _poll():
    global _state
    while True:
        try:
            import serial
            with serial_lock(),serial.Serial('/dev/serial0',9600,timeout=.25,write_timeout=.25) as port:
                port.reset_input_buffer();port.write(b'RSSI?\r\n');port.flush()
                reply=port.read_until(b'\n',64)
            value=parse_rssi(reply)
            if value is not None:_state={'value':value,'updated':time.monotonic()}
        except (OSError,ImportError):pass
        time.sleep(1)

def snapshot():
    global _thread
    if _thread is None:
        _thread=threading.Thread(target=_poll,daemon=True,name='radio-rssi');_thread.start()
    state=_state.copy()
    return {'value':state.get('value') if time.monotonic()-state.get('updated',0)<5 else None,'unit':'relative'}
