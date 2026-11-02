# Core9 release identity and qualification

## Canonical source and signed packages

- Application commit: `1231449b471720cd09487599da11354d02d8e59d`.
- Application export SHA256: `78524966280a414ab87aa5ae0db079a39dfbc1f87f27ad462b60b4335af3f9d8`.
- External reviewed packaging v6b SHA256: `71115a6ebc65afde87ccdca4680eca6bd83e1f63f244f06cb30bbf860979c9a0`. This replaces the older packaging embedded in the application export.
- Signed repository: `https://rf.ara.radio/allmode/apt/`, `trixie/main`, `arm64`.
- ARA primary fingerprint: `59DAB5C15B5F96D5660E0D94503AE6F5AD483087`.
- Signed Release SHA256: `2b8f1bdd24ad7fd96c80575d1d36acc2b6f6c3e4add0ca98f9320009c1ff2048`.
- Valid-Until: **2026-11-15 21:24:42 UTC**. Expiry checks must remain enabled.

| Package | Exact version / architecture | Bytes | SHA256 |
| --- | --- | ---: | --- |
| ara-allmode | 0.8.0~beta9-9 / arm64 | 1068228 | `437b4cee9101b6abde68762f8e9940c9f8ee0a851882055054c9708d0d0df63c` |
| ara-allmode-dvswitch-guard | 0.8.0~beta9-2 / all | 2156 | `bcd272830d72e59e6859d20a8ae56e3995bd8ed9dd224bb70e601a24479d351e` |
| ara-allmode-dvswitch | 0.8.0~beta9-2 / all | 3932 | `6df10c76bd036ee5e5f04eb3561964103308a04af161e5e9381b5a028d482162` |
| ara-allmode-meter | 0.8.0~beta9+abid1486d408855-1 / arm64 | 6476 | `b995666424613d3697bd6ade6e5075c2d316f95cc4e9c1520da148a7f26133bb` |

All fourteen public records and the signature/index/package chain were independently verified; older package hashes are retained. Guard/addon/meter are separate package identities, not aliases for the core version. Use the reviewed signed manifest and actual package metadata, not guessed names or suffixes, for any approved transaction.

## Evidence and boundaries

- Both reviewed existing stations completed core6→core9 with normalized companion packages. Controller/readiness checks, static permissions and fresh meters passed; protected settings were preserved.
- The real direct AllStar HTTPS PHP feed passed with 41,198 rows, field parity, fallback and timing tests. Installed service-user cache access passed. Display unknown/absent names honestly rather than inventing them.
- Historical core6 Wi-Fi/meter browser checks passed. The core9 refresh returned to login; no new core9 visual acceptance is claimed.
- Existing source regression CI is preserved, with the node-name contract added. Source/OS mocks do not establish actual Wi-Fi association, physical speech/RF performance, full phone/GPIO coverage or fresh-card acceptance.
- DTMF feedback remains a separate unreleased prototype and is excluded. No experimental DVSwitch/AP branch or private station state is shipped.

## Published core9 installer (2026-11-02)

Use the [published installer instructions](https://github.com/wvaraltd/allmode/blob/725fda65e4f4cf67d3c1cfd66a65624cf5cc1e23/downloads/core9-installer-v20/README.md), not the retired source entrypoints or the historical v17 candidate in this tree. The immutable [complete installer bundle](https://raw.githubusercontent.com/wvaraltd/allmode/818b54bffe9d95a2cea2f131f6c505dc753a5ea0/downloads/core9-installer-v20/allmode-core9-installer-v20-r2.tar.gz) is 77,760 bytes; SHA-256 `85f84e9f538190e6bcc13bd302b03f9fa84fe8c94f682e2ffae4d13b1191832d`. Verify the whole archive before extraction and follow its INSTALL.md. The inner installer is v20-r2 and pins public `ara-allmode=0.8.0~beta9-9`; no package, signing key or runtime is changed by this documentation update.

Qualification is deliberately version-specific: full pristine core9 installation and a separate 512 MiB/no-swap run passed with v18; actual controlled interruption, reboot and same-bundle resume passed with v19; final v20-r2 passed both synthetic legacy identities and an actual targeted fresh-readiness check on a preserved successful v18 install. That last check executes the final readiness function, not a new full v20 installation. These are inherited transaction results plus final-function evidence, not exhaustive power-loss or arbitrary legacy compatibility.

Fresh mode is for Debian 13 ARM64 with an existing administrator/SSH login, not a configured station. Initial access is an SSH tunnel to localhost; radio remains off until explicitly commissioned. A 512 MiB VM is not physical Zero 2 W/GPIO/RF/audio or phone/LAN qualification. Real Wi-Fi association remains untested. Public core9 excludes private beta10 DTMF/readback, native feedback prototype3 and neural voice assets prototype5.

The recorded signed repository metadata expires **2026-11-15 21:24:42 UTC**. No automatic renewal is configured. Keep signature and Valid-Until checks enabled; stop on expired metadata and obtain properly renewed signed metadata rather than bypassing checks. Keep the exact extracted bundle for documented same-bundle recovery.

### Retained historical failures

The v17/core7 snapshot under `installers/fresh-candidate-v17/` and earlier netcheck, payload-mode and unit-retention failures remain historical evidence. Do not run that archived candidate as the current core9 installer. The published v20-r2 bundle and its qualification record supersede the former pending-status statements, without rewriting retained artifacts. Legacy `get-allmode.sh` and `install.sh` still exit 2 without installation.

## Provenance

Runtime app/codec/native files match the exact core9 export. Root `packaging/` is the external frozen v6b snapshot. Frozen candidate source remains distinguishable from the deployed package builders. Publication-only documentation, complete checksum metadata and retired-entrypoint guards are recorded in PUBLICATION-PROVENANCE.json. This publication is not a different native package build.
