# Optional local DVSwitch transport — compatibility gate

The verified official ARM64 package index lists mmdvm-bridge version
1.6.8-20241231-96 (Depends: dvswitch-base, curl). ALLMODE's own software codecs
connect through its local TLV adapter; Analog_Bridge and md380 are not required
for this route. Do not pull in dvswitch-server's dashboard/reflector stack.

Evidence source:
https://dvswitch.org/DVSwitch_Repository/dists/bookworm/hamradio/binary-arm64/Packages

Important: official `https://dvswitch.org/trixie` bootstrap currently configures
bookworm, not a native trixie suite. This fact is not proof of Debian13 ABI
compatibility. The optional dependency package is staged, NOT approved for
production until Debian13 ARM64 solver and runtime tests pass.

Provisioning remains unsupported until the upstream root updater chain is reviewed.
The verified mmdvm-bridge postinst runs DVSM_Update.sh and `systemctl enable`, not
start. PRE-MASKING IS NOT VALID: enable on a masked unit fails package configure.
Do not use a mask to work around this postinst.

The staged guard design uses ara-allmode-dvswitch-guard, installed in a separate
completed transaction BEFORE upstream provisioning. It owns a systemd condition
drop-in for the stock daemon only; no condition applies to ALLMODE's separately
launched private-config process. The condition is false unless an administrator
explicitly creates /etc/allmode/allow-upstream-mmdvm-service (do not create it for
ALLMODE ownership). systemctl enable may succeed without permitting daemon startup.
Guard install refuses an already active stock daemon and never stops it itself.
Guard removal refuses an enabled/active stock daemon; explicitly disable it first
so removing the condition cannot unexpectedly activate RF on reboot. No automatic
start occurs on install, upgrade, remove or purge. Addon Depends guard is an
additional check, not a substitute for the required pre-provisioning transaction.

This remains a staging design requiring disposable systemd target testing and
root updater-chain review before live provisioning. No stock service masks,
updater bypasses or live service mutations have been performed.

ALLMODE owns on-demand MMDVM processes through its digital supervisor. Leave the
upstream daemon inhibited by the guard while using this mode. It launches only on explicit Connect.
The official templates/binary remain under /opt/MMDVM_Bridge; generated private
station configuration is not written into those templates.

User config `/var/lib/asterisk/allmode/dvswitch.json` is not package content and is
never overwritten. Source integration chooses native/dvswitch transport separately
from codec provider; software codecs remain default and external vocoder optional.
Native route is preserved until local DVSwitch transport has passed target tests.
Local transport ports are configurable, validated and must not collide with any
existing service. No node number, callsign, remote radio host or talkgroup is preset.

Signed ARM64 scratch APT solve against Trixie succeeded for the minimal package
chain (metadata only, no installed target runtime). The upstream MMDVM package
omits libstdc++6 despite its ELF NEEDED entry; ara-allmode-dvswitch explicitly
depends on libstdc++6, libgcc-s1 and libc6 to close that clean-install gap.

## Upstream root updater side effects (read-only review)

The verified MB postinst runs DVSM_Update.sh → dvswitch.sh update →
downloadDatabases. It fetches host/ID data from HTTPS radioid endpoints and plain
HTTP Pi-Star/dstar.su endpoints into /var/lib/mmdvm and /var/lib/dvswitch. These are
data downloads, not downloaded shell execution, but plain HTTP lacks authenticity.
DVSM_Update.sh also removes three existing ircddbgateway host files and replaces
them with symlinks, and creates private host files only when absent. Back up
/opt/MMDVM_Bridge, /var/lib/mmdvm, /var/lib/dvswitch and /usr/share/ircddbgateway
before installing on an existing station. backup.py now includes these paths.
Do not silently suppress/patch this upstream postinst; any alternative needs review.

A disposable rooted systemctl enable test with the condition drop-in succeeded.
That test proves enable does not fail like a mask; it is NOT proof that a live
systemd manager suppresses every startup path. Direct binary execution by other
upstream scripts must still be reviewed. Runtime qualification remains required.
