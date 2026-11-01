# beta.9 source validation — 2026-11-01

Candidate only; these results do not qualify a release on the physical Pi.

* Four native codec libraries built from bundled source on Linux x86_64.
* 217 application tests passed; two existing RF Unix-socket integration tests
  skipped because the execution sandbox denies Unix sockets. No policy bypass.
* 24 D-STAR tests and four AMBE2450 tests passed.
* Eight root JavaScript regression scripts passed. Operator JS and all shell
  scripts passed syntax checks. CRLF-aware git whitespace check passed.
* Native D-STAR encode/decode plus AMBE2450/P25/YSF/Codec2 loading and bitarray
  import passed (bitarray supplied only through isolated test dependency path).
* Actual official MMDVM_Bridge amd64 binary: two fresh-process cycles passed
  fake-master challenge authentication, PCM→codec→TLV→MB→DMR packets and inverse
  DMR→MB→TLV→codec→PCM, socket-process ownership, graceful stop and socket reuse.
  Every transmitted AMBE72 burst matched the encoder output exactly; every
  received AMBE72 burst matched the primary triple-silence vector. Each cycle
  produced nine TX network packets, 14 RX TLVs and 36 PCM frames plus unkey.
* No public DMR master, RF transmission, live station installation or trust
  change was involved. Existing native six-mode routes remain unchanged.

Protocol-only fixtures, exact binary hash, source provenance and loopback results
are in `app/dvswitch_reference/`. To reproduce on either architecture after
building its native codec and installing Python bitarray, run as the same
unprivileged account that runs the adapter, with a **new** output directory:

```sh
python3 tools/verify-dvswitch-loopback.py \
  --source "$PWD" \
  --binary /opt/MMDVM_Bridge/MMDVM_Bridge \
  --output /tmp/allmode-dvswitch-loopback-new
```

This tool creates only loopback mock peers and private files in the specified
new output directory. It neither installs packages nor changes services. Do not
use a public peer or RF device to substitute for this test.

Still required: final independent source review, ARM64 execution, fresh-card
installer/upgrade acceptance, boot/recovery checks, Zero 2 W CPU/RSS/underrun
measurement and operator-authorized physical two-way voice acceptance.
