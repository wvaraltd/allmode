# DMR source provenance

Vendored framing subset: https://github.com/HBLink-org/dmr_utils3 at commit 1bc82ab658a3c730771365be4228c2f915e3b8c7. GPL-3.0-or-later; original module notices and LICENSE.dmr_utils3 retained. Only __init__, bptc, hamming, crc, rs129, golay, golay_tables, qr included. No network downloader, Twisted, binary codec plugin, TETRA, or radio firmware.

Local modification: bptc.encode_emblc segment D second row used matrix index 24 twice, omitting index 25. Corrected the second occurrence to 25. Deterministic arbitrary-nine-byte LC test failed before this fix (f0a1abd602d5f6aa4d decoded as f0a1a3d602d5f6aa4d); regression test retained. Known upstream header fixture also tested.

homebrew.py protocol layout was inspected against HBLink-org/hblink3 hblink.py. This new state machine has injected I/O and clock and no socket/automatic reconnect. framing.py and transport integration are GPL-3.0-or-later. The AMBE2450 codec remains separately pinned mbelib-neo source with original notices. No patent-clearance assertion is made.

Pi dependency: official Debian trixie python3-bitarray 2.9.2-1+b4 from configured signed Debian package sources. No dependency executables bundled.
