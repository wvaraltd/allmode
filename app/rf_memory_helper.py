"""Fixed-argument app_rpt cmd helper; no destination, shell, or HTTP accepted."""
import json
import re
import socket
import sys
from rf_memories import SOCKET, slot

def main(args):
    if len(args)!=2 or not re.fullmatch('[a-f0-9]{64}',args[1]):return 2
    try:
        number=slot(args[0])
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.settimeout(5);client.connect(SOCKET)
            client.sendall(json.dumps({'slot':number,'generation':args[1]}).encode()+b'\n')
            reply=json.loads(client.makefile('rb').readline(4097))
            return 1 if reply.get('error') else 0
    except (OSError,ValueError):return 1
if __name__=='__main__':raise SystemExit(main(sys.argv[1:]))
