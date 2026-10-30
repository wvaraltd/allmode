# ALLMODE 0.8.0-beta.6

Corrected source-based fresh-install beta for Debian 13 arm64/aarch64 Raspberry Pi + SHARI. This is not an updater or an SD-card image. Existing configured stations are protected by preflight rejection.

## Corrections

- Unavailable system-service endpoints return structured JSON errors instead of dropped connections.
- Guided setup has Back controls, guarded repeated clicks, reliable audio-to-Finish navigation and persisted readiness.
- Radio Success requires the exact four serial acknowledgements; acknowledgements do not prove RF/audio acceptance.
- Owner-password messages match the existing 4-128-character policy.
- Installer/footer versions are consistent; installation is marked complete only after final web-service readiness succeeds.
- Preflight checks arm64 userspace, aarch64 kernel, required UART utility and storage, and explains low-memory-device limits.
- AMBE timing reports identify the actual execution platform rather than labelling every host Pi ARM64.

Preserves D-STAR, DMR, YSF V/D2, P25 Phase 1, NXDN4800 and M17 Codec2 3200, software-vocoder default, optional mutually exclusive hardware selection, RF suggestions and custom-frequency policy. Saving/applying station configuration does not automatically program the radio. No TETRA mode is added.

## Validation

The audited application source passed 114 tests and a 237-request HTTP matrix on Linux x86_64. Four native libraries built offline; 24 D-STAR tests, four AMBE2450 tests and two upstream executables passed, along with additional synthetic codec/protocol checks. Actual browser commissioning passed using mock system and serial services, including partial failure, retry, reload, prerequisite enforcement and durable Finish. See AUDIT-RESULTS.md for qualifications and AUDIT-ENDPOINTS.md for routes.

Release-only version/downloader/preflight changes require their own final checks before publication. Fresh spare-card installation, real ARM64/Zero 2 W CPU/RAM/latency measurements, peripheral/serial retention, two-way RF/audio and long-duration acceptance remain pending. No CI result or on-air certification is implied.

Use get-allmode.sh from the repository root, or the named beta.6 TAR/ZIP. The repository-root application remains older development code; the complete beta.6 source is inside these named packages.
