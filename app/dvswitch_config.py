# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit local DVSwitch transport selection; never installs or starts services."""
import configparser
from pathlib import Path

DEFAULT={'version':1,'dmr_transport':'native','tlv_receive':31100,'tlv_send':31103,
         'usrp_receive':34001,'usrp_send':32001}


def validate(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULT):raise ValueError('Unknown DVSwitch setting')
    c=dict(DEFAULT,**value)
    if type(c['version']) is not int or c['version']!=1 or c['dmr_transport'] not in ('native','dvswitch'):
        raise ValueError('Invalid DVSwitch transport')
    ports=[c[k] for k in ('tlv_receive','tlv_send','usrp_receive','usrp_send')]
    if any(type(p) is not int or not 1024<=p<=65535 for p in ports) or len(set(ports))!=4:
        raise ValueError('DVSwitch ports must be distinct unprivileged UDP ports')
    import digital
    reserved={v for mode,profile in digital.PROFILES.items() if mode!='DMR' for key,v in profile.items() if key in ('rx','tx','tlv','mb','remote','codec')}
    if set(ports)&reserved:raise ValueError('DVSwitch port conflicts with another local digital mode')
    return c


def load():
    import codec_selection
    return validate(codec_selection.read('dvswitch.json',{}))


def enabled():return load()['dmr_transport']=='dvswitch'


def render(station,transport,mb_template,dv_template,radio=None):
    """Preserve upstream required defaults while overriding identity and endpoints.

    Takes copies, never writes original package or saved station configuration.
    Caller creates per-run private files and launches only on explicit Connect.
    """
    from native_dmr.managed_config import validate as validate_station
    c=validate_station(station);t=validate(transport);network=c['networks'][c['selected']]
    mb=configparser.ConfigParser(interpolation=None,strict=False);mb.optionxform=str;mb.read_string(mb_template)
    dv=configparser.ConfigParser(interpolation=None,strict=False);dv.optionxform=str;dv.read_string(dv_template)
    def put(parser,section,**values):
        if not parser.has_section(section):parser.add_section(section)
        for key,value in values.items():
            value=str(value)
            if '\n' in value or '\r' in value or '\x00' in value:raise ValueError('Invalid INI value')
            parser.set(section,key,value)
    for section in ('D-Star','DMR','System Fusion','P25','NXDN','D-Star Network','DMR Network','System Fusion Network','P25 Network','NXDN Network'):
        put(mb,section,Enable=int(section in ('DMR','DMR Network')))
    put(mb,'General',Callsign=c['callsign'],Id=c['peer'],Daemon=0,Timeout=180)
    radio=radio or {}
    try:frequency=round(float(radio.get('frequency',0))*1000000)
    except (TypeError,ValueError,OverflowError):raise ValueError('Invalid radio frequency')
    if not 0<=frequency<=999999999:raise ValueError('Invalid radio frequency')
    put(mb,'Info',RXFrequency=frequency,TXFrequency=frequency,Power=0,Latitude=0,Longitude=0,Height=0,Location='',Description='ALLMODE local software',URL='')
    put(mb,'DMR',Id=c['peer'],ColorCode=c['color'])
    put(mb,'DMR Network',Address=network['host'],Port=network['port'],Password=network['password'],Options='',Slot1=int(c['slot']==1),Slot2=int(c['slot']==2),Local=0)
    put(mb,'Log',DisplayLevel=2,FileLevel=0)
    put(dv,'DMR',address='127.0.0.1',txPort=t['tlv_receive'],rxPort=t['tlv_send'],slot=c['slot'],exportTG=0)
    return mb,dv


def status():
    c=load()
    return {'dmr_transport':c['dmr_transport'],'codec_default':'software',
            'local_only':True,'m17_transport':'native',
            'mmdvm_installed':Path('/opt/MMDVM_Bridge/MMDVM_Bridge').is_file(),
            'note':'DVSwitch DMR TLV is an explicit transport option; other modes retain local native codecs. Voice interoperability requires station acceptance.'}
