# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, half-duplex NXDN PCM bridge, with injected codec and I/O."""
from collections import deque
if __package__:from . import protocol as p
else:import protocol as p

class Bridge:
    def __init__(self,source,target,codec,network,audio,clock,ran=1):
        p.header(source,target,ran)
        self.source=source;self.target=target;self.ran=ran;self.codec=codec
        self.network=network;self.audio=audio;self.clock=clock
        self.tx=False;self.tx_last=0;self.tx_start=0;self.index=0;self.partial=[]
        self.out=deque();self.incoming=deque();self.net_at=0;self.audio_at=0
        self.rx=None;self.rx_index=None;self.rx_last=0;self.keyed=False;self.ending=False;self.blocked=False
    @property
    def busy(self):return bool(self.tx or self.out or self.rx or self.incoming or self.keyed)
    def queue(self,data):
        if len(self.out)>=8:raise ValueError('NXDN queue overflow')
        self.out.append(data)
    def pcm(self,key,data):
        if type(key) is not bool or len(data) not in (0,320):raise ValueError('Invalid PCM')
        if not key:self.end_tx();self.blocked=False;return
        if self.blocked or not data or self.rx or self.incoming or self.keyed:return
        now=self.clock()
        if not self.tx:
            if self.out:return
            self.codec.reset_tx();self.tx=True;self.tx_start=now;self.index=0;self.net_at=now
            self.queue(p.header(self.source,self.target,self.ran))
        self.tx_last=now
        if now-self.tx_start>=180:self.end_tx();self.blocked=True;return
        raw=self.codec.encode(data);p.raw49(raw);self.partial.append(raw)
        if len(self.partial)==4:self.flush()
    def flush(self):
        self.queue(p.voice(self.source,self.target,self.partial,self.index,self.ran))
        self.index=(self.index+1)%4;self.partial=[]
    def end_tx(self):
        if not self.tx:return
        if self.partial:
            while len(self.partial)<4:self.partial.append(self.codec.encode(bytes(320)))
            self.flush()
        self.queue(p.header(self.source,self.target,self.ran,True));self.tx=False
    def receive(self,data):
        item=p.parse(data,self.target,self.ran)
        if item is None or item['source']==self.source or self.tx or self.out:return
        now=self.clock()
        if item['kind']=='header':
            if self.rx or self.incoming or self.keyed:return
            self.codec.reset_rx();self.rx=item['source'];self.rx_index=None;self.rx_last=now;self.audio_at=now;self.ending=False
            return
        if item['source']!=self.rx:return
        if item['kind']=='end':self.ending=True;self.rx=None;return
        if self.rx_index is not None and item['index']!=(self.rx_index+1)%4:
            return # duplicates/gaps: wait for next in-sequence packet or bounded timeout
        if len(self.incoming)>16:self.cancel_rx();return
        self.rx_index=item['index'];self.rx_last=now
        for raw in item['frames']:
            pcm=self.codec.decode(raw)
            if len(pcm)!=320:raise ValueError('Invalid decoded PCM')
            self.incoming.append(pcm)
    def cancel_rx(self):
        self.incoming.clear();self.rx=None;self.rx_index=None;self.ending=False
        if self.keyed:self.audio(False,b'');self.keyed=False
    def tick(self):
        now=self.clock()
        if self.tx and now-self.tx_last>=.5:self.end_tx();self.blocked=True
        if self.out and now>=self.net_at:
            self.network(self.out.popleft());self.net_at=now+.08
        if self.rx and now-self.rx_last>=.6:self.cancel_rx()
        if self.incoming and now>=self.audio_at:
            self.audio(True,self.incoming.popleft());self.keyed=True;self.audio_at=now+.02
        elif self.ending and not self.incoming and now>=self.audio_at:self.cancel_rx()
    def close(self):
        self.cancel_rx();self.out.clear();self.partial=[];self.tx=False;self.codec.close()
