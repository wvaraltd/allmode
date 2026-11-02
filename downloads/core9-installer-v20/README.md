# ALLMODE core9 installer — qualified beta download

This artifact branch publishes the reviewed installer without changing main, the public APT package generation, or the private beta10 pilot. The inner installer is v20-r2 and pins core 0.8.0~beta9-9.

[Download the complete installer bundle](allmode-core9-installer-v20-r2.tar.gz)

SHA-256: `85f84e9f538190e6bcc13bd302b03f9fa84fe8c94f682e2ffae4d13b1191832d` (77,760 bytes).

The archive contains INSTALL.md, QUALIFICATION.md, SHA256SUMS and the unchanged installer archive. Its documents were frozen immediately before publication and therefore say publication pending; this branch is the published distribution record. The qualification record precisely distinguishes actual final legacy A/B and fresh-readiness results from inherited full fresh/512 MiB and reboot/resume transaction evidence.

## Fresh system only

Use Debian 13 ARM64 with an existing administrator/SSH login. Do not use fresh mode on an existing configured station. Read INSTALL.md before applying. Radio stays off until explicitly commissioned; initial access is an SSH tunnel to localhost, not automatic phone/LAN access. Physical GPIO/RF/audio and Wi-Fi switching are not qualified by these VM tests.

Download and verify the complete archive before extracting or running any installer. From the extracted inner directory, `python3 bootstrap.py --mode fresh` shows the plan; `sudo python3 bootstrap.py --mode fresh --apply` performs installation. Keep that exact directory for same-bundle recovery. Never pipe an unverified network response to a root shell.

The current signed repository metadata expires 2026-11-15 21:24:42 UTC. No automatic renewal is configured. Installation fails closed on expired or invalid metadata; do not disable signature or Valid-Until checks.

Private beta10 voice assets are not included. No station credentials, identity or private signing keys are distributed.
