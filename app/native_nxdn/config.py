# SPDX-License-Identifier: GPL-3.0-or-later
"""NXDN staging capability gate. Never reports a deployed mode as ready."""
if __package__:from .protocol import poll,header
else:from protocol import poll,header

def validate(config):
    if not isinstance(config,dict):raise ValueError('Expected NXDN configuration')
    poll(config.get('callsign'),config.get('target'))
    header(config.get('source'),config['target'],config.get('ran',1))
    host=config.get('host');port=config.get('port')
    if not isinstance(host,str) or not host or len(host)>253 or any(c.isspace() for c in host):raise ValueError('Invalid NXDN host')
    if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid NXDN port')
    if config.get('backend','software')!='software':raise ValueError('NXDN hardware profile not verified; no software fallback')
    if config.get('profile','NXDN4800')!='NXDN4800':raise ValueError('Only NXDN4800 narrow voice is implemented')
    return dict(config)

def capability():
    return dict(mode='NXDN',profile='NXDN4800',software=True,hardware=False,ready=False,
                reason='Readiness requires applied identity/destination and live peer status; external interoperability unverified')

def from_station(station):
    other=station.get('other',{})
    if not (other.get('nxdn') or other.get('nxdn_host')):return None
    if station.get('dstar',{}).get('enabled'):raise ValueError('NXDN requires software; external NXDN profile is not verified')
    try:
        c=dict(version=1,callsign=station['station']['callsign'],source=int(other.get('nxdn_id','')),
               target=int(other.get('nxdn','')),host=other.get('nxdn_host',''),
               port=int(other.get('nxdn_port',41400)),ran=int(other.get('nxdn_ran',1)),profile='NXDN4800',backend='software')
    except (ValueError,TypeError,KeyError):raise ValueError('Complete NXDN ID, talkgroup, reflector host, port and RAN') from None
    return validate(c)
