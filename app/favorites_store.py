"""Versioned station favorites. No RF actions occur without a transaction adapter."""
import contextlib
import fcntl
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

MODES = {'AllStar', 'EchoLink', 'DMR', 'YSF', 'NXDN', 'P25', 'M17', 'D-STAR'}
MAX_FAVORITES = 100


class ConflictError(ValueError):
    """The caller must review/reload rather than retrying an old write."""


def identity(row):
    return row['mode'], row['target'], row.get('network')


def normalize(row, *, existing=None, loading=False, legacy=False):
    if not isinstance(row, dict):
        raise ValueError('Each favorite must be an object.')
    allowed = {'id', 'mode', 'target', 'network', 'source_id', 'note', 'slot', 'enabled'}
    if set(row) - allowed:
        raise ValueError('Unknown favorite fields.')
    mode, target = row.get('mode'), row.get('target')
    if not isinstance(mode, str) or mode not in MODES:
        raise ValueError('Choose a supported favorite mode.')
    if not isinstance(target, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _./#-]{0,47}', target) or target != target.strip():
        raise ValueError('Enter a valid destination (up to 48 ASCII characters).')
    if mode in {'AllStar', 'EchoLink', 'DMR', 'YSF', 'NXDN', 'P25'} and not re.fullmatch(r'[0-9]+', target):
        raise ValueError('This favorite mode needs a numeric destination.')
    limits = {'AllStar': (1000, 999999), 'EchoLink': (1, 999999), 'DMR': (1, 16777215), 'YSF': (0, 99999), 'NXDN': (1, 65535), 'P25': (1, 16777215)}
    if mode in limits and not limits[mode][0] <= int(target) <= limits[mode][1]:
        raise ValueError('Destination is outside the range for this mode.')
    patterns = {'AllStar': r'[0-9]{4,6}', 'EchoLink': r'[0-9]{1,6}',
                'D-STAR': r'(?:REF|DCS|XRF)[0-9]{3} ?[A-Z]',
                'M17': r'M17-[A-Z0-9]{3} [A-Z]'}
    if mode in patterns and not re.fullmatch(patterns[mode], target):
        raise ValueError('Destination format is invalid for '+mode+'. Review before saving/importing.')
    network = row.get('network')
    if mode == 'DMR':
        if network not in ('BrandMeister', 'TGIF'):
            raise ValueError('Select BrandMeister or TGIF for every DMR favorite before saving/importing.')
    elif network not in (None, ''):
        raise ValueError('Only DMR favorites have a network selection.')
    else:
        network = None
    source = row.get('source_id')
    if source == '' and isinstance(source, str):
        source = None
    if source is not None and (not isinstance(source, str) or not re.fullmatch(r'[0-9]{1,8}', source) or int(source) == 0):
        raise ValueError('Source ID must contain 1–8 digits and be nonzero.')
    note = row.get('note', '')
    if not isinstance(note, str) or len(note) > 500 or any(ord(c) < 32 and c not in '\n\t' for c in note):
        raise ValueError('Favorite notes must be text of at most 500 characters.')
    slot = row.get('slot')
    if slot is not None and (not isinstance(slot, str) or not re.fullmatch(r'[1-9][0-9]{0,2}', slot)):
        raise ValueError('Memory slots must be 1–999 without leading zeros.')
    enabled = row.get('enabled', False)
    if type(enabled) is not bool or (enabled and slot is None):
        raise ValueError('Enabled RF memories need a slot and a true/false enable selection.')
    ident = row.get('id')
    if legacy:
        if ident is not None or slot is not None or enabled:
            raise ValueError('Import only browser favorites, without station IDs or RF assignments.')
        ident = str(uuid.uuid4())
    elif ident is None and not loading:
        ident = str(uuid.uuid4())
    else:
        if not isinstance(ident, str):
            raise ValueError('Favorite ID is required.')
        try:
            if str(uuid.UUID(ident)) != ident:
                raise ValueError()
        except (ValueError, AttributeError):
            raise ValueError('Invalid favorite ID.') from None
        if not loading and ident not in existing:
            raise ConflictError('Favorite no longer exists. Reload before saving.')
    return dict(id=ident, mode=mode, target=target, network=network, source_id=source,
                note=note, slot=slot, enabled=enabled)


def validate_rows(rows, **kwargs):
    if not isinstance(rows, list) or len(rows) > MAX_FAVORITES:
        raise ValueError('Supply at most 100 favorites.')
    result = [normalize(row, **kwargs) for row in rows]
    ids, destinations, slots = set(), set(), []
    for row in result:
        if row['id'] in ids:
            raise ConflictError('Duplicate favorite ID.')
        ids.add(row['id'])
        if identity(row) in destinations:
            raise ConflictError('Duplicate destination/network. Review the favorite list.')
        destinations.add(identity(row))
        slot = row['slot']
        if slot is not None:
            if any(slot.startswith(other) or other.startswith(slot) for other in slots):
                raise ConflictError('RF memory slots overlap: choose distinct non-prefix numbers (for example 11 and 12, not 1 and 12).')
            slots.append(slot)
    return result


class Store:
    def __init__(self, path, transaction=None):
        self.path = Path(path)
        self.transaction = transaction
        self.recovery_path = Path(str(self.path) + ".recovery-required")
        self._recovery_required = False

    @contextlib.contextmanager
    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _read(self):
        if self._recovery_required or self.recovery_path.exists():
            raise ValueError('Favorites recovery is required after a storage failure; restore the recorded previous snapshot before saving or recalling.')
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {'revision': 0, 'favorites': []}
        if not isinstance(value, dict) or set(value) != {'revision', 'favorites'} or type(value['revision']) is not int or value['revision'] < 0:
            raise ValueError('Station favorites are corrupt; restore a verified backup.')
        value['favorites'] = validate_rows(value['favorites'], loading=True)
        return value

    def snapshot(self):
        with self._lock():
            return self._read()

    def _sync_directory(self):
        directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _replace_bytes(self, data):
        fd, name = tempfile.mkstemp(prefix=self.path.name + '.', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            self._sync_directory()
        finally:
            Path(name).unlink(missing_ok=True)

    def _write(self, value):
        # A failed directory fsync can occur AFTER rename made the new revision
        # visible. Restore exact prior bytes (or absence), not just the temp file.
        previous = self.path.read_bytes() if self.path.exists() else None
        try:
            self._replace_bytes((json.dumps(value, indent=2)+'\n').encode('utf-8'))
        except BaseException:
            try:
                if previous is None:
                    self.path.unlink(missing_ok=True)
                    self._sync_directory()
                else:
                    self._replace_bytes(previous)
            except BaseException as restore_error:
                self._recovery_required = True
                # Persistent storage failure must not silently expose the new
                # revision. A private recovery record blocks future instances
                # and retains the previous snapshot for administrator recovery.
                try:
                    fd = os.open(self.recovery_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                        json.dump({'previous': previous.decode('utf-8') if previous is not None else None}, stream)
                        stream.flush()
                        os.fsync(stream.fileno())
                    self._sync_directory()
                except OSError:
                    pass  # Current instance remains blocked even if storage is unusable.
                raise OSError('Favorites write and rollback failed; administrator recovery is required.') from restore_error
            raise

    def _update(self, payload, importing):
        if not isinstance(payload, dict) or set(payload) != {'revision', 'favorites'} or type(payload['revision']) is not int:
            raise ValueError('Supply a revision and favorites list.')
        with self._lock():
            old = self._read()
            if payload['revision'] != old['revision']:
                raise ConflictError('Favorites changed in another browser. Reload and review before saving.')
            if importing:
                raw = payload['favorites']
                if not isinstance(raw, list) or len(raw) > MAX_FAVORITES:
                    raise ValueError('Supply at most 100 browser favorites.')
                rows = list(old['favorites'])
                found = {identity(row): row for row in rows}
                for entry in raw:
                    row = normalize(entry, legacy=True)
                    key = identity(row)
                    if key in found:
                        previous = found[key]
                        if row['note'] != previous['note'] or row['source_id'] != previous['source_id']:
                            raise ConflictError('An imported favorite has a different note or source ID. Review and resolve before importing.')
                    else:
                        rows.append(row)
                        found[key] = row
                rows = validate_rows(rows, loading=True)
            else:
                rows = validate_rows(payload['favorites'], existing={r['id'] for r in old['favorites']})
            new = {'revision': old['revision'] + 1, 'favorites': rows}
            if self.transaction is None and (any(r['enabled'] for r in rows) or any(r['enabled'] for r in old['favorites'])):
                raise ValueError('RF memory service is unavailable; assignments cannot be applied safely.')
            transaction = self.transaction(old, new) if self.transaction else contextlib.nullcontext()
            with transaction:
                self._write(new)
            return new

    def replace(self, payload):
        return self._update(payload, False)

    def import_legacy(self, payload):
        return self._update(payload, True)
