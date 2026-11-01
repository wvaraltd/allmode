"""Owner-only favorites HTTP adapter and local RF recall dispatcher.

Handler must authenticate and enforce its existing same-origin CSRF policy first.
There is deliberately no HTTP endpoint for RF recall.
"""
import json
import contextlib
import logging
import re
import system_client

MAX_BODY = 1000000


def operation(server, action, payload=None):
    store = getattr(server, 'favorites_store', None)
    if store is not None:
        if action == 'favorites-status': result = store.snapshot()
        elif action == 'favorites-save': result = store.replace(payload)
        elif action == 'favorites-import': result = store.import_legacy(payload)
        else: raise ValueError('Unknown favorites operation.')
        return dict(result, rf={'available': False, 'reason': 'RF memories are unavailable in this local preview.'})
    if action == 'favorites-status': return system_client.request(action)
    return system_client.request(action, payload=payload)


def get(handler, path):
    if path != '/api/favorites': return False
    try:
        handler.reply(200, operation(handler.server, 'favorites-status'))
    except (OSError, ValueError, TypeError):
        handler.reply(503, {'error': 'Station favorites are unavailable. No browser favorites have been changed.'})
    return True


def post(handler, path):
    if path not in ('/api/favorites', '/api/favorites/import'): return False
    try:
        size = int(handler.headers.get('Content-Length', '0'))
        if not 0 < size <= MAX_BODY: raise ValueError('Favorites request is too large or empty.')
        if handler.headers.get('Content-Type') != 'application/json': raise ValueError('JSON required.')
        handler.connection.settimeout(10)
        raw = handler.rfile.read(size)
        if len(raw) != size: raise ValueError('Incomplete favorites request.')
        payload = json.loads(raw)
        if not isinstance(payload, dict): raise ValueError('Expected a JSON object.')
        action = 'favorites-import' if path.endswith('/import') else 'favorites-save'
        handler.reply(200, operation(handler.server, action, payload))
    except system_client.SystemConflictError as error:
        handler.reply(409, {'error': str(error), 'code': 'conflict'})
    except (ValueError, TypeError) as error:
        # Preview Store and system service share the same typed conflict contract.
        from favorites_store import ConflictError
        handler.reply(409 if isinstance(error, ConflictError) else 400, {'error': str(error)})
    except OSError:
        handler.reply(503, {'error': 'Station favorites could not be saved. Check the system service and retry.'})
    return True


@contextlib.contextmanager
def recall_lock(controller):
    # Do not queue RF requests behind another operation: stale key presses must
    # never connect later after the operator has changed destinations.
    if not controller.lock.acquire(blocking=False):
        raise ValueError('Station control is busy. Try the memory again when idle.')
    try:
        yield
    finally:
        controller.lock.release()


def recall(server, slot, digest, connect):
    """Called only by the peer-credential checked Unix socket, never the network."""
    import rf_memories
    if not isinstance(slot, str) or not re.fullmatch(r'[1-9][0-9]{0,2}', slot):
        raise ValueError('Invalid RF memory slot.')
    controller = server.controller
    with recall_lock(controller):
        snapshot = operation(server, 'favorites-status')
        rows = snapshot['favorites']
        if not isinstance(digest, str) or digest != rf_memories.generation(rows):
            raise ValueError('RF memory configuration changed. Save the dial plan again.')
        if not snapshot.get('rf', {}).get('available'):
            raise ValueError('RF memory configuration is not verified.')
        matches = [f for f in rows if f.get('slot') == slot and f.get('enabled') is True]
        if len(matches) != 1: raise ValueError('RF memory is not enabled.')
        current = controller.snapshot()
        if current.get('simulation') or current.get('readonly'):
            raise ValueError('RF controls are unavailable.')
        if current.get('pending'): raise ValueError('Wait for the current request to finish.')
        row = matches[0]
        quick_modes = set(current.get('quick_connect_modes', []))
        if row['mode'] in current.get('unavailable_modes', {}) and row['mode'] not in quick_modes:
            raise ValueError('This RF memory network is unavailable.')
        if row['mode'] not in set(current.get('modes', [])) | quick_modes:
            raise ValueError('This RF memory network is unavailable.')
        import parrot_integration
        if parrot_integration.STATE.state().get('enabled') is not False:
            raise ValueError('Stop the audio test before recalling an RF memory.')
        radio = system_client.request('radio-parrot-state')
        if 'active' not in radio or radio['active']:
            raise ValueError('Stop the radio parrot before recalling an RF memory.')
        result = connect(controller, row['mode'], row['target'], allow_bridge=False,
                         network=row.get('network'), source_id=row.get('source_id'))
        # Do not claim connection establishment or play telemetry over linked networks.
        logging.info('RF memory %s connection requested', slot)
        controller.record('RF memory '+slot+' connection requested.')
        return {'ok': True, 'slot': slot, 'status': 'requested'}
