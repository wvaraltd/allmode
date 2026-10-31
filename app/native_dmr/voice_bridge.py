# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded DMR voice engine with injected codec and I/O; no sockets here."""
from collections import deque
import secrets
import framing as f
from homebrew import packet,unpack

class VoiceBridge:
    def __init__(self,source,peer,target,codec,send_network,send_audio,clock,slot=2,color=1):
        f.lc(source,target)
        self.source=source;self.peer=peer;self.target=target;self.slot=slot;self.color=color
        self.codec=codec;self.net=send_network;self.audio=send_audio;self.clock=clock
        self.tx=0;self.tx_start=0;self.tx_last=0;self.tx_seq=0;self.tx_index=0;self.partial=[];self.out=deque();self.net_at=0
        self.rx=None;self.rx_seq=None;self.rx_last=0;self.incoming=deque();self.audio_at=0;self.keyed=False;self.ending=False;self.blocked=False
    @property
    def busy(self):return bool(self.tx or self.out or self.rx or self.incoming or self.keyed)
    def queue(self,kind,burst):
        if len(self.out)>=12:raise ValueError('DMR transmit queue overflow')
        self.out.append(packet(self.tx_seq,self.source,self.target,self.peer,self.slot,kind,self.tx,burst));self.tx_seq=(self.tx_seq+1)%256
    def pcm(self,key,data):
        if type(key) is not bool or len(data) not in (0,320):raise ValueError('Invalid PCM frame')
        now=self.clock()
        if not key:
            self.end_tx();self.blocked=False;return
        if self.blocked:return
        if not data:return
        if self.rx or self.incoming or self.keyed:return # half duplex, no recording of playback
        if not self.tx:
            if self.out:return # previous stream still draining
            self.tx=secrets.randbelow(0xffffffff)+1;self.tx_start=now;self.tx_seq=0;self.tx_index=0
            self.codec.reset_tx();self.link=f.lc(self.source,self.target);self.net_at=now
            for _ in range(3):self.queue(0x21,f.header(self.link,self.color))
        self.tx_last=now
        if now-self.tx_start>=180:self.end_tx();self.blocked=True;return
        voice=self.codec.encode(data)
        if len(voice)!=9:raise ValueError('Invalid encoder output')
        self.partial.append(voice)
        if len(self.partial)==3:self.flush()
    def flush(self):
        self.queue(0x10 if self.tx_index==0 else self.tx_index,f.voice(self.partial,self.tx_index,self.link,self.color))
        self.tx_index=(self.tx_index+1)%6;self.partial=[]
    def end_tx(self):
        if self.tx:
            if self.partial:
                self.partial.extend([f.SILENCE]*(3-len(self.partial)));self.flush()
            self.queue(0x22,f.header(self.link,self.color,True));self.tx=0
    def network(self,data):
        item=unpack(data,self.peer,self.slot,self.target)
        if item is None or item['source']==self.source or self.tx or self.out:return
        now=self.clock();kind=item['kind'];identity=(item['source'],item['stream'])
        if kind==0x21:
            if f.read_header(item['burst'],self.color)!=(item['source'],self.target):return
            if self.rx is None:
                if self.incoming or self.keyed:return
                self.rx=identity;self.rx_seq=item['seq'];self.rx_last=now;self.ending=False;self.codec.reset_rx();self.audio_at=now
            elif self.rx==identity:self.rx_seq=item['seq'];self.rx_last=now
            return
        if self.rx!=identity:return
        delta=(item['seq']-self.rx_seq)%256
        if not 1<=delta<=4:return # duplicate, stale, or excessive gap
        if kind==0x22:
            if f.read_header(item['burst'],self.color,True)!=(item['source'],self.target):return
            self.ending=True;self.rx_last=now;return
        frames=f.frames(item['burst'],0 if kind==0x10 else kind,self.color)
        if frames is None:return
        if len(self.incoming)+3*delta>18:self.cancel_rx();return
        for _ in range(delta-1):self.incoming.extend([bytes(320)]*3)
        for voice in frames:
            pcm=self.codec.decode(voice)
            if len(pcm)!=320:raise ValueError('Invalid decoder output')
            self.incoming.append(pcm)
        self.rx_seq=item['seq'];self.rx_last=now
    def cancel_rx(self):
        self.incoming.clear();self.rx=None;self.ending=False
        if self.keyed:self.audio(False,b'');self.keyed=False
    def tick(self):
        now=self.clock()
        if self.tx and now-self.tx_last>.5:self.end_tx();self.blocked=True
        if self.out and now>=self.net_at:
            self.net(self.out.popleft());self.net_at=now+.06 # never burst backlog after a stall
        if self.incoming and now>=self.audio_at:
            self.audio(True,self.incoming.popleft());self.keyed=True;self.audio_at=now+.02
        if self.rx and ((self.ending and not self.incoming) or now-self.rx_last>.6):self.cancel_rx()
    def close(self):
        self.out.clear();self.partial=[];self.tx=0;self.cancel_rx();self.codec.close()
