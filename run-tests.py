"""Run legacy application tests with appliance state isolated in a temporary tree.

Never run this as root. Mocked Asterisk tests and loopback peers do not need it.
The runner redirects fixed appliance state paths, not codec or application code.
"""
import contextlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

if os.geteuid() == 0:
    raise SystemExit('Run tests as an ordinary user, never sudo.')
root = Path(__file__).resolve().parent
os.environ['ALLMODE_VOCODER_ROOT'] = str(root/'codec')
sys.path.insert(0, str(root/'app'))
suite = unittest.defaultTestLoader.discover(str(root/'app'))
import codec_selection, m17_native, p25_native, ysf_native, nxdn_native, dmr_native
with tempfile.TemporaryDirectory(prefix='allmode-tests-') as temp, contextlib.ExitStack() as stack:
    state = Path(temp)
    prefixes = ('/var/lib/asterisk/allmode', '/var/lib/allmode', '/var/lib/allmode-system', '/etc/allmode', '/opt/allmode-dmr')
    def redirect(value):
        text = str(value)
        if any(text == p or text.startswith(p+'/') for p in prefixes):
            target = state/text.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            return target
        return value
    class StatePath(type(Path())):
        def __new__(cls, *args):
            return super().__new__(cls, redirect(Path(*args)))
        def __init__(self, *args):
            super().__init__(redirect(Path(*args)))
    for prefix in prefixes:
        (state/prefix.lstrip('/')).mkdir(parents=True, exist_ok=True)
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if not filename or not Path(filename).is_relative_to(root/'app'):
            continue
        for name, value in list(vars(module).items()):
            if value is Path:
                stack.enter_context(patch.object(module, name, StatePath))
            elif isinstance(value, Path) and str(redirect(value)) != str(value):
                stack.enter_context(patch.object(module, name, redirect(value)))
    original_open = os.open
    def state_open(path, *args, **kwargs):
        return original_open(redirect(path), *args, **kwargs)
    stack.enter_context(patch('os.open', state_open))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
