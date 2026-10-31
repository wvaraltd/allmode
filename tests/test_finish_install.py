import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = os.environ.get('BASH', 'bash')
PREAMBLE = 'source ./finish-install.sh\nsystemctl() { echo REBOOT_CALLED; }\n'


class FinishInstallTests(unittest.TestCase):
    def run_shell(self, script):
        return subprocess.run([BASH, '-c', script], cwd=ROOT, input='yes\n', text=True,
                              capture_output=True, timeout=5)

    def test_noninteractive_never_reboots_even_with_yes_input(self):
        r = self.run_shell(PREAMBLE + 'allmode_offer_reboot true')
        self.assertEqual(r.returncode, 0)
        self.assertIn('REBOOT REQUIRED', r.stdout)
        self.assertIn('Noninteractive', r.stdout)
        self.assertNotIn('REBOOT_CALLED', r.stdout)

    def test_nochange_and_unknown_do_not_prompt(self):
        for state in ('false', 'unknown'):
            r = self.run_shell(PREAMBLE + 'allmode_offer_reboot ' + state)
            self.assertEqual(r.returncode, 0)
            self.assertNotIn('Reboot now?', r.stdout)
            self.assertNotIn('REBOOT_CALLED', r.stdout)

    def test_failed_prior_install_does_not_reach_offer(self):
        r = self.run_shell('set -e\n' + PREAMBLE + 'false\nallmode_offer_reboot true')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('REBOOT', r.stdout)

    @unittest.skipUnless(os.name == 'posix', 'Requires a POSIX pseudo-terminal')
    def test_interactive_yes_and_decline(self):
        import pty
        import select
        import time
        for answer, expected in ((b'n\n', False), (b'y\n', True)):
            master, slave = pty.openpty()
            process = subprocess.Popen([BASH, '-c', PREAMBLE + 'allmode_offer_reboot true'],
                                       cwd=ROOT, stdin=slave, stdout=slave, stderr=slave)
            os.close(slave)
            output = b''
            try:
                deadline = time.monotonic() + 5
                sent = False
                while time.monotonic() < deadline:
                    if select.select([master], [], [], .1)[0]:
                        try:
                            chunk = os.read(master, 4096)
                        except OSError:
                            break
                        if not chunk:
                            break
                        output += chunk
                        if b'Reboot now?' in output and not sent:
                            os.write(master, answer)
                            sent = True
                process.wait(timeout=1)
                self.assertEqual(process.returncode, 0, output)
                self.assertEqual(b'REBOOT_CALLED' in output, expected, output)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)


if __name__ == '__main__':
    unittest.main()
