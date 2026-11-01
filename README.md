# ARA ALLMODE — beta 9 signed-package release

Canonical application source: `1231449b471720cd09487599da11354d02d8e59d`. The current signed core package is **ara-allmode 0.8.0~beta9-9**, built with reviewed packaging v6b. It includes station favorites/RF-memory controls, corrected setup/activation fingerprints, reliable startup recovery, Wi-Fi selection, persistent audio-meter recovery, local DVSwitch DMR transport and the revised Radio display.

## Install and update safely

**The legacy source installer and old beta 7 bootstrap are retired.** Current `get-allmode.sh` and `install.sh` stop without installing anything. Do not use historical source-install commands or reinstall over a configured station. Previous source and packages remain recoverable through Git history or retained signed package versions.

Signed repository: `https://rf.ara.radio/allmode/apt/`, suite `trixie`, component `main`, architecture `arm64`. The public signature/index/package chain and final package bytes are independently verified. Exact identities and qualification limits are in [RELEASE-STATUS.md](RELEASE-STATUS.md).

**There is no qualified generic fresh-install command.** Frozen [bootstrap v17 source](installers/fresh-candidate-v17/README.md) is retained only for review. It contains a reviewed proof-unit retention repair, but full fresh installation remains unqualified. Its pins target core7, not core9; mock tests and a narrow proof are not full fresh acceptance. See [BEGINNER-INSTALL.md](BEGINNER-INSTALL.md) and [FRESH-INSTALL-BLOCKER.md](FRESH-INSTALL-BLOCKER.md).

For existing stations, confirm radio idle, preserve settings/credentials/calibration/favorites, and use a reviewed, backed-up, exact-version maintenance procedure. `apt update` only refreshes signed indexes; actual installation is separate. Never perform an unattended whole-system upgrade while transmitting. Nothing here authorizes automatic RF activation, radio programming or enabling RF-memory slots.

## Interface and verification scope

Original, Sidebar and Radio layouts remain. Radio displays the actual connected destination at top center, current speaker at bottom center when known, and RX/TX/PL at the right. Unknown speaker information is not fabricated. CPU usage appears with Fahrenheit temperature; audio testing is optional. Audio meters display dBFS, not calibrated RF signal strength.

Both reviewed existing stations run the final core package with protected settings unchanged. Persistent meter taps and fresh RX/TX data were verified, but actual voice/RF acceptance is not claimed. Wi-Fi profile generation passed ordinary-user offline NetworkManager tests; real Wi-Fi association was not tested. Fresh-card, every-phone and GPIO qualification are not established. New DTMF voice feedback, AP design and experimental multimode/offline branches are not included.

## Connected node names and package permissions
Core9 resolves names from the direct AllStar HTTPS PHP feed with validated field mapping, bounded caching and honest fallback. The verified feed supplied 41,198 records; installed service-user cache access passed. Reviewed packaging v6b normalizes static payload permissions and performs only the narrowly reviewed nofollow legacy-directory migration. Both reviewed stations installed core9 and normalized companions with settings preserved. No fresh-install or new core9 browser-visual pass is implied.
