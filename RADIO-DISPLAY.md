# Radio front panel — beta.9 display update

The Radio layout now presents confirmed connected destinations prominently in
its center, an active **network-mode** badge beside them, and the current active
speaker below. Programmed RX/TX frequencies and both PL tones are at the far
right. The separate `RF · FM` label describes the SHARI radio air interface;
DMR/YSF/etc. badges describe the linked network, not digital RF modulation.

The badge is derived from confirmed `active_connections`, not the menu's selected
or pending mode. Multiple confirmed network modes show `MULTI-LINK`. Disconnected
state shows `NO LINK` / `Not connected`, not a previous link or selected mode.

## Speaker evidence and limits

* The new authenticated read-only `/api/current-speaker` endpoint reads already
  accepted stream metadata and existing worker status. It does not link,
  transmit or resolve a station directory. Digital-only reads use worker status.
  For AllStar/EchoLink it shares a read-only xnode cache, at most one CLI query
  per second across browsers, replacing the former lstats query.
* Speaker identity is present only while actual decoded PCM playout is keyed,
  never merely after receiving a header or from a last-heard record. Existing
  receive idle watchdogs clear a lost stream within about 600 ms (native paths)
  or one second (D-STAR); this is active-transmission status, not speech/VAD.
* DMR/NXDN/P25 display a source **ID**, not an inferred callsign. YSF/M17/D-STAR
  use the source callsign carried by the already accepted stream. DVSwitch DMR
  uses the accepted TLV source ID. Metadata assignments do not change codec,
  packet-acceptance, network-transmit or audio-playout decisions.
* Status requires a live matching worker process, update age under 1.5 seconds,
  current requested mode and matching confirmed destination. Stop, disconnect,
  target change, process death or expiry removes the identity. Multiple active
  inputs, or active local RF without identity metadata, are explicitly unknown.
* AllStar/EchoLink use strict `rpt xnode` `RPT_ALINKS` K/U tokens correlated
  with ESTABLISHED rows and currently confirmed peers. A fresh keyed receiving
  link is labeled **Via node N** (or Via EchoLink node N), never as an originating
  user's callsign. A hub does not supply that identity through this telemetry.
  Malformed, missing, mismatched or stale telemetry gives an explicit unavailable
  note. Multiple keyed links cannot be attributed to one speaker. The cache
  coalesces concurrent clients, expires within 1.5 seconds, has no background
  thread, and performs no speaker polls once disconnected. Protocol evidence:
  [official ASL rpt_link.c](https://github.com/AllStarLink/app_rpt/blob/master/apps/app_rpt/rpt_link.c)
  and [rpt_cli.c](https://github.com/AllStarLink/app_rpt/blob/master/apps/app_rpt/rpt_cli.c).
* Browser speaker reads run every 750 ms only on the Radio home panel. Each GET
  has a 1.2-second timeout; identity expiry is at most 1.5 seconds, subtracting
  request latency. A separate 200 ms watchdog clears stale identity even when a
  response hangs. Visibility changes, disconnected state and newer connections
  invalidate in-flight results. Other layouts keep their existing behavior.

## Preserved controls and tests

Original and Sidebar layouts, large Favorites selection dial, explicit Connect,
RX/TX A/TX B gain controls, FIFO meter timing and the four phone tabs are retained.
MENU remains a local panel. Back returns to MENU; EXIT/Escape returns to the main
radio display and restores focus. No tuning, PTT or connect side effects are added.
On phones the frequency column remains right-aligned; the meter moves below the
center/frequency pair to prevent squeezing or horizontal overflow.

Validation: 252 application tests run, 250 pass and two pre-existing Unix-socket
integration tests are sandbox-skipped; nine Node regression scripts pass. New
Python tests trace accepted source metadata and stream clear for every supported
digital mode, unknown activity, TTL/future/dead-process/target-change/disconnect,
AllStar/EchoLink K/U, correlation, cache concurrency/expiry/disconnect and endpoint authentication. New JS tests cover actual
mode versus menu selection, stale/delayed/disconnected speaker, identity safety,
layout-only polling, both PL tones and panel Back/Exit/focus restoration.

Actual browser visual review uses the production assets with explicitly labeled
synthetic data, not a generated image. A local Chromium subprocess was blocked by
sandbox Unix-socket restrictions; no workaround was used. A supported cloud-browser review of the authorized static HTTPS fixture
passed desktop/390px visual layout, all three layouts, and MENU/Back/Close/focus.
Affected final AllStar/favorites/default checks remain a deployment gate. No live station was changed by this source task.

## Fresh-only standalone preset

The installer may create `/etc/allmode/install-profile.json` containing
`{"version":1,"dvswitch_dmr_default":true}` only after installing and qualifying
the local MMDVM_Bridge addon. If no draft or applied configuration/state exists
and the installed binary is present, the initial DMR wizard checkbox is checked.
The first station save retains it. Software remains the codec default; networks
stay disabled and IDs/passwords stay blank. Any existing draft, even an empty or
legacy one, or any applied state prevents the preset from changing that station.
Protected-state uncertainty is resolved through a fixed read-only helper; unknown
or unavailable helper state fails closed. Sixteen tests cover these conditions.
This does not change the browser's default Sidebar layout or saved layout choices.
