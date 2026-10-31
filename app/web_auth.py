"""Password login for the TLS-proxied local appliance."""
import hashlib
import hmac
import json
import secrets
import threading
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

OWNER_PENDING = Path('/etc/allmode/os-owner-pending')

class Auth:
    def __init__(self, path):
        self.path=Path(path)
        self.config = json.loads(Path(path).read_text()) if Path(path).exists() else {'unclaimed':True}
        self.sessions = {}
        self.failures = []
        self.lock = threading.Lock()

    @property
    def unclaimed(self):return self.config.get('unclaimed') is True

    def claim(self,password):
        if not isinstance(password,str) or not 4<=len(password)<=128 or any(c in password for c in '\r\n\0'):raise ValueError('Choose a password of 4–128 characters.')
        with self.lock:
            if not self.unclaimed:raise ValueError('This station already has an owner password.')
            salt=secrets.token_bytes(16)
            config={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()}
            from operator_store import atomic
            pending=OWNER_PENDING
            if pending.exists():
                import system_client
                system_client.request('owner-password',password=password)
            atomic(self.path,config);self.config=config

    def valid(self, handler):
        try:
            cookie = SimpleCookie(handler.headers.get('Cookie', ''))
            token = cookie['allmode_session'].value
        except Exception:
            return False
        with self.lock:
            self.sessions = {k:v for k,v in self.sessions.items() if v > time.monotonic()}
            return token in self.sessions

    def login(self, handler):
        if self.unclaimed:
            handler.reply(409,{'error':'Choose an owner password in first-run setup.'});return
        try:
            size = int(handler.headers.get('Content-Length','0'))
            if not 0 < size <= 1024:
                raise ValueError()
            data = parse_qs(handler.rfile.read(size).decode())
            username = data.get('username',[''])[0]
            password = data.get('password',[''])[0]
        except (ValueError, UnicodeError):
            handler.reply(400, {'error':'Invalid login request.'})
            return
        with self.lock:
            now = time.monotonic()
            self.failures = [t for t in self.failures if now-t < 60]
            if len(self.failures) >= 10:
                handler.reply(429, {'error':'Too many login attempts. Wait one minute.'})
                return
            digest = hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(self.config['salt']),600000).hex()
            if username != 'admin' or not hmac.compare_digest(digest,self.config['hash']):
                self.failures.append(now)
                handler.send_response(303)
                handler.send_header('Location','/login?error=1')
                handler.send_header('Content-Length','0')
                handler.end_headers()
                return
            token = secrets.token_urlsafe(32)
            self.sessions = {k:v for k,v in self.sessions.items() if v > now}
            if len(self.sessions) >= 100:
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[token] = now+8*3600
        handler.send_response(303)
        handler.send_header('Set-Cookie',f'allmode_session={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=28800')
        import operator_store
        ob=getattr(handler.server,'onboarding',None)
        handler.send_header('Location','/' if ob and operator_store.completed(ob) else '/setup')
        handler.send_header('Content-Length','0')
        handler.end_headers()

    def change(self,current,password):
        if not isinstance(password,str) or not 4<=len(password)<=128 or any(c in password for c in '\r\n\0'):
            raise ValueError('Choose a password of 4–128 characters.')
        if not isinstance(current,str):raise ValueError('Enter the current password.')
        with self.lock:
            digest=hashlib.pbkdf2_hmac('sha256',current.encode(),bytes.fromhex(self.config['salt']),600000).hex()
            if not hmac.compare_digest(digest,self.config['hash']):raise ValueError('Current password is incorrect.')
            salt=secrets.token_bytes(16)
            config={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()}
            from operator_store import atomic
            atomic(self.path,config)
            self.config=config;self.sessions.clear()

    def logout(self, handler):
        try:
            token=SimpleCookie(handler.headers.get('Cookie',''))['allmode_session'].value
            with self.lock:
                self.sessions.pop(token,None)
        except Exception:
            pass
        handler.send_response(303)
        handler.send_header('Set-Cookie','allmode_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0')
        handler.send_header('Location','/login')
        handler.send_header('Content-Length','0')
        handler.end_headers()
