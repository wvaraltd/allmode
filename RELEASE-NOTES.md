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
