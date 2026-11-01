import copy,json,os,socket,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import dvswitch_config as config
from dvswitch_tlv import Bridge,begin,parse
from dvswitch_worker import Worker,HEADER,owned_udp
ROOT=Path(__file__).parent
V=json.loads((ROOT/'dvswitch_reference/dmr-wire-vectors.json').read_text())


def station(source=7654321,call='N0TEST',slot=2):
    return dict(version=1,source=source,peer=source*100+1,callsign=call,color=1,slot=slot,selected='TGIF',networks={
        'BrandMeister':dict(enabled=False),'TGIF':dict(enabled=True,host='127.0.0.1',port=62031,password='test-only',talkgroup=91)})

class Codec:
    def __init__(self):self.closed=False;self.tx=self.rx=0
    def reset_tx(self):self.tx+=1
    def reset_rx(self):self.rx+=1
    def encode(self,pcm):return b'\x55'*9
    def decode(self,voice):return b'\x01\x00'*160
    def close(self):self.closed=True

class TLVTests(unittest.TestCase):
    def setUp(self):
        self.now=0.;self.net=[];self.audio=[];self.codec=Codec()
        self.b=Bridge(7654321,765432101,91,2,1,self.codec,self.net.append,lambda *x:self.audio.append(x),lambda:self.now)
    def rx(self):self.b.network(bytes.fromhex(V['receive_begin_group_no_callsign']))
    def voice(self):self.b.network(bytes.fromhex(V['voice_three_silence_frames']))
    def test_golden_wire_vectors(self):
        self.assertEqual(begin(1234567,123456701,91,2,1).hex(),V['transmit_begin_color1'])
        for key in ('receive_begin_group_no_callsign','receive_begin_group_callsign'):
            self.assertEqual(parse(bytes.fromhex(V[key]))[1],(1234567,0,91,2,0))
        self.assertEqual(parse(bytes.fromhex(V['end'])),(2,(2,)))
        self.assertEqual(parse(bytes.fromhex(V['voice_three_silence_frames']))[1][1],(bytes.fromhex('acaa40200044408080'),)*3)
    def test_reject_malformed(self):
        for data in (b'',b'\x00',b'\x07\x1b'+bytes(28),b'\x07\x1c\x03'+bytes(27),bytes.fromhex(V['receive_begin_group_callsign'])[:-1]+b'X',b'\x01\x00'):
            with self.assertRaises(ValueError):parse(data)
    def test_reject_private_and_wrong_slot_target(self):
        self.b.network(bytes.fromhex(V['receive_begin_private_no_callsign']));self.assertFalse(self.b.rx)
        for offset in (11,12):
            data=bytearray.fromhex(V['receive_begin_group_no_callsign']);data[offset]=1
            self.b.network(data);self.assertFalse(self.b.rx)
    def test_tx_aggregation_and_pacing(self):
        for _ in range(3):self.b.pcm(True,bytes(320))
        self.assertEqual(self.net,[begin(7654321,765432101,91,2,1)])
        self.b.tick();self.assertEqual(self.net[-1],b'\x07\x1c\x02'+b'\x55'*27)
        self.b.pcm(False,b'');self.b.tick();self.assertEqual(len(self.net),2)
        self.now=.061;self.b.tick();self.assertEqual(self.net[-1],b'\x02\x01\x02')
    def test_rx_pacing_and_delayed_unkey(self):
        self.rx();self.voice();self.b.network(bytes.fromhex(V['end']))
        for time in (0,.021,.042):self.now=time;self.b.tick()
        self.assertEqual([key for key,pcm in self.audio],[True]*3)
        self.now=.063;self.b.tick();self.assertEqual(self.audio[-1],(False,b''))
    def test_halfduplex_latch(self):
        self.rx();self.b.pcm(True,bytes(320));self.now=1;self.b.tick()
        self.b.pcm(True,bytes(320));self.assertFalse(self.b.tx)
        self.b.pcm(False,b'');self.b.pcm(True,bytes(320));self.assertTrue(self.b.tx)
    def test_idle_and_maximum_watchdogs(self):
        self.b.pcm(True,bytes(320));self.now=.51;self.b.tick();self.assertFalse(self.b.tx);self.assertTrue(self.b.blocked)
        self.b.close();self.setUp();self.rx();self.voice();self.b.tick()
        self.now=.61;self.b.tick();self.assertFalse(self.b.rx);self.assertEqual(self.audio[-1],(False,b''))
        self.rx();self.now=181;self.b.rx_last=181;self.b.tick();self.assertFalse(self.b.rx)
    def test_queue_overflow_unkeys(self):
        self.rx()
        for _ in range(7):self.voice()
        self.assertFalse(self.b.rx);self.assertFalse(self.b.incoming)
    def test_shutdown_discards_backlog(self):
        self.b.pcm(True,bytes(320));self.b.close()
        self.assertEqual(self.net[-1],b'\x02\x01\x02');self.assertTrue(self.codec.closed);self.assertFalse(self.b.busy)
    def test_two_generic_configs_preserve_inputs(self):
        for c in (station(),station(2345678,'K1TEST',1)):
            original=copy.deepcopy(c)
            mb,dv=config.render(c,{'dmr_transport':'dvswitch'},(ROOT/'dvswitch_reference/MMDVM_Bridge.ini').read_text(),(ROOT/'dvswitch_reference/DVSwitch.ini').read_text())
            self.assertEqual(c,original);self.assertEqual(mb['General']['Callsign'],c['callsign'])
            self.assertEqual(mb['General']['Id'],str(c['peer']));self.assertEqual(dv['DMR']['slot'],str(c['slot']))
            self.assertEqual(dv['DMR']['exportTG'],'0');self.assertEqual(mb['DMR Network']['Address'],'127.0.0.1')
    def test_invalid_ports_and_ini_injection(self):
        for c in ({'tlv_send':31100},{'usrp_send':True},{'tlv_send':0},{'surprise':1},{'usrp_receive':34006},{'tlv_receive':33100},{'usrp_send':32002}):
            with self.assertRaises(ValueError):config.validate(c)
        c=station();c['networks']['TGIF']['password']='x\nEnable=1'
        with self.assertRaises(ValueError):config.render(c,{},'[General]','[DMR]')
    def test_upgrade_default_and_ports_preserved(self):
        self.assertEqual(config.validate({})['dmr_transport'],'native')
        original={'dmr_transport':'dvswitch','tlv_send':45103,'tlv_receive':45100}
        new=config.validate(original);self.assertEqual(new['tlv_send'],45103);self.assertEqual(original['dmr_transport'],'dvswitch')
    def test_udp_socket_ownership(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.bind(('127.0.0.1',0));self.assertTrue(owned_udp(os.getpid(),s.getsockname()))
            self.assertFalse(owned_udp(1,s.getsockname()));self.assertFalse(owned_udp(os.getpid(),('192.0.2.1',s.getsockname()[1])))
    def test_actual_loopback_bidirectional(self):
        sockets=[]
        try:
            for _ in range(4):
                s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('127.0.0.1',0));s.settimeout(1);sockets.append(s)
            a,t,ar,tr=sockets;ports=[s.getsockname()[1] for s in sockets];ar.close();tr.close()
            cfg=dict(usrp_send=ports[0],tlv_send=ports[1],usrp_receive=ports[2],tlv_receive=ports[3],dmr_transport='dvswitch')
            w=Worker(station(),cfg,Codec(),owner=lambda source:owned_udp(os.getpid(),source))
            try:
                for i in range(3):a.sendto(HEADER.pack(b'USRP',i,0,1,0,0,0,0)+bytes(320),('127.0.0.1',ports[2]));w.step(.01)
                self.assertEqual(t.recvfrom(100)[0],begin(7654321,765432101,91,2,1));self.assertEqual(t.recvfrom(100)[0],b'\x07\x1c\x02'+b'\x55'*27)
                w.engine.out.clear();w.engine.partial=[];w.engine.tx=False
                for key in ('receive_begin_group_callsign','voice_three_silence_frames'):
                    t.sendto(bytes.fromhex(V[key]),('127.0.0.1',ports[3]));w.step(.01)
                packet=a.recvfrom(400)[0];self.assertEqual(packet[:4],b'USRP');self.assertEqual(len(packet),352);self.assertEqual(packet[32:],b'\x01\x00'*160)
            finally:w.close()
        finally:
            for s in sockets:s.close()
    def test_hardware_selection_fails_before_open(self):
        import codec_selection
        with patch('dvswitch_config.enabled',return_value=True),patch.object(codec_selection,'hardware_config') as hardware:
            with self.assertRaisesRegex(ValueError,'native DMR'):codec_selection.request('hardware')
            hardware.assert_not_called()
    def test_custom_ports_are_applied_to_asterisk(self):
        import system_service
        from onboarding import GROUPS
        c={g:{k:d for k,_,_,d in rows} for g,rows in GROUPS.items()}
        c['station']['callsign']='K1TEST';c['dmr'].update(id='2345678',dvswitch=True)
        c['tgif'].update(enabled=True,password='test-only')
        templates={name:'[general]\n[node-main](!)\n' for name in system_service.FILES}
        ports=config.validate({'usrp_receive':45001,'usrp_send':45002})
        with patch('dvswitch_config.load',return_value=ports):
            _,files=system_service.render(c,templates)
        self.assertIn('USRP/127.0.0.1:45001:45002',files['rpt.conf'])
    def test_upstream_station_defaults_not_exported(self):
        mb,dv=config.render(station(),{},(ROOT/'dvswitch_reference/MMDVM_Bridge.ini').read_text(),(ROOT/'dvswitch_reference/DVSwitch.ini').read_text())
        self.assertEqual(mb['Info']['Location'],'');self.assertEqual(mb['Info']['Latitude'],'0');self.assertEqual(mb['Info']['RXFrequency'],'0')
    def test_authentication_log_state_survives_quiet_checks(self):
        import dmr_worker
        with tempfile.TemporaryDirectory() as tmp,patch.object(dmr_worker,'RUN',Path(tmp)),patch('dvswitch_config.enabled',return_value=True),patch('dmr_native.status',return_value={}),patch('digital.save'):
            adapter=dmr_worker.Adapter('DMR');(adapter.directory/'analog.log').write_text('Starting USRP')
            log=adapter.directory/'mmdvm.log';log.write_text('DMR, Logged into the master successfully: 127.0.0.1:62031\n')
            self.assertTrue(adapter.check());self.assertTrue(adapter.authenticated)
            self.assertTrue(adapter.check());self.assertTrue(adapter.authenticated)
            with log.open('a') as f:f.write('DMR, Connection to the master has timed out, retrying connection\n')
            adapter.check();self.assertFalse(adapter.authenticated)
    def test_port_conflict_closes_codec(self):
        codec=Codec()
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1',0))
            ports=config.validate({'usrp_receive':sock.getsockname()[1]})
            with self.assertRaises(OSError):Worker(station(),ports,codec)
            self.assertTrue(codec.closed)
    def test_shutdown_send_failure_still_unkeys_and_closes(self):
        self.b.tx=True;self.b.keyed=True
        self.b.send_tlv=lambda _:(_ for _ in ()).throw(OSError('closed'))
        with self.assertRaises(OSError):self.b.close()
        self.assertTrue(self.codec.closed);self.assertEqual(self.audio[-1],(False,b''));self.assertFalse(self.b.busy)
    def test_native_software_codec_boundary(self):
        from native_dmr.native2450 import Codec as RealCodec
        codec=RealCodec(ROOT.parent/'codec/ambe2450')
        try:
            frame=codec.encode(bytes(320));self.assertEqual(len(frame),9)
            self.assertEqual(len(codec.decode(bytes.fromhex('acaa40200044408080'))),320)
            self.assertEqual(len(codec.decode(frame)),320)
        finally:codec.close()

if __name__=='__main__':unittest.main()
