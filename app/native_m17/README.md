# ALLMODE M17 Codec2 3200

Implemented profile: clear 3200-bit/s voice using the existing official Debian
`libcodec2-1.2:arm64` 1.2.0-3. No AMBE path, 1600 voice/data, packet mode,
encryption, stream signatures or external hardware profile. No RF modem is included.

Each Codec2 frame consumes 160 S16LE samples at 8 kHz and produces 8 bytes.
Two frames form the 16-byte/40-ms M17 stream payload. The native 1.2.0 library has
a process-global decoder RNG; each TX and RX stream therefore uses a separate
bounded helper process with fixed-size binary pipe messages, a 2-second response
deadline and explicit cleanup. Reset replaces the helper, including RNG state.
No system library was modified or installed. The installed shared library remains
replaceable and is not bundled. LGPL/component copyright notices are retained.

The 54-byte UDP stream contains magic, stream ID, destination/source addresses,
TYPE/META, sequence/end bit, 16-byte payload and CRC. Callsigns use base40 and
are limited to ordinary 1..9-character uppercase addresses. Configured reflector
targets have the explicit form `M17-ABC A`; no endpoint is guessed or downloaded.
CAN is 0..15. TYPE is 5 plus CAN, META is zero. Receiver accepts configured
destination or broadcast, rejects reserved source addresses, wrong target/CAN,
unsupported TYPE/META and malformed lengths/CRC. It requires sequence zero to
start; duplicates/gaps and identity changes cannot join an active stream.

CRC uses polynomial 0x5935, initial 0xffff. LSF CRC covers 28 LSF bytes; the IP
stream CRC covers the 46 bytes from destination through payload, matching pinned
official pyM17 IPFrame.calculate_crc. Pinned DroidStar instead places LSF-only CRC
on voice packets and zero CRC on termination: this implementation rejects those
legacy packets. This interoperability restriction is explicit, not silently
bypassed. Official CRC/callsign vectors and an independently extracted pure
official IP CRC method are tested. Neither is a real reflector/radio capture.

CONN/ACKN/NACK, PING/PONG and DISC state transitions require the configured UDP
endpoint. ACK/liveness is not cryptographic authentication. Connection timeout is
10 seconds, keepalive timeout 30 seconds; no automatic retry. Tests bind loopback
only. RX timeout .6s, TX input timeout .5s, maximum TX180s, bounded queues and
half duplex apply. An ending frame pads silence as needed and drains before unkey.

Installed worker uses private node1993, loopback USRP34007/32007 and control36100.
Managed Apply includes M17 configuration/rollback, initially disconnected. The
shared selector stops software at an idle stream boundary if hardware is selected;
there is no fallback or simultaneous route. A selected destination must match a
confirmed worker before the controller links audio. All native mode links are
disconnected when their worker fails. No autonomous public connection or RF test.

Sources and exact pins: PROVENANCE.json. Binding/integration GPL-3.0-or-later;
system Codec2 LGPL-2.1-or-later plus component notices. pyM17 declares MIT in its
retained pyproject.toml but has no standalone LICENSE file in the inspected pin;
its reference files are retained for audit/testing, not loaded by the runtime.
Pinned DroidStar comparison source retains GPL notices. No TETRA or firmware.

Tests: `python3 -m unittest -v test_m17 test_integration test_coherence`.
UI bounds: `node test_form.js staged/operator.js` (existing desktop Node).
No dependency download/install is required on this Pi. Real audio quality,
reflector interoperability, digital RF and physical M17 hardware are untested.
