# ALLMODE bootstrap v17 candidate — source-only, qualification pending

This bundle is a candidate reusable installer, not an assertion that a pristine
Debian image has completed the entire workflow. It has not been run against any
live server by its author. Do not publish it as production-ready before the gates
below are closed.

## Included

- `bootstrap.py`: read-only plan by default, explicit `--apply` for writes.
- `provision-fresh-profile.py`: copied unchanged from the parent packaging worker.
- `verify-dvswitch-loopback.py`: exact reviewed final source harness.
- `packaging/`: private extraction of independently reviewed immutable v4.
- `tests_bootstrap.py`: temporary-filesystem and fake-command orchestration tests.

## Intended usage after qualification

```
python3 bootstrap.py --mode fresh
sudo python3 bootstrap.py --mode fresh --apply
```

Fresh means a plain Debian 13 ARM64 machine with no existing ASL or station setup.
Existing ASL-only installations are not silently reinitialized. Existing ALLMODE
legacy beta8 users select `--mode legacy-migrate`, first use **System & maintenance
→ Stop radio services** after confirming RF idle. The bootstrap never automatically
stops an active transmitter and refuses active Asterisk/digital/MMDVM services.

The installer prints an SSH-tunnel command using the actual SSH destination when available (otherwise explains how to reuse your existing login/host) for initial localhost-only setup.
It does not silently expose an unauthenticated LAN listener. Existing migrated
TLS/authentication/port/comma-separated origins are preserved. No station number,
call sign, password, frequency, radio calibration, or network enablement is preset.

## Implemented sequence

1. Require Debian13 ARM64, healthy dpkg state, required system tools and radio-off
   state. Fresh mode refuses existing ASL and administrator Asterisk configuration.
2. Stop existing console/directory helpers, create a root-only backup and durable
   phase journal. No recursive ownership changes to station files.
3. Download HTTPS keys, verify pinned primary fingerprints, preserve matching
   installed trust, refuse conflicts, install only scoped Signed-By sources and
   DVSwitch package allowlist pin. `apt update` refreshes indexes only.
4. Install the guard in a **separate completed transaction** before upstream MB.
   Simulate every package install, reject removals/non-ALLMODE upgrades and wrong
   ASL ABI. Pin the entire simulated dependency closure, re-simulate it, authenticate downloads into a private cache, validate package/version/architecture, record archive hashes, and install with no additional downloads. Explicit APT authentication/insecure-repository restrictions override ambient permissive settings. Verify installed versions afterward.
5. On both fresh and legacy hosts, install persistent temporary **drop-in conditions** for Asterisk, ALLMODE digital and stock MMDVM, not base units or masks, before any APT changes. Record prior enablement and disable loaded radio units; retain all guards on failure/reboot. Audited ASL postinst moves base units and starts
   via systemd; the drop-in survives. Upstream enable is allowed without activation.
6. For supported legacy installs, translate known CLI options into a validated
   conffile. Move old code/base units/known LAN overrides into the private backup;
   keep station files untouched and retain RF socket cleanup. Never overlay old code.
7. Install exact core/meter/addon versions with force-confold, compare migrated
   station-state hashes, validate launcher config. Keep the guards through native validation and console startup; commit leaves Asterisk disabled and removes only unchanged owned guards. Prior radio enablement is deliberately NOT restored automatically.
8. Run the real native loopback harness as the service user using temporary private
   source-layout symlinks to installed root-owned code. Capture the report through
   nofollow file access and bind it to the installed binary. On fresh-only setups,
   call the strict preset helper; never call it on existing state.
9. Enable/start console/helper/directory timer only. Digital gets a future Asterisk
   dependency but is not started. Radio remains stopped for explicit commissioning.

## Verified here

`python3 -m unittest -v tests_bootstrap`: 26 tests pass, covering distinct users,
legacy-origin preservation, unsafe CLI rejection, nofollow writes, exact solver
closure, no unrelated upgrades/removals, exclusive bootstrap locking, private journal/command diagnostics, clean migration preserving
state/RF cleanup, guard-first ordering, failure phases, and no migration preset/RF
start. These are unit/simulation tests—not a live package transaction.

The copied parent helper's own tests are not duplicated in this file. Parent reports
its seven tests plus existing packaging tests passed. Actual Pi native codec,
official MMDVM loopback, exact-meter ABI load and stock-MMDVM condition qualification
are separate writer evidence; this bootstrap does not imply a new live execution.

## Gates before public-ready

- Independent review of this new orchestration and trust/bootstrap surface.
- Effective conditions are checked through the documented systemd D-Bus
  `Conditions` signature `a(sbbsi)`, requiring an exact non-trigger, non-negated
  missing-path condition before any test start. Unknown JSON/type/rows fail closed.
  The sole writer confirmed the exact JSON representation read-only on the actual
  Pi: GetUnit type `o` with a one-element path list, Conditions type `a(sbbsi)`
  with the expected false/false missing-path row. No start was performed for that read.
  Interface reference: https://www.freedesktop.org/software/systemd/man/257/org.freedesktop.systemd1.html
- Run a complete disposable fresh ARM64 transaction and a disposable legacy fixture,
  including an interrupted configure/recovery run. Current failure handling keeps a
  private backup/journal and never auto-resumes RF, but is not an automatic rollback.
- The candidate now retargets only known legacy absolute enablement links from
  `/etc/systemd/system/allmode-*` to installed `/usr/lib/systemd/system/allmode-*`,
  preserving other custom links and recording the changes privately. Its fixture
  test passes; verify this normalization on a disposable legacy image.
- Ensure signed repository is published with these exact version candidates before
  offering the commands. Existing user deployment is independent and must not wait.
- Distribute the entire bundle through an authenticated release channel. Pinned key
  fingerprints do not authenticate an arbitrarily downloaded bootstrap script itself.

The script does not run upstream shell installers, `apt upgrade`, `apt-key`,
`trusted=yes`, or unauthenticated APT. Upstream MB's own authenticated package
postinst still downloads some host data over plain HTTP and replaces host-file
links; those known side effects are backed up and must remain disclosed.

Command output is recorded only in root-only `commands/*.json` beneath the private
backup directory, including failed APT/native validation diagnostics. Failure messages
point to the exact log rather than printing potentially sensitive system output.

If initial verifier tooling is missing, the bootstrap obtains pinned `gpg`/CA
packages only through existing authenticated system repositories before third-party
trust setup. The same removal/unrelated-upgrade restrictions still apply.

## Resuming an interrupted attempt

A failure prints one exact `sudo python3 .../bootstrap.py --resume /var/backups/ara-allmode/bootstrap-... --apply` command. Use the identical authenticated bundle: the resume journal binds hashes of bootstrap, fresh helper, native harness, and launcher. Generated SSH commands preserve the actual SSH server port, including nondefault ports. The root-only journal records original configuration/state metadata, before-backup, intended package versions/closures, download hashes, moved-code inode/device ledger, and phases. Resume refuses unrecorded pending packages and does not run blanket `dpkg --configure -a`. Moves and known enablement-link rewrites are idempotent. Existing package-managed installations are rejected by **initial** legacy mode and directed to packaged maintenance instead. Resume is simulated locally; interruption recovery on a real disposable ARM64 guest remains a qualification gate, not an asserted result.

Initial console instructions explain SSH-authenticated localhost access, direct Guided setup (no separate console-login creation with the fresh default), review/apply, and explicit activation. There is no new default station identity or credential. Existing `/etc/nginx` and its no-store cache/security headers are untouched. After an existing proxy update, reload the browser page (hard reload if needed); fresh setup uses only SSH localhost access, not invented TLS or widened listeners.

## v7 narrow upstream-key retrieval correction

The actual fresh guest v5 stopped safely when the upstream repository-bootstrap
.deb download returned HTTP403 / Cloudflare1010. No client disguise or bypass is
used. v7 retains the reviewed v6 changes and replaces ONLY that download/extraction
with the SAME publisher's public key at its official GitHub repository, pinned to
commit32d4dd6af2baf2d313ce15b6b27023cfafcc8030 and SHA256
af652e0473ed95d73345a8c6912cb38ac29001b67c30ea767fa99fa7cbd5e9de.
URL: https://raw.githubusercontent.com/AllStarLink/asl-apt-repos/32d4dd6af2baf2d313ce15b6b27023cfafcc8030/allstarlink.gpg
Plain standard HTTPS urllib GET succeeded and its2265bytes exactly matched the
key extracted from the previously verified official repo .deb. The existing
F2AF416869932ABB39E165E5409D50181BD84509 fingerprint check and scoped APT trust are
unchanged. No public key is rehosted by ARA, no key is rotated/generated, and no
User-Agent substitution or denied-endpoint retry is implemented. All package pins
remain beta9-1; this is not qualification of any later source patch.

## v8 source-only prerequisite correction — HOLD for qualification

Actual v7 pristine Debian 13 ARM64 qualification failed at the system-bus
transport, not at unit loading. The read-only guest diagnostic reported:
`Failed to connect to system scope bus via local transport: No such file or directory`.
Its journal recorded `guard-installed` as the failed phase and
`radio_resumed: false`; the stock unit and protective drop-ins existed.
No fresh-install, replay, LAN, or physical-radio success is claimed.

v8 first probes the same system-scope D-Bus transport with systemd's Peer.Ping,
before application stops, backup/payload changes, or guard operations. An
already functioning bus is left untouched. If no bus is available and neither
`dbus` nor `dbus-broker` is installed, existing signed Debian APT sources are
refreshed and the reviewed Debian Trixie `dbus=1.16.2-2` prerequisite is installed.
The normal exact private-cache transaction, authenticated metadata, no-removal,
no unrelated upgrades, and a dedicated new-dependency allowlist apply. This
installs the standard system message-bus service; it does not start radio
services or install a desktop/session bus. Package post-install activation must
produce a working system bus, verified again before continuing. Existing
installed but unavailable bus services are not restarted, enabled, or repaired
silently: installation stops with an actionable diagnostic.

Debian package provenance: https://packages.debian.org/trixie/dbus .
The bootstrap requires existing valid signed Debian repositories; it does not
replace their keys or trust unsigned packages. A missing pinned version or any
required non-ALLMODE upgrade is a safe refusal, not permission to broaden the
transaction. Core/ASL/DVSwitch pins, the effective-guard GetUnit logic, and all
commissioning policies remain unchanged from v7.

The 32 local tests are mocked lifecycle/command tests, not a second guest run.
A new disposable signed Debian ARM64 qualification window is required. Old
v7 journals remain bound to v7 executable hashes: do not use v8 `--resume` on
them or edit the binding. Use a separate pristine guest for v8 qualification;
recovery of an existing failed installation needs an explicitly reviewed plan.

## v9 final package-pin separation

v9 adds only the authorized final package-pin split to the v8 prerequisite
correction: core `0.8.0~beta9-2`, addon and guard each `0.8.0~beta9-1`, and
unchanged exact-ABI meter `0.8.0~beta9+abid1486d408855`. These supersede the
historical v8 statement that all package pins remain unchanged.
`release-manifest.json` records the independently verified public core artifact
SHA256, byte count, source commit, and URL. Package installation remains through
the signed APT chain with exact versions, not by executing a downloaded URL.
The local suite now has 34 tests including exact package-set solver assertions
and system-bus-before-guard ordering for both fresh and legacy flows. These
remain mocked tests; no new guest, live install, replay, LAN, or hardware test
was performed. No GPIO, optional-tool, auth, trust, or GetUnit behavior is added
by v9. Future guest fixtures must explicitly repin their expected core version
and completion-marker path; old fixture results do not qualify v9.

## v10 narrow final-core repin

v10 changes only the core pin from beta9-2 to beta9-3 and its accompanying
manifest/test expectations. Addon/guard revision1, meter, missing-bus fix,
GetUnit, and all lifecycle policies remain unchanged. This supersedes the
historical v9 core-version paragraph above. Exact final core SHA256:
94a6af758239f996714b8d82a685c582b647d4205f315070c19883dd8c686ba2.
34 mocked source tests pass; no new guest acceptance is claimed by this bundle.

## v11 proven static-D-Bus activation correction

The actual v10 guest installed signed dbus successfully, but package output
explicitly said its static/disabled service was not started. Peer.Ping then
failed because no system-bus socket existed; no guards had been changed.
v11 therefore explicitly starts dbus.socket and dbus.service immediately after
its own successful new-only authenticated dbus transaction, then repeats the
same Peer.Ping. It never enables, unmasks, or restarts a bus; already installed
but unavailable bus services still cause refusal. Existing available buses
remain untouched. This supersedes the earlier expectation that postinst alone
activates the fresh system bus. 36 local mocked tests pass. Core3 and every
other package pin, radio safeguards, and GetUnit logic remain unchanged.
Actual fresh qualification is still required under the parent's bounded window.

## v12 source-only condition proof contract — NOT guest-qualified

Actual v11 passed the new D-Bus stage but failed safely because attempting to
start the real stock MMDVM unit pulled in its upstream netcheck dependency.
This candidate no longer starts the real stock daemon or netcheck to test its
guard. Core remains beta9-3; this is not a newer-core installer qualification.

A small shared `guard_proof.py` validates actual stock D-Bus effective Conditions,
loaded/inactive/MainPID0, exact root-owned fragment/drop-in hashes and boot ID.
It then creates a random uniquely named administrator-owned runtime unit with
only the same exact nontrigger/nonnegated absent-marker condition,
DefaultDependencies=no, Type=oneshot, null output, and ExecStart=/usr/bin/false.
There are no upstream Requires/After/Wants or Install/autostart entries.
The harmless command MUST remain unexecuted. Proof requires ConditionResult=no,
positive ConditionTimestampMonotonic, exact failed-condition result -1,
inactive/MainPID0 and zero ExecMainStartTimestampMonotonic. Actual stock state,
configuration and boot ID must remain identical before/after proof and cleanup.

Runtime file operations are administrator-owned/no-follow/FD-relative. Existing
unit/file/drop-in collisions refuse; calls have 20-second subprocess bounds.
Finally cleanup stops only the uniquely owned proof unit after exact-byte
verification, rechecks bytes, unlinks that one file, fsyncs and reloads. Changed
or untrusted files are never stopped/deleted; cleanup errors fail closed and
leave the exact path in private command diagnostics for administrator review.

The root-owned private guard-proof.json explicitly labels evidence as harmless
condition semantics, NOT real-stock startup history. Fresh-profile helper now
requires --guard-proof, rejects stale/different-boot/config/state or incomplete
evidence, and independently resamples actual stock state before processing and
immediately before atomic profile publication. It no longer requires or fakes
the stock ConditionResult. Failed proof/binding never publishes a fresh marker.
The shared module is included in the resume bundle identity; old journals must
not be edited/rebound to this new candidate.

56 local tests exercise mocked lifecycle, cleanup/collision/tampering/refusal,
no MB/netcheck starts, proof freshness/current-config/boot binding and existing
profile preservation. They do not establish real systemd qualification. If
systemd garbage-collects the skipped proof unit before its evaluation evidence
is read, the candidate refuses rather than treating defaults as proof; no new
persistent-D-Bus framework or dependency bypass has been added. Unrecognized
unit paths (including unexpected symlink ancestors) also refuse safely.

No new VM, live Pi, upstream dependency repair, network action, or artifact
publication has occurred. A separately authorized disposable qualification and
independent source review are required before use. Earlier frozen archives and
failed-guest evidence remain unchanged.

## v13 bounded-file-read review correction

v13 changes only the shared proof reader and its regression tests: O_NONBLOCK
prevents FIFO opens from blocking before type checks; reads are capped at
1MiB+1; descriptor and named-file identity/metadata are checked before/after
reading so growth or replacement refuses. 58 mocked tests pass including real
local FIFO rejection and injected growth/path replacement. Frozen v12 remains
unchanged. This is still source-only, core3-pinned and not guest-qualified.

## v14 new-proof CLI reader correction

The helper's newly introduced --guard-proof input now uses the hardened shared
reader directly (trusted root-owned ancestors, nofollow/nonblocking open,
bounded read and descriptor/named identity revalidation). It no longer passes
new proof data through the inherited binary/native-report reader. Two helper
CLI integration tests confirm FIFO and replacement rejection before any
provisioning/marker write; total60 local tests pass. Frozen v13 is unchanged.
Existing native-binary/report reader behavior is outside this narrow change.
This remains historical core3 source-only; no new guest or live execution.

## v15 narrow core6 repin — source-only

v15 changes only the core pin and accompanying manifest/test expectations to
0.8.0~beta9-6, SHA256
719c4b349399020343ed839963162f1be621b7f390ca67cbd40c8de5dea4a5d8,
1064472 bytes, source a3cbe328dacaf172653db1f4c332d9b66cfd609d.
Addon/guard revision1 and exact-ABI meter are unchanged; all reviewed v14 guard
proof/helper code is byte-identical. This supersedes historical core3 pin notes
above; it does not relabel any older guest result. Actual v11 failed safely.
60 mocked tests pass. No new guest/window/upload/execution was performed.
Signed public availability was pending sole-writer confirmation when frozen;
the manifest URL is the intended exact artifact location, not a success claim.

## v16 normalized-package matrix — qualification pending

Actual v15 correctly refused writable package-owned systemd guard directories.
New independently built package revisions normalize root/directory/file modes:
core beta9-7, addon/guard beta9-2, meter same exact ABI with Debian revision -1.
The release manifest records all four authoritative native package SHA256s.
Application source remains a3cbe328dacaf172653db1f4c332d9b66cfd609d.
Proof/helper code and its strict permission checks remain byte-identical to v14;
no chmod workaround, weaker group trust, or guard bypass is added.
60 source tests pass; native mode validators passed per sole builder, while
independent artifact review/publication and actual fresh acceptance were pending
at freeze. No launch or new execution authorization is implied by this archive.

## v17 retained harmless proof — actual GC evidence, runtime validation pending

GCv4's real disposable run showed the skipped probe's positive condition result
was lost between separate queries: timestamp became0 and GetUnit later reported
not loaded. Its daemon reload completed13.28s, below unchanged production20s.
v17 retains strict positive timestamp/failed-condition/no-execution evidence.
A second unique owned harmless oneshot anchor uses DefaultDependencies=no,
RemainAfterExit=yes, ExecStart=/usr/bin/true and ONLY After=<owned probe>.
It has no Wants/Requires or references to stock/netcheck/radio services. Starting
the anchor first retains the probe reference without enqueueing its start;
then the probe is explicitly tested. Anchor active/exited/MainPID0 evidence is
bound into the semantic proof report. Actual stock snapshots remain unchanged
before/after/cleanup. Both exact root-owned files are verified before startup;
cleanup independently stops/removes only matching owned files and reloads,
failing closed on collision/tampering/cleanup errors. Timeouts remain20s.
The shared semantic_probe function is the exact production implementation
available for isolated guest testing while actual radio units stay masked.
63 local tests pass; no new guest/full-fresh success is implied by this freeze.
All package pins and application code remain unchanged from v16.
