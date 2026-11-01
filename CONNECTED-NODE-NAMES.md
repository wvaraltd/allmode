# Connected AllStar node names — canonical-feed correction

The display uses the first nonblank line of a matching station favorite note,
then AllStarLink's public callsign/description/location label, then `Node N`.
The node number is also displayed separately. These labels describe the connected
node, not an originating current speaker. Commands, RF, DTMF and settings are unchanged.

## Fixed public feed

Pin `https://allmondb.allstarlink.org/allmondb.php` directly. Redirects remain
rejected, TLS verification remains enabled, and request headers are unchanged.
No caller-provided URL or credentials are accepted.

Evidence checked on 2026-11-01:

- [Official Allmon3 source](https://github.com/AllStarLink/Allmon3/blob/develop/src/asl_allmon/node_db/__init__.py)
  starts at the HTTPS root and parses node, callsign, description and location
  as four pipe-separated fields. Its normal HTTP client follows redirects.
- [Official ASL updater source](https://github.com/AllStarLink/asl3-update-nodelist/blob/develop/asl3-update-astdb)
  also starts at the directory host's root using wget's redirect-capable client.
- A bounded Pi4 GET with normal TLS to that official HTTPS root returned HTTP 301
  with Location `https://allmondb.allstarlink.org/allmondb.php`: same hostname,
  no credentials, query, fragment or nondefault port. This header-only check read
  zero body bytes and did not follow the redirect. Observation job:
  `job_01M6CF4SDX0065QG6SMXPGVMVE`.
- [AllStarLink terms](https://allstarlink.org/terms/) permit reasonable published
  directory use for ordinary node operation.

The prior core8 candidate pinned the root while rejecting redirects. Its actual
Pi4 feed test therefore failed safely with HTTP 301; source-only tests did not
establish live directory availability. This correction pins the publisher's
observed canonical feed instead of relaxing redirect or TLS protections.

A synthetic HTTP-handler regression exercises the observed root 301 without
following it, then verifies exactly one request to the pinned direct feed and
four-field parsing. It does not substitute for the separately required bounded
real-feed qualification on the Pi.

Existing limits remain: one background fetch per station cache, 15-minute
refresh/backoff, 5-second socket timeout/10-second read budget, 8 MiB input cap,
100,000 rows, 7-day maximum stale age, and numeric fallback. Initial local cache
loading is synchronous; network refresh is off-thread. Names are escaped or
inserted with textContent. Browser visual, RF/audio and fresh-install acceptance
are separate from these metadata tests. No live feed data is bundled here.
