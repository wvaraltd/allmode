# Standalone DVSwitch DMR — beta.9 candidate

## What runs where

All codecs and bridging run on this Pi. Network masters/reflectors are radio
network destinations, **not external codec servers**.

* Native D-STAR, DMR, YSF V/D2, NXDN4800, clear P25 Phase 1, and M17 Codec2 3200
  remain local software paths. No TETRA, YSF wide, NXDN9600 or encrypted P25 claim.
* Optional **local DVSwitch DMR** route:
  `ASL chan_usrp ↔ loopback PCM ↔ ALLMODE software AMBE2450 ↔ loopback TLV ↔ local MMDVM_Bridge ↔ DMR master`.
* The existing external AMBE option is mutually exclusive with this software
  route. Select native transport before hardware. A missing/failed selected
  codec stops the path; it never starts a remote codec or silently falls back.
* Analog_Bridge's decoder fallback is not a universal software encoder.
  Analog_Bridge and MD380 emulator are not needed by this custom software route.

## Configuration and ownership

The authenticated DMR identity form has **Use local DVSwitch for DMR**. Saving
is not connecting. Disconnect before applying. Existing station drafts gain
this field as false, preserving native routing on upgrade. A qualified fresh-install marker may preset it when no draft or applied station
exists; otherwise testers can choose it after installing and qualifying the
official local package. No network is enabled by that preset. See RADIO-DISPLAY.md.

The root setup helper writes `/var/lib/asterisk/allmode/dvswitch.json` with
version 1 and `dmr_transport` `native` or `dvswitch`. Missing file means native.
Administrator-configurable loopback UDP defaults:

| Key | Default | Owner |
|---|---:|---|
| usrp_receive | 34001 | ALLMODE DVSwitch PCM worker |
| usrp_send | 32001 | local Asterisk chan_usrp |
| tlv_receive | 31100 | ALLMODE DVSwitch worker (also existing local controls) |
| tlv_send | 31103 | supervised MMDVM_Bridge TLV importer |

Ports must be distinct, unprivileged, and not reserved by another local mode. Apply saved settings after changing
ports so chan_usrp is regenerated consistently. The fixed private ASL adapter
node is an internal implementation identifier, never a user's AllStar node.
Station callsign, IDs, ESSID, master, password, talkgroup, color code, radio
frequency and hardware settings come from existing generic station forms.
No real station ID, LAN address, credentials or coordinates are shipped.
Generated MB station coordinates are neutral, not the upstream example QTH.

`allmode-digital` owns both children, exclusively, on explicit Connect. It writes
private mode-0600 configs under `/var/lib/asterisk/allmode/DMR/`, using official
package templates under `/opt/MMDVM_Bridge`. Never run the stock
`mmdvm_bridge.service` simultaneously. No separate adapter service is enabled.
The TLV export socket is ephemeral: each received voice datagram is checked
against the supervised MB process's `/proc` socket inodes, not a guessed source
port. USRP accepts only its configured local Asterisk source port. Existing
local tag-5 controls remain same-host loopback controls, not an Internet API.

## Failure handling

* Bind/codec/config failures stop the route. No SO_REUSEPORT or competing owner.
* Outgoing frames are grouped 3×9 bytes/60 ms; incoming PCM is paced at 20 ms.
* Queues are bounded; no backlog burst after scheduler stalls.
* Half-duplex input is blocked until PTT is released after a receive collision.
* Missing TX input ends at 500 ms; missing RX input unkeys after 600 ms.
* Both directions have a 180-second duration guard; received private calls are
  rejected. Last PCM gets its 20 ms interval before unkey.
* Supervisor process failure clears readiness; worker status ages out. Network
  login is distinct from codec readiness and from actual voice acceptance.
* Shutdown releases TX/RX and drops buffered voice. Reconnect explicitly after
  a codec-selection/process failure; never surprise-key or auto-fallback.

## Deployment and rollback gates

1. Back up the existing package, `/etc/allmode`, `/etc/asterisk`, and ALLMODE
   state/calibration/favorites. Record installed ASL/Asterisk ABI and service state.
2. Disconnect, enter the authorized maintenance/stopped-radio state. Do not run
   the fresh installer over an existing station.
3. Verify signed official DVSwitch package metadata and a clean Debian 13 ARM64
   dependency solve. Official Trixie bootstrap currently uses the **Bookworm**
   DVSwitch repository; do not import Bookworm system libraries to force it.
4. Install the minimal `mmdvm-bridge` package (and its `dvswitch-base` dependency)
   with stock unit not started; deploy the reviewed beta.9 package. Never run a
   remote installer blindly. No signing/trust or DNS changes are part of source.
5. Preserve upgrade native selection. First qualify the new route with loopback
   mock peers on ARM64, with no public network/RF, then choose DVSwitch via UI.
6. Measure CPU/RSS, audio underruns and service recovery on the 512 MB Zero 2 W.
   Actual RF/public-network voice tests need the operator's safe test context.
7. Rollback: stop the new route, restore prior package and saved configs/state,
   preserve current ASL runtime/module ABI, select native, then restore only the
   previously authorized service state. Never enable RF as a rollback side effect.

## Evidence and reproducibility

`app/dvswitch_reference/` contains upstream **test templates**, wire fixtures and
provenance, not live configs. Production copies templates from the installed
official package and overwrites identity, endpoints and Info defaults.

Run `bash build-native.sh`, `python3 run-tests.py`, all root `test_*.cjs`, and
`node --check app/web/operator.js`. Tests cover two distinct generic station
configs, missing-file native upgrade default, custom-port preservation, strict
frames, actual loopback sockets, process socket ownership, native codec payloads,
watchdogs, collision latch and shutdown. Full suite preserves beta.8 regression
coverage. The separate official-binary/mock-Homebrew harness verifies the real
MB boundary in both directions without public networking. AMD64 results are not
ARM64 performance evidence, codec-quality certification or physical RF acceptance.
