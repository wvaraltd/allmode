#!/bin/bash
set -u
failed=0
check() { if "$@"; then echo "PASS: $*"; else echo "FAIL: $*"; failed=1; fi; }
check systemctl is-active --quiet allmode-system
check systemctl is-active --quiet allmode-setup
check systemctl is-active --quiet nginx
check systemctl is-enabled --quiet allmode-directories.timer
check curl --retry 10 --retry-connrefused --retry-delay 1 --fail --silent --output /dev/null http://127.0.0.1:8788/login
check nginx -t
check python3 /opt/allmode/check_codecs.py
echo 'Checks do not connect networks, program the radio, or transmit.'
exit "$failed"
