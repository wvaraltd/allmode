#!/usr/bin/python3
"""Build optional dependency-only package. No upstream binaries bundled."""
import argparse,pathlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
out=a.output.resolve();stage=out/'dvswitch-stage';shutil.rmtree(stage,ignore_errors=True);(stage/'DEBIAN').mkdir(parents=True)
(stage/'DEBIAN/control').write_text('''Package: ara-allmode-dvswitch
Version: 0.8.0~beta9-1
Architecture: all
Maintainer: ARA ALLMODE packaging team <allmode@localhost>
Section: hamradio
Priority: optional
Depends: ara-allmode, ara-allmode-dvswitch-guard, mmdvm-bridge (>= 1.6.8-20241231-96), libstdc++6, libgcc-s1, libc6
Description: Optional local DVSwitch transport dependencies for ALLMODE
 Dependency-only integration; upstream binaries come from official repositories.
 Requires reviewed upstream compatibility and pre-install service isolation.
''')
f=stage/'DEBIAN/preinst';f.write_text('''#!/bin/sh
set -eu
if command -v systemctl >/dev/null && systemctl is-active --quiet mmdvm_bridge.service; then
 echo 'Stop idle upstream MMDVM service and isolate its ports before ALLMODE integration.' >&2; exit 1
fi
''');f.chmod(0o755)
d=stage/'usr/share/doc/ara-allmode-dvswitch';d.mkdir(parents=True);shutil.copy2(pathlib.Path(__file__).parent/'DVSWITCH.md',d)
subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(out/'ara-allmode-dvswitch_0.8.0~beta9-1_all.deb')],check=True)

# Install this guard in a separate completed transaction BEFORE upstream packages.
guard=out/'guard-stage';shutil.rmtree(guard,ignore_errors=True);(guard/'DEBIAN').mkdir(parents=True)
(guard/'DEBIAN/control').write_text("""Package: ara-allmode-dvswitch-guard
Version: 0.8.0~beta9-1
Architecture: all
Maintainer: ARA ALLMODE packaging team <allmode@localhost>
Section: hamradio
Priority: optional
Depends: systemd
Description: Inhibit stock MMDVM daemon for explicitly selected ALLMODE ownership
 Install before upstream MMDVM provisioning in a separate completed transaction.
 Does not stop, start, enable, mask or unmask any radio service.
""")
drop=guard/'usr/lib/systemd/system/mmdvm_bridge.service.d';drop.mkdir(parents=True)
(drop/'ara-allmode-owner.conf').write_text('[Unit]\n# ALLMODE launches its own private-config process, not this stock daemon.\nConditionPathExists=/etc/allmode/allow-upstream-mmdvm-service\n')
for name,content in {
 'preinst':"""#!/bin/sh
set -eu
if test -e /etc/allmode/allow-upstream-mmdvm-service; then
 echo 'Existing stock-service consent marker must be reviewed and removed explicitly before selecting ALLMODE ownership.' >&2; exit 1
fi
if systemctl is-active --quiet mmdvm_bridge.service; then
 echo 'Stock MMDVM service active: confirm idle and stop explicitly before changing ownership.' >&2; exit 1
fi
""",
 'postinst':"""#!/bin/sh
set -eu
if test -d /run/systemd/system; then systemctl daemon-reload; fi
""",
 'prerm':"""#!/bin/sh
set -eu
case "${1:-}" in remove|deconfigure)
 if systemctl is-enabled --quiet mmdvm_bridge.service || systemctl is-active --quiet mmdvm_bridge.service; then
  echo 'Explicitly disable and stop the stock MMDVM service before removing its guard, to prevent automatic RF on next boot.' >&2; exit 1
 fi
;; esac
""",
 'postrm':"""#!/bin/sh
set -eu
if test -d /run/systemd/system; then systemctl daemon-reload; fi
"""}.items():
 f=guard/'DEBIAN'/name;f.write_text(content);f.chmod(0o755)
subprocess.run(['dpkg-deb','--root-owner-group','--build',str(guard),str(out/'ara-allmode-dvswitch-guard_0.8.0~beta9-1_all.deb')],check=True)
