# NXDN4800 native component

This is source for a narrow-voice NXDN reflector/PCM bridge with production
selector, supervisor and managed Apply integration. Installation does not
configure or activate a network. NXDN becomes selectable only after the user
supplies an NXDN ID, talkgroup, reflector host/port and applies the configuration.
No NXDN reflector has been contacted, no RF has been transmitted, and no
hardware vocoder or private recorded speech is used by these tests.

Implemented:

- NXDN group voice datagrams (`NXDND`, 43 bytes), poll/unlink (`NXDNP`/`NXDNU`,
  17 bytes), source/destination validation, LICH, SACCH CRC6 and header CRC12.
- Four 49-bit AMBE2450 frames per 80 ms packet; seven-byte raw parameter
  frames are distinct from the nine-byte DMR FEC frames and from RF framing.
- Native 8 kHz S16LE codec boundary using the existing pinned source-built
  AMBE2450 library. The 72-bit wrapper is bridged through upstream FEC
  encode/decode APIs; each direction owns separate prediction state.
- Explicit-start endpoint-filtered UDP peer, one-second polls, five-second
  failure deadline, no reconnect loop. This protocol does not authenticate
  peers cryptographically; status never reports `authenticated=true`.
- Bounded half-duplex PCM routing, 180-second TX limit, 500 ms input-stall
  release, 600 ms receive timeout, 20 ms playback cadence, stream cleanup.
- Actual loopback USRP/UDP worker and strict configuration/profile validation.
  Unsupported hardware selection fails without software fallback.

`config.capability()` deliberately returns `ready=false`: the pure codec/profile
module cannot establish runtime readiness. `nxdn_native.configured()` checks
installed files and applied settings; `status()` requires a current live worker
and poll response to report a connection. Public interoperability remains
unverified even after a poll response. No automatic network startup was added.
Hardware NXDN, NXDN9600, private/encrypted calls and late entry are unsupported.
YSF narrow/full-rate, P25 phases 1/2 and M17 are separate profiles, not implied
by this implementation.

## Source and interoperability limits

See `PROVENANCE.json` and retained reference notices. Primary sources are
G4KLX NXDNClients `498f451bbc66cd90f267ecd46b6eea0ba2df6145` and DroidStar
`becf1dede57c4a70a865e9cb4cac9247e505599a`. Derived code is GPL-3.0-or-later;
G4KLX GPL-2.0-or-later notices remain in copied files. The existing codec stays
at mbelib-neo `a3c7bbdae9eb21cbfab57006c1a5daca7bdcba7f`, with its existing
component notices. No TETRA or firmware implementation is included.

An independently compiled, socket-free extraction of pinned packet functions
checks header, voice and trailer framing. Inspection/testing found that the
pinned DroidStar code duplicates a voice bit into unused padding and omits
header CRC12. Our receiver ignores unused padding, but rejects headers lacking
the correct CRC12; our transmitter supplies the G4KLX CRC12. This is an explicit
compatibility restriction, not proof of broad reflector interoperability.
Raw codec roundtrips verify internal consistency and stream independence;
cross-implementation speech-quality/interoperability testing remains necessary.

## Repeat the Pi tests

Existing GCC/Python and the already-installed AMBE2450 library are sufficient.
No package installation is required. In the staged `nxdn` directory:

```sh
gcc -std=c99 -O2 -Wall -Wextra reference/fixture.c -o reference/fixture
python3 -m unittest -v test_nxdn
```

Tests cover reference packet agreement, malformed fields/payloads, peer
endpoint/poll/timeout/unlink behavior, profile/backend gates, half-duplex and
release/timeout cleanup, independent native streams and both directions of
real loopback UDP/USRP routing. No production service restart is required.

The first reference test failed on the pinned source's padding behavior; that
difference was investigated and corrected in the receiver/test expectation.
Subsequent CRC12 source inspection added the stricter header check described
above. Final results are recorded alongside this source after the test run.
