# Release source reconciliation

The three layouts were recovered from PihatUBETA's actual `/opt/allmode/web/operator.js` and `operator.css`, dated October 28. Reference UI archive SHA256: `03693cc68e62def2b9172e5ade595115b1cbe7c2c322c117e920e180a37cf736`.

Current layouts are **1 Original, 2 Sidebar, 3 Radio**, persisted as `ara.layout`. The older `station.js` console/app/technical chooser was not the agreed design and is not the active layout implementation.

The integration retains the audited current backend, optional audio skip, boot-ID reboot marker with service-readable permissions, 100.0 Hz defaults, exact RF checks and four-command manual programming. CPU usage uses aggregate `/proc/stat` deltas and temperature is Fahrenheit. Phone controls use the same mode availability checks as full Connect; no connection starts automatically.

The recovered radio gauge renderer uses the current 100 ms request loop, timeout and independent stale-data watchdog. The 50 ms FIFO collector and native writer remain unchanged. Software codec selection, mutually exclusive optional hardware, handheld parrot and separate browser audio test are retained.

Release verification checks these integration points and complete source/archive parity. Historical releases remain recoverable from Git history. No history rewrite is part of cleanup.

## Final reviewed radio-control refinement

- RX, TX A and TX B remain independent small gain knobs; TX A sits above TX B.
- The large Radio-layout dial selects saved favorites only. Pointer, wheel and keyboard selection never connect or change gain; the separate Connect button sends the guarded request.
- Selection retains the exact DMR network and survives status refreshes and favorite reordering. Empty, invalid, own-node, unavailable, busy, pending and read-only cases are covered by `test_radio_favorites.cjs`.
- This source candidate incorporates the reviewed knob patch without changing backend behavior or the 100 ms freshness-safe meter. Existing-station deployment remains separate from fresh-card acceptance.

### Shared radio audio meter
The Radio layout gauge shows live RX/TX audio levels in dBFS, current peak and clipping status. Idle, stale and unavailable inputs are explicitly labeled; stale peaks are hidden. It is an audio meter, not a calibrated RF signal-strength meter. The existing 100 ms update cadence remains unchanged.
