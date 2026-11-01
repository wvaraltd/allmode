# ALLMODE offline packaging prototype

This directory builds packages; it does NOT install them or publish a repository.
The current structural test build is amd64 and cannot validate Raspberry Pi codec
loading, RF safety, performance or ASL integration. Do not install it on a Pi.

## Builder

On a disposable **Debian 13 ARM64** builder with existing build-essential, Python,
matching ASL runtime/dev/modules and required Debian libraries:

```
python3 build-package.py --release --source /path/to/final-reviewed-source --output /path/to/artifacts --version 0.8.0~beta9-1
python3 build-meter.py --source /path/to/final-reviewed-source --output /path/to/artifacts
python3 prepare-repo.py --output /path/to/repository /path/to/artifacts/*.deb
```

Build dependencies are provisioned explicitly by the builder administrator, not
inside maintainer scripts. No upstream DVSwitch/ASL binaries are redistributed.
Final standalone integration and verified upstream package dependency names must
be incorporated before marking a release ready. Production contact/copyright and
release license approval must replace staging metadata before publication.

The source build checks pinned vendor manifests. Every staged ELF is checked
against native dpkg architecture; release mode refuses amd64. ARM emulation or
cross compiler presence alone is not a native ARM performance test. The meter
package depends on the exact matching ASL Asterisk runtime/module version and its
build never invokes apt. An ASL upgrade requires a separately rebuilt compatible
meter package; do not circumvent dependency resolution with force flags.

## Lifecycle and state

* Code is root-owned under existing `/opt/allmode` paths for source compatibility.
* `/etc/allmode/service.json` is a dpkg conffile. Dpkg preserves locally modified
  content using its normal conffile prompts; do not use `--force-confnew`.
* Runtime settings are not package payload: `/var/lib/allmode`,
  `/var/lib/allmode-system`, `/var/lib/asterisk/allmode`, `/etc/asterisk`.
* Web runs as allmode, localhost-bound with strict systemd filesystem protection.
  Root helper is beta8's existing Unix-socket API, not arbitrary shell delegation.
  Its existing privilege surface still requires the integration/security review.
* Package scripts never run apt, mask services, start, enable or restart radios,
  rewrite station settings, touch UART boot configuration or perform OS upgrades.
* Active station services block install/upgrade before payload replacement.
  Operator confirms idle, stops safely and creates a consistent private backup.
* Old `/etc/systemd/system` base units block migration rather than silently shadow
  packaged units; reviewed operator migration is described separately.
* Removal retains persistent station data and account. Explicitly stop/disable
  services before removal; automatic uninstall is not a radio-safety workflow.

The fresh default console is accessible via localhost/SSH tunnel only. Remote LAN
use requires user-selected hostname/IP, TLS and the existing authentication setup;
no hostname, station number, callsign, credential or public talkgroup is preset.
User onboarding remains the authority for station-specific defaults and calibration.

## Validation scope

`python3 -m unittest discover -s tests -v` exercises launcher config, distinct user
configs, invalid input, shell-script lifecycle simulation, active-service refusal,
repeat configure behavior and native ARM release guard. Privileged commands are
mocked; this is NOT a real dpkg install, real Asterisk upgrade or hardware test.

Before publication: native ARM64 build; disposable Debian13 ARM64 fresh install;
second-user onboarding; coherent beta8 upgrade fixture including credentials,
calibration, frequencies, favorites, RF isolation; failed configure/rollback;
real meter ABI load; all three layouts; idle CPU; local DVSwitch roundtrip;
reboot and explicit start policy; authenticated signed APT install and update.

## Simple controlled updates

`apt update` only refreshes indexes and is safe to run without radio downtime.
For an installed station, first use the System & maintenance → Stop radio services action **after
confirming RF is idle**. A single package-maintenance command then handles console
stop, private backup, version-pinned ALLMODE-only installation, config check and
restores previously running console/helper services:

```
sudo /usr/libexec/ara-allmode/maintenance-upgrade.py --version REVIEWED_VERSION --apply
```

Omit `--apply` to inspect the planned transaction. Any Asterisk still running,
unknown dependency changes, removals, or ABI mismatch fails closed. The script
never stops a running transmitter automatically or resumes RF after upgrade.
A meter update requires an explicitly selected matching `--meter-version`.
This deliberately does not advertise unattended `apt upgrade` while transmitting.

The helper downloads authenticated exact package versions and uses dpkg to install
only those verified files, so a second apt solver cannot upgrade unrelated dependencies.
It refuses pending dpkg state; a missing dependency leaves a recoverable stopped
station rather than installing extra packages. A durable root-only journal records
backup/install/config/service phases and before/after versions.
