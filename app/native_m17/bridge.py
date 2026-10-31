# SPDX-License-Identifier: GPL-3.0-or-later
from collections import deque
import secrets
if __package__:from . import protocol as p
else:import protocol as p
class Bridge:
    def __init__(self,source,target,codec,network,audio,clock,ran=0):
        p.lsf(source,target,ran);self.source=source;self.target=target;self.can=ran;self.codec=codec;self.network=network;self.audio=audio;self.clock=clock
        self.tx=False;self.tx_last=0;self.tx_start=0;self.index=0;self.stream=0;self.blocked=False;self.partial=[]
        self.out=deque();self.incoming=deque();self.rx=None;self.rx_last=0;self.rx_index=None;self.rx_lsf=None
        self.keyed=False;self.ending=False;self.net_at=0;self.audio_at=0
    @property
    def busy(self):return bool(self.tx or self.out or self.rx or self.incoming or self.keyed)
    def flush(self,end=False):
        if len(self.out)>=12:raise ValueError('M17 queue overflow')
        while len(self.partial)<2:self.partial.append(self.codec.encode(bytes(320)))
        self.out.append(p.packet(self.source,self.target,self.stream,self.index,b''.join(self.partial),self.can,end));self.partial=[];self.index=(self.index+1)&32767
    def pcm(self,key,data):
        if type(key) is not bool or len(data) not in (0,320):raise ValueError('Invalid PCM')
        if not key:self.end_tx();self.blocked=False;return
        if self.blocked or not data or self.rx or self.incoming or self.keyed:return
        now=self.clock()
        if not self.tx:
            if self.out:return
            self.codec.reset_tx();self.tx=True;self.tx_start=now;self.index=0;self.stream=secrets.randbelow(65535)+1;self.net_at=now
        self.tx_last=now
        if now-self.tx_start>=180:self.end_tx();self.blocked=True;return
        self.partial.append(self.codec.encode(data))
        if len(self.partial)==2:self.flush()
    def end_tx(self):
        if not self.tx:return
        self.flush(True);self.tx=False
    def receive(self,data):
        if self.tx or self.out:return
        item=p.parse(data,self.target,self.can)
        if item is None or item['source']==self.source:return
        identity=(item['source'],item['stream'])
        if self.rx is None:
            if item['sequence']!=0 or self.keyed or self.incoming:return
            self.codec.reset_rx();self.rx=identity;self.rx_index=-1;self.rx_lsf=item['lsf'];self.audio_at=self.clock();self.ending=False
        if identity!=self.rx or item['lsf']!=self.rx_lsf:return
        if item['sequence']!=((self.rx_index+1)&32767):return
        if len(self.incoming)>20:self.cancel_rx();return
        self.rx_index=item['sequence'];self.rx_last=self.clock()
        for i in (0,8):self.incoming.append(self.codec.decode(item['payload'][i:i+8]))
        if item['end']:self.ending=True;self.rx=None
    def cancel_rx(self):
        self.incoming.clear();self.rx=None;self.rx_index=None;self.rx_lsf=None;self.ending=False
        if self.keyed:self.audio(False,b'');self.keyed=False
    def tick(self):
        now=self.clock()
        if self.tx and now-self.tx_last>=.5:self.end_tx();self.blocked=True
        if self.out and now>=self.net_at:self.network(self.out.popleft());self.net_at=now+.04
        if self.rx and now-self.rx_last>=.6:self.cancel_rx()
        if self.incoming and now>=self.audio_at:self.audio(True,self.incoming.popleft());self.keyed=True;self.audio_at=now+.02
        elif self.ending and now>=self.audio_at:self.cancel_rx()
    def close(self):self.cancel_rx();self.out.clear();self.partial=[];self.tx=False;self.codec.close()
