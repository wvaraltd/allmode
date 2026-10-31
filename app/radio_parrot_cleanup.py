"""systemd stop hook: only acts when a radio-test lease exists."""
from system_service import RADIO_PARROT
if RADIO_PARROT.active:RADIO_PARROT.stop('Radio service controller stopped')
