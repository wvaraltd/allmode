# SPDX-License-Identifier: GPL-3.0-or-later
"""AMBE3000 DMR 2450/1150 profile, nine-byte FEC voice payload.

Protocol reference Copyright (C) 2019-2021 Doug McLain, GPL-3.0-or-later.
Rate parameters inspected in nostar/DroidStar serialambe.cpp at
becf1dede57c4a70a865e9cb4cac9247e505599a. Uses existing UDP adapter;
no firmware, binary plugins, fallback codec or reflector client.
"""
from dstar_hardware import HardwareCodec
class Codec:
    def __init__(self,host=None,port=None):
        if host is None:
            import codec_selection
            c=codec_selection.hardware_config();host=c['host'];port=c.get('port',2460)
        self.codec=HardwareCodec(host,port or 2460,profile='DMR')
    def reset_tx(self):self.configure()
    def reset_rx(self):self.configure()
    def configure(self):
        if self.codec.exchange(self.codec.rate_packet,0,.5)!=b'\x0a\x00':raise OSError('External DMR profile reinitialization rejected')
    def encode(self,pcm):return self.codec.encode(pcm,1.0)
    def decode(self,voice):return self.codec.decode(voice,1.0)
    def close(self):self.codec.close()
