"""Current adjacent ASL link telemetry, not originating-speaker inference."""
import threading,time,unittest
from unittest.mock import Mock,patch
import speaker_status as sp
from server import LiveController
ROW='23456 192.0.2.1 0 IN 00:00:01 ESTABLISHED\n'
LINK={'mode':'AllStar','target':'23456','peer':'23456'}
class AllStarSpeakerTests(unittest.TestCase):
 def parse(self,value='1,23456TK',age=.2,rows=ROW,links=None):
  return sp.linked_audio(rows+'RPT_ALINKS='+value+'\n',links or [LINK],age)
 def test_keyed_unkeyed_mode_and_source_label(self):
  r=self.parse();self.assertTrue(r['known']);self.assertEqual(r['rows'][0]['identity'],'Via node 23456');self.assertIn('originating',r['rows'][0]['reason']);self.assertEqual(r['rows'][0]['expires_in_ms'],1300)
  for token in ('23456TU','23456CU'):
   r=self.parse('1,'+token);self.assertTrue(r['known']);self.assertEqual(r['rows'],[])
 def test_unknown_malformed_stale_and_uncorrelated_fail_closed(self):
  for value in ('','2,23456TK','1,23456TX','1,000000RU','2,23456TK,23456TK','x,23456TK','1,23456TK\nRPT_ALINKS=1,23456TU'):
   self.assertFalse(self.parse(value)['known'])
  self.assertFalse(self.parse(age=1.5)['known']);self.assertFalse(self.parse(age=-1)['known'])
  self.assertFalse(self.parse(links=[dict(mode='AllStar',target='34567')])['rows'])
  self.assertFalse(self.parse(rows='23456 192.0.2.1 0 IN 00:00:01 CONNECTING\n')['rows'])
 def test_multiple_echo_and_disconnect(self):
  echo={'mode':'EchoLink','target':'123456','peer':'3123456'}
  report=self.parse('2,23456TK,3123456RK',rows=ROW+'3123456 192.0.2.2 0 IN 00:00:01 ESTABLISHED\n',links=[LINK,echo])
  self.assertEqual(report['rows'][1]['identity'],'Via EchoLink node 123456')
  result=sp.current([LINK,echo],True,lambda *args:{},requested=[],link_report=report)
  self.assertTrue(result['active']);self.assertIsNone(result['identity']);self.assertIn('Multiple',result['reason'])
  self.assertFalse(sp.current([LINK],False,lambda *args:{},link_report=report)['active'])
  idle=self.parse('1,23456TU');self.assertIsNone(sp.current([LINK],True,lambda *args:{},link_report=idle)['reason'])
 def test_shared_one_hz_cache_and_failure(self):
  c=LiveController('12345',False);c.run_cli=Mock(return_value=ROW+'RPT_ALINKS=1,23456TK\n');c._speaker_context=dict(sampled=100.,connected=True,connections=[LINK],rf_active=False)
  with patch('server.time.monotonic',return_value=100.),patch('digital.load',return_value=[]):
   for _ in range(20):self.assertEqual(c.current_speaker()['identity'],'Via node 23456')
  self.assertEqual(c.run_cli.call_count,1);c.run_cli.assert_called_with('rpt xnode 12345')
  with patch('server.time.monotonic',return_value=101.1),patch('digital.load',return_value=[]):
   c.run_cli.return_value=ROW+'RPT_ALINKS=1,23456TU\n';self.assertFalse(c.current_speaker()['active'])
  self.assertEqual(c.run_cli.call_count,2)
  with patch('server.time.monotonic',return_value=102.2),patch('digital.load',return_value=[]):
   c.run_cli.side_effect=ValueError('CLI unavailable');self.assertFalse(c.current_speaker()['active']);self.assertFalse(c.current_speaker()['active'])
  self.assertEqual(c.run_cli.call_count,3)
 def test_no_background_poll_after_disconnect(self):
  c=LiveController('12345');c.run_cli=Mock(side_effect=AssertionError('No CLI while disconnected'))
  c._speaker_context=dict(sampled=time.monotonic(),connected=False,connections=[],rf_active=False)
  with patch('digital.load',return_value=[]):
   for _ in range(20):self.assertEqual(c.current_speaker()['state'],'disconnected')
  c.run_cli.assert_not_called()
 def test_inflight_coalesces_concurrent_clients(self):
  c=LiveController('12345');entered=threading.Event();release=threading.Event()
  def cli(_):entered.set();release.wait(2);return ROW+'RPT_ALINKS=1,23456TK\n'
  c.run_cli=Mock(side_effect=cli);thread=threading.Thread(target=c.read_xnode);thread.start();self.assertTrue(entered.wait(1))
  try:
   for _ in range(5):
    with self.assertRaises(ValueError):c.read_xnode()
   self.assertEqual(c.run_cli.call_count,1)
  finally:release.set();thread.join(2)
if __name__=='__main__':unittest.main()
