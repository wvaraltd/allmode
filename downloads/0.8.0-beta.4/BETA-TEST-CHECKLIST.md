# Beta tester checklist — 0.8.0-beta.4

Record Pi model, RAM, OS image/version, SHARI model/band and date. Mark each item PASS / FAIL / NOT TESTED with observations.

- Clean SD installation completes; required reboot/resume works.
- Local hostname and direct IP reach HTTPS; certificate matches Pi fingerprint.
- Owner claim, login, logout and wrong-password rejection work.
- Hardware port detection, validation and explicit programming work.
- Guided Apply works; radio starts only when requested.
- Receive and transmit audio, live sliders, level persistence and meters work.
- Each used network connects, passes two-way speech and disconnects.
- Changing destination does not leave the old link attached.
- Lost Internet and restored Internet leave a clear status and safe recovery.
- Maintenance stops radio operations while keeping web access.
- Reboot retains credentials, radio records and audio levels; check radio startup behavior.
- Controlled bridge test only with willing network participants; verify stop and failure recovery.
- Run for 24 hours; note unexpected restarts, stuck transmissions, heat or storage growth.

Issue report: version; hardware; mode/profile; destination; exact reproduction; expected/actual behavior; timestamp; redacted diagnostics. Do not include passwords or station configuration dumps.
