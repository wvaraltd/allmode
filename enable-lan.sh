#!/bin/bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo'; exit 1; }
source "$(dirname -- "${BASH_SOURCE[0]}")/package-manager.sh"
allmode_apt install -y nginx openssl avahi-daemon
ip=$(ip -4 route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++)if($i=="src"){print $(i+1);exit}}')
[[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]
host=$(hostname | tr "[:upper:]" "[:lower:]")
install -d -m 0750 -o root -g allmode /etc/allmode
# Owner chooses the password during first-run setup; existing installs retain theirs.
if [[ ! -f /var/lib/allmode/auth.json ]]; then
  if [[ -f /etc/allmode/auth.json ]]; then
    install -o allmode -g allmode -m 0600 /etc/allmode/auth.json /var/lib/allmode/auth.json
  else
    printf '{"unclaimed":true}\n' > /var/lib/allmode/auth.json
  fi
fi
chown allmode:allmode /var/lib/allmode/auth.json
chmod 0600 /var/lib/allmode/auth.json
if [[ ! -f /etc/allmode/tls.key ]]; then
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 -keyout /etc/allmode/tls.key -out /etc/allmode/tls.crt -subj "/CN=$host.local" -addext "subjectAltName=DNS:$host.local,DNS:$host,IP:$ip" -addext 'basicConstraints=critical,CA:FALSE' -addext 'extendedKeyUsage=serverAuth'
  chmod 0600 /etc/allmode/tls.key
fi
cat > /etc/nginx/sites-available/allmode <<EOF
server {
    listen 80;
    listen 8787;
    server_name _;
    return 302 https://\$server_addr\$request_uri;
}
server {
    listen 443 ssl;
    server_name $ip $host $host.local;
    ssl_certificate /etc/allmode/tls.crt;
    ssl_certificate_key /etc/allmode/tls.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 17m;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy same-origin always;
    location / {
        proxy_pass http://127.0.0.1:8788;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto https;
    }
}
EOF
# Only replace nginx's package default site on this dedicated fresh appliance.
if [[ -L /etc/nginx/sites-enabled/default ]]; then unlink /etc/nginx/sites-enabled/default; fi
ln -sfn /etc/nginx/sites-available/allmode /etc/nginx/sites-enabled/allmode
install -d /etc/systemd/system/allmode-setup.service.d
cat > /etc/systemd/system/allmode-setup.service.d/lan.conf <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/allmode/server.py --managed --hardware --port 8788 --auth-file /var/lib/allmode/auth.json --lan-proxy --public-origin https://$host.local,https://$host
EOF
nginx -t
systemctl daemon-reload
systemctl restart allmode-setup
systemctl enable --now nginx avahi-daemon
systemctl restart nginx
echo "Open https://$ip/setup or https://$host.local/setup"
echo 'First boot: choose your owner password in setup. Username: admin.'
echo 'Local certificate: /etc/allmode/tls.crt. Trust it on your devices after verifying its fingerprint.'
openssl x509 -in /etc/allmode/tls.crt -noout -fingerprint -sha256
