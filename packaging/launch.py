#!/usr/bin/python3
"""Strict package-level web configuration; never interpret shell fragments."""
import json, os, pathlib, sys
from urllib.parse import urlsplit

def arguments(path):
    c=json.loads(pathlib.Path(path).read_text())
    required={'schema','port','public_origin','auth_file','hardware','lan_proxy'}
    if not isinstance(c,dict) or set(c)!=required or c['schema']!=1: raise ValueError('Invalid configuration schema')
    if type(c['port']) is not int or not 1024<=c['port']<=65535: raise ValueError('Invalid port')
    if type(c['hardware']) is not bool or type(c['lan_proxy']) is not bool: raise ValueError('Expected boolean')
    # Existing LAN installations use a comma-separated allowlist. Preserve it
    # byte-for-byte for the application; validate every origin, not the whole list.
    if not isinstance(c['public_origin'],str): raise ValueError('Invalid public origins')
    origins=c['public_origin'].split(',')
    if not 1<=len(origins)<=16: raise ValueError('Invalid public origins')
    for origin in origins:
        if not origin or any(ch.isspace() or ord(ch)<32 for ch in origin): raise ValueError('Invalid public origin')
        u=urlsplit(origin)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.path not in ('','/') or u.query or u.fragment: raise ValueError('Invalid public origin')
        if u.port is not None and not 1<=u.port<=65535: raise ValueError('Invalid public origin port')
        if u.hostname not in ('127.0.0.1','localhost','::1') and (u.scheme!='https' or not c['auth_file']): raise ValueError('Remote origin requires HTTPS and authentication')
    a=['/usr/bin/python3','/opt/allmode/server.py','--managed','--port',str(c['port']),'--public-origin',c['public_origin']]
    if c['auth_file'] is not None:
        if c['auth_file']!='/var/lib/allmode/auth.json': raise ValueError('Invalid auth path')
        a+=['--auth-file',c['auth_file']]
    for key in ('hardware','lan_proxy'):
        if c[key]: a+=['--'+key.replace('_','-')]
    return a
if __name__=='__main__':
    try: args=arguments('/etc/allmode/service.json')
    except (ValueError,OSError,TypeError): sys.exit('Invalid /etc/allmode/service.json; service not started')
    if sys.argv[1:]==['--check']: sys.exit(0)
    if sys.argv[1:]: sys.exit('Usage: allmode-launch [--check]')
    os.execv(args[0],args)
