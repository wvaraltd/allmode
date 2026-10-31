# DHCP-safe LAN browser origin validation

The LAN installer captured its original IP in the POST origin allowlist and
HTTP redirect. After moving networks, GET /login still loaded but POST /login
failed with `Same-origin browser access required.`

This patch adds opt-in `--lan-proxy` validation. The application remains bound
to loopback. Nginx must overwrite `Host` and `X-Forwarded-Proto`, as the bundled
configuration does. POST requests require a loopback peer, exactly one of each
header, HTTPS on default port 443, and a browser origin matching the request
authority. The authority must be either a configured stable hostname or an
IPv4 address currently assigned to a local interface. Secondary/multihomed IPv4
addresses are included; removed addresses immediately stop matching. Interface
discovery failure denies numeric-IP requests. Arbitrary reflected Host values,
DNS resolution, wildcards and stale configured numeric addresses are not used.

The current installer listens on IPv4; this change does not claim IPv6 support.
Explicit :443 is equivalent to the default port; non-default HTTPS ports are
not enabled. Existing explicit-origin mode is unchanged unless --lan-proxy is
selected. Login cookies retain Secure, HttpOnly and SameSite=Strict. GET routes
are unchanged and all POST routes still pass origin validation before login or
authenticated actions. HTTP redirects use nginx's local destination address
instead of the install-time IP.

## Verification

Run `python3 run-tests.py` as an ordinary user from the package root. Added
policy, real HTTP login, authenticated logout/CSRF and installer contract tests
cover address changes, secondary addresses, stable names, missing/cross-site
origins, proxy/header spoofing, duplicate headers and explicit ports. Run
`bash -n enable-lan.sh` and Python compilation as well.

## Deployment boundaries

Do not rerun the fresh installer over a configured station. Back up and compare
the deployed application version, install the compatible helper/server changes,
add --lan-proxy to the existing service invocation while retaining stable
hostname origins, and update only the redirect in its existing nginx site.
Validate nginx before reload and verify GET/login/CSRF after restart. Do not
overwrite passwords, radio settings, active radio services or station state.

This does not renew the self-signed TLS certificate or its old IP SAN. The
stable hostname covered by the existing certificate remains the portable TLS
identity. Direct-IP use after an IP change separately needs verified certificate
renewal/trust; never silently bypass a browser certificate warning.

Repository root is older development source. Applying this beta patch there
does not update the pinned beta download. Release publication must update the
canonical beta source, reproducible archives, internal checksums, external
archive hashes and download pin together; do not replace beta source with the
older root source or silently rewrite previously published archives.
