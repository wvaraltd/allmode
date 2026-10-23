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
