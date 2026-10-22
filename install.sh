#!/bin/bash
# Fresh Debian 13 arm64 Raspberry Pi commissioning installer.
set -Eeuo pipefail
trap 'echo "Installation stopped at line $LINENO. Fix the reported error and rerun sudo bash install.sh. Radio services remain stopped." >&2' ERR
[[ $EUID == 0 ]] || { echo 'Run: sudo bash install.sh'; exit 1; }
source /etc/os-release
[[ ${ID:-} == debian || ${ID:-} == raspbian ]] && [[ ${VERSION_ID:-} == 13 ]] || { echo 'Debian 13 required.'; exit 1; }
[[ $(dpkg --print-architecture) == arm64 ]] || { echo '64-bit arm64 required; use a 64-bit Debian 13 image.'; exit 1; }
grep -q 'Raspberry Pi' /proc/device-tree/model || { echo 'This installer targets Raspberry Pi hardware only.'; exit 1; }
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -f $src/sa818_hardware.py && -d $src/web ]] || { echo 'Extract the entire package before installing.'; exit 1; }
[[ ! -d /etc/asterisk || -f /var/lib/allmode/installer-started ]] || { echo 'Existing Asterisk installation found. This fresh-Pi installer will not replace it.'; exit 1; }
echo 'Step 1: Updating Debian package lists and installed packages first.'
kernel_before=$(dpkg-query -W -f='${Package} ${Version}\n' 'linux-image*' 'raspberrypi-kernel*' 2>/dev/null || true)
apt-get update
# Keep apt interactive for configuration changes and review of the upgrade transaction.
apt-get upgrade
kernel_after=$(dpkg-query -W -f='${Package} ${Version}\n' 'linux-image*' 'raspberrypi-kernel*' 2>/dev/null || true)
if [[ -f /var/run/reboot-required || $kernel_before != "$kernel_after" ]]; then
  echo 'Debian requires a reboot. Run sudo reboot, reconnect, then rerun sudo bash install.sh.'
  exit 0
fi
echo 'Step 2: Installing Python, serial support, SSH, audio tools and ASL3.'
apt-get install -y ca-certificates curl python3 python3-serial openssh-server alsa-utils
install -d -m 0755 /var/lib/allmode
touch /var/lib/allmode/installer-started
# Mask before installing ASL packages so default configuration cannot key a radio.
systemctl mask --now asterisk.service
tempdir=$(mktemp -d)
trap 'rm -rf -- "$tempdir"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 https://repo.allstarlink.org/public/asl-apt-repos.deb13_all.deb -o "$tempdir/asl-repos.deb"
dpkg -i "$tempdir/asl-repos.deb"
apt-get update
apt-get install -y asl3
systemctl mask --now asterisk.service
id allmode >/dev/null 2>&1 || useradd --system --home /var/lib/allmode --shell /usr/sbin/nologin allmode
usermod -a -G dialout allmode
install -d -o allmode -g allmode -m 0750 /var/lib/allmode
chown allmode:allmode /var/lib/allmode
install -d -m 0755 /opt/allmode
if [[ -f /opt/allmode/server.py ]]; then
  tar -czf "/var/lib/allmode/code-backup-$(date +%Y%m%d-%H%M%S).tar.gz" -C /opt allmode
fi
install -m 0644 "$src"/*.py /opt/allmode/
cp -R "$src/web" /opt/allmode/
install -m 0644 "$src/BEGINNER-INSTALL.md" /opt/allmode/
# Dedicated shared lock directory; existing RSSI reader uses the same env override.
install -d -o allmode -g allmode -m 0750 /var/lib/allmode/locks
cat > /etc/systemd/system/allmode-setup.service <<'UNIT'
[Unit]
Description=ALLMODE SA818S hardware commissioning
After=network.target
Conflicts=asterisk.service
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
systemctl enable --now ssh allmode-setup
curl --fail --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:8787/api/hardware >/dev/null
dpkg-query -W -f='${Package} ${Version}\n' python3 python3-serial asl3 > /var/lib/allmode/installed-packages.txt
echo 'Installation complete. Asterisk is masked; no RF programming has occurred.'
echo 'On your PC open a terminal: ssh -L 8787:127.0.0.1:8787 YOUR_PI_USER@YOUR_PI_IP'
echo 'Keep that terminal open, then browse http://127.0.0.1:8787/hardware'
echo 'Read BEGINNER-INSTALL.md for UART setup, node credentials, audio calibration and recovery.'
