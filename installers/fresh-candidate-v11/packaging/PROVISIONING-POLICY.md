# Fresh upstream provisioning policy (review design, NOT EXECUTED)

Prevent upstream ASL/MMDVM maintainer scripts from starting radio services before
ALLMODE has been configured. Prepare this in a disposable target first; existing
station upgrades use maintenance instead of fresh provisioning.

1. Verify radio services are inactive and operator approved provisioning.
2. Take an exclusive provisioning lock. Inspect `/usr/sbin/policy-rc.d` without
   altering it. Refuse a symlink, ambiguous existing journal or unsafe ownership.
3. Save existing bytes, mode, owner and existence in a root-only journal/backup.
   Atomically install a temporary root-owned policy wrapper returning 101 for
   `asterisk`, `mmdvm_bridge`, `analog_bridge` and their `.service` names. For
   other services delegate to the preserved existing policy with unchanged args,
   or return 0 if none existed. Never replace an existing policy with blanket allow.
4. Use only the reviewed exact package transaction and official verified repos.
   Test upstream scripts actually use invoke-rc.d/deb-systemd-invoke; direct
   `systemctl start` bypasses policy-rc.d. Do not pre-mask MMDVM: its verified postinst enables the service and fails on a
   mask. Use the separately reviewed condition guard before provisioning instead,
   and inspect all direct binary launches in the updater chain.
5. Restore original policy atomically in normal completion and exception handlers,
   with EXIT/INT/TERM/HUP traps; verify bytes/metadata afterward. Do not leave a
   policy wrapper or accidental mask behind.
6. SIGKILL/power loss cannot guarantee trap execution. Persist a recoverable journal
   before mutation, refuse reentry until reconciled, and provide an explicit
   restore-only path that verifies current wrapper hash before restoring anything.
7. Keep all radio services stopped after fresh provisioning. Commission explicitly.

No policy-rc.d installer is executed or shipped as an automatic package hook here.
This design needs upstream script inspection and target tests before implementation
can claim reliable suppression. No blanket global OS upgrade belongs in this step.
