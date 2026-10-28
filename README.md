# ALLMODE — beta installer downloads

**0.8.0-beta.1 full application installer** for a fresh Debian 13 arm64 Raspberry Pi + SHARI HAT. Internet required. Use a spare SD card. Existing installations are rejected.

## Quick install

On a fresh Debian 13 arm64 Pi, paste this into its terminal:

```sh
curl -fsSLO https://raw.githubusercontent.com/wvaraltd/allmode/main/get-allmode.sh && sudo bash get-allmode.sh
```

The script downloads the pinned beta, checks the archive and file checksums, and starts the installer. If asked to reboot, reboot and run the same command again. If curl is missing, first run `sudo apt-get update && sudo apt-get install -y curl`. Keep the terminal open for installation prompts. Finish station setup at the web address printed by the installer.

- [Download TAR.GZ installer](https://github.com/wvaraltd/allmode/raw/refs/heads/main/downloads/allmode-0.8.0-beta.1.tar.gz) · [SHA-256](downloads/allmode-0.8.0-beta.1.tar.gz.sha256)
- [Download ZIP installer](https://github.com/wvaraltd/allmode/raw/refs/heads/main/downloads/allmode-0.8.0-beta.1.zip) · [SHA-256](downloads/allmode-0.8.0-beta.1.zip.sha256)
- [Beginner installation guide](downloads/0.8.0-beta.1/BEGINNER-INSTALL.md)
- [Validation and remaining acceptance tests](downloads/0.8.0-beta.1/VALIDATION.md) · [Tester checklist](downloads/0.8.0-beta.1/BETA-TEST-CHECKLIST.md)

Includes the full application and native codec source, dependency installation, guided setup, HTTPS, diagnostics and digital adapters. 125 application/codec tests passed; native builds passed on ARM64. Fresh-card installation, reboot and RF/audio acceptance remain required. This is a beta candidate, not an SD-card image or an updater.

**Use the named download packages above for this beta.** The repository-root source below is the older development version; cloning main or using GitHub’s automatic Source code archive does not install the new beta.

<details>
<summary>Older development source documentation</summary>

# ALLMODE

SA818S hardware configuration for a fresh Debian 13 arm64 Raspberry Pi with SHARI
HAT. Development release **0.6.3**. Inspired by the user's AllNode interface
screenshots, with hardware defaults from their Kits4Hams ASL3 settings sheets.

## Install

```sh
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/wvaraltd/allmode.git
cd allmode
sudo bash install.sh
```

The installer **updates Debian first**, stops if a kernel update/reboot is needed,
then installs Python, pyserial, SSH, audio tools and ASL3. Asterisk remains masked
until you finish commissioning. Read [the beginner guide](BEGINNER-INSTALL.md)
for browser access, UART setup, credentials, radio programming and recovery.

## Included

- Independent RX/TX frequencies and CTCSS, band, bandwidth, squelch, volume,
  reverse burst, emphasis and high/low-pass filters.
- Serial candidate detection, explicit connection/firmware test, local draft,
  validated command preview, explicit programming and bounded logs.
- Stopped-service checks, no PTT commands, strict acknowledgements and persistent
  incomplete-write records. Saved values are never presented as hardware readback.
- Direct LAN HTTPS access with password login and a local certificate.
- First-run station, AllStar, EchoLink, BrandMeister, TGIF and reflector settings.
  Credentials are saved privately; live service activation remains a separate step.
- Live AllStar console, explicit radio activation, audio calibration controls, and external D-STAR AMBE server settings.
- Configuration backups and rollback on failed Apply; configuration drift detection; web access stays available during maintenance.

## Tested and untested

74 software tests pass locally, including serial mocks, rollback, validation,
HTTP routes and origin checks. Deployed on Debian 13 Raspberry Pi 4 with a SHARI
HAT; AllStar registration and the SimpleUSB channel were observed live. SA818
programming was acknowledged by the module; these acknowledgements are not full
hardware readback. Physical RF/audio acceptance remains outstanding. External
D-STAR testing is deferred at the operator's request. DMR and other digital
adapter provisioning remain incomplete; enabling an unprovisioned network is
blocked. This is a development release, not a finished all-mode appliance.

```sh
python3 -m unittest discover -v
```

Use your own station credentials. No user screenshots, secrets, audio recordings,
or previous deployment configuration are included in this repository.

## Guided setup

Station identity → network choices → radio programming → review and Apply → explicit radio activation → audio checks. Each step saves independently. Apply first validates the Asterisk node without opening the radio channel. Radio activation requires acknowledged programming and operator confirmation. The web console remains available during maintenance. Audio verification is recorded only after the operator checks receive and transmit audio.

Apply backs up all managed Asterisk files, private applied settings and runtime settings. A failed startup or later apply operation restores those files. Changes made outside ALLMODE invalidate the applied fingerprint. Service startup clears previous digital connection requests. Code updates and recovery are still manual; configuration rollback does not undo radio programming.

## Station interface

Version 0.6.3 provides consistent navigation across the console, guided setup and radio pages; a live node/registration/radio status strip; last-acknowledged radio settings and audio-verification summaries; day/night themes; and responsive forms. The layout draws on operator workflows in AllNode and the ClearNode documentation, implemented independently. Features without working adapters remain unavailable.

Version 0.6.3 simplifies navigation to five destinations, adds audio adjustment buttons and restore controls, displays unsaved/saved/applied state, and reports temperature, disk usage, uptime and kernel on the review step.

Three operating designs are available through the on-page design selector: Radio console, Radio app and Technical. The choice is saved in the browser and changes presentation only. Direct links use `/?look=console`, `/?look=app` and `/?look=technical`. All three use the same live APIs; visual comparison does not test RF or digital audio.

</details>
