# ALLMODE beta.5 audit candidate — 2026-10-30

Unpublished source candidate. No live Pi deployment, RF transmission, radio programming, public network connection, or production credential change was performed. A complete fresh-install/hardware acceptance claim is not made.

## Changes

- GET dependency failures now return JSON 503 rather than aborting the connection, including digital identities, codec state and radio-parrot state.
- Codec selection and radio-parrot POST dependency failures return 503 rather than treating an unavailable service as bad user input.
- Owner claim error text matches the existing 4–128-character policy. Password policy itself is unchanged.
- Audio wizard Continue now opens Finish directly and lets normal wizard rendering persist both step identifiers. Previously the stale named step overrode the newly written numeric step on reload.
- Group wizard pages now provide Back. Back, Skip and Cancel respect an in-flight save; Skip is explicitly a non-submit button.
- Radio Success and continuation require the exact four acknowledgement names in order, matching backend commissioning checks. Four unrelated entries no longer display Success.
- Installer records the version from release.json instead of hard-coding beta.3. Operator footer displays beta.5 rather than beta.1.
- Preflight verifies both arm64 userspace and an aarch64 kernel.
- AMBE2450 timing reports now record the actual platform.system()/platform.machine() and realtime_guarantee=false instead of falsely labelling every host Pi ARM64.

No RF presets, permitted frequency boundaries, digital modes, or software/hardware codec defaults were changed.

## Evidence

- Remote main verified at 298a20bd44be8d7f681c019020930a4e43843270; package commit 2946c49bab3488b7174aad69de73b0a7edb89a57.
- Original TAR SHA-256 matched bootstrap and published checksum: 9cf56f8fbc52bab7a98a52f5efaa4ccab27401be00b4200d8292edb6198f471b. All 378 original package manifest entries verified from archived bytes.
- Final Windows audit: 84 application tests passed. Harness redirects appliance state to temporary storage; POSIX flock is replaced with a no-op for this Windows-only run; pwd is an import-only shim and real account lookup is not emulated; timezone data comes from the bundled runtime. This is not Linux locking/service acceptance.
- All 121 Python source files parse; all 15 JavaScript/CJS scripts pass Node syntax checks.
- Existing five connection-label assertions pass; 100 meter refresh iterations preserve the meter subtree. New UI regressions cover exact serial acknowledgement integrity, audio Finish navigation, and apply confirmed/error/unconfirmed responses.
- Actual browser on isolated loopback server: empty station rejected, N0CALL saved in temporary storage, reload resumes current step, Back returns to saved station, Cancel discards edits, optional networks skip, software codec remains default, Radio detects no hardware and disables programming/continuation. Suggestion fills RX/TX without programming; 438.000 is blocked and 449.995 is accepted with warning. At 390x844 override the radio document width equals viewport width (375 CSS px after scrollbar), no horizontal overflow.
- Independent Linux final-candidate validation reported 114/114 application tests, the 237-request HTTP matrix, all three previously failing dependency GET routes returning 503, and full mocked setup prerequisites/save/program/apply/activate/audio/Finish persistence passing. The original beta.5 baseline had 109 tests.
- Linux x86_64: all four bundled native libraries built offline; 24 D-STAR tests, four AMBE2450 tests and two upstream executables passed. check_codecs passed with bitarray 3.12.3 in an isolated environment. Additional 100 synthetic roundtrips/reset/invalid-length checks per DMR, NXDN, YSF V/D2 and P25, plus M17 CRC/corruption checks passed. These results do not establish ARM64/Zero 2 W timing, Codec2 helper execution on ARM64, or RF/audio interoperability.
- Extended actual browser commissioning used real UI, HTTP handlers, settings persistence and Hardware acknowledgement logic with a synthetic serial port and fake system-service dispatcher only. First programming attempt failed at AT+SETFILTER; program.json retained incomplete state with exactly the first two acknowledgements and no setup completion marker. Reload retained the failed result and saved draft, with Continue disabled. Full retry sent one handshake plus four commands and enabled Continue only after success. Repeated save/program/apply/audio/Finish clicks did not skip steps or duplicate service actions; fixture recorded exactly one apply, one activate and one audio-confirm. Reload after apply resumed Audio. Advancing before audio completion showed disabled Finish. Start without RF checkbox and audio confirmation without checkbox were rejected. With synthetic prerequisites satisfied, Continue opened Finish, reload remained on Finish, and Finish persisted setup-complete.json then redirected to Dashboard. Reopening /setup redirected to Dashboard. No physical audio check is claimed.
- All literal browser API URL families were cross-checked against server and extension dispatch (including relative ./api/hardware and ./api/command, dynamic directory source and radio-parrot action routes); no unsupported active fetch route was found. Methods/auth/payloads are listed in AUDIT-ENDPOINTS.md.

## Raspberry Pi Zero 2 W assessment

The CPU supports ARM64. Its 512 MB RAM, four Cortex-A53 cores, 2.4 GHz Wi-Fi, single OTG data port and unpopulated GPIO constrain the deployment. ASL's current Debian 13 arm64 appliance documentation lists Zero 2 W support, but this ALLMODE installer deliberately refuses an already-installed Asterisk host: use its documented fresh OS path, not an existing configured ASL station.

Build review found sequential Python subprocess compiler invocations, no unlimited make -j/nproc parallelism, and no newer-CPU-specific -march flag. This reduces build-memory risk but is not a measured peak-RAM result. Native software vocoder realtime throughput, combined Asterisk/web/digital-worker RAM, thermal/power behavior and audio underruns require a real Zero 2 W test. No arbitrary MemoryMax limit was added that could kill audio processing.

Sources supplied by independent hardware review: https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/ ; https://allstarlink.github.io/install/pi-appliance/ ; https://allstarlink.github.io/install/debian/install/ ; https://allstarlink.github.io/basics/incompatibles/ .

## Remaining gates

1. Independently verify the final refreshed archive/manifest after the timing-report metadata-only correction. Linux execution checks above passed for application/native source; physical ARM64 execution remains outstanding.
2. Fresh Debian 13 ARM64 spare-card installation, apt/ASL installation, interrupted install/reboot/resume, service startup, owner enrollment, trusted TLS setup, and checksums. Never run the fresh installer over the existing station.
3. Real Zero 2 W resource/performance measurement and correct powered OTG/UART/CM108 wiring; exclusive audio/PTT ownership and safe release after failures.
4. Serial programming, power-cycle retention, two-way RF/audio and approved network tests for D-STAR, DMR, YSF, P25, M17, NXDN; recovery and sustained operation.
5. Repeat commissioning with actual services and devices on a spare card; mocked HTTP and actual-browser commissioning now pass, but neither establishes physical behavior.

The self-signed certificate issue is unchanged. No browser warning was bypassed. Full project correctness cannot be inferred from these automated and isolated checks.
