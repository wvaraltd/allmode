#!/usr/bin/env python3
"""Update ALLMODE owner-password validation to 4 characters; preserve credentials."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPLACEMENTS = {
    'web_auth.py': [('8<=len(password)<=128', '4<=len(password)<=128'),
                    ('8–128', '4–128')],
    'system_service.py': [('8<=len(password)<=128', '4<=len(password)<=128')],
    'web/claim.html': [('minlength="8" maxlength="128"', 'minlength="4" maxlength="128"')],
    'web/operator.js': [('minlength="8" maxlength="128"', 'minlength="4" maxlength="128"')],
}

def apply(root):
    prepared = []
    for name, replacements in REPLACEMENTS.items():
        path = root/name
        before = path.read_text(encoding='utf-8')
        after = before
        for old, new in replacements:
            if old not in after and new not in after:
                raise RuntimeError('Unrecognized ALLMODE version: '+name)
            after = after.replace(old, new)
        if path.suffix == '.py':
            compile(after, str(path), 'exec')
        if after != before:
            prepared.append((path, after))
    # Validate every file before changing any file; retain original copies.
    for path, after in prepared:
        backup = path.with_name(path.name+'.before-password-min4')
        if not backup.exists():
            shutil.copy2(path, backup)
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.password-min4-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(after)
            os.chmod(temp, path.stat().st_mode & 0o777)
            if hasattr(os, 'chown'):
                os.chown(temp, path.stat().st_uid, path.stat().st_gid)
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)
    return len(prepared)

if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Run: sudo python3 password-min4.py')
    apply(Path('/opt/allmode'))
    subprocess.run(['systemctl', 'restart', 'allmode-system', 'allmode-setup'], check=True)
    print('Owner password minimum is now 4 characters. Refresh the setup page.')
