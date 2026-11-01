# Exact release identity and qualification

## Published package and source

- Application source commit: `d6e2bc378fa8a79ac12a102d28af0af6994c0b88`.
- Immutable application export SHA256: `ff0db4a7561ecc8f3c33974a61ba59b157f9a825dda53652b953805777853074`.
- Reviewed packaging v5 export SHA256: `e6c5062b91f9531811f82b5ff3defadb5007799d4c8f85eececbd301439a35bd`.
- Final public core: `ara-allmode_0.8.0~beta9-5_arm64.deb`, 1,063,952 bytes.
- Core SHA256: `7f7e407e2e71eff411c74265d4b85342b10a6f98b765e2694241ad97a5e39406`.
- Signed Release SHA256: `6485a3aeeb7bbaa90c13bdee734b8a0787c945b40b3683bd7be895faf77a9b09`.
- Release Valid-Until: **2026-11-15 19:32:06 UTC**; expired metadata must fail closed.
- Repository: `https://rf.ara.radio/allmode/apt/`, `trixie/main`, `arm64`.
- ARA primary fingerprint: `59DAB5C15B5F96D5660E0D94503AE6F5AD483087`.

The verified index contains seven records: core revisions 1, 2, 3 and 5 plus unchanged meter/addon/guard packages. All previous package hashes are retained. Core4 and rejected intermediate builds were not published.

Application, codec and native runtime files match the exact source export. Root `packaging/` matches the reviewed v5 snapshot. Documentation, complete checksum metadata, retired-entrypoint guards and publication verification are explicitly identified publication-only edits, not a different native package build. See PUBLICATION-PROVENANCE.json.

## Verified scope

| Area | Evidence / limitation |
| --- | --- |
| Public distribution | Actual HTTPS key → pinned fingerprint → signed Release → Packages → final package hash chain independently verified |
| Native ARM64 | Reviewed codecs, official MMDVM loopback and exact Asterisk meter ABI qualified |
| Final existing-station upgrades | Two reviewed targets installed core5; managed controller checks passed; protected settings unchanged |
| Meter recovery | Persistent owned tap and advancing sequences/fresh RX/TX verified on both targets; actual speech/RF acceptance not claimed |
| Wi-Fi | Ordinary-user NetworkManager offline generation passed five synthetic profiles; no real Wi-Fi association test |
| Radio UI | Core3 historical authenticated Settings/Radio browser checks passed. Core5 actual browser acceptance is blocked at login after the update; no credentials entered and no core5 browser pass claimed. Core5 source tests/offline parser checks passed |
| Generic fresh bootstrap v11 | Actual fresh run FAILED at upstream netcheck dependency guard test before core install completed; VM off |
| Full fresh-card, phone/GPIO, physical RF acceptance | Not established by source/package tests |

## Frozen installer candidate, not a ready installer

The source under `installers/fresh-candidate-v11/` is the exact reviewed candidate export SHA256 `0dc06b0e2a9861d13a126b7633611169987e6dc5716d37fcfdf0a26b0cea1214`. It retains core3 pins and its original scoped evidence. Do not present it as a tested core5 fresh installer. FRESH-INSTALL-BLOCKER.md describes the actual failure without private diagnostic paths or station identifiers.

## Exclusions and maintenance

No private keys, credentials, station settings or active RF-memory presets are shipped. New DTMF voice feedback, AP design, optional/offline tools and experimental multimode work are not included. Requested/queued connections are not asserted established before normal status confirms them.

Signed metadata renewal is a publisher obligation; no scheduled renewal is claimed here. Historical audits and candidate reports remain evidence of their original scope, not current installation instructions. BEGINNER-INSTALL.md intentionally provides no unqualified fresh apply command.
