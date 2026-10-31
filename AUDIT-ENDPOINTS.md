# Beta.5 endpoint audit inventory

Base: published package SHA-256 `9cf56f8fbc52bab7a98a52f5efaa4ccab27401be00b4200d8292edb6198f471b`, GitHub main `298a20bd44be8d7f681c019020930a4e43843270`.

This is a source/contract inventory, not a claim that every physical or network operation was exercised. Current changes are an unpublished audit candidate.

Authentication: when configured, all API endpoints below require a valid owner session except initial `/api/claim`. Every POST is checked for same origin before dispatch, including login, claim, and extension routes. Ordinary POST bodies are JSON objects, 1–8192 bytes; claim is 1–1024 bytes. Login is URL-encoded, 1–1024 bytes. Upload and audio routes have separate limits below. Missing login returns 401; rejected origin 403; invalid data normally 400; unavailable local service now returns JSON 503 on the previously broken dependency routes. `/api/system` intentionally returns a degraded 200 status object; `/api/audio-meter` returns an inactive 200 object on dependency failure.

| Method / route | Request / purpose | UI caller |
|---|---|---|
| GET `/api/claim` | Initial unclaimed status; unavailable after claim | claim |
| POST `/api/claim` | `{password}`; one-time 4–128-character owner claim | claim.js |
| POST `/login` | `username=admin&password=...`; redirect + secure session cookie | login form |
| POST `/logout` | Revoke session, redirect | shared navigation |
| GET `/api/status` | Controller state | operator.js, app.js |
| POST `/api/command` | `{action,value}`; mode/connect/disconnect/audio; `connect-network` additionally mode, network, source_id, allow_bridge | operator.js, app.js |
| GET `/api/setup` | Legacy schema or managed-mode guidance | app.js |
| GET `/api/hardware` | Ports, draft, last programming result, preset | hardware.js |
| POST `/api/hardware` | preview/save: settings; probe/program: detected port, safe=true, settings and confirm=PROGRAM for program; rssi: paused | hardware.js, dashboard |
| GET `/api/onboarding` | Redacted station schema and derived workflow | operator.js, hardware.js |
| POST `/api/onboarding` | Complete group map, or `{section,values}` | legacy first-run.js |
| POST `/api/settings` | `{group,values}`; independently save one group | operator.js |
| POST `/api/finish` | Empty object; requires every workflow step complete | operator.js |
| GET/POST `/api/profiles` | List / `{action:save or restore,name}`; restore does not activate or program | operator.js |
| POST `/api/password` | `{current,password}`; revoke sessions on success | operator.js |
| GET/POST `/api/features` | Snapshot / add,toggle,delete schedule; newly added rules disabled | operator.js |
| GET `/api/network` | Local interface status | operator.js |
| GET `/api/digital-identities` | NXDN/P25/M17 identities | operator.js |
| GET `/api/directory?source=...` | Allowlisted local directory | operator.js |
| GET `/api/destinations` | Digital catalog | legacy app.js |
| GET `/api/system` | Runtime readiness / degraded state | operator.js |
| POST `/api/system` | apply; activate with confirm=ACTIVATE and saved fingerprint; maintenance; audio with levels; audio-confirm with checked; test-ambe; wifi-scan/save/connect; digital-identities-save | operator.js, hardware.js |
| GET `/api/audio-meter` | Live meter or inactive object | audio-meter.js |
| GET `/api/codec/libraries` | Installed/uploaded codec metadata | operator.js |
| GET `/api/codec/state` | Shared vocoder selection | operator.js |
| POST `/api/codec/select` | `{backend}`; JSON up to 1024 bytes | operator.js |
| POST `/api/codec/upload` | Binary up to 16 MiB, X-Codec-Profile and X-Codec-Name headers; inspect/store, not activation | operator.js |
| GET `/api/radio-parrot/state` | Radio-test state | audio-tools.js |
| POST `/api/radio-parrot/arm` | `{confirm,mode}` up to 1024 bytes; explicit radio test | audio-tools.js |
| POST `/api/radio-parrot/stop`, `/heartbeat` | Up to 1024 bytes | audio-tools.js |
| GET `/api/parrot/state` | Browser parrot state | codec/deploy/web/parrot.js |
| POST `/api/parrot/enable`, `/disable`, `/record`, `/stop`, `/finished`, `/backend`, `/heartbeat` | JSON; seconds/name where applicable; maximum 960000 bytes | codec/deploy/web/parrot.js |
| POST `/api/parrot/complete` | Recorded WAV bytes, maximum 960000 | codec/deploy/web/parrot.js |
| POST `/api/parrot/play` | Returns audio/wav | codec/deploy/web/parrot.js |
| POST `/api/parrot/compare` | Explicitly unsupported; 400 | legacy comparison UI |

Public initial assets: `/setup`, `/claim.js`, `/operator.css`; public login assets: `/login`, `/login.js`, `/hardware.css`, `/operator.css`. After claiming, normal pages redirect to login without a session. Authenticated pages: `/`, `/settings`, `/setup`, `/connections`, `/logs`, `/profiles`, `/network`, `/admin`, `/schedules`, `/airtime`, `/hardware`; JS/CSS assets are explicitly mapped, not arbitrary filesystem paths. `/audio-tools` and `/codec` redirect to settings; older parrot pages redirect through audio-tools. Legacy `/allmode/` GET alias and command/hardware POST aliases remain; nginx uses root URLs.

New regression tests enumerate login/origin enforcement for protected API families, verify positive payload preservation for the three dependency GET routes, check unavailable-service JSON responses for GET and selected POST routes, and check the owner-password minimum message. Existing tests cover core controller, account, origin, serial, configuration rollback, and setup validations. Successful mocks do not prove systemd, USB, serial, codec ABI, public network interoperability, RF, or audio performance.
