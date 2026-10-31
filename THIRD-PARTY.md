# Source and attribution

This archive includes source and retained license/provenance files for its native components. It does not include the former binary-only DroidStar vocoder plugin, DVSwitch executables, AllNode reference code or the developer's station data.

- D-STAR/AMBE2450: mbelib-neo pinned source; see codec/vendor/manifest.json, codec/ambe2450/manifest.json, codec/LICENSE and codec/vendor/mbelib/LICENSES. D-STAR source commit a3c7bbdae9eb21cbfab57006c1a5daca7bdcba7f.
- FFT: PFFFT pinned source with original license; see codec/vendor/manifest.json and codec/vendor/pffft.
- DMR framing: dmr_utils3; see app/native_dmr/LICENSE.dmr_utils3, PROVENANCE.md and vendor-manifest.json.
- P25: source IMBE implementation and wrapper; see app/native_p25/COPYING and PROVENANCE.json.
- YSF: framing/FEC source; see app/native_ysf/COPYING and PROVENANCE.json.
- NXDN and M17: see their PROVENANCE.json files and reference license notices.
- Codec2 is installed by Debian apt, with system package copyright information under /usr/share/doc/libcodec2-1.2.
- ASL3 and Debian dependencies are obtained from their repositories; they are not binary payloads in this archive.

Build with `bash build-native.sh` on Debian arm64 with build-essential, Python, python3-bitarray and libcodec2-1.2 installed. Upstream license notices are preserved. This package does not assert patent clearance. Public host directories are fetched at install/runtime from the sources listed in app/directory_sync.py.
