# Fresh-install qualification is still open

This repository does not offer a qualified generic fresh installer. Existing-station package acceptance and source tests are separate evidence.

Earlier real disposable tests exposed these issues:

1. An inhibition test queued the stock bridge's upstream netcheck dependency before the bridge's own condition was evaluated. A clean guest shutdown did not make that failed install successful.
2. Published legacy payload directories/files had writable modes rejected by the trust checker. Reviewed packaging v6b and normalized companion revisions repair the proven static modes, including only a narrow nofollow legacy-directory migration. That package repair does not itself qualify the whole installer.
3. A systemd proof unit could be garbage-collected before its result was inspected. Frozen v17 includes the reviewed anchor/retention repair and passed source mocks and an actual ARM64 semantic retention probe, but full-fresh acceptance has not passed.

The exact source-only v17 candidate is retained for review with its core7 pins; it is not a tested core9 bootstrap. Any actual proof and complete fresh transaction require their own authorized disposable test and retained results. Do not bypass guards, fabricate condition results, clear dependencies, suppress signature/expiry checks or start RF to force a green result.

Legacy source entrypoints remain fail-closed. No private guest logs, station identifiers, credentials or configuration are required to explain these public limitations.
