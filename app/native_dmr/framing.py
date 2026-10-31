# SPDX-License-Identifier: GPL-3.0-or-later
"""DMR group voice burst framing. No RF modem or socket operations."""
from bitarray import bitarray
from dmr_utils3 import bptc,golay,qr
from homebrew import number
def bits(data):
    out=bitarray(endian='big');out.frombytes(data);return out
VOICE_SYNC=bits(bytes.fromhex('755fd7df75f7'))
DATA_SYNC=bits(bytes.fromhex('dff57d75df5d'))
SILENCE=bytes.fromhex('acaa40200044408080')
def lc(source,target):
    number(source,1,0xffffff);number(target,1,0xffffff)
    return bytes(3)+target.to_bytes(3,'big')+source.to_bytes(3,'big')
def header(link,color=1,terminate=False):
    if len(link)!=9:raise ValueError('Expected nine-byte link control')
    number(color,0,15)
    encoded=(bptc.encode_terminator_lc if terminate else bptc.encode_header_lc)(link)
    slot=bitarray(f'{golay.encode_2087(bytes([(color<<4)|(2 if terminate else 1)])):020b}',endian='big')
    return (encoded[:98]+slot[:10]+DATA_SYNC+slot[10:]+encoded[98:]).tobytes()
def read_header(burst,color=1,terminate=False):
    if len(burst)!=33:raise ValueError('Expected 33-byte voice burst')
    data=bits(burst);link=bptc.decode_full_lc(data[:98]+data[166:]).tobytes()
    # Reject damaged LC, encryption flags, unsupported services, and wrong CC.
    if link[:3]!=bytes(3) or header(link,color,terminate)!=burst:return None
    return int.from_bytes(link[6:9],'big'),int.from_bytes(link[3:6],'big')
def voice(frames,index,link,color=1):
    if len(frames)!=3 or any(len(f)!=9 for f in frames):raise ValueError('Expected three AMBE frames')
    number(index,0,5);number(color,0,15)
    if len(link)!=9:raise ValueError('Expected link control')
    if index==0:middle=VOICE_SYNC
    else:
        lcss={1:1,2:3,3:3,4:2,5:0}[index]
        emb=bits(bytes(qr.encode(bytearray([(color<<4)|(lcss<<1),0]))))
        segment=bptc.encode_emblc(link)[index] if index<5 else bitarray('0'*32)
        middle=emb[:8]+segment+emb[8:]
    data=bits(b''.join(frames))
    return (data[:108]+middle+data[108:]).tobytes()
def frames(burst,index,color=1):
    if len(burst)!=33:raise ValueError('Expected 33-byte voice burst')
    number(index,0,5);number(color,0,15);data=bits(burst)
    if index==0:
        if data[108:156]!=VOICE_SYNC:return None
    else:
        emb=data[108:116]+data[148:156]
        expected=bits(bytes(qr.encode(bytearray([(color<<4)|({1:1,2:3,3:3,4:2,5:0}[index]<<1),0]))))
        if emb!=expected:return None
    data=data[:108]+data[156:]
    return [data[i:i+72].tobytes() for i in (0,72,144)]
