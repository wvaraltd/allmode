# ARA ALLMODE 0.8.0-beta.1 — installation guide

This is the complete source-based application installer for a **fresh Raspberry Pi running 64-bit Debian 13 with a SHARI HAT**. Use a spare SD card for beta testing. This download is not an SD-card image and does not install Debian itself. Internet access is needed for Debian/ASL packages and public directories. Existing AllStar/ALLMODE installations are rejected; this release is not an updater.

## What is included

- Guided station setup, owner password, HTTPS and local-name discovery.
- ASL3/Asterisk, serial support, USB audio tools and system services.
- SHARI/SA818 configuration and explicit radio programming.
- AllStar and EchoLink configuration; separate network identities and credentials.
- Native D-STAR, DMR, YSF V/D2, P25 Phase 1, NXDN4800 and M17 Codec2 3200 adapters.
- Bundled D-STAR/AMBE2450, P25 and YSF source compiled on the Pi; Debian Codec2.
- Digital directories and scheduled refresh, live audio sliders and meters, local audio tests.
- Startup checks, source checksums, dependency inventory and a limited diagnostics report.

FCS and other profiles are not included as working beta modes. Network connection and audio support are limited to the profiles above. External AMBE is optional for D-STAR/DMR; a shared device serves only one of those modes at a time. Software is the default. Your network accounts, callsign, IDs, station passwords and radio settings must be entered by you.

## 1. Prepare the Pi

Install a 64-bit Debian 13 image appropriate to your Pi. Enable SSH or use a local keyboard/display. Connect Ethernet for initial installation and make sure the Pi can access the Internet. Use a reliable power supply and leave at least 2 GiB of free space after installing Debian. A 16 GiB or larger SD card is suggested. Installation requires an account with sudo access.

Keep the old working SD card intact. Shut down and disconnect power before fitting the SHARI HAT. Attach a suitable antenna or dummy load before radio testing.

## 2. Copy and verify the download

Copy `allmode-0.8.0-beta.1.tar.gz` and its matching `.sha256` file to the Pi, using your preferred file-transfer program. In a terminal in that folder, run:

```sh
sha256sum -c allmode-0.8.0-beta.1.tar.gz.sha256
tar -xzf allmode-0.8.0-beta.1.tar.gz
cd allmode-0.8.0-beta.1
sudo bash install.sh --check
sudo bash install.sh
```

The archive must report OK. Obtain both files from the release maintainer; hashes detect file changes, but are not a digital signature. The installer checks its internal file manifest before doing any installation. The optional `--check` performs platform, storage and conflict checks without changing configuration.

Review the Debian upgrade when prompted. If the installer asks for a reboot, run `sudo reboot`, reconnect, return to the extracted folder and run `sudo bash install.sh` again. The script also supports retry after an interrupted initial installation. A completed installation is rejected on rerun to protect configured stations. Keep the extracted folder unchanged until installation completes.

The installer downloads ASL's Debian 13 repository package over HTTPS, then uses apt for ASL and OS dependencies. Bundled codec sources are pinned by their manifests. Apt package versions depend on the repositories at installation time and are recorded in `/etc/allmode/installed-packages.txt`; this is not an offline or bit-for-bit OS image.

## 3. Open setup and claim ownership

At completion the installer prints `https://YOUR_PI_IP/setup` and `https://YOUR_HOSTNAME.local/setup`. Use either address on the same LAN. If the local name fails, use the IP address. Reserve that IP in your router.

The Pi generates its own TLS certificate. Compare its fingerprint with:

```sh
sudo openssl x509 -in /etc/allmode/tls.crt -noout -fingerprint -sha256
```

Trust that exact certificate on your device, or verify the fingerprint before accepting a browser exception. The certificate is valid for one year and covers the current hostname/IP. An IP or hostname change requires certificate/LAN configuration renewal. Do initial claiming on your trusted LAN; the first person to reach an unclaimed station can claim it. Keep this beta console off the public Internet.

Choose your owner password (at least eight characters); username is `admin`. There is no shared default web password. Your Debian SSH login remains the account/password you created when preparing Debian.

## 4. Configure the station

1. Enter callsign and station identity.
2. Enter your AllStar node/password if used, and credentials for networks you enable. Leave unused networks off. Blank password fields preserve previously saved secrets.
3. Open Hardware. Select the actual radio band and serial port, check the connection, and enter your permitted frequencies, tones and other settings. Preview before explicitly programming. This never happens automatically during installation.
4. If a GPIO UART is missing, disable serial login and enable serial hardware using your image's supported configuration method, then reboot. Verify SSH/local-console recovery first. Pi boot-file locations and overlays differ; the installer does not guess them.
5. Use guided Review/Apply. Initial application uses a non-radio channel. Then explicitly start the radio for controlled audio tests.
6. Calibrate RX/TX levels on your actual hardware. Sliders apply live with readback confirmation. Meters show audio level, not calibrated RF deviation.
7. Select a permitted test destination and verify transmit and receive in each enabled mode. A login/connection alone does not prove usable voice audio.

SA818 acknowledgements and saved settings are not full hardware readback. An interrupted programming operation may leave partial changes; return to maintenance and explicitly reprogram the complete intended settings. Check frequency, tones, deviation and power-cycle retention with appropriate equipment.

## 5. Report beta results

Run the passive checks after installation and after reboot:

```sh
sudo bash /opt/allmode/healthcheck.sh
python3 /opt/allmode/diagnostics.py > allmode-beta-diagnostics.json
```

The diagnostics report includes versions and service state, not station files or journals. Review before sharing. Include the beta version, Pi model, SHARI band, mode/destination, exact steps, expected result, actual result and whether it survives reboot. Use `BETA-TEST-CHECKLIST.md`.

Private station files and backups in `/var/lib/allmode`, `/var/lib/allmode-system` and `/var/lib/asterisk/allmode` can contain credentials. Do not attach those directories. For local troubleshooting: `sudo journalctl -u allmode-system -u allmode-setup -u allmode-digital -n 100 --no-pager`; inspect/redact before sharing logs.

## Recovery

An installation failure prints the failing line. Resolve the reported problem and rerun the same extracted installer. Asterisk is masked before ASL installation and remains stopped until guided setup activates it. Do not run the installer as an upgrade over a working node.

For a failed beta after activation, use Enter maintenance in the console, or stop radio operation with `sudo systemctl stop allmode-digital asterisk`. The web console remains available. A full return to the pre-beta system is: shut down, remove power and restore your untouched original SD card. No automatic OS/package downgrade or radio-setting rollback is provided. Software config Apply has its own private backups, but cannot reverse a physical radio write.

## Validation boundary

See `VALIDATION.md` for checks actually performed. This candidate still needs installation on a spare freshly flashed card, reboot/UART verification and tester RF/audio acceptance. Do not interpret source/build tests as fresh-install or on-air certification.

ASL installation reference: https://allstarlink.github.io/install/debian/install/
