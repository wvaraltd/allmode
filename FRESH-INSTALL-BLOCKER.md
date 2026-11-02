# Historical fresh-install blockers (superseded status)

**Current status:** the [verified core9 installer](https://github.com/wvaraltd/allmode/blob/725fda65e4f4cf67d3c1cfd66a65624cf5cc1e23/downloads/core9-installer-v20/README.md) is published. See [RELEASE-STATUS.md](RELEASE-STATUS.md) for precise v18/v19/v20 evidence and remaining physical qualification limits. The text below is the retained 2026-11-01 pre-qualification history, not the current download status.

Earlier real disposable tests exposed these issues:

1. An inhibition test queued the stock bridge's upstream netcheck dependency before the bridge's own condition was evaluated. A clean guest shutdown did not make that failed install successful.
2. Published legacy payload directories/files had writable modes rejected by the trust checker. Reviewed packaging v6b and normalized companion revisions repair the proven static modes, including only a narrow nofollow legacy-directory migration. That package repair does not itself qualify the whole installer.
3. A systemd proof unit could be garbage-collected before its result was inspected. Frozen v17 includes the reviewed anchor/retention repair and passed source mocks and an actual ARM64 semantic retention probe, but full-fresh acceptance has not passed.

The exact source-only v17 candidate is retained for review with its core7 pins; it is not a tested core9 bootstrap. Any actual proof and complete fresh transaction require their own authorized disposable test and retained results. Do not bypass guards, fabricate condition results, clear dependencies, suppress signature/expiry checks or start RF to force a green result.

Legacy source entrypoints remain fail-closed. No private guest logs, station identifiers, credentials or configuration are required to explain these public limitations.
