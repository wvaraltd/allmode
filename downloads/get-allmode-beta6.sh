#!/bin/bash
# Download the complete, pinned ALLMODE beta and launch its installer.
set -Eeuo pipefail
case "${1:-}" in
  '') [[ $# == 0 ]] || exit 2 ;;
  --check|--download-only) [[ $# == 1 ]] || exit 2 ;;
  *) echo 'Usage: sudo bash get-allmode.sh [--check|--download-only]' >&2; exit 2 ;;
esac
if [[ ${1:-} != --download-only && $EUID != 0 ]]; then
  echo 'Run: sudo bash get-allmode.sh' >&2
  exit 1
fi
version=0.8.0-beta.6
archive="allmode-$version-lockfix.1.tar.gz"
source_commit=4acaf6279abd59b551883cb2dab936a525ebfb4f
expected=f1e74ba9b49cac3efcec04360c8465cc700810b6c8f133173b171913f078f8fb
for command in curl sha256sum tar mktemp; do
  command -v "$command" >/dev/null || { echo "Missing $command. Install curl and coreutils/tar, then retry." >&2; exit 1; }
done
umask 077
work=$(mktemp -d /tmp/allmode-install.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
trap 'echo "ALLMODE installation stopped. Resolve the error above, then rerun the same download command." >&2' ERR
cd "$work"
echo 'Fresh-install package only: Debian 13, arm64 userspace, aarch64 kernel, Raspberry Pi + SHARI.'
echo 'Existing configured stations are rejected. Zero 2 W software-vocoder performance still requires hardware testing.'
echo "Downloading ALLMODE $version..."
curl --fail --show-error --location --proto '=https' --tlsv1.2 --retry 3 --connect-timeout 20 --max-time 300 \
  "https://raw.githubusercontent.com/wvaraltd/allmode/$source_commit/downloads/$archive" -o "$archive"
if ! printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --status; then
  echo 'Archive checksum mismatch. Nothing was installed; download again from the official repository.' >&2
  exit 1
fi
tar --extract --gzip --file "$archive" --no-same-owner
cd "allmode-$version"
sha256sum --check --quiet SHA256SUMS
echo 'Download and package checksums verified.'
if [[ ${1:-} == --download-only ]]; then
  echo 'Download test passed; no installation performed.'
  exit 0
fi
# apt remains attached to the terminal for prompts; no curl-to-shell pipeline.
if [[ ${1:-} == --check ]]; then
  bash install.sh --check
else
  bash install.sh
  if [[ ! -f /etc/allmode/beta-installed.json ]]; then
    echo 'If a reboot was requested, reboot and run the same download command again.'
  fi
fi

