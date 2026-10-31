#!/bin/bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run: sudo bash install.sh'; exit 1; }
source /etc/os-release
[[ ${ID:-} == debian || ${ID:-} == raspbian ]] && [[ ${VERSION_ID:-} == 13 ]] || { echo 'Debian 13 is required.'; exit 1; }
[[ $(dpkg --print-architecture) == arm64 ]] || { echo '64-bit arm64 is required.'; exit 1; }
[[ $(uname -m) == aarch64 ]] || { echo 'A 64-bit aarch64 kernel is required.'; exit 1; }
grep -q 'Raspberry Pi' /proc/device-tree/model || { echo 'Raspberry Pi hardware is required.'; exit 1; }
[[ ! -f /etc/allmode/beta-installed.json ]] || { echo 'Already installed. This is a fresh-install package, not an updater.'; exit 1; }
[[ ! -d /etc/asterisk || -f /var/lib/allmode/beta-install-started ]] || { echo 'Existing Asterisk installation found. Use a fresh SD card; existing nodes are not modified.'; exit 1; }
[[ ! -d /opt/allmode || -f /var/lib/allmode/beta-install-started ]] || { echo 'Existing ALLMODE installation found. Use a fresh SD card.'; exit 1; }
[[ $(df -Pk / | awk 'END {print $4}') -ge 2097152 ]] || { echo 'At least 2 GiB free space is required.'; exit 1; }
if [[ ! -f /var/lib/allmode/beta-install-started ]]; then
  if ss -H -ltn | awk '{print $4}' | grep -Eq ':(80|443|8787|8788)$'; then
    echo 'A required web port (80, 443, 8787, 8788) is occupied. Use a dedicated fresh image.'; exit 1
  fi
  for path in /etc/nginx/sites-available/allmode /opt/allmode-vocoder-prototype; do
    [[ ! -e $path ]] || { echo "Existing component at $path; use a fresh SD card."; exit 1; }
  done
fi
command -v raspi-config >/dev/null || { echo 'raspi-config is required for GPIO UART setup. Use a compatible Debian 13 Raspberry Pi image or install its supported raspi-config package first.'; exit 1; }
mem_kib=$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo)
if [[ $mem_kib =~ ^[0-9]+$ ]] && (( mem_kib < 600000 )); then
  echo 'Low-memory Pi: native builds run sequentially. Keep other applications closed; Zero 2 W software-vocoder performance still needs hardware testing.'
fi
echo 'Preflight passed. No configuration changed.'
