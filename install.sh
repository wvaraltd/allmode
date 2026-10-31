#!/bin/bash
# Fresh Debian 13 arm64 Raspberry Pi commissioning installer.
set -Eeuo pipefail
trap 'echo "Installation stopped at line $LINENO. Fix the reported error and rerun sudo bash install.sh. Do not activate radio services until installation completes." >&2' ERR
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$src"
source "$src/package-manager.sh"
[[ $# == 0 || ( $# == 1 && $1 == --check ) ]] || { echo "Usage: sudo bash install.sh [--check]"; exit 1; }
sha256sum --check --quiet SHA256SUMS
bash "$src/preflight.sh"
[[ ${1:-} != --check ]] || exit 0
# Mark only this installer as owning an incomplete fresh installation.
install -d -m 0755 /var/lib/allmode
touch /var/lib/allmode/beta-install-started
echo 'Step 1: Updating Debian package lists and installed packages first.'
kernel_before=$(dpkg-query -W -f='${Package} ${Version}\n' 'linux-image*' 'raspberrypi-kernel*' 2>/dev/null || true)
allmode_apt update
# Keep apt interactive for configuration changes and review of the upgrade transaction.
allmode_apt upgrade
kernel_after=$(dpkg-query -W -f='${Package} ${Version}\n' 'linux-image*' 'raspberrypi-kernel*' 2>/dev/null || true)
if [[ -f /var/run/reboot-required || $kernel_before != "$kernel_after" ]]; then
  echo 'Debian requires a reboot. Run sudo reboot, reconnect, then rerun sudo bash install.sh.'
  exit 0
fi
echo 'Step 2: Installing Python, serial support, SSH, audio tools and ASL3.'
allmode_apt install -y ca-certificates curl python3 python3-serial python3-bitarray openssh-server alsa-utils build-essential libcodec2-1.2 network-manager iproute2 logrotate
install -d -m 0755 /var/lib/allmode
touch /var/lib/allmode/installer-started
# Mask before installing ASL packages so default configuration cannot key a radio.
systemctl mask --now asterisk.service
bash "$src/configure-serial.sh"
tempdir=$(mktemp -d)
trap 'rm -rf -- "$tempdir"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 https://repo.allstarlink.org/public/asl-apt-repos.deb13_all.deb -o "$tempdir/asl-repos.deb"
allmode_apt install -y "$tempdir/asl-repos.deb"
allmode_apt update
allmode_apt install -y asl3
systemctl mask --now asterisk.service
bash "$src/install-meter.sh"
echo 'Step 3: Building bundled digital codecs from pinned source.'
bash "$src/build-native.sh"
id allmode >/dev/null 2>&1 || useradd --system --home /var/lib/allmode --shell /usr/sbin/nologin allmode
usermod -a -G dialout allmode
install -d -o allmode -g allmode -m 0750 /var/lib/allmode
chown allmode:allmode /var/lib/allmode
install -d -m 0755 /opt/allmode
if [[ -f /opt/allmode/server.py ]]; then
  tar -czf "/var/lib/allmode/code-backup-$(date +%Y%m%d-%H%M%S).tar.gz" -C /opt allmode
fi
cp -R "$src/app/." /opt/allmode/
install -d -m 0755 /opt/allmode-vocoder-prototype/current
cp -R "$src/codec/." /opt/allmode-vocoder-prototype/current/
chown -R root:root /opt/allmode /opt/allmode-vocoder-prototype
chmod -R a+rX /opt/allmode /opt/allmode-vocoder-prototype
install -m 0644 "$src/healthcheck.sh" "$src/diagnostics.py" /opt/allmode/
install -m 0644 "$src/BEGINNER-INSTALL.md" /opt/allmode/
# Dedicated shared lock directory; existing RSSI reader uses the same env override.
install -d -o allmode -g allmode -m 0750 /var/lib/allmode/locks
cat > /etc/systemd/system/allmode-setup.service <<'UNIT'
[Unit]
Description=ALLMODE SA818S hardware commissioning
After=network.target
[Service]
User=allmode
Group=allmode
SupplementaryGroups=dialout
WorkingDirectory=/opt/allmode
Environment=ALLMODE_SERIAL_LOCK_DIR=/var/lib/allmode/locks
ExecStart=/usr/bin/python3 /opt/allmode/server.py --hardware --port 8787 --public-origin http://127.0.0.1:8787
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/lib/allmode
UMask=0077
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable allmode-setup
systemctl enable --now ssh
bash "$src/install-runtime.sh"
bash "$src/enable-lan.sh"
install -d -m 0755 /var/lib/allmode/directories /opt/allmode-dmr/hosts
install -m 0644 "$src/allmode-directories.service" "$src/allmode-directories.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now allmode-directories.timer
systemctl start --no-block allmode-directories.service
install -d -m 0755 /etc/logrotate.d
cat > /etc/logrotate.d/allmode <<'LOGROTATE'
/var/lib/asterisk/allmode/*.log /var/lib/asterisk/allmode/*/*.log {
    weekly
    rotate 3
    maxsize 5M
    missingok
    notifempty
    copytruncate
    compress
    su allmode allmode
}
LOGROTATE
bash "$src/healthcheck.sh"
# Confirm the web service before marking installation complete.
curl --fail --retry 10 --retry-connrefused --retry-delay 1 --connect-timeout 5 --max-time 15 http://127.0.0.1:8788/login >/dev/null
python3 - <<'PYMANIFEST'
import json,subprocess
from pathlib import Path
packages=subprocess.check_output(['dpkg-query','-W','-f=${Package} ${Version}\n'],text=True)
Path('/etc/allmode/installed-packages.txt').write_text(packages)
version=json.loads(Path('release.json').read_text())['version']
Path('/etc/allmode/beta-installed.json').write_text(json.dumps({'version':version,'status':'installed; RF acceptance pending'}))
PYMANIFEST
echo 'Installation complete. Asterisk remains masked; no RF programming has occurred.'
echo 'Open the setup address shown above after any required reboot. No SSH tunnel is required.'
echo 'Read BEGINNER-INSTALL.md for certificate trust, credentials, UART setup and audio calibration.'
# This is deliberately last: failed installation must never offer a reboot.
source "$src/finish-install.sh"
uart_pending=$(python3 - "$src/app" <<'PYREBOOT'
import sys
sys.path.insert(0, sys.argv[1])
from sa818_hardware import uart_reboot_required
result = uart_reboot_required('/var/lib/allmode')
print('true' if result is True else 'false' if result is False else 'unknown')
PYREBOOT
)
allmode_offer_reboot "$uart_pending"
