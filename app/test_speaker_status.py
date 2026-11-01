"""Current-talker tests: no RF, public peers or fabricated directory identity."""
import importlib,json,socket,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import speaker_status as speaker

class Codec:
    def reset_rx(self):pass
    def reset_tx(self):pass
    def decode(self,*args):return bytes(320)
    def encode(self,*args):return bytes(9)
    def close(self):pass

class SpeakerStatusTests(unittest.TestCase):
    def setUp(self):
        self.now=100.;self.reports={};self.connection={'mode':'DMR','target':'91'}
    def read(self,name,default):return self.reports.get(name,default)
    def report(self,mode='DMR',target=91,name='DMR ID 1234567'):
        self.reports[speaker.REPORTS[mode][0]]=dict(pid=42,updated=99.8,target=target,speaker=dict(active=True,identity=name))
    def current(self,**kw):
        args=dict(connections=[self.connection],connected=True,read=self.read,now=self.now,alive=lambda *_:True,requested=[self.connection['mode']]);args.update(kw)
        return speaker.current(**args)
    def test_all_modes_fresh_report_identity_and_ttl(self):
        for mode,target,name in [('DMR',91,'DMR ID 1234567'),('NXDN',123,'NXDN ID 321'),('P25',123,'P25 ID 1234567'),('YSF',123,'W1TEST'),('M17','M17-ABC A','W1TEST'),('D-STAR','REF001C','W1TEST B')]:
            self.connection=dict(mode=mode,target=str(target).zfill(5) if mode=='YSF' else str(target));self.report(mode,target,name)
            result=self.current();self.assertTrue(result['active']);self.assertEqual(result['identity'],name);self.assertTrue(1298<=result['expires_in_ms']<=1300)
    def test_expiry_future_dead_process_target_change_and_disconnect(self):
        self.report()
        for extra in ({'now':102},{'now':99},{'alive':lambda *_:False},{'requested':[]},{'connected':False},{'connections':[dict(mode='DMR',target='92')]}):
            result=self.current(**extra);self.assertFalse(result['active']);self.assertIsNone(result['identity'])
        self.assertEqual(self.current(connected=False)['state'],'disconnected')
    def test_header_or_idle_status_never_becomes_active(self):
        self.report();self.reports['dmr-native-status.json']['speaker']['active']=False
        result=self.current();self.assertEqual(result['state'],'listening');self.assertIsNone(result['identity'])
    def test_no_directory_or_lastheard_inference(self):
        for mode in ('AllStar','EchoLink','FCS'):
            self.connection=dict(mode=mode,target='12345',callsign='W1DIRECTORY',lastheard='W2OLD')
            self.assertEqual(self.current()['state'],'listening');self.assertIsNone(self.current()['identity'])
            if mode in ('AllStar','EchoLink'):self.assertEqual(self.current()['reason'],'Live speaker telemetry unavailable for this network')
    def test_active_unknown_and_multiple_sources(self):
        self.report(name=None);r=self.current();self.assertTrue(r['active']);self.assertIsNone(r['identity']);self.assertIn('unavailable',r['reason'])
        self.report('M17','M17-ABC A','W1TEST');r=self.current(connections=[self.connection,dict(mode='M17',target='M17-ABC A')],requested=['DMR','M17'])
        self.assertTrue(r['active']);self.assertIsNone(r['identity']);self.assertIn('Multiple',r['reason'])
    def test_rf_evidence_does_not_refresh_itself(self):
        r=self.current(rf_active=True,rf_age=.2);self.assertTrue(r['active']);self.assertIsNone(r['identity']);self.assertEqual(r['mode'],'RF')
        self.assertFalse(self.current(rf_active=True,rf_age=2)['active'])
    def test_dvswitch_uses_selected_report_not_native_lastheard(self):
        self.report();self.reports['dvswitch.json']={'dmr_transport':'dvswitch'}
        self.assertFalse(self.current()['active'])
        self.reports['dvswitch-worker-status.json']=dict(self.reports['dmr-native-status.json'])
        seen=[];r=self.current(alive=lambda pid,path:seen.append(path) or True)
        self.assertTrue(r['active']);self.assertEqual(seen,['dvswitch_worker.py'])
    def test_malformed_report_fails_closed(self):
        for report in ([],{'updated':'100'},dict(updated=float('nan')),dict(updated=100,pid=42,target=91,speaker='x')):
            self.reports['dmr-native-status.json']=report;self.assertFalse(self.current()['active'])
        self.report(name='<script>bad</script>');self.assertTrue(self.current()['active']);self.assertIsNone(self.current()['identity'])
    def test_identity_requires_actual_keyed_playout(self):
        for mode,value,expected in [('DMR',(1234567,42),'DMR ID 1234567'),('NXDN',123,'NXDN ID 123'),('P25',1234567,'P25 ID 1234567'),('YSF','W1TEST','W1TEST'),('M17','W1TEST','W1TEST'),('D-STAR',b'W1TEST B','W1TEST B')]:
            engine=SimpleNamespace(keyed=False,rx_key=False,rx_identity=value)
            if mode=='DMR':del engine.rx_identity;engine.rx=value
            self.assertFalse(speaker.playout(engine,mode)['active'])
            engine.keyed=True;engine.rx_key=True
            self.assertEqual(speaker.playout(engine,mode)['identity'],expected)
            self.assertIsNone(speaker.playout(engine,mode,False)['identity'])
    def test_cached_endpoint_does_not_call_asterisk(self):
        from server import LiveController
        c=LiveController('12345',False);c.run_cli=Mock(side_effect=AssertionError('No rpt query allowed'))
        c._speaker_context=dict(sampled=time.monotonic(),connected=True,connections=[self.connection],rf_active=False)
        self.report();self.reports['dmr-native-status.json']['updated']=time.time();self.reports['digital-modes.json']=['DMR']
        with patch('digital.load',side_effect=self.read),patch('speaker_status.live_process',return_value=True):
            # Default callback is intentionally captured: inject PID check via proc read.
            with patch.object(speaker.Path,'read_text',return_value='python native_dmr/worker.py'):
                self.assertTrue(c.current_speaker()['active'])
            self.reports['digital-modes.json']=[];self.assertFalse(c.current_speaker()['active'])
        c.run_cli.assert_not_called()
    def test_digital_bridge_metadata_clears_after_unkey(self):
        now=[0.]
        for mode,source,target,other in [('NXDN',123,91,321),('P25',1234567,91,7654321),('M17','N0CALL','M17-ABC A','W1TEST'),('YSF','N0CALL',123,'W1TEST')]:
            mod=importlib.import_module('native_'+mode.lower()+'.bridge');p=mod.p
            b=mod.Bridge(source,target,Codec(),lambda _:None,lambda *_:None,lambda:now[0])
            try:
                if mode in ('NXDN','YSF'):
                    b.receive(p.header(other,target));self.assertFalse(speaker.playout(b,mode)['active'])
                    b.receive(p.voice(other,target,[bytes(7)]*(4 if mode=='NXDN' else 5),0 if mode=='NXDN' else 1))
                elif mode=='P25':
                    for i in range(18):b.receive(p.record(i,p.SILENCE,other,target))
                else:b.receive(p.packet(other,target,42,0,bytes(16)))
                b.tick();self.assertTrue(speaker.playout(b,mode)['active']);self.assertEqual(speaker.playout(b,mode)['identity'],speaker.identity(mode,other))
                b.cancel_rx();self.assertIsNone(b.rx_identity);self.assertFalse(speaker.playout(b,mode)['active'])
            finally:b.close()
    def test_dvswitch_begin_metadata_only_becomes_active_after_pcm(self):
        from dvswitch_tlv import Bridge,begin
        b=Bridge(7654321,765432101,91,2,1,Codec(),lambda _:None,lambda *_:None,lambda:0.)
        try:
            packet=bytearray(begin(1234567,123456701,91,2,1));packet[-1]=0
            b.network(packet);self.assertFalse(speaker.playout(b,'DMR')['active'])
            b.network(bytes((7,28,2))+bytes(27));b.tick()
            self.assertEqual(speaker.playout(b,'DMR')['identity'],'DMR ID 1234567')
            b.cancel_rx();self.assertFalse(speaker.playout(b,'DMR')['active']);self.assertIsNone(b.rx_identity)
        finally:b.close()
    def test_dstar_dcs_and_ref_use_only_accepted_stream_identity(self):
        import digital
        from dstar_worker import Bridge,voice_packet
        from dstar_ref import header,frame
        with tempfile.TemporaryDirectory() as directory,patch.object(digital,'RUN',Path(directory)):
            peer=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);peer.bind(('127.0.0.1',0))
            sink=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sink.bind(('127.0.0.1',0))
            b=Bridge('N0CAL',dict(tx=sink.getsockname()[1],rx=0,remote=0,tlv=0),Codec())
            try:
                for target in ('DCS001C','REF001C'):
                    b.target=target;b.endpoint=peer.getsockname();b.confirmed=True;b.next_ping=100;b.last_network=1
                    if target.startswith('DCS'):b.on_network(voice_packet('W1TEST',target,42,0,bytes(9)),peer.getsockname(),1)
                    else:
                        b.on_network(header('W1TEST','B',target,42),peer.getsockname(),1)
                        b.on_network(frame(42,0,bytes(9)),peer.getsockname(),1)
                    self.assertFalse(speaker.playout(b,'D-STAR')['active'])
                    b.tick(1.07);self.assertTrue(speaker.playout(b,'D-STAR')['active']);self.assertTrue(speaker.playout(b,'D-STAR')['identity'].startswith('W1TEST'))
                    b.unlink();self.assertIsNone(b.rx_identity);self.assertFalse(speaker.playout(b,'D-STAR')['active'])
            finally:b.close();peer.close();sink.close()

if __name__=='__main__':unittest.main()
