# SPDX-License-Identifier: GPL-3.0-or-later
"""NXDN reflector group voice, 43-byte packets; NOT an RF modem.

Wire layout derived from G4KLX NXDNClients (GPL-2.0-or-later), and
DroidStar nxdn.cpp, Copyright (C) 2019-2021 Doug McLain (GPL-3.0-or-later).
Only non-encrypted, non-stolen, narrow voice is supported. No late entry.
"""
import re
import time


def identity(value):
    if type(value) is not int or not 1 <= value <= 65535:
        raise ValueError('NXDN identity must be 1..65535')
    return value.to_bytes(2, 'big')


def poll(callsign, target, unlink=False):
    if not isinstance(callsign, str) or not re.fullmatch(r'[A-Z0-9/-]{1,10}', callsign):
        raise ValueError('Invalid NXDN callsign')
    return (b'NXDNU' if unlink else b'NXDNP') + callsign.ljust(10).encode('ascii') + identity(target)


def crc6(value):
    crc = 63
    for i in range(25, -1, -1):
        feedback = ((value >> i) & 1) ^ ((crc >> 5) & 1)
        crc = ((crc << 1) ^ (0x27 if feedback else 0)) & 63
    return crc


def sacch(ran, structure, message):
    if type(ran) is not int or not 0 <= ran <= 63:
        raise ValueError('Invalid RAN')
    value = ((structure << 6 | ran) << 18) | message
    return ((value << 6) | crc6(value)).to_bytes(4, 'big')


def layer3(source, target, end=False):
    return bytes([8 if end else 1, 0, 0x20]) + identity(source) + identity(target) + bytes(7)


def protected_layer3(source, target, end=False):
    link = layer3(source, target, end)[:10]
    crc = 0xfff
    for byte in link:
        for i in range(7, -1, -1):
            feedback = ((byte >> i) & 1) ^ ((crc >> 11) & 1)
            crc = ((crc << 1) ^ (0x80f if feedback else 0)) & 0xfff
    return link + (crc << 4).to_bytes(2, 'big') + bytes(2)


def header(source, target, ran=1, end=False):
    link = protected_layer3(source, target, end)
    return b'NXDND' + identity(source) + identity(target) + bytes([9 if end else 5, 0x81]) + sacch(ran, 0, 0x4000) + link * 2


def raw49(frame):
    if not isinstance(frame, bytes) or len(frame) != 7 or frame[6] & 127:
        raise ValueError('Expected 49 bits, MSB-first in seven bytes with zero padding')
    return int.from_bytes(frame, 'big') >> 7


def pair(a, b):
    return ((raw49(a) << 63) | (raw49(b) << 14)).to_bytes(14, 'big')


def unpair(data):
    value = int.from_bytes(data, 'big')
    return tuple((((value >> shift) & ((1 << 49)-1)) << 7).to_bytes(7, 'big') for shift in (63, 14))


def voice(source, target, frames, index, ran=1):
    if len(frames) != 4 or type(index) is not int or not 0 <= index <= 3:
        raise ValueError('Expected four voice frames and SACCH index 0..3')
    link = int.from_bytes(layer3(source, target), 'big')
    segment = (link >> (112 - 18*(index+1))) & 0x3ffff
    return b'NXDND' + identity(source) + identity(target) + b'\x01\xac' + sacch(ran, 3-index, segment) + pair(*frames[:2]) + pair(*frames[2:])


def parse(data, target, ran=1):
    if not isinstance(data, bytes) or len(data) != 43 or data[:5] != b'NXDND':
        return None
    source = int.from_bytes(data[5:7], 'big')
    if not source or data[7:9] != identity(target):
        return None
    s = int.from_bytes(data[11:15], 'big')
    if (s >> 24) & 63 != ran or crc6(s >> 6) != (s & 63):
        return None
    if data[9] in (5, 9) and data[10] in (0x81, 0x83):
        end = data[9] == 9
        if data[15:] != protected_layer3(source, target, end)*2:
            return None  # encrypted/private/noncanonical or mismatched link control
        return dict(kind='end' if end else 'header', source=source)
    if data[9] != 1 or data[10] not in (0xac, 0xae):
        return None
    # The last 14 bits of each block are not voice. Some DroidStar versions
    # duplicate the final voice bit into this padding; ignore it on receive.
    # Transmit always zeroes it. LICH above rejects stolen/data/full-rate frames.
    index = 3-(s >> 30)
    segment = (int.from_bytes(layer3(source, target), 'big') >> (112-18*(index+1))) & 0x3ffff
    if ((s >> 6) & 0x3ffff) != segment:
        return None
    return dict(kind='voice', source=source, index=index, frames=unpair(data[15:29])+unpair(data[29:43]))


class Peer:
    """Explicit start; endpoint-filtered poll/voice/unlink and bounded liveness.

    NXDN polling has no cryptographic authentication. Connected means a valid
    response from the configured endpoint, never authenticated identity.
    """
    def __init__(self, endpoint, callsign, target, send, clock=time.monotonic):
        self.endpoint = endpoint
        self.request = poll(callsign, target)
        self.unlink = poll(callsign, target, True)
        self.target = target
        self.send = send
        self.clock = clock
        self.state = 'stopped'
        self.last = self.next = 0

    def start(self):
        if self.state != 'stopped':
            raise ValueError('Create a fresh peer for a new connection')
        self.state = 'connecting'
        self.last = self.clock()
        self.next = self.last + 1
        self.send(self.request, self.endpoint)

    def receive(self, data, endpoint):
        if endpoint != self.endpoint or self.state not in ('connecting', 'connected'):
            return None
        if data == self.request:
            self.state = 'connected'
            self.last = self.clock()
        elif self.state == 'connected' and len(data) == 43 and data[:5] == b'NXDND':
            return data
        return None

    def tick(self):
        if self.state not in ('connecting', 'connected'):
            return
        now = self.clock()
        if now - self.last >= 5:
            self.state = 'failed'
        elif now >= self.next:
            self.send(self.request, self.endpoint)
            self.next = now + 1

    def voice(self, data):
        if self.state != 'connected' or len(data) != 43 or data[:5] != b'NXDND':
            raise ValueError('NXDN peer unavailable or invalid voice packet')
        self.send(data, self.endpoint)

    def close(self):
        if self.state in ('connecting', 'connected'):
            self.send(self.unlink, self.endpoint)
        self.state = 'stopped'
