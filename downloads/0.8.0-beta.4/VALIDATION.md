# Validation — 0.8.0-beta.4

Prepared October 27, 2026. Candidate for controlled beta acceptance, not a fully accepted appliance image.

## Passed

- Built all four bundled native libraries from packaged source on the existing Debian 13 ARM64 Pi in an isolated temporary directory: D-STAR, AMBE2450, P25 and YSF. Existing station services/configuration were not replaced.
- Verified 172 pinned upstream source hashes across four build manifests.
- 97 application tests passed with appliance state redirected to temporary directories. Includes authentication, input validation, setup/config rollback, radio programming mocks, audio meter calculations, directories, destination switching and loopback protocol peers.
- 24 D-STAR codec/format/routing/local HTTP tests and 4 AMBE2450 codec tests passed.
- AMBE2450 build also ran its two bundled upstream codec test executables successfully.
- Local D-STAR encode/decode and dynamic loading of AMBE2450, P25, YSF and Codec2 passed, along with Python bitarray import.
- JavaScript syntax checked for all packaged UI scripts. Dashboard test preserved the meter region across 100 refreshes; five connection label checks passed.
- Bundled codec sources retain their licenses/provenance. No live station state, private recovery archive, SSH key, certificate, password file, audio recording or binary-only plugin is part of the release payload.

Tests use fake radio I/O, mocked Asterisk calls and loopback peers. They do not establish two-way on-air voice quality or fresh-install correctness. Older application fixtures were corrected to isolate appliance paths and account for native profiles that do not use legacy MMDVM ports. A preview-mode connection bug was fixed in this package so simulation cannot enter live preparation paths.

- Extracted archive passed its full checksum manifest and all shell scripts passed Bash syntax checks on the Pi. Read-only installer preflight correctly rejected the existing Asterisk station before any installation action.

## Required before broader distribution

- Run the complete installer on a freshly flashed spare SD card, including apt dependencies, ASL package scripts, reboot/resume, systemd startup, TLS and owner claiming.
- Verify the actual Pi model/UART/HAT combination, programming and power-cycle retention.
- Perform two-way RF/audio testing for each enabled network/profile, then network-loss/restart recovery and at least 24 hours of operation.
- Verify calibration, bridge stop/failure behavior and recovery instructions with participating beta operators.

No fresh card was flashed or full installer run on the working station during package creation. FCS is not a bundled working mode. Software codecs are experimental; connection readiness is not audio acceptance.

## Reproduce

On an ordinary Linux account, after dependencies are present:

```sh
bash build-native.sh
python3 run-tests.py
(cd codec && python3 -m unittest discover -s tests -v)
(cd codec/ambe2450 && python3 -m unittest -v)
ALLMODE_VOCODER_ROOT="$PWD/codec" python3 app/check_codecs.py
```

The application test runner refuses root. Do not run unisolated legacy test files against a configured station. Installer healthcheck is separate and does not connect public networks or transmit.

## Beta 2 changes

Owner passwords accept 4�128 characters. Wizard Next applies settings and advances only after confirmation. GPIO UART setup uses raspi-config with a reboot notice. No-port help is shown on the Radio page. Wizard success, request failure, unconfirmed application and duplicate-click regression checks pass. Shell syntax checks pass. A complete beta 2 fresh-card installation and RF/audio acceptance remain pending.

## Beta 3 DHCP origin regression fix (October 28, 2026)

109 application tests pass in the isolated ordinary-user runner, including 12
new policy, real HTTP login/CSRF, and installer contract tests. Python compilation
and Bash syntax pass. These tests mock local interface discovery and radio I/O;
no new ARM64 native build or fresh-install/RF acceptance claim is made.
See LAN-ORIGIN-FIX.md for the IPv4-only HTTPS proxy contract and TLS limitations.
