# SPDX-License-Identifier: GPL-3.0-or-later
"""DMR configuration translation. Pure functions never connect or apply settings."""
import copy,re
if __package__:from .homebrew import number,configuration
else:from homebrew import number,configuration

def validate(c):
    if not isinstance(c,dict) or c.get('version')!=1:raise ValueError('Native DMR configuration is not applied')
    number(c.get('source'),1000000,9999999);number(c.get('peer'),100000000,999999999)
    if c['peer']//100!=c['source']:raise ValueError('DMR identity and ESSID disagree')
    number(c.get('color'),0,15);number(c.get('slot'),1,2)
    configuration(c['peer'],c.get('callsign'),color=c['color'])
    if c.get('selected') not in ('BrandMeister','TGIF'):raise ValueError('Select a DMR network')
    networks=c.get('networks')
    if not isinstance(networks,dict) or set(networks)!={'BrandMeister','TGIF'}:raise ValueError('Invalid DMR network configuration')
    for name,n in networks.items():
        if not isinstance(n,dict) or type(n.get('enabled')) is not bool:raise ValueError('Invalid network enable state')
        if n['enabled']:
            if not isinstance(n.get('host'),str) or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',n['host']):raise ValueError('Invalid DMR master hostname')
            if not isinstance(n.get('password'),str) or not 1<=len(n['password'].encode())<=256:raise ValueError('DMR hotspot password missing or too long')
            number(n.get('port'),1,65535);number(n.get('talkgroup'),1,0xffffff)
    if not networks[c['selected']]['enabled']:raise ValueError('Selected DMR network is disabled')
    return c

def from_station(station,previous=None):
    enabled=[name for name,key in [('BrandMeister','brandmeister'),('TGIF','tgif')] if station[key]['enabled']]
    if not enabled:return None
    old=(previous or {}).get('selected');selected=old if old in enabled else enabled[0]
    c=dict(version=1,source=int(station['dmr']['id']),peer=int(station['dmr']['id']+station['dmr']['essid']),
           callsign=station['station']['callsign'],color=station['dmr']['color_code'],slot=2,selected=selected,networks={})
    for name,key in [('BrandMeister','brandmeister'),('TGIF','tgif')]:
        n=station[key];c['networks'][name]=dict(enabled=n['enabled'],host=n['master'],port=62031,password=n['password'],talkgroup=int(n['talkgroup'] or '9'))
    return validate(c)

def public_fields(c):
    validate(c);master=c['networks']['BrandMeister']['host'].split('.')[0]
    return dict(Network=c['selected'],Master=master if master in ('3102','3103','3104') else '',Callsign=c['callsign'],Id=str(c['peer']),ColorCode=str(c['color']),Jitter='60')

def update(c,values):
    c=copy.deepcopy(validate(c))
    if 'Network' in values:c['selected']=values['Network']
    if 'Master' in values:
        if values['Master'] not in ('3102','3103','3104'):raise ValueError('Unsupported legacy master selector')
        c['networks']['BrandMeister']['host']=values['Master']+'.master.brandmeister.network'
    if 'Callsign' in values:c['callsign']=values['Callsign']
    if 'Id' in values:c['peer']=int(values['Id']);c['source']=c['peer']//100
    if 'ColorCode' in values:c['color']=int(values['ColorCode'])
    if 'Jitter' in values and int(values['Jitter'])!=60:raise ValueError('Native DMR currently uses a 60 ms burst buffer')
    for field,name in [('BMPassword','BrandMeister'),('TGIFPassword','TGIF')]:
        if values.get(field):c['networks'][name]['password']=values[field]
    return validate(c)
