# FIFO-only live audio meter

Recovered unchanged production C writer, Python collector and browser meter from the working 2026-10-27 meter release. The unrelated experimental Asterisk core-buffering patch is deliberately excluded.

The dedicated write-only `.ameter` format uses nonblocking atomic FIFO writes instead of the stock signed-linear recording buffer. It rejects ordinary files, malformed frames and backpressure. Collector cadence is 50 ms; browser cadence is 100 ms, with stale detection and independent two-second peak hold. No audio recording is retained by this meter.

`install-meter.sh` installs the exact `asl3-asterisk-dev` version matching the installed `asl3-asterisk`, builds and runs the synthetic FIFO regression, then compiles and installs only `format_allmode_meter.so`. Existing Asterisk binaries and formats remain unchanged. It does not start Asterisk or transmit. Future Asterisk upgrades require rebuilding against matching headers; a missing/unloadable format is reported unavailable rather than silently using the buffered format.

Linux checks: `gcc -O2 -Wall -Wextra -Werror native-meter/test_fifo.c -o /tmp/allmode-meter-test && /tmp/allmode-meter-test`; `python3 native-meter/test_meter.py`; `node native-meter/test_browser.cjs`. The isolated Asterisk harness requires a separately compiled self-test module in its isolated modules directory and matching installed headers/binary; it disables channel/network modules. Do not load the self-test build into a live station.

Historical synthetic Pi measurement was 98.9 ms onset, not live RF latency. Current Zero 2 W performance remains unverified until measured on that target.
