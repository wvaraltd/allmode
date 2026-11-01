# 0.8.0-beta.9 candidate — local DVSwitch DMR transport and radio display

- Radio display centers confirmed destination/active network mode above fresh
  speaker identity, with RX/TX/PL at right. ASL receiving links are labeled Via
  node N, never an inferred originating callsign. Fresh-only qualified DVSwitch
  preset preserves all existing drafts and keeps networks disabled.
- Preserves all beta.8 favorites, RF-memory isolation, layouts, phone controls,
  calibration, authentication, meter timing and saved station settings.
- Adds explicit local DVSwitch DMR transport using existing software AMBE2450.
  No external computer, AMBEServer or MD380 emulator is required.
- Six native software modes remain available; DVSwitch transport is currently
  qualified only for DMR. M17 remains native Codec2, not a DVSwitch mode.
- Existing stations retain native DMR by default on upgrade. Choose local
  DVSwitch in DMR identity, then apply while disconnected. Software is default;
  optional external AMBE requires the native route and is never a fallback.
- Mocked bidirectional tests are not RF acceptance. ARM64 runtime and Zero 2 W
  load qualification must pass before declaring this candidate release ready.

# 0.8.0-beta.8 — station favorites and RF memories

- Durable station favorites with stable IDs, revision conflicts and reviewed browser import.
- Fixed RF slots and complete `*5` command previews beneath favorites; new slots default off.
- Local-only RF recall through the existing non-bridging, validation-before-disconnect dispatcher.
- Explicit hash-reviewed caller isolation preserves local `*3`/`*5` and other remote commands.
- Preserves reviewed isolation and memory blocks across station Apply, with consistent configuration hashes.
- Atomic rollback covers late directory-sync failures; persistent restore failures block recall pending recovery.
- Feedback remains logs/controller events and status UI only; no spoken acknowledgement or unkey scheduling.

Candidate validation and hardware limits are documented in FAVORITES-CANDIDATE.md and RF-MEMORIES.md.
Existing layouts, phone controls, metering, optional audio and installer safeguards are retained.

# 0.8.0-beta.7

- Canonical repository source now matches the distributed application.
- Restores the actual Original, Sidebar and Radio layouts from the reference Pi.
- Retains 50 ms FIFO metering and 100 ms browser updates with stale-data handling.
- Adds phone navigation, explicit Quick Connect, Fahrenheit and measured CPU usage.
- Makes the audio check optional without recording a false pass.
- Adds UART reboot guidance and an explicit successful-install reboot offer.
- Defaults RX/TX PL to 100.0 Hz while preserving saved values.
- Preserves bounded package-lock waiting, endpoint failure handling and setup/RF safeguards.

Fresh-install and physical RF acceptance are not implied by automated tests or the reviewed existing-station update.

## Final reviewed radio-control refinement

- RX, TX A and TX B remain independent small gain knobs; TX A sits above TX B.
- The large Radio-layout dial selects saved favorites only. Pointer, wheel and keyboard selection never connect or change gain; the separate Connect button sends the guarded request.
- Selection retains the exact DMR network and survives status refreshes and favorite reordering. Empty, invalid, own-node, unavailable, busy, pending and read-only cases are covered by `test_radio_favorites.cjs`.
- This source candidate incorporates the reviewed knob patch without changing backend behavior or the 100 ms freshness-safe meter. Existing-station deployment remains separate from fresh-card acceptance.

### Shared radio audio meter
The Radio layout gauge shows live RX/TX audio levels in dBFS, current peak and clipping status. Idle, stale and unavailable inputs are explicitly labeled; stale peaks are hidden. It is an audio meter, not a calibrated RF signal-strength meter. The existing 100 ms update cadence remains unchanged.
