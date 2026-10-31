# SPDX-License-Identifier: GPL-3.0-or-later
from collections import deque
if __package__:from . import protocol as p
else:import protocol as p
class Bridge:
    def __init__(self,source,target,codec,network,audio,clock,ran=0):
        p.identity(source);p.identity(target)
        self.source=source;self.target=target;self.codec=codec;self.network=network;self.audio=audio;self.clock=clock
        self.tx=False;self.tx_last=0;self.tx_start=0;self.index=0;self.blocked=False
        self.out=deque();self.incoming=deque();self.partial=[];self.rx=None;self.rx_last=0
        self.keyed=False;self.ending=False;self.net_at=0;self.audio_at=0
    @property
    def busy(self):return bool(self.tx or self.out or self.partial or self.rx or self.incoming or self.keyed)
    def queue(self,raw):
        if len(self.out)>=36:raise ValueError('P25 queue overflow')
        self.out.append(p.record(self.index,raw,self.source,self.target));self.index=(self.index+1)%18
    def pcm(self,key,data):
        if type(key) is not bool or len(data) not in (0,320):raise ValueError('Invalid PCM')
        if not key:self.end_tx();self.blocked=False;return
        if self.blocked or not data or self.rx or self.partial or self.incoming or self.keyed:return
        now=self.clock()
        if not self.tx:
            if self.out:return
            self.codec.reset_tx();self.tx=True;self.tx_start=now;self.index=0;self.net_at=now
        self.tx_last=now
        if now-self.tx_start>=180:self.end_tx();self.blocked=True;return
        self.queue(self.codec.encode(data))
    def end_tx(self):
        if not self.tx:return
        # Finish the metadata cycle; padding is bounded to 17 frames/340 ms.
        while self.index:self.queue(p.SILENCE)
        if len(self.out)>=36:raise ValueError('P25 queue overflow')
        self.out.append(p.END);self.tx=False
    def receive(self,data):
        if self.tx or self.out:return
        if not p.valid_record(data):self.cancel_rx();return
        if data==p.END:
            if self.partial:self.cancel_rx()
            else:self.ending=True;self.rx=None
            return
        if data[0]==0x62:self.partial=[]
        if data[0]!=0x62+len(self.partial):self.cancel_rx();return
        self.partial.append(data);self.rx_last=self.clock()
        if len(self.partial)!=18:return
        try:source,frames=p.cycle(self.partial,self.target)
        except ValueError:self.cancel_rx();return
        self.partial=[]
        if source==self.source or (self.rx is not None and source!=self.rx) or len(self.incoming)>18:self.cancel_rx();return
        if self.rx is None:
            if self.keyed or self.incoming:return
            self.codec.reset_rx();self.rx=source;self.audio_at=self.clock();self.ending=False
        for raw in frames:
            pcm=self.codec.decode(raw)
            if len(pcm)!=320:raise ValueError('Invalid decoded PCM')
            self.incoming.append(pcm)
    def cancel_rx(self):
        self.incoming.clear();self.partial=[];self.rx=None;self.ending=False
        if self.keyed:self.audio(False,b'');self.keyed=False
    def tick(self):
        now=self.clock()
        if self.tx and now-self.tx_last>=.5:self.end_tx();self.blocked=True
        if self.out and now>=self.net_at:self.network(self.out.popleft());self.net_at=now+.02
        if (self.rx or self.partial) and now-self.rx_last>=.6:self.cancel_rx()
        if self.incoming and now>=self.audio_at:self.audio(True,self.incoming.popleft());self.keyed=True;self.audio_at=now+.02
        elif self.ending and now>=self.audio_at:self.cancel_rx()
    def close(self):self.cancel_rx();self.out.clear();self.tx=False;self.codec.close()
