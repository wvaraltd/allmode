"""Fail release preparation if required integration or archive/source parity is lost."""
import argparse
import hashlib
from pathlib import Path
import tarfile


def verify(root, archive=None):
    root = Path(root)
    required = {
        'app/web/operator.js': ["'ara.layout'", 'Layout 1', 'Original', 'Layout 2', 'Sidebar', 'Layout 3', 'Radio', "dataset.layout==='3'", 'id="transceiver"', 'function connectionUnavailable(', 'cpuHealthTile', 'function rigFavoriteRows(', 'function bindRigFavorites(', 'function refreshRigFavorites(', 'rig-control-favorites', "${rigDialMarkup('rx','RX GAIN')}${rigDialMarkup('txa','TX A')}${rigDialMarkup('txb','TX B')}", "action:'skip-audio'", '!s.complete&&!s.optional'],
        'app/web/operator.css': ['data-layout="2"', 'data-layout="3"', '.transceiver', '#phone-navigation', '.rig-control-favorites'],
        'test_radio_favorites.cjs': ['no auto connect/gain mutation', 'reorder/removal reconciliation'],
        'app/web/operator.html': ['/operator.js', '/operator.css', '/audio-meter.js'],
        'app/web/audio-meter.js': ['setInterval(update,100)', 'AbortController', 'sequence', 'function updateSharedMeter(', 'rig-needle'],
        'app/audio_meter.py': ['time.sleep(.05)', 'refresh_ms=100', 'format_allmode_meter.so', '.ameter'],
        'native-meter/format_allmode_meter.c': ['meter_fifo_write', 'allmode_meter'],
        'native-meter/meter_fifo.h': ['S_ISFIFO', 'O_NONBLOCK', 'PIPE_BUF'],
        'install.sh': ['bash "$src/install-meter.sh"', 'allmode_offer_reboot "$uart_pending"'],
        'install-meter.sh': ['asl3-asterisk-dev=$version', 'asl3-asterisk-modules', 'test_fifo', 'format_allmode_meter.so', 'gcc -shared'],
        'configure-serial.sh': ['boot_id=', 'chmod 0644 /var/lib/allmode/serial-reboot-required'],
        'app/sa818_hardware.py': ["rx_ctcss='100.0', tx_ctcss='100.0'", 'uart_reboot_required'],
        'finish-install.sh': ['[[ -t 0 && -t 1 ]]', 'Reboot now? [y/N]'],
        'app/operator_store.py': ["if not s.get('optional')", "'status':'skipped'"],
        'package-manager.sh': ['set -o pipefail', 'DPkg::Lock::Timeout'],
    }
    for name, tokens in required.items():
        text = (root/name).read_text(encoding='utf-8')
        for token in tokens:
            assert token in text, f'{name}: missing integration {token}'
    declared = {}
    for line in (root/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
        declared[name] = (root/name).read_bytes()
    # Repository-only distribution metadata is not application source.
    repository_only = {'get-allmode.sh', '.gitignore'}
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
              and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts
              and '.git' not in p.parts and p.suffix != '.pyc'
              and p.relative_to(root).parts[0] not in {'downloads', '.github'}
              and p.relative_to(root).as_posix() not in repository_only}
    assert actual == set(declared), 'Manifest must cover every canonical source file'
    if archive:
        with tarfile.open(archive) as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            prefix = members[0].name.split('/')[0]+'/'
            packaged = {m.name.removeprefix(prefix):tar.extractfile(m).read() for m in members}
        declared['SHA256SUMS'] = (root/'SHA256SUMS').read_bytes()
        assert packaged == declared, 'Archive does not exactly match canonical source'
    print('PASS: required feature integration, complete manifest, and requested archive parity')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=Path(__file__).resolve().parent)
    parser.add_argument('--archive')
    args = parser.parse_args()
    verify(args.root, args.archive)
