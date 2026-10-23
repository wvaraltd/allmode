#!/bin/bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || exit 1
install -d -m 0700 /var/lib/allmode-system
install -d -o allmode -g allmode -m 0750 /var/lib/asterisk/allmode /var/lib/allmode/locks
# Both services share this lock; creating it as allmode avoids a root-owned lock file.
[[ -e /var/lib/allmode/locks/radio-serial.lock ]] || install -o allmode -g allmode -m 0600 /dev/null /var/lib/allmode/locks/radio-serial.lock
cat > /etc/systemd/system/allmode-system.service <<'UNIT'
[Unit]
Description=ALLMODE restricted station configuration service
After=network.target
[Service]
ExecStart=/usr/bin/python3 /opt/allmode/system_service.py
Environment=ALLMODE_SERIAL_LOCK_DIR=/var/lib/allmode/locks
RuntimeDirectory=allmode-system
RuntimeDirectoryMode=0755
UMask=0077
Restart=on-failure
ProtectHome=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/allmode-digital.service <<'UNIT'
[Unit]
Description=ALLMODE on-demand digital adapters
After=asterisk.service
PartOf=asterisk.service
[Service]
User=allmode
Group=allmode
WorkingDirectory=/opt/allmode
ExecStartPre=/usr/bin/rm -f /var/lib/asterisk/allmode/digital-modes.json
ExecStart=/usr/bin/python3 /opt/allmode/dmr_worker.py
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/lib/asterisk/allmode
UMask=0077
[Install]
WantedBy=asterisk.service
UNIT
# The console must remain reachable while Asterisk is running or stopped.
sed -i '/^Conflicts=asterisk.service$/d' /etc/systemd/system/allmode-setup.service
install -d /etc/systemd/system/allmode-setup.service.d
cat > /etc/systemd/system/allmode-setup.service.d/runtime.conf <<'UNIT'
[Unit]
After=allmode-system.service
Requires=allmode-system.service
[Service]
ReadWritePaths=/var/lib/asterisk/allmode
UNIT
# Preserve the existing IP addresses, TLS auth and port.
for file in /etc/systemd/system/allmode-setup.service /etc/systemd/system/allmode-setup.service.d/lan.conf; do
  if [[ -f $file ]] && ! grep -q -- '--managed' "$file"; then sed -i 's/server.py --hardware/server.py --managed --hardware/' "$file"; fi
done
install -d -m 0755 /opt/allmode-dmr/hosts
# Directory data only; downloaded over HTTPS from Pi-Star's maintained host lists.
for pair in DCS_Hosts:DCSHosts DPlus_Hosts:REFHosts; do
  upstream=${pair%%:*}; localname=${pair##*:}
  temp=$(mktemp)
  if curl --fail --silent --show-error --location --max-time 30 "https://www.pistar.uk/downloads/${upstream}.txt" -o "$temp"; then
    install -m 0644 "$temp" "/opt/allmode-dmr/hosts/${localname}.txt"
  else
    echo "Could not refresh $localname; existing directory retained."
  fi
  rm -f "$temp"
done
systemctl daemon-reload
systemctl enable allmode-digital
systemctl enable --now allmode-system
systemctl restart allmode-setup
