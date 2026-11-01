# Legacy beta8 → package migration (explicit operator procedure)

Do not run the legacy installer in a package maintainer script. It performs a
system-wide apt upgrade and downloads dependencies. Existing user data is not
part of the package payload and is never replaced by package upgrades.

1. Review station status and confirm transmit is idle/disconnected. Stop Asterisk,
   allmode-digital, allmode-setup, and allmode-system explicitly. Do not interrupt TX.
2. Run `sudo python3 backup.py --output /root/allmode-before-package.tar.gz`.
   Keep the previous source/binary release and exact ASL package versions available.
   Verify backup members, permissions, size and a private trial extraction.
3. Compare `/etc/systemd/system/allmode-*.service` and drop-ins to packaged units.
   Preserve custom origins, TLS/auth, port, hardware settings and local changes.
   Translate web CLI options into `/etc/allmode/service.json` or a reviewed local
   ExecStart override. Do NOT blindly delete lan.conf or any other drop-in.
4. After review, move ONLY the three legacy base units allmode-setup/system/digital
   outside the unit search path into the private backup directory. Keep reviewed
   compatible drop-ins. Also review directories timer/service and tmpfiles rules.
   There is deliberately no automated overwrite of administrator units.
5. Simulate the exact pinned package installation (`apt-get -s install ...`).
   Stop if ASL or unrelated packages would be upgraded/removed. Install only the
   reviewed transaction. Install matching meter package before enabling audio.
6. Validate `allmode-launch --check`, `systemd-analyze verify` and all state fixtures.
   Existing favorites, RF memory revision/activation mapping, credentials,
   calibration, frequencies, and active-profile identity must survive unchanged.
7. Explicitly start web/helper only, verify console and hardware setup with RF idle.
   Enable radio/digital services only after commissioning and target tests pass.

Rollback: remain idle/stopped; install prior package version or restore prior code
and units from the private backup. Restore configuration/state only as one coherent
snapshot when migration changed them; never overwrite newer state blindly. Verify
Asterisk module ABI against restored runtime. Review systemd units and configuration,
then restart explicitly. Do not purge ASL or delete user data to roll back.

Removal/purge retains all station data. Deleting credentials, favorites or RF memory
state requires a separate explicit operator action. No firmware/UART/OS-owner changes
are made by these package lifecycle scripts.
