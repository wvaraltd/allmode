"""Fail-closed AllStar local-receiver memories. No network control or shell input."""
import contextlib
import fcntl
import hashlib
import glob
import json
import logging
import os
from pathlib import Path
import pwd
import re
import socket
import socketserver
import struct
import tempfile
import threading

BEGIN = '; BEGIN ALLMODE RF MEMORIES'
END = '; END ALLMODE RF MEMORIES'
SOCKET = '/run/allmode-favorites/recall.sock'
HELPER = '/opt/allmode/rf_memory_helper.py'


def generation(favorites):
    rows = [{k:f.get(k) for k in ('id','slot','mode','target','network','source_id')} for f in favorites if f.get('enabled')]
    return hashlib.sha256(json.dumps(sorted(rows,key=lambda f:str(f['id'])),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def slot(value):
    if not isinstance(value,str) or not re.fullmatch(r'[1-9][0-9]{0,2}',value):
        raise ValueError('RF memory must be 1–999 without leading zeroes.')
    return value


def overlap(a,b):
    return a.startswith(b) or b.startswith(a)


def unmanaged(text):
    if text.count(BEGIN)!=text.count(END) or text.count(BEGIN)>2:
        raise ValueError('Malformed managed RF configuration block.')
    return re.sub(re.escape(BEGIN)+r'\n.*?'+re.escape(END)+r'\n?', '', text, flags=re.S)


class Config:
    def __init__(self,path='/etc/asterisk/rpt.conf',node=None,reload=None,lock='/var/lib/allmode-system/rf-memories.lock'):
        self.path=Path(path); self.node=str(node or ''); self.reload=reload; self.lock=Path(lock)

    def read(self):
        files={}; sections={}; locations={}; parents={}; active=[]
        def visit(path):
            path=path.resolve()
            if path in active or path in files:raise ValueError('Recursive or repeated rpt.conf include is ambiguous.')
            if not path.is_relative_to(self.path.resolve().parent):raise ValueError('Include outside Asterisk configuration directory requires review.')
            active.append(path)
            raw=path.read_text(); text=unmanaged(raw); files[path]=(raw,text)
            section=None
            for line in text.splitlines():
                line=line.strip()
                if not line or line.startswith(';'):continue
                if line.startswith('#'):
                    match=re.fullmatch(r'#(include|tryinclude)\s+["<]?([^"<>\s]+)[">]?',line)
                    if not match or '$' in match[2]:raise ValueError('Unsupported or ambiguous Asterisk include directive.')
                    include=Path(match[2]); pattern=str(include if include.is_absolute() else path.parent/include)
                    matches=sorted(glob.glob(pattern))
                    if not matches and match[1]=='include':raise ValueError('Required Asterisk include is missing.')
                    for child in matches:visit(Path(child))
                    continue
                match=re.fullmatch(r'\[([^\]]+)\](?:\(([^)]+)\))?\s*(?:;.*)?',line)
                if match:
                    section=match[1]
                    if section in sections:raise ValueError('Duplicate Asterisk section requires review: '+section)
                    sections[section]={};locations[section]=path
                    parents[section]=[p.strip() for p in (match[2] or '').split(',') if p.strip() and p.strip()!='!']
                    if '+' in parents[section]:raise ValueError('Appended Asterisk sections require review.')
                    continue
                if section is None:raise ValueError('Asterisk value outside a section.')
                match=re.fullmatch(r'([^=\s]+)\s*=\s*(.*?)\s*(?:;.*)?',line)
                if not match:raise ValueError('Unsupported Asterisk syntax requires review.')
                key,value=match.groups()
                if key in sections[section]:raise ValueError('Duplicate Asterisk key requires review: '+key)
                sections[section][key]=value
            active.pop()
        visit(self.path)
        def effective(name,seen=()):
            if name in seen or name not in sections:raise ValueError('Missing or cyclic Asterisk section: '+name)
            result={}
            for parent in parents[name]:result.update(effective(parent,seen+(name,)))
            result.update(sections[name]);return result
        effective.parents=parents
        return files,sections,locations,effective

    def plan(self,favorites):
        enabled=[f for f in favorites if f.get('enabled')]
        files,sections,locations,effective=self.read()
        if not re.fullmatch(r'[0-9]+',self.node):raise ValueError('Station node is unavailable.')
        node=effective(self.node)
        if node.get('funcchar','*')!='*':raise ValueError('RF memories require the existing * function character.')
        if node.get('alt_functions') or node.get('remote') or node.get('remote_functions') or node.get('auth_users'):
            raise ValueError('Alternate or remote-base control sources require owner review; RF memories remain disabled.')
        fn=node.get('functions','functions'); macro=node.get('macro','macro')
        functions=effective(fn); macros=effective(macro)
        if fn==macro:raise ValueError('Function and macro sections must be separate.')
        if functions.get('5','').replace(' ','') not in ('macro','macro,1'):raise ValueError('Existing *5 is not the conventional macro function; preserved unchanged.')
        # Macros lose caller provenance. Never expose a macro dispatcher remotely.
        for key in ('link_functions','phone_functions','dphone_functions'):
            table=node.get(key)
            if not table or table==fn:raise ValueError('RF enable requires separate '+key+' with no macro access.')
            values=effective(table)
            if any(v.split(',')[0].strip().lower() in ('macro','cmd') for v in values.values()):
                raise ValueError('Remote '+key+' exposes macro/cmd access; RF memories remain disabled.')
        for name in sections:
            if name.isdigit() and name!=self.node and (effective(name).get('functions','functions')==fn or effective(name).get('macro','macro')==macro):
                raise ValueError('Local function or macro table is shared with another node; isolate it before enabling RF memories.')
        for name,parents in effective.parents.items():
            if fn in parents or macro in parents:
                raise ValueError('Function or macro table has inherited consumers; isolate it before enabling RF memories.')
        slots=[slot(f.get('slot')) for f in enabled]
        if len(set(slots))!=len(slots):raise ValueError('Duplicate RF memory slot.')
        additions={fn:[],macro:[]}; digest=generation(favorites)
        for i,s in enumerate(slots):
            if any(overlap(s,x) for x in slots[:i]) or any(overlap(s,x) for x in macros if x.isdigit()):raise ValueError('RF macro slot '+s+' overlaps an existing or assigned macro.')
            invocation='5'+s
            if any(k!='5' and overlap(invocation.upper(),k.upper()) for k in functions):raise ValueError('RF command *'+invocation+' overlaps an existing function.')
            # Fixed helper codes contain letters so they cannot overlap macro numbers.
            code='D'+s+'D'
            if any(overlap(code.upper(),k.upper()) for k in functions):raise ValueError('Reserved RF helper code conflicts with an existing function.')
            additions[fn].append(f'{code}=cmd,/usr/bin/python3 {HELPER} {s} {digest}')
            additions[macro].append(f'{s}=*{code}#')
        output={path:text for path,(_,text) in files.items()}
        for section,lines in additions.items():
            if not lines:continue
            path=locations[section]
            pattern=r'(?m)^(\['+re.escape(section)+r'\](?:\([^\n]*\))?[^\n]*\n)'
            output[path],count=re.subn(pattern,lambda m:m[1]+BEGIN+'\n'+'\n'.join(lines)+'\n'+END+'\n',output[path],count=1)
            if count!=1:raise ValueError('Cannot uniquely locate RF function/macro section header.')
        return files,output,digest

    def isolation_plan(self):
        """Read-only exact effective-table plan; never applies caller-policy changes."""
        files,sections,locations,effective=self.read()
        if not re.fullmatch(r'[0-9]+',self.node):raise ValueError('Station node is unavailable.')
        node=effective(self.node)
        fn=node.get('functions','functions');macro=node.get('macro','macro')
        functions=effective(fn);macros=effective(macro)
        if functions.get('5','').replace(' ','') not in ('macro','macro,1'):
            raise ValueError('Existing *5 has nonconventional semantics; manual plan required.')
        if node.get('alt_functions') or node.get('remote') or node.get('remote_functions') or node.get('auth_users'):
            raise ValueError('Alternate or remote-base control sources require manual review.')
        prefix='allmode-'+self.node
        tables={prefix+'-local':functions,prefix+'-macro':macros}
        overrides={'functions':prefix+'-local','macro':prefix+'-macro'}
        removed={}
        for source in ('link_functions','phone_functions','dphone_functions'):
            name=node.get(source,fn if source=='link_functions' else None);values=effective(name) if name else {}
            if any(v.split(',')[0].strip().lower()=='cmd' for v in values.values()):
                raise ValueError('Remote cmd functions require individual review; no automatic isolation plan.')
            removed[source]={k:v for k,v in values.items() if v.split(',')[0].strip().lower()=='macro'}
            if any(k!='5' for k in removed[source]):
                raise ValueError('Additional remote macro aliases require separate owner review; only *5 isolation is approved.')
            table_name=prefix+'-'+source.removesuffix('_functions')
            tables[table_name]={k:v for k,v in values.items() if k not in removed[source]}
            overrides[source]=table_name
        if any(name in sections for name in tables):raise ValueError('Planned section names already exist; manual review required.')
        text='\n'.join('['+name+']\n'+'\n'.join(k+'='+v for k,v in values.items())+'\n' for name,values in tables.items())
        result={'node':self.node,'node_overrides':overrides,'new_sections':text,
                'removed_remote_macro_commands':removed,
                'source_sha256':{str(p):hashlib.sha256(raw.encode()).hexdigest() for p,(raw,_) in files.items()},
                'requires_owner_approval':True,
                'warning':'Review all indirect/privileged callers. Replace only node bindings, append these new sections, preserve all existing sections and includes. Never apply this plan automatically.'}
        result['plan_digest']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
        return result

    def apply_isolation(self,expected_digest,metadata_path=None,after_apply=None):
        """Explicit sysadmin operation, separate from favorites/installer saves."""
        if not isinstance(expected_digest,str) or not re.fullmatch('[a-f0-9]{64}',expected_digest):
            raise ValueError('Exact reviewed isolation plan digest is required.')
        self.lock.parent.mkdir(parents=True,exist_ok=True)
        with self.lock.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            plan=self.isolation_plan()
            if plan['plan_digest']!=expected_digest:raise ValueError('Configuration changed since review; regenerate and review isolation plan.')
            files,_,locations,_=self.read()
            observed={str(p):hashlib.sha256(raw.encode()).hexdigest() for p,(raw,_) in files.items()}
            if observed!=plan['source_sha256']:raise ValueError('Configuration changed after isolation plan verification.')
            path=locations[self.node]
            original=files[path][0]
            # No whole-section replacement: retain comments and every unrelated key.
            pattern=r'(?ms)(^\['+re.escape(self.node)+r'\](?:\([^\n]*\))?[^\n]*\n)(.*?)(?=^\[|\Z)'
            def replace(match):
                body=match[2]
                if re.search(r'(?m)^\s*#',body):raise ValueError('Include inside physical node section requires manual isolation review.')
                for key in plan['node_overrides']:
                    body=re.sub(r'(?m)^\s*'+re.escape(key)+r'\s*=.*\n?', '', body)
                return match[1]+body.rstrip()+'\n'+''.join(k+'='+v+'\n' for k,v in plan['node_overrides'].items())+'\n'
            updated,count=re.subn(pattern,replace,original)
            if count!=1:raise ValueError('Cannot uniquely locate physical node section.')
            updated=updated.rstrip()+'\n\n; Explicit owner-reviewed RF source isolation\n'+plan['new_sections']
            for source,(raw,_) in files.items():
                if source.read_text()!=raw:raise ValueError('Configuration changed during isolation review.')
            backup=path.with_name(path.name+'.allmode-rf-isolation-backup')
            self.atomic(backup,original,path.stat())
            metadata=Path(metadata_path) if metadata_path is not None else None
            old_metadata=metadata.read_text() if metadata is not None and metadata.exists() else None
            try:
                self.atomic(path,updated,path.stat())
                if not self.status()['available']:raise ValueError('Isolated configuration failed safety validation.')
                if self.reload:self.reload()
                if metadata is not None:
                    from types import SimpleNamespace
                    metadata.parent.mkdir(parents=True,exist_ok=True)
                    self.atomic(metadata,json.dumps(plan,indent=2),SimpleNamespace(st_mode=0o600,st_uid=os.getuid(),st_gid=os.getgid()))
                if after_apply:after_apply()
            except BaseException:
                if metadata is not None:
                    if old_metadata is None:metadata.unlink(missing_ok=True)
                    else:self.atomic(metadata,old_metadata,metadata.stat())
                self.atomic(path,original,path.stat())
                if self.reload:self.reload()
                raise
            return {'applied':True,'node':self.node,'plan_digest':expected_digest,'backup':str(backup)}

    def status(self,favorites=()):
        try:self.plan(favorites);return dict(available=True,reason='Local-only RF memory configuration is ready.')
        except (OSError,ValueError) as exc:return dict(available=False,reason=str(exc))

    @contextlib.contextmanager
    def transaction(self,favorites):
        self.lock.parent.mkdir(parents=True,exist_ok=True)
        with self.lock.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            enabled=any(f.get('enabled') for f in favorites)
            if enabled:files,output,_=self.plan(favorites)
            else:
                # Disable needs no source-isolation prerequisite but still parses all includes.
                try:files,_,_,_=self.read();output={p:clean for p,(_,clean) in files.items()}
                except (OSError,ValueError):
                    # All callbacks also require a matching enabled-store generation.
                    # Inactive favorites remain usable while RF config is unavailable.
                    yield
                    return
            changed=[p for p in output if files[p][0]!=output[p]]
            for path,(raw,_) in files.items():
                if path.read_text()!=raw:raise ValueError('Asterisk configuration changed during review; reload and retry.')
            written=[]
            try:
                for path in changed:
                    raw=files[path][0]
                    backup=path.with_name(path.name+'.allmode-rf-backup')
                    self.atomic(backup,raw,path.stat())
                    # Register before replace: directory fsync may fail after rename.
                    written.append(path)
                    self.atomic(path,output[path],path.stat())
                if changed and self.reload:self.reload()
                yield
            except BaseException:
                for path in reversed(written):self.atomic(path,files[path][0],path.stat())
                if written and self.reload:self.reload()
                raise

    @staticmethod
    def atomic(path,text,stat):
        fd,temp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
        try:
            with os.fdopen(fd,'w') as stream:
                stream.write(text);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),stat.st_mode&0o777)
                if os.geteuid()==0:os.fchown(stream.fileno(),stat.st_uid,stat.st_gid)
            os.replace(temp,path)
            d=os.open(path.parent,os.O_RDONLY)
            try:os.fsync(d)
            finally:os.close(d)
        finally:
            if os.path.exists(temp):os.unlink(temp)


def decode_request(raw,peer_uid,asterisk_uid):
    if peer_uid!=asterisk_uid:raise ValueError('Unauthorized local peer.')
    if not isinstance(raw,bytes) or len(raw)>256:raise ValueError('Request too large.')
    data=json.loads(raw)
    if not isinstance(data,dict) or set(data)!= {'slot','generation'} or not isinstance(data['generation'],str) or not re.fullmatch('[a-f0-9]{64}',data['generation']):
        raise ValueError('Invalid recall request.')
    return slot(data['slot']),data['generation']


class UnixMemoryServer:
    """Bounded local-only transport. Callback must validate current generation and gates."""
    def __init__(self,callback,path=SOCKET,asterisk_uid=None):
        uid=pwd.getpwnam('asterisk').pw_uid if asterisk_uid is None else asterisk_uid
        pending=threading.Lock()
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(2)
                _,peer,_=struct.unpack('3i',self.connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                if peer!=uid:return
                try:
                    raw=self.rfile.readline(257)
                    number,digest=decode_request(raw,peer,uid)
                    if not pending.acquire(blocking=False):raise ValueError('An RF recall is already pending.')
                    try:
                        # Acknowledge only receipt, never connection. No queue: one
                        # request owns admission until the dispatcher finishes.
                        self.wfile.write(b'{"requested":true}\n');self.wfile.flush()
                        try:
                            result=callback(number,digest)
                            logging.getLogger('allmode.favorites').info('RF memory request slot=%s outcome=%s',number,'rejected' if isinstance(result,dict) and result.get('error') else 'dispatched')
                        except Exception:
                            logging.getLogger('allmode.favorites').warning('RF memory request slot=%s rejected',number)
                    finally:pending.release()
                except Exception:
                    self.wfile.write(b'{"error":"RF memory recall rejected."}\n')
        self.path=Path(path)
        if self.path.exists():raise ValueError('RF recall socket already exists; service restart required.')
        self.server=socketserver.ThreadingUnixStreamServer(str(self.path),Handler)
        self.server.daemon_threads=True
        os.chmod(self.path,0o660)
        # Installer makes runtime directory allmode:asterisk with setgid.
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
    def start(self):self.thread.start();return self
    def close(self):
        self.server.shutdown();self.server.server_close();self.path.unlink(missing_ok=True)
