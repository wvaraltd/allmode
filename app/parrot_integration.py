# SPDX-License-Identifier: GPL-2.0-or-later
"""Authenticated ALLMODE handler extension. Host checks session and Origin first."""
import json
import os
from pathlib import Path
import sys
COMPONENT=Path(os.environ.get('ALLMODE_VOCODER_ROOT','/opt/allmode-vocoder-prototype/current'))
if str(COMPONENT) not in sys.path:sys.path.insert(0,str(COMPONENT))
from parrot import Parrot
STATE=Parrot()

def tick(): STATE.tick()
def close(): STATE.disable()
def raw(handler,data,mime):
    handler.send_response(200);handler.send_header('Content-Type',mime)
    handler.send_header('Content-Length',str(len(data)));handler.send_header('Cache-Control','no-store')
    handler.send_header('X-Content-Type-Options','nosniff')
    handler.send_header('Content-Security-Policy',"default-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'")
    handler.end_headers();handler.wfile.write(data)

def get(handler,path):
    if path=='/audio-tools':
        handler.send_response(303);handler.send_header('Location','/settings#audio');handler.send_header('Content-Length','0');handler.end_headers();return True
    if path=='/codec':
        handler.send_response(303);handler.send_header('Location','/settings#dstar');handler.send_header('Content-Length','0');handler.end_headers();return True
    if path in ('/radio-parrot','/browser-parrot','/parrot'):
        handler.send_response(303);handler.send_header('Location','/audio-tools');handler.send_header('Content-Length','0');handler.end_headers();return True
    if path in ('/audio-tools','/audio-tools.js'):
        name='audio-tools.html' if path=='/audio-tools' else 'audio-tools.js'
        mime='text/html; charset=utf-8' if path=='/audio-tools' else 'text/javascript; charset=utf-8'
        raw(handler,(Path(__file__).parent/'web'/name).read_bytes(),mime);return True
    if path=='/audio-meter.js':
        raw(handler,(Path(__file__).parent/'web/audio-meter.js').read_bytes(),'text/javascript; charset=utf-8');return True
    if path=='/api/audio-meter':
        import system_client
        try:handler.reply(200,system_client.request('audio-meter'))
        except (ValueError,OSError) as e:handler.reply(200,{'active':False,'error':str(e)})
        return True
    if path=='/api/codec/libraries':
        import codec_library
        handler.reply(200,codec_library.inventory());return True
    if path=='/api/codec/state':
        import system_client
        handler.reply(200,system_client.request('codec-state'));return True
    if path=='/api/radio-parrot/state':
        import system_client
        handler.reply(200,system_client.request('radio-parrot-state'));return True
    if path=='/api/parrot/state':handler.reply(200,STATE.state());return True
    files={'/codec':('codec.html','text/html; charset=utf-8'),'/codec.js':('codec.js','text/javascript; charset=utf-8'),'/radio-parrot':('radio-parrot.html','text/html; charset=utf-8'),'/radio-parrot.js':('radio-parrot.js','text/javascript; charset=utf-8'),'/browser-parrot':('parrot.html','text/html; charset=utf-8'),'/parrot':('radio-parrot.html','text/html; charset=utf-8'),
           '/parrot.js':('parrot.js','text/javascript; charset=utf-8'),
           '/parrot.css':('parrot.css','text/css; charset=utf-8')}
    if path not in files:return False
    name,mime=files[path];raw(handler,(COMPONENT/'deploy/web'/name).read_bytes(),mime);return True

def post(handler,path):
    if path=='/api/codec/upload':
        import codec_library
        try:
            size=int(handler.headers.get('Content-Length','-1'))
            if not 0<size<=codec_library.MAX:raise ValueError('Codec upload limit is 16 MiB')
            if handler.headers.get('Content-Type')!='application/octet-stream':raise ValueError('Expected a binary codec library')
            handler.connection.settimeout(30);body=handler.rfile.read(size)
            if len(body)!=size:raise ValueError('Upload incomplete')
            result=codec_library.upload(handler.headers.get('X-Codec-Profile'),handler.headers.get('X-Codec-Name',''),body)
            handler.reply(200,result)
        except (ValueError,OSError) as error:handler.reply(400,{'error':str(error)})
        except Exception:handler.reply(400,{'error':'Library inspection failed; upload not installed'})
        return True

    if path=='/api/codec/select':
        import system_client
        try:
            size=int(handler.headers.get('Content-Length','-1'))
            if not 0<=size<=1024:raise ValueError('Invalid request length')
            handler.connection.settimeout(5)
            data=json.loads(handler.rfile.read(size) or b'{}')
            if not isinstance(data,dict):raise ValueError('Expected JSON')
            handler.reply(200,system_client.request('codec-select',backend=data.get('backend')))
        except ValueError as e:handler.reply(400,{'error':str(e)})
        except OSError:handler.reply(503,{'error':'System service unavailable. Retry when it is running.'})
        return True
    if path.startswith('/api/radio-parrot/'):

        import system_client
        try:
            size=int(handler.headers.get('Content-Length','-1'))
            if not 0<=size<=1024:raise ValueError('Invalid request length')
            handler.connection.settimeout(5)
            data=json.loads(handler.rfile.read(size) or b'{}')
            if not isinstance(data,dict):raise ValueError('Expected JSON')
            action=path.rsplit('/',1)[-1]
            if action not in ('arm','stop','heartbeat'):raise ValueError('Unknown radio test action')
            handler.reply(200,system_client.request('radio-parrot-'+action,confirm=data.get('confirm'),mode=data.get('mode','analog')))
        except ValueError as e:handler.reply(400,{'error':str(e)})
        except OSError:handler.reply(503,{'error':'System service unavailable. Retry when it is running.'})
        return True
    if not path.startswith('/api/parrot/'):return False
    try:
        size=int(handler.headers.get('Content-Length','-1'))
        if not 0<=size<=960000:raise ValueError('Invalid request length')
        handler.connection.settimeout(5)
        body=handler.rfile.read(size)
        if len(body)!=size:raise ValueError('Truncated request')
        action=path[len('/api/parrot/'):]
        if action=='complete':result=STATE.complete(body)
        elif action=='play':raw(handler,STATE.playback(),'audio/wav');return True
        else:
            data=json.loads(body or b'{}')
            if not isinstance(data,dict):raise ValueError('Expected JSON object')
            if action=='enable':result=STATE.enable(data.get('seconds',30))
            elif action=='disable':result=STATE.disable()
            elif action=='record':result=STATE.record()
            elif action=='stop':result=STATE.stop()
            elif action=='finished':result=STATE.finished()
            elif action=='backend':result=STATE.select(data.get('name'))
            elif action=='heartbeat':STATE.heartbeat();result=STATE.state()
            elif action=='compare':raise ValueError('Hardware comparison adapter unavailable; no fabricated results')
            else:raise ValueError('Unknown parrot action')
        handler.reply(200,result)
    except (ValueError,RuntimeError,OSError) as e:handler.reply(400,{'error':str(e)})
    return True
