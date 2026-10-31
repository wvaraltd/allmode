"""Allowlisted diagnostics: no station files, environment, journals or credentials."""
import datetime
import json
import platform
from pathlib import Path
import subprocess

def run(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return {'exit_code': p.returncode, 'output': p.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {'error': type(e).__name__}

report = {'release': '0.8.0-beta.3', 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'machine': platform.machine(), 'kernel': platform.release(), 'python': platform.python_version()}
report['packages'] = run(['dpkg-query', '-W', '-f=${Package} ${Version}\n', 'asl3', 'asl3-asterisk', 'python3', 'python3-serial', 'python3-bitarray', 'libcodec2-1.2', 'nginx'])
report['services'] = {name: run(['systemctl', 'show', name, '--property=ActiveState,SubState,Result']) for name in ['allmode-setup', 'allmode-system', 'allmode-digital', 'allmode-directories', 'asterisk', 'nginx']}
print(json.dumps(report, indent=2))
