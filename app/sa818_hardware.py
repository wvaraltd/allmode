"""SA818S commissioning. Saved settings and acknowledgements are NOT RF readback."""
import glob
import json
import os
import re
import subprocess
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

TONES = '0 67.0 71.9 74.4 77.0 79.7 82.5 85.4 88.5 91.5 94.8 97.4 100.0 103.5 107.2 110.9 114.8 118.8 123.0 127.3 131.8 136.5 141.3 146.2 151.4 156.7 162.2 167.9 173.8 179.9 186.2 192.8 203.5 210.7 218.1 225.7 233.6 241.8 250.3'.split()
PRESET = dict(band='UHF', rx='', tx='', bandwidth=1, squelch=6, volume=6,
              rx_ctcss='100.0', tx_ctcss='100.0', reverse_burst=False,
              emphasis=True, highpass=True, lowpass=True)
LIMITATION = ('No supported full settings readback. Defaults, drafts and last acknowledged writes '
              'are local records, not measured radio state. Version/handshake prove communication only. '
              'Tail acknowledgements can be unreliable on some firmware; verify behavior on hardware.')


def validate(settings):
    if not isinstance(settings, dict) or set(settings) != set(PRESET):
        raise ValueError('Supply every hardware setting, with no extra fields.')
    s = settings.copy()
    if s['band'] not in ('UHF', 'VHF'):
        raise ValueError('Select the band printed on the installed module.')
    # Conservative amateur-band envelope, not an authorization or local band plan.
    low, high = (Decimal('430.000'), Decimal('449.995')) if s['band'] == 'UHF' else (144, 148)
    for key in ('rx', 'tx'):
        if not isinstance(s[key], str) or not re.fullmatch(r'\d{3}(?:\.\d{1,4})?', s[key]):
            raise ValueError(key.upper() + ': enter MHz with up to four decimal places.')
        n = Decimal(s[key])
        if not low <= n <= high or n % Decimal('0.0025'):
            raise ValueError(f'{key.upper()}: use {low}â€“{high} MHz on a 2.5 kHz grid; check your local band plan.')
        if s['band'] == 'UHF' and Decimal('435.000') <= n <= Decimal('438.000'):
            raise ValueError(key.upper() + ': Blocked satellite range (435.000–438.000 MHz).')
        s[key] = f'{n:.4f}'
    for key, low, high in [('bandwidth', 0, 1), ('squelch', 0, 8), ('volume', 1, 8)]:
        if type(s[key]) is not int or not low <= s[key] <= high:
            raise ValueError(f'{key}: use an integer from {low} to {high}.')
    for key in ('rx_ctcss', 'tx_ctcss'):
        if s[key] not in TONES:
            raise ValueError('Choose one of the 38 supported CTCSS tones or Off.')
    for key in ('reverse_burst', 'emphasis', 'highpass', 'lowpass'):
        if type(s[key]) is not bool:
            raise ValueError(key + ' must be true or false.')
    if s['reverse_burst'] and s['tx_ctcss'] == '0':
        raise ValueError('Reverse burst requires a TX CTCSS tone.')
    return s


def commands(s):
    s = validate(s)
    tone = lambda key: f'{TONES.index(s[key]):04d}'
    return [
        (f"AT+DMOSETGROUP={s['bandwidth']},{s['tx']},{s['rx']},{tone('tx_ctcss')},{s['squelch']},{tone('rx_ctcss')}", '+DMOSETGROUP:0'),
        (f"AT+DMOSETVOLUME={s['volume']}", '+DMOSETVOLUME:0'),
        ('AT+SETFILTER=' + ','.join(str(int(not s[k])) for k in ('emphasis', 'highpass', 'lowpass')), '+DMOSETFILTER:0'),
        (f"AT+SETTAIL={int(s['reverse_burst'])}", '+DMOSETTAIL:0')]


def uart_reboot_required(root, boot_id_path=Path('/proc/sys/kernel/random/boot_id'),
                         boot_stat_path=Path('/proc/stat')):
    """True only when UART configuration changed during this boot; None if unknown.

    New installers record a boot ID. Legacy empty markers use Linux boot time,
    so retaining the marker after reboot does not leave a permanent warning.
    """
    marker = Path(root) / 'serial-reboot-required'
    try:
        saved = marker.read_text().strip()
    except FileNotFoundError:
        return False
    except OSError:
        return None
    try:
        if saved.startswith('boot_id='):
            previous = saved.removeprefix('boot_id=')
            current = Path(boot_id_path).read_text().strip()
            return previous == current if previous and current else None
        if saved:
            return None
        boot_time = next(int(line.split()[1]) for line in Path(boot_stat_path).read_text().splitlines()
                         if line.startswith('btime '))
        return marker.stat().st_mtime >= boot_time
    except (OSError, ValueError, IndexError, StopIteration):
        return None


def ports():
    found = {}
    for pattern in ('/dev/serial/by-id/*', '/dev/serial0', '/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyAMA*', '/dev/ttyS*'):
        for path in sorted(glob.glob(pattern)):
            real = os.path.realpath(path)
            found.setdefault(real, {'path': path, 'device': real, 'accessible': os.access(path, os.R_OK | os.W_OK)})
    return list(found.values())


def maintenance_guard():
    # Acknowledgement alone is insufficient: deny access while any known RF worker runs.
    for unit in ('asterisk', 'allmode-dmr', 'allmode-digital', 'allmode-dstar'):
        result = subprocess.run(['systemctl', 'show', unit, '--property=ActiveState', '--value'],
                                capture_output=True, text=True, timeout=3)
        if result.returncode or result.stdout.strip() not in ('inactive', 'failed'):
            raise ValueError(f'Cannot confirm {unit} is stopped. Stop radio services before commissioning.')


@contextmanager
def serial_session(path):
    import serial
    real = os.path.realpath(path)
    cmdline = Path('/proc/cmdline').read_text()
    console_names = re.findall(r'\bconsole=([^,\s]+)', cmdline)
    if any(os.path.realpath('/dev/' + name) == real for name in console_names):
        raise ValueError('Selected UART is the Linux console. Disable serial login and reboot first.')
    unit = 'serial-getty@' + Path(real).name + '.service'
    getty = subprocess.run(['systemctl','show',unit,'--property=ActiveState','--value'],
                           capture_output=True,text=True,timeout=3)
    if getty.returncode or getty.stdout.strip() not in ('inactive','failed'):
        raise ValueError('Selected UART has an active or unknown serial login service. Disable it first.')
    # Shared with existing RSSI reader, plus kernel exclusive open.
    import radio_readback
    with radio_readback.serial_lock(blocking=True):
        port = serial.Serial(port=None, baudrate=9600, timeout=.2, write_timeout=1, exclusive=True)
        port.dtr = False
        port.rts = False
        port.port = path
        try:
            port.open()
            yield port
        finally:
            port.close()


class Hardware:
    def __init__(self, root=None, enabled=False, transport=serial_session, guard=maintenance_guard):
        self.root = Path(root or os.environ.get('ALLMODE_HARDWARE_STATE', '/var/lib/allmode'))
        self.enabled = enabled
        self.transport = transport
        self.guard = guard
        self.lock = threading.Lock()
        self.events = []

    def read(self, name):
        try:
            return json.loads((self.root / name).read_text())
        except (OSError, ValueError):
            return None

    def write(self, name, value):
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / (name + '.tmp')
        with temporary.open('w', encoding='utf-8') as file:
            json.dump(value, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(self.root / name)

    def record(self, message):
        self.events = ([{'time': datetime.now(timezone.utc).isoformat(), 'message': message}] + self.events)[:60]
        print('SA818: ' + message, flush=True)

    def snapshot(self):
        return dict(enabled=self.enabled, ports=ports(), preset=PRESET, tones=TONES,
                    uart_reboot_required=uart_reboot_required(self.root),
                    draft=self.read('draft.json'), last_program=self.read('program.json'),
                    device=self.read('device.json'), limitation=LIMITATION, events=self.events.copy())

    def exchange(self, port, command, expected=None):
        port.reset_input_buffer()
        port.write((command + '\r\n').encode('ascii'))
        port.flush()
        deadline = time.monotonic() + 2
        received = []
        while time.monotonic() < deadline:
            line = port.read_until(b'\n', 128).decode('ascii', errors='replace').strip()
            if not line or line == command:
                continue
            received.append(line)
            if (expected and line == expected) or (not expected and line.startswith('+VERSION:')):
                self.record(command + ' -> ' + line)
                return line
            if len(received) >= 16:
                break
        self.record(command + ' -> rejected, unsupported or timed out: ' + repr(received))
        raise ValueError('No valid acknowledgement for ' + command.split('=')[0] + '. Check power, UART, permissions and firmware; see logs.')

    def action(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('Expected a JSON object.')
        if not self.lock.acquire(blocking=False):
            raise ValueError('Hardware operation in progress; wait before retrying.')
        try:
            action = payload.get('action')
            if action == 'rssi':
                if not self.enabled:
                    raise ValueError('Hardware access is disabled.')
                from radio_readback import set_paused
                return set_paused(payload.get('paused'))
            if action in ('preview', 'save', 'program'):
                settings = validate(payload.get('settings'))
                plan = commands(settings)
                if action == 'preview':
                    return dict(settings=settings, commands=[c for c, _ in plan], limitation=LIMITATION)
                if action == 'save':
                    self.write('draft.json', settings)
                    self.record('Draft saved locally; no radio commands sent.')
                    return self.snapshot()
            elif action != 'probe':
                raise ValueError('Unknown hardware action.')
            if not self.enabled:
                raise ValueError('Hardware access is disabled. Start with --hardware for commissioning.')
            if uart_reboot_required(self.root) is True:
                raise ValueError('GPIO serial configuration needs a reboot. Reboot the Pi, then refresh ports before testing or programming. Saved drafts are retained.')
            if payload.get('safe') is not True:
                raise ValueError('Confirm the RF safety checklist before opening the serial port.')
            if action == 'program' and payload.get('confirm') != 'PROGRAM':
                raise ValueError('Type PROGRAM to confirm the reviewed configuration.')
            path = payload.get('port')
            if not isinstance(path, str) or path not in [p['path'] for p in ports()]:
                raise ValueError('Select a detected serial port. Refresh detection after reconnecting hardware.')
            self.guard()
            with self.transport(path) as port:
                # Recheck under the shared lock so activation cannot race the initial check.
                self.guard()
                self.exchange(port, 'AT+DMOCONNECT', '+DMOCONNECT:0')
                if action == 'probe':
                    try:
                        version = self.exchange(port, 'AT+VERSION')
                    except ValueError:
                        version = 'Version query unsupported or timed out; handshake succeeded.'
                    self.write('device.json', dict(port=path, version=version, checked_at=datetime.now(timezone.utc).isoformat(), note='Last observation, not continuous status. Band cannot be autodetected.'))
                else:
                    record = dict(settings=settings, port=path, state='incomplete', acknowledged=[],
                                  time=datetime.now(timezone.utc).isoformat(), verified_by_readback=False)
                    # Persist uncertainty BEFORE the first mutating command; survive power loss.
                    self.write('program.json', record)
                    try:
                        for command, expected in plan:
                            self.guard()
                            self.exchange(port, command, expected)
                            record['acknowledged'].append(command.split('=')[0])
                            self.write('program.json', record)
                        record['state'] = 'acknowledged-not-verified'
                    except Exception:
                        self.record('Programming incomplete: some settings may have changed. No automatic rollback. Review and reprogram the complete set.')
                        raise
                    finally:
                        self.write('program.json', record)
            return self.snapshot()
        finally:
            self.lock.release()
