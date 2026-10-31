"""Local client for the fixed-operation system service. No shell commands accepted."""
import json
import socket
SOCKET='/run/allmode-system/control.sock'
def request(action, **values):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(45)
        client.connect(SOCKET)
        client.sendall(json.dumps(dict(action=action,**values)).encode()+b'\n')
        with client.makefile('rb') as stream:
            raw=stream.readline(131073)
        if len(raw)>131072:raise ValueError('System response too large.')
        reply=json.loads(raw)
        if 'error' in reply:raise ValueError(reply['error'])
        return reply

def status():
    try:return request('status')
    except (OSError,ValueError,AttributeError):return dict(available=False,active=False,applied=False,error='System service unavailable.')
