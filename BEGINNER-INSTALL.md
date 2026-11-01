# Installation and maintenance status

## Fresh Raspberry Pi: no qualified install command yet

Do not run old beta 7 download commands or source installers. The current legacy `get-allmode.sh` and `install.sh` deliberately exit without changes. Keep a working SD card intact.

The target remains Debian 13 ARM64 on supported Raspberry Pi hardware. The reviewed source-only bootstrap v11 in `installers/fresh-candidate-v11/` is not fresh-qualified: its actual disposable test failed at the upstream netcheck dependency during the stock MMDVM guard test, before core installation completed. D-Bus initialization passed, but a clean VM shutdown is not installer success. Its core3 pins are preserved as reviewed evidence; do not treat it as a tested core5 installer. See FRESH-INSTALL-BLOCKER.md.

## Existing configured station

Do not reset or initialize it. Arrange a reviewed maintenance window, confirm radio idle, stop radio services explicitly, make a consistent private backup, inspect the exact transaction and retain recovery access. Never expose configuration backups or use `--force-confnew`, unauthenticated APT or an indiscriminate system upgrade to bypass a guard.

Verified repository identity:

- Origin: `https://rf.ara.radio/allmode/apt/`
- Suite/component/architecture: `trixie` / `main` / `arm64`
- ARA primary fingerprint: `59DAB5C15B5F96D5660E0D94503AE6F5AD483087`
- Public key: `https://rf.ara.radio/allmode/apt/allmode-archive-keyring.gpg`
- Scoped keyring: `/etc/apt/keyrings/ara-allmode.gpg`

These identify the verified repository; they are not a complete trust/migration procedure. Verify the full fingerprint and use a dedicated `Signed-By` source, never `trusted=yes` or `--allow-unauthenticated`. Expired metadata must fail closed; do not disable expiry checks.

`apt update` refreshes indexes only. Actual installation is a separate reviewed transaction. Current core is `ara-allmode=0.8.0~beta9-5`; meter/addon/guard versions are separately pinned and must not be guessed to use the core suffix. Keep Asterisk ABI dependencies exact. Package source under `packaging/` describes maintenance guards, private backups and stopped-radio behavior.

Two reviewed existing-station upgrades passed with protected settings unchanged. That is not proof that arbitrary legacy appliances or fresh images work. Real Wi-Fi association, physical voice/RF acceptance and comprehensive phone/GPIO testing remain separate. Do not automatically resume RF after a failure or reboot.
