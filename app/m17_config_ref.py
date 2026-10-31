# SPDX-License-Identifier: GPL-3.0-or-later
if __package__:from .protocol import address,destination
else:from protocol import address,destination
def validate(c):
    if not isinstance(c,dict):raise ValueError('Expected M17 configuration')
    address(c.get('callsign'));address(c.get('source'));destination(c.get('target'))
    if c['source']!=c['callsign']:raise ValueError('M17 source must match configured callsign')
    h=c.get('host');port=c.get('port')
    if not isinstance(h,str) or not h or len(h)>253 or any(x.isspace() for x in h):raise ValueError('Enter M17 reflector hostname or IPv4')
    if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid M17 UDP port')
    if type(c.get('ran',0)) is not int or not 0<=c.get('ran',0)<=15:raise ValueError('M17 CAN must be 0..15')
    if c.get('backend','software')!='software':raise ValueError('M17 external hardware unsupported; no software fallback')
    if c.get('profile','M17_3200')!='M17_3200':raise ValueError('Only M17 Codec2 3200 voice implemented; 1600/data/encryption/signatures unsupported')
    return dict(c)
def from_station(station):
    o=station.get('other',{})
    if not(o.get('m17') or o.get('m17_host')):return None
    if station.get('dstar',{}).get('enabled'):raise ValueError('M17 requires software; external codec unsupported')
    try:c=dict(version=1,callsign=station['station']['callsign'],source=station['station']['callsign'],target=o.get('m17','').upper().strip(),host=o.get('m17_host',''),port=int(o.get('m17_port',17000)),ran=int(o.get('m17_can',0)),profile='M17_3200',backend='software')
    except (ValueError,TypeError,KeyError):raise ValueError('Complete M17 reflector/module, host, port and CAN') from None
    return validate(c)
