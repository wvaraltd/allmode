# ARA ALLMODE 0.8.0-beta.7

This repository root is the canonical current source. The release archives are generated from these files and checked for byte-for-byte parity. Earlier code and download packages remain recoverable through Git history, not mixed into the current source tree.

For a **fresh Debian 13 arm64 Raspberry Pi + SHARI** installation, follow [BEGINNER-INSTALL.md](BEGINNER-INSTALL.md). The bootstrap is `get-allmode.sh`; it downloads a commit-pinned, checksum-verified archive. It is not an existing-station updater. Never reinstall over a configured node.

The interface includes the reference Pi's three layouts: Original, Sidebar and Radio. Radio retains its transceiver chassis, controls, connection map and meter styles. All layouts share the same station data. Phone navigation, explicit Quick Connect, Fahrenheit temperature and measured CPU usage are included.

Setup retains explicit radio programming, four-command acknowledgements, optional audio testing, reboot guidance and 100.0 Hz default tones without changing saved settings. Audio metering uses the FIFO-only native writer, a 50 ms collector and 100 ms browser updates.

Run `python3 run-tests.py`, the Node regression tests and `python3 verify-release.py --archive downloads/allmode-0.8.0-beta.7.tar.gz`. See VALIDATION.md and THIRD-PARTY.md for test limits and dependency provenance. Fresh-card, real RF interoperability and sustained Zero 2 W performance acceptance remain separate from source tests.

### Radio-layout controls

The three small knobs adjust RX, TX A and TX B gain. The large Favorites dial selects a saved destination; press its separate **Connect** button to connect. Turning that dial does not transmit, connect, or change gain.

### Shared radio audio meter
The Radio layout gauge shows live RX/TX audio levels in dBFS, current peak and clipping status. Idle, stale and unavailable inputs are explicitly labeled; stale peaks are hidden. It is an audio meter, not a calibrated RF signal-strength meter. The existing 100 ms update cadence remains unchanged.
