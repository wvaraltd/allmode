import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == 'posix', 'POSIX permission bits required')
class MarkerPermissionsTests(unittest.TestCase):
    def test_new_and_legacy_markers_are_readable_under_restrictive_umask(self):
        source = (Path(__file__).resolve().parents[1]/'configure-serial.sh').read_text()
        block = source[source.index('# The boot ID is nonsecret;'):source.index("echo 'GPIO UART enabled;")]
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp)/'serial-reboot-required'
            for value in ('boot_id=fixture', ''):
                marker.write_text(value)
                marker.chmod(0o600)
                # Exercise the exact production permission block for both paths.
                script = 'umask 077\n' + block.replace('/var/lib/allmode', temp)
                subprocess.run(['bash', '-c', script], check=True)
                self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o644)
                self.assertEqual(marker.read_text(), value)


if __name__ == '__main__':
    unittest.main()
