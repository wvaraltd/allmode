# Generic fresh installer: qualification failed

The actual disposable ARM64 test of frozen bootstrap v11 ended on 2026-11-01 at 19:20 UTC with installer exit 1, before completing core installation. The new D-Bus prerequisite/start hurdle passed. The real stock MMDVM service inhibition test then failed because systemd pulled in its upstream `netcheck.service` dependency. The guest was shut down; a clean QEMU process exit is not installer success. No further test-window extension or fresh-install acceptance is claimed.

The upstream unit has `Requires=netcheck.service` and orders after it. A service condition does not prevent its dependencies from being queued. The underlying netcheck failure is not diagnosed by the serial symptom alone. Do not bypass this by clearing dependencies, ignoring the failure, enabling the stock bridge or fabricating a successful condition result.

The reviewed candidate is retained only as source for further review. Its coupled bootstrap and fresh-profile validation contracts need a reviewed fix and a new authorized disposable qualification run before a generic fresh command can be recommended. Do not run it over an existing station.

The separate signed-package existing-station release and its verified migrations are not invalidated by this unqualified fresh orchestration path. Legacy source-install entrypoints remain retired and fail closed.
