# ALLMODE

SA818S hardware configuration for a fresh Debian 13 arm64 Raspberry Pi with SHARI
HAT. Development release **0.5.1**. Inspired by the user's AllNode interface
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
- Legacy ALLMODE console and bridge source, disabled in the fresh-install path.

## Tested and untested

62 software tests pass locally, including serial mocks, failure handling, validation,
HTTP routes and origin checks. JavaScript syntax checked. Installed on a Debian 13 Raspberry Pi 4 with a SHARI HAT. SA818 serial
commands were acknowledged by the physical module. No on-air RF acceptance
tests were performed. Full digital-mode provisioning,
live-console deployment, automated UART changes and network registration are not
completed by this package. This is a commissioning development release, not a
finished all-mode radio appliance.

```sh
python3 -m unittest discover -v
```

Use your own station credentials. No user screenshots, secrets, audio recordings,
or previous deployment configuration are included in this repository.
