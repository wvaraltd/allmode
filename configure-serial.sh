#!/bin/bash
# Configure Raspberry Pi GPIO UART using the image's supported utility.
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
if [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi' /proc/device-tree/model; then
  echo 'GPIO serial setup skipped: not a Raspberry Pi. Connect the USB serial interface.'
  exit 0
fi
command -v raspi-config >/dev/null || { echo 'raspi-config is required to configure the Pi GPIO UART. Install it for this image, then rerun installation.' >&2; exit 1; }
before=$(raspi-config nonint get_serial_hw; raspi-config nonint get_serial_cons)
raspi-config nonint do_serial_cons 1
raspi-config nonint do_serial_hw 0
after=$(raspi-config nonint get_serial_hw; raspi-config nonint get_serial_cons)
[[ $after == $'0\n1' ]] || { echo 'Serial configuration could not be verified.' >&2; exit 1; }
if [[ $before != "$after" ]]; then
  install -d -m 0755 /var/lib/allmode
  printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)" > /var/lib/allmode/serial-reboot-required
fi
# The boot ID is nonsecret; the unprivileged setup service must read it.
if [[ -f /var/lib/allmode/serial-reboot-required ]]; then
  chmod 0644 /var/lib/allmode/serial-reboot-required
fi
echo 'GPIO UART enabled; serial login disabled.'
