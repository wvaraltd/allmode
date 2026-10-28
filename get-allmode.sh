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
version=0.8.0-beta.1
archive="allmode-$version.tar.gz"
source_commit=0e33ec3fc82eafb60da685e8f4a423f8f484a3a9
expected=6145a650596ed06435a652be6ab04f8d2a4026cf2dd7c532130ae0a53ad55d1f
for command in curl sha256sum tar mktemp; do
  command -v "$command" >/dev/null || { echo "Missing $command. Install curl and coreutils/tar, then retry." >&2; exit 1; }
done
umask 077
work=$(mktemp -d /tmp/allmode-install.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
trap 'echo "ALLMODE installation stopped. Resolve the error above, then rerun the same download command." >&2' ERR
cd "$work"
echo "Downloading ALLMODE $version..."
curl --fail --show-error --location --proto '=https' --tlsv1.2 --retry 3 --connect-timeout 20 --max-time 300 \
  "https://raw.githubusercontent.com/wvaraltd/allmode/$source_commit/downloads/$archive" -o "$archive"
printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --status
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
