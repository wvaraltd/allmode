# Installation and maintenance status

## Published core9 installer (2026-11-02)

Use the [published installer instructions](https://github.com/wvaraltd/allmode/blob/725fda65e4f4cf67d3c1cfd66a65624cf5cc1e23/downloads/core9-installer-v20/README.md), not the retired source entrypoints or the historical v17 candidate in this tree. The immutable [complete installer bundle](https://raw.githubusercontent.com/wvaraltd/allmode/818b54bffe9d95a2cea2f131f6c505dc753a5ea0/downloads/core9-installer-v20/allmode-core9-installer-v20-r2.tar.gz) is 77,760 bytes; SHA-256 `85f84e9f538190e6bcc13bd302b03f9fa84fe8c94f682e2ffae4d13b1191832d`. Verify the whole archive before extraction and follow its INSTALL.md. The inner installer is v20-r2 and pins public `ara-allmode=0.8.0~beta9-9`; no package, signing key or runtime is changed by this documentation update.

Qualification is deliberately version-specific: full pristine core9 installation and a separate 512 MiB/no-swap run passed with v18; actual controlled interruption, reboot and same-bundle resume passed with v19; final v20-r2 passed both synthetic legacy identities and an actual targeted fresh-readiness check on a preserved successful v18 install. That last check executes the final readiness function, not a new full v20 installation. These are inherited transaction results plus final-function evidence, not exhaustive power-loss or arbitrary legacy compatibility.

Fresh mode is for Debian 13 ARM64 with an existing administrator/SSH login, not a configured station. Initial access is an SSH tunnel to localhost; radio remains off until explicitly commissioned. A 512 MiB VM is not physical Zero 2 W/GPIO/RF/audio or phone/LAN qualification. Real Wi-Fi association remains untested. Public core9 excludes private beta10 DTMF/readback, native feedback prototype3 and neural voice assets prototype5.

The recorded signed repository metadata expires **2026-11-15 21:24:42 UTC**. No automatic renewal is configured. Keep signature and Valid-Until checks enabled; stop on expired metadata and obtain properly renewed signed metadata rather than bypassing checks. Keep the exact extracted bundle for documented same-bundle recovery.

## Existing configured station

Do not reset or initialize it. Arrange a reviewed maintenance window, confirm radio idle, stop radio services explicitly, make a consistent private backup, inspect the exact transaction and retain recovery access. Never expose configuration backups or use `--force-confnew`, unauthenticated APT or an indiscriminate system upgrade to bypass a guard.

Verified repository identity:

- Origin: `https://rf.ara.radio/allmode/apt/`
- Suite/component/architecture: `trixie` / `main` / `arm64`
- ARA primary fingerprint: `59DAB5C15B5F96D5660E0D94503AE6F5AD483087`
- Public key: `https://rf.ara.radio/allmode/apt/allmode-archive-keyring.gpg`
- Scoped keyring: `/etc/apt/keyrings/ara-allmode.gpg`

These identify the verified repository; they are not a complete trust/migration procedure. Verify the full fingerprint and use a dedicated `Signed-By` source, never `trusted=yes` or `--allow-unauthenticated`. Expired metadata must fail closed; do not disable expiry checks.

`apt update` refreshes indexes only. Actual installation is a separate reviewed transaction. Current core is `ara-allmode=0.8.0~beta9-9`; meter/addon/guard versions are separately pinned and must not be guessed to use the core suffix. Keep Asterisk ABI dependencies exact. Package source under `packaging/` describes maintenance guards, private backups and stopped-radio behavior.

Two reviewed existing-station upgrades passed with protected settings unchanged. That is not proof that arbitrary legacy appliances or fresh images work. Real Wi-Fi association, physical voice/RF acceptance and comprehensive phone/GPIO testing remain separate. Do not automatically resume RF after a failure or reboot.
