# Beta 6 package-manager lock hotfix 1

The installer now waits up to 600 seconds for competing package operations. The ASL repository DEB is installed through apt rather than an unguarded dpkg invocation. All installer and LAN-setup apt commands share the bounded helper. It never deletes lock files or terminates another package process. Unrelated package errors remain failures.

This remains a fresh-install package, including resuming this installer after an interrupted fresh install. Existing configured stations are not upgrade targets. Download get-allmode.sh again using the same published command. Original beta 6 packages remain available unchanged. The application version remains 0.8.0-beta.6.
