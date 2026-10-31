#!/bin/bash
# Source this file. Let apt acquire its own POSIX locks; never inspect/remove locks.
allmode_apt() (
  set -o pipefail
  local timeout=${ALLMODE_APT_LOCK_TIMEOUT:-600} started=$SECONDS remaining rc delay log
  local -a statuses
  [[ $timeout =~ ^[1-9][0-9]{0,4}$ ]] || {
    echo 'ALLMODE_APT_LOCK_TIMEOUT must be 1-99999 seconds.' >&2; exit 2;
  }
  log=$(mktemp) || exit 1
  trap 'rm -f -- "$log"' EXIT
  while :; do
    remaining=$((timeout - SECONDS + started))
    if (( remaining <= 0 )); then
      echo "Package-manager lock wait timed out after ${timeout}s. No locks were removed. Let the other package operation finish, then rerun the installer." >&2
      exit 100
    fi
    # Native waiting covers both frontend and dpkg locks. update's lists lock
    # needs the narrowly classified retry below. Keep stdin for upgrade prompts.
    if LC_ALL=C apt-get -o "DPkg::Lock::Timeout=$remaining" "$@" 2>&1 | tee "$log"; then
      exit 0
    else
      statuses=("${PIPESTATUS[@]}")
    fi
    rc=${statuses[0]}
    (( statuses[1] == 0 )) || exit "${statuses[1]}"
    (( rc == 100 )) || exit "$rc"
    # Only apt's acquisition failures qualify. Any other E: diagnostic stops.
    if ! grep -Eq '^E: Could not get lock /[^ ]+ - open \(11: Resource temporarily unavailable\)$|^E: Could not get lock /[^ ]+\. It is held by process [0-9]+' "$log" ||
       grep '^E:' "$log" | grep -Evq '^E: (Could not get lock /|Unable to acquire the dpkg frontend lock |Unable to lock (directory |the administration directory ))'; then
      exit "$rc"
    fi
    remaining=$((timeout - SECONDS + started))
    (( remaining > 0 )) || continue
    delay=5
    (( remaining >= delay )) || delay=$remaining
    echo "Another package operation is running; waiting ${delay}s (${remaining}s remaining)." >&2
    sleep "$delay"
  done
)
