# ALLMODE — fresh Pi installation

Development release for a fresh **64-bit Debian 13 Raspberry Pi and SHARI HAT**.
This package installs the SA818S commissioning UI, Python/serial dependencies,
SSH, audio tools and ASL3. It updates Debian **before** installing these components.
It is not yet a complete digital-mode appliance: bundled legacy bridge sources
require separately installed codecs, services and network credentials. They are
not enabled by this installer. No physical Pi or RF acceptance testing is claimed.

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

On the Pi, `hostname -I` shows its IP address. On your Windows PC open PowerShell:

```sh
ssh -L 8787:127.0.0.1:8787 YOUR_PI_USER@YOUR_PI_IP
```

Replace the uppercase placeholders with your Pi login and address. Authenticate
using your Pi password or SSH key and leave this window open. In your PC browser,
open **http://127.0.0.1:8787/hardware**. The SSH tunnel supplies authentication and
encryption; the application itself listens only on the Pi loopback interface.
Do not expose port 8787 through a reverse proxy without authentication.

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

## Finish AllStar setup

After programming, run `sudo systemctl disable --now allmode-setup`. Keep PTT
secured while configuring your own callsign, node ID/password and SimpleUSB using
`sudo asl-menu`. Credentials are not supplied in this package. Follow the ASL3
menu for your actual USB audio device. The Kits4Hams sheet's starting values are
RX 650, TX A 600, TX B 500, boost off, emphasis/de-emphasis off, PL filter off,
PTT ground, carrier usbinvert, CTCSS from no, and delays zero. Calibrate your unit.
Only after reviewing RF settings and node configuration, run:

```sh
sudo systemctl unmask asterisk
sudo systemctl enable --now asterisk
```

That starts a radio-capable service; use a controlled test setup. The main ALLMODE
console remains a simulator unless separately configured for a live node. The
fresh installer does not activate legacy digital bridges or copy old station data.
This is a complete installer for **hardware commissioning and ASL3 packages**;
network registration, live-console deployment and digital-mode provisioning remain
separate work, not completed features.

## Diagnostics, maintenance and recovery

`sudo journalctl -u allmode-setup -n 100 --no-pager` shows serial and server logs.
Drafts, last programming attempt and last observed device are in `/var/lib/allmode`.
The page retains 60 session events; persistent service logs use system journald's
retention. `installed-packages.txt` records installed dependency versions.
For later programming, stop Asterisk and all bridges, secure PTT, then
`sudo systemctl start allmode-setup`. Never restart radio services mid-write.

To stop the web service: `sudo systemctl disable --now allmode-setup`.
For code rollback, stop it, inspect a `code-backup-*.tar.gz`, restore `/opt/allmode`
from that archive and restart. Code rollback does not restore radio settings.
To update code, stop the service, `git pull --ff-only`, review changes and rerun
the installer. Do not use this development installer to upgrade a working node.

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
