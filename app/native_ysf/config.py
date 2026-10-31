# SPDX-License-Identifier: GPL-3.0-or-later
if __package__:from .protocol import callsign
else:from protocol import callsign
def validate(c):
    if not isinstance(c,dict):raise ValueError('Expected YSF configuration')
    callsign(c.get('callsign'))
    if c.get('source')!=c['callsign']:raise ValueError('YSF source must match configured callsign')
    if type(c.get('target')) is not int or not 0<=c['target']<=99999:raise ValueError('YSF reflector ID must be 00000..99999')
    h=c.get('host');p=c.get('port')
    if not isinstance(h,str) or not h or len(h)>253 or any(x.isspace() for x in h):raise ValueError('Enter YSF reflector hostname or IPv4')
    if type(p) is not int or not 1<=p<=65535:raise ValueError('Invalid YSF UDP port')
    if type(c.get('ran',0)) is not int or not 0<=c.get('ran',0)<=99:raise ValueError('YSF DG-ID must be 0..99')
    if c.get('backend','software')!='software':raise ValueError('YSF external hardware unsupported; no software fallback')
    if c.get('profile','YSF_VD2')!='YSF_VD2':raise ValueError('Only YSF V/D mode 2 is implemented; V/D1 and full-rate unsupported')
    return dict(c)
def from_station(station):
    o=station.get('other',{})
    if not (o.get('ysf') or o.get('ysf_host')):return None
    if station.get('dstar',{}).get('enabled'):raise ValueError('YSF V/D mode 2 requires software; external profile unverified')
    try:
        call=station['station']['callsign']
        c=dict(version=1,callsign=call,source=call,target=int(o.get('ysf','')),host=o.get('ysf_host',''),port=int(o.get('ysf_port',42000)),ran=int(o.get('ysf_dgid',0)),profile='YSF_VD2',backend='software')
    except (ValueError,TypeError,KeyError):raise ValueError('Complete YSF reflector ID, host, port and DG-ID') from None
    return validate(c)
def capability():return dict(mode='YSF',profile='YSF_VD2',software=True,hardware=False,ready=False,unsupported=['VD1','VOICE_FR','DATA_FR','FCS'])
