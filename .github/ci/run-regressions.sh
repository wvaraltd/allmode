#!/usr/bin/env bash
# Run only in a disposable Linux checkout, never against a configured station.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
if [[ $(id -u) -eq 0 ]]; then
  echo 'Run regressions as an ordinary user, never sudo.' >&2
  exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD/app:$PWD/codec"
export ALLMODE_VOCODER_ROOT="$PWD/codec"
export ALLMODE_ENABLE_RSSI=0

echo '::group::Source manifest and shell syntax'
python3 verify-release.py
for script in ./*.sh .github/ci/*.sh; do bash -n "$script"; done
for script in packaging/preinst packaging/postinst packaging/prerm packaging/postrm; do sh -n "$script"; done
echo '::endgroup::'

echo '::group::Wi-Fi HTTP/helper, managed status whitelist, meter recovery'
# Explicit names fail if a regression test disappears; no broad hardware suite.
python3 -m unittest -v test_wifi_http_contract test_wifi_flow test_xnode_allowlist test_meter_recovery test_audio_meter
python3 .github/ci/test_managed_status_contract.py
# Deterministic collector behavior only, not the wall-clock cadence benchmark.
python3 native-meter/test_meter.py \
  MeterTests.test_pcm MeterTests.test_latest_window_and_stream_independence \
  MeterTests.test_stale MeterTests.test_bad_node_and_missing_format \
  MeterTests.test_backlog_not_fresh
temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT
gcc -O2 -Wall -Wextra -Werror native-meter/test_fifo.c -o "$temp/test_fifo"
"$temp/test_fifo"
echo '::endgroup::'

echo '::group::JavaScript syntax and mocked browser regressions'
for script in app/web/*.js; do node --check "$script"; done
# Current root tests cover shared-meter peak/error UI. The historical native-meter
# browser fixture predates those DOM nodes; it is not this regression gate.
for required in test_wifi_flow.cjs test_shared_meter.cjs test_meter_error_visibility.cjs test_startup_recovery.cjs; do
  test -f "$required"
done
for test in ./test_*.cjs; do node "$test"; done
echo '::endgroup::'

echo '::group::Generic packaging and safe lifecycle contracts'
python3 -m unittest discover -s packaging/tests -v
python3 -m unittest discover -s tests -v
echo '::endgroup::'
