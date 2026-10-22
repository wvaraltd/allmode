#!/bin/bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo'; exit 1; }
apt-get install -y nginx openssl avahi-daemon
ip=$(ip -4 route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++)if($i=="src"){print $(i+1);exit}}')
[[ $ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]
host=$(hostname | tr "[:upper:]" "[:lower:]")
install -d -m 0750 -o root -g allmode /etc/allmode
if [[ ! -f /etc/allmode/auth.json ]]; then
  python3 - <<'PY'
import hashlib,json,secrets,os
from pathlib import Path
password='allmode'
salt=secrets.token_bytes(32)
Path('/etc/allmode/auth.json').write_text(json.dumps(dict(salt=salt.hex(),hash=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex())))
Path('/var/lib/allmode/admin-login.txt').write_text('Username: admin\nPassword: '+password+'\n')
os.chmod('/var/lib/allmode/admin-login.txt',0o600)
PY
fi
chown root:allmode /etc/allmode/auth.json
chmod 0640 /etc/allmode/auth.json
if [[ ! -f /etc/allmode/tls.key ]]; then
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 -keyout /etc/allmode/tls.key -out /etc/allmode/tls.crt -subj "/CN=$host.local" -addext "subjectAltName=DNS:$host.local,DNS:$host,IP:$ip" -addext 'basicConstraints=critical,CA:FALSE' -addext 'extendedKeyUsage=serverAuth'
  chmod 0600 /etc/allmode/tls.key
fi
cat > /etc/nginx/sites-available/allmode <<EOF
server {
    listen 80;
    listen 8787;
    server_name _;
    return 302 https://$ip\$request_uri;
}
server {
    listen 443 ssl;
    server_name $ip $host $host.local;
    ssl_certificate /etc/allmode/tls.crt;
    ssl_certificate_key /etc/allmode/tls.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 8k;
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
ExecStart=/usr/bin/python3 /opt/allmode/server.py --hardware --port 8788 --auth-file /etc/allmode/auth.json --public-origin https://$ip,https://$host.local,https://$host
EOF
nginx -t
systemctl daemon-reload
systemctl restart allmode-setup
systemctl enable --now nginx avahi-daemon
systemctl restart nginx
echo "Open https://$ip/setup or https://$host.local/setup"
echo 'Credentials: sudo cat /var/lib/allmode/admin-login.txt'
echo 'Local certificate: /etc/allmode/tls.crt. Trust it on your devices after verifying its fingerprint.'
openssl x509 -in /etc/allmode/tls.crt -noout -fingerprint -sha256
