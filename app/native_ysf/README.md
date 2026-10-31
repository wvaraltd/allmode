# Native YSF V/D mode 2

This component implements **YSF V/D mode 2 only** using the existing source-built
AMBE2450 codec. V/D mode 1, full-rate voice, full-rate data, FCS and hardware
YSF are unsupported and rejected. This is an analog-audio/reflector bridge,
not a digital RF modem or proof of on-air YSF interoperability.

Five 49-bit speech parameter frames occupy each 100 ms / 155-byte YSFD packet.
The VCH repeats the first 27 bits three times and leaves the final 22 voice
bits unprotected; decoding uses majority voting for the protected bits.
Scrambling, interleaving, FICH Golay/convolutional coding and data CRCs follow
the pinned sources. Corruption in unprotected voice bits cannot always be
detected. Full-rate data coding is used for the required call header/trailer;
that does not enable full-rate voice/data calls.

The production worker has distinct USRP ports 34002/32002 and control port
35100. It checks the shared software/hardware selection before DNS or codec
initialization. Changes wait for a completed stream; unsupported hardware
stops processing without fallback. Queues are bounded, input stalls release
after 500 ms, receive stalls unkey after 600 ms, and transmission is limited
to 180 seconds. Network polling is every five seconds with a 15-second failure
deadline and no automatic reconnect loop. A poll response is connectivity,
not cryptographic authentication or verified interoperability.

Managed setup adds reflector host/port and DG-ID beside the reflector ID.
Apply renders private node 1998 only when YSF is configured, creates private
runtime configuration, and leaves requested modes empty. Installation does
not Apply, start a worker, connect a reflector, or transmit. No destination is
guessed. There is no configured reflector/host directory on this Pi yet.

## Provenance and tests

`PROVENANCE.json` pins G4KLX YSFClients
`6e9359db895807bf5242917be0beac523f973e65` and DroidStar
`becf1dede57c4a70a865e9cb4cac9247e505599a`. Source notices are retained, including
the Golay file's Jonathan Naylor and Robert H. Morelos-Zaragoza notice. The
component is distributed under GPL-3.0-or-later with upstream GPL-2.0-or-later
notices retained. This is component provenance, not patent clearance.
Only unused Log.h/Utils.h includes were removed from the pure G4KLX FEC source
to avoid unrelated gateway dependencies. No TETRA, firmware, codec plugin,
or downloaded binary is included.

The production FEC code is built from G4KLX. A separate executable uses pinned
DroidStar FICH/data/voice functions to generate exact comparison vectors;
these verify FICH, header payload and five-channel voice/data packing, beyond
self-roundtrip tests. Both projects share some historical FEC code, so this
is not a substitute for captured radio vectors or external interoperability.

Build and test with the already-installed Pi compiler/Python:

```sh
python3 build.py
python3 -m unittest -v test_ysf test_integration
```

Tests use synthetic audio, temporary settings and loopback peers only. They
cover CRC/mode rejection, voice majority correction, packet-sequence and FICH
cycle wrap, codec independence, duplex guards/timeouts, control validation,
both UDP/USRP directions, shared selector transitions, native supervisor routing,
managed save/Apply generation, and existing HTTP authentication/rollback tests.
Public reflector and physical radio tests remain unperformed.
