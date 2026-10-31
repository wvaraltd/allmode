# SPDX-License-Identifier: GPL-3.0-or-later
# Rate/profile protocol reference: DroidStar, Copyright (C) 2019-2021 Doug McLain.
"""AMBE3000 UDP codec for D-STAR. Packet layout follows DroidStar serialambe.cpp."""
import os
import socket
import struct
import time


class HardwareCodec:
    def __init__(self, host, port=2460, profile='DSTAR'):
        if profile not in ('DSTAR','DMR'):raise ValueError('Unsupported external codec profile')
        import fcntl
        self.lock_fd=os.open('/var/lib/asterisk/allmode/ambe-hardware.lock',os.O_CREAT|os.O_RDWR,0o600)
        if os.geteuid()==0:
            import pwd
            a=pwd.getpwnam('allmode');os.fchown(self.lock_fd,a.pw_uid,a.pw_gid)
        try:fcntl.flock(self.lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lock_fd);self.lock_fd=None
            raise OSError('External vocoder is already in use; no software fallback')
        self.profile=profile
        self.rate_packet=bytes.fromhex('61000d000a013007634000000000000048' if profile=='DSTAR' else '61000d000a043107542400000000006f48')
        self.socket=None
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.connect((host, int(port)))
            self.socket.settimeout(.5)
            product = self.exchange(bytes.fromhex('6100010030'), 0, .5)
            if not product.startswith(b'\x30AMBE3000'):
                raise OSError('Unsupported AMBE hardware')
            for packet, command in [('610004003f002f14', 0x3f),
                                    (self.rate_packet.hex(), 0x0a)]:
                reply = self.exchange(bytes.fromhex(packet), 0, .5)
                if reply != bytes([command, 0]):
                    raise OSError('AMBE hardware rejected '+profile+' configuration')
            print(profile+' hardware codec: '+product[1:].rstrip(b'\0').decode('ascii')+
                  ' at '+host+':'+str(port), flush=True)
        except Exception:
            self.close()
            raise

    def exchange(self, packet, kind, timeout=.5):
        self.socket.send(packet)
        deadline = time.monotonic()+timeout
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError('AMBE hardware response timed out')
            self.socket.settimeout(remaining)
            try:data = self.socket.recv(2048)
            except socket.timeout as exc:raise TimeoutError('AMBE hardware timed out waiting for '+{0:'configuration',1:'voice',2:'decoded PCM'}.get(kind,'response')) from exc
            if len(data) < 4 or data[0] != 0x61:
                continue
            length = int.from_bytes(data[1:3], 'big')
            if len(data) != length+4 or data[3] != kind:
                continue
            return data[4:]

    @staticmethod
    def scaled(samples, gain):
        return [max(-32768, min(32767, round(value*gain))) for value in samples]

    def encode(self, data, gain):
        if len(data) != 320:
            raise ValueError('Expected 160 PCM samples')
        pcm = struct.pack('>160h', *self.scaled(struct.unpack('<160h', data), gain))
        reply = self.exchange(bytes.fromhex('610143024000a0')+pcm, 1)
        if len(reply) != 11 or reply[:2] != b'\x01\x48':
            raise OSError('Invalid AMBE hardware voice response')
        return reply[2:]

    def decode(self, voice, gain):
        if len(voice) != 9:
            raise ValueError('Expected nine D-STAR voice bytes')
        reply = self.exchange(bytes.fromhex('61000b010148')+voice, 2)
        if len(reply) != 322 or reply[:2] != b'\x00\xa0':
            raise OSError('Invalid AMBE hardware PCM response')
        return struct.pack('<160h', *self.scaled(struct.unpack('>160h', reply[2:]), gain))

    def close(self):
        if getattr(self,'socket',None) is not None:self.socket.close()
        if getattr(self,'lock_fd',None) is not None:
            os.close(self.lock_fd);self.lock_fd=None
