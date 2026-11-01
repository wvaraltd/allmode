# Favorites / RF memory candidate — review before release

Baseline: `wvaraltd/allmode` main `6638231867fc438870367468f652909d8699499f`.
This is the 0.8.0-beta.8 source candidate, not an installed or published release.
Matching beta.8 archives are prepared. The repository-only bootstrap remains the
previous published beta.7 installer and is excluded from this source archive. The
publisher must update its version, source commit and checksum only after verifying the
actual published beta.8 package commit. No beta.8 installer command is ready yet.

## User-visible changes

- Favorites and notes live on the station with stable IDs and revision-checked atomic saves.
- Browser-only favorites remain untouched until explicitly reviewed/imported; conflicting notes
  or source identities stop the whole import. DMR network identity must be explicit.
- Favorites now have a dial-plan area with a fixed optional slot, full `*5` command preview,
  enable checkbox, and Save. New memories default off. Deletion never renumbers others.
- Slot 1 is `*51`, not `*501`; no trailing `#` is needed over RF. Existing `*3` remains unchanged.

## RF safety and installation

See `RF-MEMORIES.md`. The installer copies the new Python modules and configures a restricted
local Unix socket; no third-party package is added. It does not silently change existing
remote command access, import favorites, enable slots, or transmit test audio.

The physical node must have reviewed local-only function/macro tables. The audited node 60670
has shared local/link/phone macros, so a narrow owner-approved isolation step is required
before an explicitly saved enabled memory can work. Read-only plan generation and guarded
application are separate from normal favorites saves. Review the generated plan and input
hashes; other indirect/privileged callers fail closed. No network-unauthenticated recall route
is added. The fixed helper supplies only slot and generation; RF dispatch re-resolves the
current saved favorite and uses `connect_destination(..., allow_bridge=False)`.

No automatic voice feedback is enabled. Logs distinguish receipt/request from connection;
there is no assertion that a network is connected before the existing status confirms it.

## Verification boundary

The original 132 Python tests were run successfully before editing. Candidate verification
includes the original suite plus new durable-store, HTTP, mocked all-mode dispatch, parser,
conflict, rollback, source-isolation and regeneration tests; installer tests; all existing
frontend guards plus new isolated VM/DOM tests; syntax checks; and native FIFO checks.
Exact final counts and hashes are in the accompanying candidate manifest/report.

Actual Chromium execution could not start in this cloud sandbox. The retained mocked browser
runner is explicitly not counted as passed. Two real AF_UNIX integration cases are skipped
where the sandbox denies Unix sockets; isolated peer/request decoding is tested, but target
staging must run the real socket tests before feature enable. This is not live Pi, Asterisk,
RF, audio-quality or fresh-card acceptance. No real destination was connected, no RF was
transmitted, and no GitHub publication or Pi deployment was performed by this builder.
