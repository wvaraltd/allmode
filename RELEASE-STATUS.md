# Exact release identity and qualification

## Published package and source

- Application source commit: `a3cbe328dacaf172653db1f4c332d9b66cfd609d`.
- Immutable application export SHA256: `bc16e7a4ac8645cabdb88469ffbe7f66560590243167aef7ec1988ea485f077d`.
- Reviewed packaging v5 export SHA256: `e6c5062b91f9531811f82b5ff3defadb5007799d4c8f85eececbd301439a35bd`.
- Final public core: `ara-allmode_0.8.0~beta9-6_arm64.deb`, 1,064,472 bytes.
- Core SHA256: `719c4b349399020343ed839963162f1be621b7f390ca67cbd40c8de5dea4a5d8`.
- Signed Release SHA256: `61d40fe6a3e4dc9e2fc74753d442af0d81ec502856c7d3534e17d140eb89d1e0`.
- Release Valid-Until: **2026-11-15 19:55:32 UTC**; expired metadata must fail closed.
- Repository: `https://rf.ara.radio/allmode/apt/`, `trixie/main`, `arm64`.
- ARA primary fingerprint: `59DAB5C15B5F96D5660E0D94503AE6F5AD483087`.

The verified index contains eight records: core revisions 1, 2, 3, 5 and 6 plus unchanged meter/addon/guard packages. All previous package hashes are retained. Core4 and rejected intermediate builds were not published.

Application, codec and native runtime files match the exact source export. Root `packaging/` matches the reviewed v5 snapshot. Documentation, complete checksum metadata, retired-entrypoint guards and publication verification are explicitly identified publication-only edits, not a different native package build. See PUBLICATION-PROVENANCE.json.

## Verified scope

| Area | Evidence / limitation |
| --- | --- |
| Public distribution | Actual HTTPS key → pinned fingerprint → signed Release → Packages → final package hash chain independently verified |
| Native ARM64 | Reviewed codecs, official MMDVM loopback and exact Asterisk meter ABI qualified |
| Final existing-station upgrades | Two reviewed targets installed core6; managed controller checks passed; protected settings unchanged |
| Meter recovery | Persistent owned tap and advancing sequences/fresh RX/TX verified on both targets; actual speech/RF acceptance not claimed |
| Wi-Fi | Ordinary-user NetworkManager offline generation passed five synthetic profiles; no real Wi-Fi association test |
| Radio UI | Core3 historical authenticated Settings/Radio browser checks passed. Core6 actual browser acceptance is blocked at login after the update; no credentials entered and no core6 browser pass claimed. Core6 source tests/offline parser checks passed |
| Generic fresh bootstrap v11 | Actual fresh run FAILED at upstream netcheck dependency guard test before core install completed; VM off |
| Full fresh-card, phone/GPIO, physical RF acceptance | Not established by source/package tests |

## Frozen installer candidate, not a ready installer

The source under `installers/fresh-candidate-v11/` is the exact reviewed candidate export SHA256 `0dc06b0e2a9861d13a126b7633611169987e6dc5716d37fcfdf0a26b0cea1214`. It retains core3 pins and its original scoped evidence. Do not present it as a tested core6 fresh installer. FRESH-INSTALL-BLOCKER.md describes the actual failure without private diagnostic paths or station identifiers.

## Exclusions and maintenance

No private keys, credentials, station settings or active RF-memory presets are shipped. New DTMF voice feedback, AP design, optional/offline tools and experimental multimode work are not included. Requested/queued connections are not asserted established before normal status confirms them.

Signed metadata renewal is a publisher obligation; no scheduled renewal is claimed here. Historical audits and candidate reports remain evidence of their original scope, not current installation instructions. BEGINNER-INSTALL.md intentionally provides no unqualified fresh apply command.

## Core6 Wi-Fi request-contract correction
The HTTP route now forwards security, hidden-network and connect options to the existing validated helper rather than dropping them. Six authenticated HTTP-to-helper regressions passed with OS mutations mocked, including tests against the extracted package. The complete source suite ran 297 tests (295 passed, two known skips) plus 12 JavaScript suites. Both reviewed stations installed core6 with protected settings preserved and fresh meter frames. Real network association was not performed; actual browser acceptance remains blocked at login. New DTMF feedback remains unreleased and is excluded.
