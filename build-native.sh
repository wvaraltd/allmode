#!/bin/bash
set -Eeuo pipefail
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python3 "$src/codec/build.py"
python3 "$src/codec/ambe2450/build.py"
python3 "$src/app/native_p25/build.py"
python3 "$src/app/native_ysf/build.py"
echo 'All four bundled native libraries built successfully.'
