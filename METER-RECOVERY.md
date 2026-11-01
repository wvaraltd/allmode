# Passive meter restart recovery

The observed failure was not a calibration error or a zero TX level. Asterisk
restarted while the helper retained an old MixMonitor identity and FIFO readers.
With app_mixmonitor unloaded, the next list command raised before local cleanup;
startup/module loading was never reached again.

The helper now releases its own stale identity/descriptors, reloads the existing
passive meter modules through its normal attachment path, and retries failed
attachment no more than once per second. Cleanup runs even when the CLI fails.
Stop/adoption requires an exact current channel listing with the meter's reserved
full mixed/rx/tx filename triple and full ID token (actual CLI reports
extensionless paths; the full .ameter triple is also recognized); sequential ID reuse by a foreign
recording is tested and rejected. Listing and stopping are separate CLI calls,
not an atomic transaction against a concurrent Asterisk restart.

The Radio layout now exposes the meter status/error text. The freshness watchdog
retains the underlying error until a successful response clears it; stale samples
still never display as live. RX means radio-to-network PCM, TX means
network-to-radio PCM. Readings remain audio dBFS before radio hardware, not
calibrated RF deviation.

Validation: six new restart/ownership/failure tests; six native collector tests;
12 JavaScript regression programs. Combined application suite: 291 run, 289
passed, two existing sandbox Unix-socket skips. Synthetic pipe TX produced the
expected -6 dBFS, without radio or network transmission. The pre-existing
controller-to-helper status contract also remains unchanged.

This source includes the separately reviewed Wi-Fi selection flow, whose five
synthetic keyfiles passed actual nmcli 1.52.1 offline normalization as ordinary
UID 1000 with daemon bus access disabled. No AP setup or real Wi-Fi switch is
performed by installation. Deploy only as a new immutable package revision;
preserve previous package bytes, configuration, calibration and saved profiles.
