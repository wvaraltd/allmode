"""Load and exercise local codecs without network access or radio commands."""
import ctypes
import os
from pathlib import Path
import sys

base = Path(__file__).resolve().parent
codec = Path(os.environ.get('ALLMODE_VOCODER_ROOT', '/opt/allmode-vocoder-prototype/current'))
sys.path.insert(0, str(codec))
from dstar import Stream

with_stream = Stream()
try:
    encoded = with_stream.encode(bytes(320))
    assert len(encoded) == 9
    decoded = with_stream.decode(encoded)[0]
    assert len(decoded) == 320
finally:
    with_stream.close()
for path in [codec/'ambe2450/build/liballmode_2450.so', base/'native_p25/build/liballmode_p25.so', base/'native_ysf/build/liballmode_ysf.so']:
    ctypes.CDLL(str(path))
ctypes.CDLL('libcodec2.so.1.2')
import bitarray
print('D-STAR encode/decode, AMBE2450, P25, YSF, Codec2 and bitarray loaded.')
