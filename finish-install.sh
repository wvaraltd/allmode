#!/bin/bash
# Source only; call after all installation and readiness checks succeed.
allmode_offer_reboot() {
  local pending=${1:-unknown} answer
  [[ $pending != false ]] || return 0
  if [[ $pending != true ]]; then
    echo 'UART reboot status could not be checked. If you have not rebooted since GPIO serial configuration changed, run sudo reboot before Radio setup.'
    return 0
  fi
  echo 'REBOOT REQUIRED: GPIO serial settings changed during this boot. Saved setup drafts are retained. Run sudo reboot before Radio setup.'
  if [[ -t 0 && -t 1 ]]; then
    if read -r -p 'Reboot now? [y/N] ' answer && [[ $answer == y || $answer == Y || $answer == yes || $answer == YES ]]; then
      echo 'Rebooting. Reconnect and reopen ALLMODE when the Pi returns.'
      systemctl reboot
    else
      echo 'Reboot postponed. Run sudo reboot before testing or programming the radio.'
    fi
  else
    echo 'Noninteractive session: no reboot performed. Run sudo reboot when ready.'
  fi
}
