"""Read-only public directories. AllStar uses one bounded, nonblocking cache."""
from collections import OrderedDict
import json
import math
import re
import threading
import time
import urllib.error
import urllib.request
from operator_store import atomic

# Official root canonicalizes to this same-origin feed; do not follow redirects.
ALLSTAR_URL = 'https://allmondb.allstarlink.org/allmondb.php'
TTL = 900  # Same refresh interval as the official Allmon3 client.
MAX_STALE = 7 * 86400
MAX_BYTES = 8 * 1024 * 1024
MAX_CACHE_BYTES = 64 * 1024 * 1024  # JSON expansion of the bounded text feed.
MAX_ROWS = 100000
LOCK = threading.Lock()
CACHES = OrderedDict()


def node_id(value):
    return isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{3,5}', value) is not None


def text(value):
    if not isinstance(value, str):
        return ''
    # Plain data, not HTML; clients must still escape at their output sink.
    return ' '.join(re.sub(r'[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]', ' ', value).split())[:120]


def normalized(row):
    if not isinstance(row, dict) or not node_id(row.get('target')):
        return None
    fields = {key: text(row.get(key)) for key in ('callsign', 'description', 'location')}
    names = list(dict.fromkeys(value for value in fields.values() if value))
    # Reuse the existing local cache's name without inventing missing fields.
    name = ' · '.join(names) if names else text(row.get('name'))
    return dict(target=row['target'], name=name, **fields)


def parse(raw):
    rows = OrderedDict()
    for line in raw.decode('utf-8', errors='replace').splitlines():
        fields = line.split('|')
        if len(fields) != 4:
            continue
        row = normalized(dict(zip(('target', 'callsign', 'description', 'location'), fields)))
        if row and row['target'] not in rows:  # Stable first-row policy for duplicates.
            rows[row['target']] = row
        if len(rows) >= MAX_ROWS:
            break
    if not rows:
        raise ValueError('Empty or invalid AllStar directory.')
    return list(rows.values())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Directory redirects are not permitted.')


def download():
    # Only this fixed public HTTPS origin; no URLs or credentials from the caller.
    request = urllib.request.Request(ALLSTAR_URL, headers={
        'User-Agent': 'ARA-AllMode/0.8 node display', 'Accept': 'text/plain'})
    deadline = time.monotonic() + 10
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=5) as response:
        chunks, size = [], 0
        while True:
            block = response.read1(min(65536, MAX_BYTES + 1 - size))
            size += len(block)
            if size > MAX_BYTES or time.monotonic() > deadline:
                raise ValueError('Directory response exceeds limits.')
            if not block:
                break
            chunks.append(block)
    return b''.join(chunks)


def timestamp(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else 0


class AllStarCache:
    def __init__(self, root):
        self.path = root / 'directory-AllStar.json'
        self.lock = threading.Lock()
        self.rows = {}
        self.updated = self.attempt = 0
        self.error = None
        self.refreshing = False
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(MAX_CACHE_BYTES + 1)
            if len(raw) > MAX_CACHE_BYTES:
                raise ValueError('Cache too large.')
            cached = json.loads(raw)
            if not isinstance(cached, dict) or not isinstance(cached.get('rows'), list):
                raise ValueError('Invalid cache.')
            for item in cached['rows'][:MAX_ROWS]:
                row = normalized(item)
                if row and row['target'] not in self.rows:
                    self.rows[row['target']] = row
            self.updated = timestamp(cached.get('updated'))
            self.attempt = timestamp(cached.get('attempt'))
            self.error = 'Directory refresh unavailable; using cached entries.' if cached.get('error') else None
        except (OSError, ValueError):
            pass

    def snapshot(self, targets=None):
        with self.lock:
            now = time.time()
            # Future timestamps (clock changes/corruption) must not suppress retries.
            if not self.refreshing and not (self.attempt and 0 <= now - self.attempt < TTL):
                self.attempt, self.refreshing = now, True
                threading.Thread(target=self.refresh, daemon=True, name='allstar-directory').start()
            usable = bool(self.updated) and 0 <= now - self.updated <= MAX_STALE
            rows = self.rows if usable else {}
            selected = rows.values() if targets is None else (rows[n] for n in targets if n in rows)
            return {'source': 'AllStar', 'url': ALLSTAR_URL, 'updated': self.updated or None,
                    'rows': list(selected), 'error': self.error, 'refreshing': self.refreshing,
                    'stale': not usable or now - self.updated >= TTL,
                    'expires_in': max(0, min(60, MAX_STALE - (now - self.updated))) if usable else 0}

    def refresh(self):
        try:
            rows = parse(download())
            with self.lock:
                self.rows = {row['target']: row for row in rows}
                self.updated, self.error = time.time(), None
        except (OSError, ValueError):
            with self.lock:
                self.error = 'Directory refresh failed. Showing cached entries if available.'
        finally:
            # Keep the in-memory backoff even when disk persistence is unavailable.
            with self.lock:
                self.attempt = time.time()
                value = dict(source='AllStar', url=ALLSTAR_URL, updated=self.updated,
                             attempt=self.attempt, rows=list(self.rows.values()), error=self.error)
            try:
                atomic(self.path, value)
            except OSError:
                with self.lock:
                    self.error = 'Directory cache could not be saved; using memory until restart.'
            finally:
                with self.lock:
                    self.refreshing = False


def cache(root):
    with LOCK:
        key = str(root)
        if key not in CACHES:
            # There is normally one station root per server. Bound test/multi-root use.
            if len(CACHES) >= 4:
                idle = next((k for k, v in CACHES.items() if not v.refreshing), None)
                if idle is None:
                    raise ValueError('Directory cache is busy.')
                CACHES.pop(idle)
            CACHES[key] = AllStarCache(root)
        CACHES.move_to_end(key)
        return CACHES[key]


def node_names(root, targets):
    if not isinstance(targets, list) or not 1 <= len(targets) <= 100 or any(not node_id(n) for n in targets):
        raise ValueError('Supply 1–100 AllStar node numbers (4–6 digits, no leading zeros).')
    return cache(root).snapshot(list(dict.fromkeys(targets)))


def directory(root, source):
    if source == 'AllStar':
        return cache(root).snapshot()
    import directory_sync
    return directory_sync.listing(source)
