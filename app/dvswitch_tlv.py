# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict DVSwitch DMR AMBE72 wire boundary, not an over-air DMR packet.

Reference: n0mjs710/dmr_utils dmr_utils/ambe_bridge.py, AMBE_BASE.
Only the independently documented DMR tags are accepted. No guessed D-Star,
YSF or P25 conversions. All scheduling and half-duplex state is local.
"""
from collections import deque


def begin(source, repeater, target, slot, color):
    for value, low, high in ((source,1,0xffffff),(repeater,1,0xffffffff),
                             (target,1,0xffffff),(slot,1,2),(color,0,15)):
        if type(value) is not int or not low <= value <= high:
            raise ValueError('Invalid DMR TLV metadata')
    return bytes((0,12))+source.to_bytes(3,'big')+repeater.to_bytes(4,'big')+target.to_bytes(3,'big')+bytes((slot,color))


def parse(data):
    if len(data)<2 or data[1]!=len(data)-2:raise ValueError('Invalid TLV length')
    tag,value=data[0],data[2:]
    if tag==0 and 12<=len(value)<=255:
        result=(int.from_bytes(value[:3],'big'),int.from_bytes(value[3:7],'big'),
                int.from_bytes(value[7:10],'big'),value[10],value[11])
        source,repeater,target,slot,flags=result
        if not source or not target or slot not in (1,2) or flags not in (0,0x80):
            raise ValueError('Invalid received DMR metadata')
        if len(value)>12 and (value[-1]!=0 or any(b<32 or b>126 for b in value[12:-1])):
            raise ValueError('Invalid callsign extension')
        return tag,result
    if tag==7 and len(value)==28 and value[0] in (1,2):
        return tag,(value[0],tuple(value[i:i+9] for i in (1,10,19)))
    if tag==2 and len(value)==1 and value[0] in (1,2):return tag,(value[0],)
    raise ValueError('Unsupported DMR TLV record')


class Bridge:
    """Injected codec and I/O; queues bounded to 360 ms; no socket side effects."""
    def __init__(self, source, repeater, target, slot, color, codec, send_tlv, send_audio, clock):
        begin(source,repeater,target,slot,color)
        self.source,self.repeater,self.target,self.slot,self.color=source,repeater,target,slot,color
        self.codec,self.send_tlv,self.send_audio,self.clock=codec,send_tlv,send_audio,clock
        self.tx=False;self.rx=False;self.rx_identity=None;self.keyed=False;self.blocked=False
        self.partial=[];self.out=deque();self.incoming=deque()
        self.tx_at=self.rx_at=self.tx_last=self.rx_last=self.tx_start=self.rx_start=0
        self.ending=False
    @property
    def busy(self):return bool(self.tx or self.rx or self.out or self.incoming or self.keyed)
    def pcm(self,key,pcm):
        if type(key) is not bool or len(pcm) not in (0,320):raise ValueError('Invalid PCM')
        if not key:self.end_tx();self.blocked=False;return
        if self.rx or self.keyed or self.incoming:self.blocked=True;return
        if self.blocked or not pcm:return
        now=self.clock()
        if not self.tx:
            if self.out:return
            self.codec.reset_tx();self.tx=True;self.tx_start=now;self.tx_at=now
            self.send_tlv(begin(self.source,self.repeater,self.target,self.slot,self.color))
        if now-self.tx_start>=180:self.end_tx();self.blocked=True;return
        self.tx_last=now
        voice=self.codec.encode(pcm)
        if len(voice)!=9:raise ValueError('Invalid AMBE72 output')
        self.partial.append(voice)
        if len(self.partial)==3:self.flush()
    def flush(self):
        if len(self.out)>=6:raise ValueError('Transmit queue overflow')
        self.out.append(bytes((7,28,self.slot))+b''.join(self.partial));self.partial=[]
    def end_tx(self):
        if not self.tx:return
        if self.partial:
            # Encode silence with the selected codec; never assume air silence packing.
            while len(self.partial)<3:
                voice=self.codec.encode(bytes(320))
                if len(voice)!=9:raise ValueError('Invalid AMBE72 output')
                self.partial.append(voice)
            self.flush()
        self.out.append(bytes((2,1,self.slot)));self.tx=False
    def network(self,data):
        tag,value=parse(data);now=self.clock()
        if self.tx or self.out:return
        if tag==0:
            source,repeater,target,slot,color=value
            if target!=self.target or slot!=self.slot or color&0x80 or source==self.source:return
            if self.rx or self.incoming or self.keyed:return
            self.codec.reset_rx();self.rx=True;self.rx_identity=source;self.ending=False;self.rx_last=now;self.rx_at=now;self.rx_start=now
        elif self.rx and value[0]==self.slot:
            if tag==2:self.ending=True;self.rx_last=now
            elif tag==7 and not self.ending:
                if len(self.incoming)+3>18:self.cancel_rx();return
                for voice in value[1]:
                    pcm=self.codec.decode(voice)
                    if len(pcm)!=320:raise ValueError('Invalid PCM output')
                    self.incoming.append(pcm)
                self.rx_last=now
    def cancel_rx(self):
        self.incoming.clear();self.rx=False;self.rx_identity=None;self.ending=False
        if self.keyed:
            self.keyed=False;self.send_audio(False,b'')
    def tick(self):
        now=self.clock()
        if self.tx and now-self.tx_last>.5:self.end_tx();self.blocked=True
        if self.out and now>=self.tx_at:
            self.send_tlv(self.out.popleft());self.tx_at=now+.06
        if self.incoming and now>=self.rx_at:
            self.send_audio(True,self.incoming.popleft());self.keyed=True;self.rx_at=now+.02
        if self.rx and ((self.ending and not self.incoming and now>=self.rx_at) or now-self.rx_last>.6 or now-self.rx_start>=180):self.cancel_rx()
    def close(self):
        # Release both sides immediately on shutdown, without replaying buffered voice.
        try:
            if self.tx or self.out:self.send_tlv(bytes((2,1,self.slot)))
        finally:
            self.out.clear();self.partial=[];self.tx=False
            try:self.cancel_rx()
            finally:self.codec.close()
