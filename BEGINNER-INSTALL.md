# ALLMODE — fresh Pi installation

Development release for a fresh **64-bit Debian 13 Raspberry Pi and SHARI HAT**.
This package installs the SA818S commissioning UI, Python/serial dependencies,
SSH, audio tools and ASL3. It updates Debian **before** installing these components.
It is not yet a complete digital-mode appliance: bundled legacy bridge sources
require separately installed codecs, services and network credentials. They are
not enabled by this installer. Serial programming was checked on a physical Pi/SHARI; RF acceptance testing is still required.

## Download and install

On the Pi, open a terminal. Connect it to the Internet first. Run:

```sh
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/wvaraltd/allmode.git
cd allmode
sudo bash install.sh
```

Alternatively download the repository ZIP with GitHub's **Code → Download ZIP**,
extract it, open a terminal in the extracted folder, and run `sudo bash install.sh`.
The script refreshes Debian package lists and runs `apt-get upgrade` interactively;
review apt's proposed changes. If `/var/run/reboot-required` exists, reboot and run
the same script again. Some Debian kernels do not create that marker: if apt
reports a kernel update, reboot before continuing hardware commissioning.
Never power off during an upgrade. Existing unowned Asterisk installations are
rejected. Installer reruns preserve drafts and radio records and back up old code.

## Open the interface

Open **https://YOUR_PI_IP/setup** on your LAN. HTTP and port 8787 redirect to
HTTPS; no SSH tunnel is required. The default login is admin / allmode. Retrieve the saved login on the Pi with
`sudo cat /var/lib/allmode/admin-login.txt`. Username: `admin`.

Copy `/etc/allmode/tls.crt` to each trusted device and compare its SHA256 fingerprint
with `openssl x509 -in /etc/allmode/tls.crt -noout -fingerprint -sha256` on the Pi.
Install that exact certificate in the device's trusted certificate store. Do not
bypass unexplained certificate warnings. Reserve the Pi IP in your router; an IP
change requires updating the LAN configuration and certificate. Certificate
validity is one year. Keep this service on your home LAN.

The initial setup page includes station identity, AllStar node/password,
EchoLink callsign/node/password/contact details, DMR ID/ESSID/color code, separate
BrandMeister and TGIF masters/hotspot passwords/talkgroups, and other reflectors.
Unused networks may stay disabled. Blank passwords preserve saved secrets.
Passwords are never returned to the browser. Configuration is stored privately
in `/var/lib/allmode/station-setup.json`. Saving collects configuration; service
activation and audio calibration are still required. Radio configuration is
linked directly from this page.

## If no serial port appears

Check HAT power and seating with power disconnected. The module band must match
the physical UHF/VHF hardware. A GPIO UART must be enabled and must not be used
by the Linux serial console. On images with `raspi-config`, use its serial-port
options: disable serial login, enable serial hardware, then reboot. On plain Debian,
use the boot configuration appropriate to your image; do not guess the config.txt
location or UART overlay (Pi models differ). Check `/dev/serial0`, `/dev/ttyAMA*`,
`ls -l /dev/serial*`, and `cat /proc/cmdline`. Remove the serial console only after
confirming SSH/local display recovery works. USB variants can use `/dev/ttyUSB*`.
The installer deliberately does not rewrite boot files on an unverified image.

## Program the SA818S

1. Attach a suitable antenna or dummy load and secure PTT so another controller
   cannot assert it. A software acknowledgement cannot establish electrical PTT state.
2. Refresh serial ports, select the SHARI port and check connection/firmware.
   Detection does not probe arbitrary devices automatically.
3. Choose the installed band, your permitted RX/TX frequencies and bandwidth.
   The Kits4Hams preset leaves frequencies blank intentionally. The sheet's
   446.1000 MHz is an example. Select tones or Off independently for RX and TX.
4. Save a local draft if desired. Validate and preview, review every setting,
   type PROGRAM and press **Program radio**. It never issues a PTT command.
5. An incomplete result may mean some settings were already written. Keep radio
   services stopped, correct the issue, then reprogram the complete set. There
   is no safe automatic rollback because prior hardware settings are unknown.
6. Last acknowledged settings are local records, not full hardware readback.
   Test frequency, deviation, CTCSS, reverse burst, audio and power-cycle retention
   on appropriate equipment before normal operation.

## Finish station setup

Keep the web service running. In Guided setup, save station identity and enabled
network credentials. Program the radio, then go to Review and press Apply. This
checks Asterisk using a non-radio channel. Next open Audio, confirm the controlled
RF setup and press Start radio for full system test. AllStar registration and
radio activation are shown separately from audio verification.

The initial SimpleUSB levels are RX 650, TX A 600, TX B 500. Calibrate your actual
unit using receive and transmit checks. Only mark audio verified after performing
those checks. External D-STAR AMBE host, UDP port and terminal can be entered in
Networks. Do not treat a successful codec handshake as an on-air audio test.
DMR and other digital adapter provisioning are not yet complete in this release.

## Diagnostics, maintenance and recovery

Use Enter maintenance before radio programming; the web page remains available.
Logs: `sudo journalctl -u allmode-system -u allmode-setup -u allmode-digital -n 100 --no-pager`.
Drafts and programming acknowledgements are in `/var/lib/allmode`. Private applied
configuration and configuration backups are in `/var/lib/allmode-system`, readable
only by root. Never publish these files: they contain station credentials.

Apply restores the previous configuration and private state when startup or a
later apply operation fails. An interrupted radio write cannot be rolled back:
review and program the full settings again. Files changed outside ALLMODE require
a fresh Apply. After a restart, digital connections must be selected again.

Code recovery remains manual. Stop ALLMODE and Asterisk, inspect the installer
code backup, restore `/opt/allmode`, then restart the services. Retain backups
until the new version is verified. Do not rerun the fresh installer over a working
station as an unattended update. A clean-install/reboot acceptance test remains
necessary before distributing this as a finished appliance.

## References and acceptance

The user's two Kits4Hams ASL3 v19+ v1.01 sheets establish the baseline. The AllNode
frequency-settings screenshot informed grouping and explicit connection/program
actions; its fixed volume 4 was not adopted over the SHARI sheet's volume 6.
No screenshot credentials or personal configuration are included.

- https://allstarlink.github.io/adv-topics/sa818modules/
- https://allstarlink.github.io/install/debian/install/
- https://github.com/0x9900/SA818 (protocol semantics: 38 CTCSS codes, filters 0=enabled, tail 0=closed)

Release acceptance still requires a clean Debian 13 arm64 install, reboot/UART
checks, HAT detection, interrupted-write recovery and measured RF/audio tests.
