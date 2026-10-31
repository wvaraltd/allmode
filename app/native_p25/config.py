# SPDX-License-Identifier: GPL-3.0-or-later
if __package__:from .protocol import callsign,identity
else:from protocol import callsign,identity
def validate(c):
    if not isinstance(c,dict):raise ValueError('Expected P25 configuration')
    callsign(c.get('callsign'));identity(c.get('source'));identity(c.get('target'))
    h=c.get('host');port=c.get('port')
    if not isinstance(h,str) or not h or len(h)>253 or any(x.isspace() for x in h):raise ValueError('Enter P25 reflector hostname or IPv4')
    if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid P25 UDP port')
    if c.get('backend','software')!='software':raise ValueError('P25 hardware unsupported; no software fallback')
    if c.get('profile','P25_PHASE1')!='P25_PHASE1':raise ValueError('Only clear P25 Phase 1 group voice is implemented; Phase 2 unsupported')
    return dict(c)
def from_station(station):
    o=station.get('other',{})
    if not(o.get('p25') or o.get('p25_host')):return None
    if station.get('dstar',{}).get('enabled'):raise ValueError('P25 Phase 1 requires software; external profile unverified')
    try:c=dict(version=1,callsign=station['station']['callsign'],source=int(o.get('p25_id','')),target=int(o.get('p25','')),host=o.get('p25_host',''),port=int(o.get('p25_port',41000)),profile='P25_PHASE1',backend='software')
    except (ValueError,TypeError,KeyError):raise ValueError('Complete P25 source ID, target talkgroup, host and port') from None
    return validate(c)
def capability():return dict(mode='P25',profile='P25_PHASE1',software=True,hardware=False,ready=False,unsupported=['PHASE2','ENCRYPTED','PRIVATE'])
