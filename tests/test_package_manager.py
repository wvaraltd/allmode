"""No package mutations: run the helper against shell-function apt mocks."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageLockTests(unittest.TestCase):
    def run_helper(self, mock, timeout=1):
        script = 'source ./package-manager.sh\n' + mock + '\nallmode_apt install -y example\n'
        return subprocess.run([os.environ.get('BASH', 'bash'), '-c', script],
                              cwd=ROOT, text=True, capture_output=True, timeout=10,
                              env={**os.environ, 'ALLMODE_APT_LOCK_TIMEOUT': str(timeout)})

    def test_success_and_native_timeout(self):
        r = self.run_helper('apt-get() { [[ $1 == -o && $2 == DPkg::Lock::Timeout=* && $3 == install ]]; }')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_eventual_unlock_each_lock(self):
        for lock in ('/var/lib/dpkg/lock-frontend', '/var/lib/dpkg/lock', '/var/lib/apt/lists/lock'):
            with self.subTest(lock=lock):
                # Pipeline functions run in a subshell: use a temporary sentinel.
                mock = '''state=$(mktemp); rm "$state"
sleep() { :; }
apt-get() {
 if [[ ! -e $state ]]; then
   touch "$state"
   echo 'E: Could not get lock LOCK. It is held by process 123 (apt-get)'
   return 100
 fi
 rm "$state"; return 0
}'''.replace('LOCK', lock)
                r = self.run_helper(mock, 5)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn('waiting', r.stderr)

    def test_timeout(self):
        r = self.run_helper("apt-get() { echo 'E: Could not get lock /var/lib/dpkg/lock-frontend. It is held by process 123 (apt-get)'; return 100; }")
        self.assertEqual(r.returncode, 100)
        self.assertIn('timed out', r.stderr)

    def test_unrelated_error_preserved(self):
        for status in (42, 100):
            r = self.run_helper("apt-get() { echo 'E: Failed to fetch package'; return %d; }" % status)
            self.assertEqual(r.returncode, status)
            self.assertNotIn('waiting', r.stderr)

    def test_mixed_error_not_retried(self):
        r = self.run_helper("apt-get() { echo 'E: Could not get lock /var/lib/dpkg/lock. It is held by process 123 (apt-get)'; echo 'E: Broken packages'; return 100; }")
        self.assertEqual(r.returncode, 100)
        self.assertNotIn('waiting', r.stderr)

    def test_invalid_timeout(self):
        r = self.run_helper('apt-get() { echo UNEXPECTED; }', 0)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn('UNEXPECTED', r.stdout)


if __name__ == '__main__':
    unittest.main()
