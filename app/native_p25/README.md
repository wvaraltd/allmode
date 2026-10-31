# ALLMODE P25 Phase 1 native component

Software-only, clear standard group voice, G4KLX/DroidStar reflector record protocol.
Not Phase 2, encrypted/private voice, external hardware, a trunking controller, or an RF modem.
Installed capability is distinct from configured, connected and interoperability verified.

`raw_codec.Codec` owns separate transmit/receive IMBE states. Each 20 ms frame is
160 signed little-endian 16-bit PCM samples at 8 kHz and 11 raw IMBE bytes (88 bits).
Those bytes alone are not a P25 RF frame. The C ABI validates lengths and returns
zero PCM for reserved pitch values without advancing decoder state. A codec-wide
mutex swaps upstream random seed and arithmetic flags per context. No silent
hardware/software fallback. Reset creates a fresh independently initialized state.

`protocol.py` emits records 0x62 through 0x73, one voice frame per datagram, then
0x80 termination. Source and target IDs are 24-bit. Templates and offsets follow
the pinned source references in PROVENANCE.json. Clear algorithm 0x80 follows
DroidStar; the old G4 announcement template's zero algorithm is rejected. This
is a restricted clear-only implementation. Upstream record parity placeholders
are retained for this reflector interface; this is not a standards-complete RF
FEC generator. No external reflector interoperability is claimed.

RX requires a complete ordered 18-record cycle, adding approximately 360 ms startup
latency, to validate source, target, group opcode, message indicator and clear
algorithm/key ID before releasing any PCM. Gaps, incomplete cycles, non-clear
metadata and wrong targets fail closed. Late entry is unsupported. TX pads up to
17 silence frames on release to complete metadata, then sends termination.
Queues are bounded; half duplex, 180-second TX limit, 0.5-second TX input timeout,
0.6-second RX timeout and cleanup unkey are enforced. The UDP peer requires the
exact configured endpoint and a matching poll response; this is liveness, **not
authentication**. There is no automatic retry or public connection during setup.

The worker uses loopback USRP ports 34003/32003 and control 34100, private node
1997. Backend changes wait for an idle stream boundary; hardware selection stops
software with an explicit unsupported error. Managed Apply renders configuration
and private audio node, initially leaving all digital workers disconnected.
User P25 source ID, talkgroup and reflector host are required and never inferred
from a different mode. Existing channel, identities, credentials and pending
settings are preserved by the installer. Apply remains a separate user action.

Sources: Pavel Yazev's GPL-3.0-or-later fixed-point IMBE implementation in pinned
DroidStar; G4KLX P25Clients protocol reference GPL-2.0-or-later. Original notices
(including arithmetic routines' historical AMR/ETSI notices) are retained.
GPLv3 text is supplied for the combined derivative. No TETRA, optional OP25 patch,
firmware or proprietary binary codec is included. This is not patent clearance.

Build on Linux with existing Python3 and g++: `python3 build.py`.
Tests: `python3 -m unittest -v test_codec test_p25 test_integration`.
Memory check with compiler's existing runtime: `python3 check_native.py`.
Integration tests use temporary configurations and injected workers; UDP tests
use loopback only. Source-derived protocol vectors are not captured radio vectors.
Physical audio quality, real reflector interoperability and digital RF remain untested.
