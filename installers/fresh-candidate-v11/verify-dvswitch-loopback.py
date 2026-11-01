#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline loopback integration test; never contacts a public master or RF device.
Requires architecture-native official MMDVM_Bridge, compiled local AMBE2450
library in SOURCE/codec/ambe2450/build, and Python bitarray. Installs nothing.
Run with a NEW --output directory; all generated files stay there.
"""
import sys,pathlib,socket,subprocess,os,time,hashlib,json,struct,argparse
args_parser=argparse.ArgumentParser(description=__doc__)
args_parser.add_argument('--source',type=pathlib.Path,required=True)
args_parser.add_argument('--binary',type=pathlib.Path,required=True)
args_parser.add_argument('--output',type=pathlib.Path,required=True)
args=args_parser.parse_args()
R=args.source.resolve(); binary=args.binary.resolve(); P=args.output.resolve()
if not binary.is_file() or not os.access(binary,os.X_OK):args_parser.error('--binary must be an executable architecture-native MMDVM_Bridge')
if not (R/'app/dvswitch_reference/MMDVM_Bridge.ini').is_file():args_parser.error('--source must contain ALLMODE DVSwitch reference templates')
P.mkdir(mode=0o700,parents=True,exist_ok=False)
T=R/'app/dvswitch_reference'

sys.path[:0]=[str(R/'app'),str(R/'app/native_dmr')]
from dvswitch_config import render
from dvswitch_worker import Worker,owned_udp,HEADER
from native_dmr.native2450 import Codec
from native_dmr import homebrew
import framing

import digital
reserved_ports={v for mode,profile in digital.PROFILES.items() if mode!='DMR' for key,v in profile.items() if key in ('rx','tx','tlv','mb','remote','codec')}
issued_ports=set()
def port():
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close()
 if p in issued_ports or p in reserved_ports:return port()
 issued_ports.add(p);return p
results=[]
for cycle in range(2):
 master=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);master.bind(('127.0.0.1',0));master.setblocking(False)
 t=dict(version=1,dmr_transport='dvswitch',tlv_receive=port(),tlv_send=port(),usrp_receive=port(),usrp_send=port())
 c=dict(version=1,source=1234567,peer=123456701,callsign='N0CALL',color=1,slot=2,selected='BrandMeister',networks={'BrandMeister':dict(enabled=True,host='127.0.0.1',port=master.getsockname()[1],password='loopback-only',talkgroup=91),'TGIF':dict(enabled=False)})
 mb,dv=render(c,t,(T/'MMDVM_Bridge.ini').read_text(),(T/'DVSwitch.ini').read_text())
 # No outside hostname, files or external mode: all networks except mock DMR disabled by render.
 mb.set('DMR Id Lookup','File',str(P/'empty-ids')); mb.set('NXDN Id Lookup','File',str(P/'empty-ids'))
 (P/'empty-ids').write_text('')
 for name,obj in [('mock-MMDVM.ini',mb),('mock-DVSwitch.ini',dv)]:
  with (P/name).open('w') as f:obj.write(f,space_around_delimiters=False)
  (P/name).chmod(0o600)
 log=(P/f'loopback-{cycle}.log').open('w');proc=subprocess.Popen([str(binary),str(P/'mock-MMDVM.ini')],cwd=P,env=dict(os.environ,DVSWITCH=str(P/'mock-DVSwitch.ini')),stdout=log,stderr=subprocess.STDOUT)
 worker=None;audio=None;record=dict(cycle=cycle,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),source=str(R),scope='loopback-only; no RF; architecture '+os.uname().machine)
 try:
  worker=Worker(c,t,Codec(R/'codec/ambe2450'),owner=lambda s:owned_udp(proc.pid,s))
  seen=[];out=[];audio_packets=[];sent_tlv=[];peer=None;auth=False;connected=False
  real_send=worker.engine.send_tlv
  def record_send(data):sent_tlv.append(data);return real_send(data)
  worker.engine.send_tlv=record_send
  original=worker.engine.network
  def tap(data):seen.append(data);return original(data)
  worker.engine.network=tap
  audio=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);audio.bind(('127.0.0.1',t['usrp_send']));audio.setblocking(False)
  def pump(duration):
   global peer,auth,connected
   end=time.monotonic()+duration
   while time.monotonic()<end:
    if proc.poll() is not None:raise RuntimeError('MB exited '+str(proc.returncode))
    worker.step(.001)
    while True:
     try:d,a=master.recvfrom(2048)
     except BlockingIOError:break
     if d.startswith(b'RPTL'):peer=a;master.sendto(b'RPTACK'+b'\x01\x02\x03\x04',a)
     elif d.startswith(b'RPTK'):
      assert d[8:]==hashlib.sha256(b'\x01\x02\x03\x04loopback-only').digest();auth=True;master.sendto(b'RPTACK'+d[4:8],a)
     elif d.startswith(b'RPTC'):connected=True;master.sendto(b'RPTACK'+d[4:8],a)
     elif d.startswith(b'RPTO'):master.sendto(b'RPTACK'+d[4:8],a)
     elif d.startswith(b'RPTPING'):master.sendto(b'MSTPONG'+d[7:11],a)
     elif d.startswith(b'DMRD'):out.append(d)
    while True:
     try:d,a=audio.recvfrom(2048);audio_packets.append(d)
     except BlockingIOError:break
  pump(12);assert auth and connected,(auth,connected)
  for i in range(18):
   audio.sendto(HEADER.pack(b'USRP',i,0,1,0,0,0,0)+bytes(320),('127.0.0.1',t['usrp_receive']));pump(.02)
  audio.sendto(HEADER.pack(b'USRP',18,0,0,0,0,0,0),('127.0.0.1',t['usrp_receive']));pump(1)
  assert any((d[15]&0x3f)==0x21 for d in out),'No TX header'
  assert any((d[15]&0x3f)==0x22 for d in out),'No TX end'
  encoded=[d[3:] for d in sent_tlv if d[0]==7]
  recovered=[]
  for d in out:
   if (d[15]&0x3f) in (0x10,1,2,3,4,5):
    b=framing.bits(d[20:53]);recovered.append((b[:108]+b[156:]).tobytes())
  assert encoded==recovered,('TX AMBE72 mismatch',len(encoded),len(recovered))
  link=framing.lc(7654321,91);seq=0
  for _ in range(3):master.sendto(homebrew.packet(seq,7654321,91,c['peer'],2,0x21,456,framing.header(link)),peer);seq+=1;pump(.06)
  for i in range(12):master.sendto(homebrew.packet(seq,7654321,91,c['peer'],2,0x10 if i%6==0 else i%6,456,framing.voice([framing.SILENCE]*3,i%6,link)),peer);seq+=1;pump(.06)
  master.sendto(homebrew.packet(seq,7654321,91,c['peer'],2,0x22,456,framing.header(link,terminate=True)),peer);pump(2)
  assert any(d[0]==0 for d in seen),'No RX begin'
  assert any(d[:3]==bytes([7,28,2]) for d in seen),'No RX voice'
  assert any(d==bytes([2,1,2]) for d in seen),'No RX end'
  assert any(len(d)==352 and HEADER.unpack(d[:32])[3]==1 for d in audio_packets),'No RX PCM'
  assert any(len(d)==32 and HEADER.unpack(d[:32])[3]==0 for d in audio_packets),'No RX unkey'
  assert all(d[3:]==framing.SILENCE*3 for d in seen if d[0]==7),'RX AMBE payload mismatch'
  record.update(pass_=True,authenticated=auth,tx_network_packets=len(out),rx_tlv_packets=len(seen),rx_pcm_packets=sum(len(d)==352 for d in audio_packets),rx_begin=[d.hex() for d in seen if d[0]==0],rx_voice_golden=True,tx_voice_matches_codec=True,owned_exporter=True)
 except Exception as e:record.update(pass_=False,error=repr(e));raise
 finally:
  if worker:worker.close()
  if audio:audio.close()
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
  master.close();log.close();record['child_exit']=proc.returncode;results.append(record);(P/'loopback-results.json').write_text(json.dumps(results,indent=2)+'\n');print(record,flush=True)
