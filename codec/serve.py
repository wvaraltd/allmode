# SPDX-License-Identifier: GPL-2.0-or-later
"""Loopback-only parrot interface. No RF/PTT/reflector or external codec connections."""
import argparse
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import time
from parrot import Parrot

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--port',type=int,default=8765); args=ap.parse_args()
    if not 1024<=args.port<=65535: ap.error('Use an unprivileged port between 1024 and 65535')
    state=Parrot(); token=secrets.token_urlsafe(32)
    host=f'127.0.0.1:{args.port}'; origin='http://'+host
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass # do not log tokens/audio
        def response(self,status,data,content='application/json'):
            self.send_response(status); self.send_header('Content-Type',content)
            self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; media-src 'self' blob:; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(data)
        def valid(self):
            return self.headers.get('Host')==host and self.headers.get('Origin',origin)==origin
        def do_GET(self):
            if not self.valid(): self.response(403,b'{}'); return
            if self.path=='/':
                page=Path(__file__).with_name('web.html').read_text(encoding='utf-8').replace('__TOKEN__',token)
                self.response(200,page.encode(),'text/html; charset=utf-8')
            elif self.path=='/state': self.response(200,json.dumps(state.state()).encode())
            else: self.response(404,b'{}')
        def do_POST(self):
            if not self.valid() or self.headers.get('X-Parrot-Token')!=token:
                self.response(403,b'{}'); return
            try:
                n=int(self.headers.get('Content-Length','-1'))
                if n<0 or n>60*16000: raise ValueError('Invalid request size')
                self.connection.settimeout(5)
                body=self.rfile.read(n)
                if len(body)!=n: raise ValueError('Truncated body')
                if self.path=='/complete': result=state.complete(body)
                elif self.path=='/play':
                    self.response(200,state.playback(),'audio/wav'); return
                else:
                    payload=json.loads(body or b'{}')
                    if not isinstance(payload,dict): raise ValueError('Expected JSON object')
                    if self.path=='/enable': result=state.enable(payload.get('seconds',30))
                    elif self.path=='/disable': result=state.disable()
                    elif self.path=='/record': result=state.record()
                    elif self.path=='/stop': result=state.stop()
                    elif self.path=='/finished': result=state.finished()
                    elif self.path=='/backend': result=state.select(payload.get('name'))
                    elif self.path=='/heartbeat': state.heartbeat(); result=state.state()
                    elif self.path=='/compare': raise ValueError('Hardware adapter unavailable; use routing.compare_recording after connecting a reviewed adapter')
                    else: self.response(404,b'{}'); return
                self.response(200,json.dumps(result).encode())
            except (ValueError,RuntimeError,OSError) as exc:
                self.response(400,json.dumps({'error':str(exc)}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    shutdown=threading.Event()
    def watchdog():
        while not shutdown.wait(.5): state.tick()
    threading.Thread(target=watchdog,daemon=True).start()
    print(f'Local parrot: {origin} — software default; no hardware adapter or RF/network TX',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: state.disable(); shutdown.set(); server.server_close()

if __name__=='__main__': main()
