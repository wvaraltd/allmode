# Repository approval and bootstrap plan

## Hosting layout

Proposed authorized target is the existing **https://rf.ara.radio** HTTPS origin,
with a separately mounted static directory `/allmode/apt/` (publication approval
pending; not yet deployed or verified as an APT repository). Do not
invent `packages.ara.radio`, add DNS records, or change the RF site's document root.
Parent is requesting approval for this exact origin/path and signing/trust changes.

```
/allmode/apt/pool/main/a/ara-allmode/ara-allmode_<version>_arm64.deb
/allmode/apt/pool/main/a/ara-allmode/ara-allmode-meter_<version>_arm64.deb
/allmode/apt/dists/trixie/InRelease
/allmode/apt/dists/trixie/Release
/allmode/apt/dists/trixie/Release.gpg
/allmode/apt/dists/trixie/main/binary-arm64/Packages
/allmode/apt/dists/trixie/main/binary-arm64/Packages.gz
```

Pool files should be immutable. Stage whole repository generation, verify every
size/hash, sign Release, then atomically switch publication directory. Retain prior
package versions for rollback and publish refreshed signed metadata before 14-day
Valid-Until expires. Serve package MIME types as static downloads without auth
redirects or HTML fallbacks. Keep signing secrets off the web server and repository.

## Required approvals before signing or trust changes

- Confirm actual origin, path, server access and publication authorization.
- Confirm release source/license, native ARM64 build/test artifacts, maintainers.
- Identify existing authorized ARA archive key or approve new signing key creation,
  custodian, encrypted offline storage, expiry, rotation and revocation process.
- Approve signed public key publication and independent fingerprint distribution.
- Approve tester machine trust configuration and exact install transaction.
- Confirm official upstream Debian13 ARM64 ASL/DVSwitch repository compatibility,
  package names and fingerprint/bootstrap instructions; do not guess these.

No production key has been created/used by this work. The local staging Release is
intentionally unsigned. A real isolated apt client correctly refuses it. Neither
`trusted=yes` nor `--allow-unauthenticated` is an acceptable workaround.

## Bootstrap after approval (review template, not commands to run yet)

1. Download the approved public archive key over HTTPS; verify its complete
   fingerprint through an independent authorized channel. Install it as
   `/etc/apt/keyrings/ara-allmode.gpg` with root ownership and mode 0644.
2. Add a deb822 `/etc/apt/sources.list.d/ara-allmode.sources` with:

   ```
   Types: deb
   URIs: https://rf.ara.radio/allmode/apt/
   Suites: trixie
   Components: main
   Architectures: arm64
   Signed-By: /etc/apt/keyrings/ara-allmode.gpg
   ```

   Use this exact scope only after explicit signing, publishing and tester trust approval.
3. Set up upstream repositories only using their verified official compatible
   bootstrap and keys. Do not package/rehost their proprietary binaries.
4. `sudo apt update` refreshes signed package indexes; it does NOT install new code.
5. Inspect `apt-cache policy ara-allmode ara-allmode-meter` and simulate the exact
   version-pinned transaction using `apt-get -s install ...`.
6. Confirm radio idle, stop station services, back up and explicitly install the
   selected packages. `apt upgrade` installs available updates across installed
   packages; never substitute it for an ALLMODE-only controlled update.
7. Validate fingerprints, InRelease signature, Release/Packages/package SHA256,
   installed dpkg versions and on-target behavior. Only then call repository live.

Build-machine tests are not an actual published signed APT-client acceptance test.
