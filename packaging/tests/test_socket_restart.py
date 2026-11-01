import pathlib, socket, subprocess, tempfile, unittest

P=pathlib.Path(__file__).resolve().parents[1]
class SocketRestart(unittest.TestCase):
    def test_cleanup_is_service_user_and_fixed_path(self):
        text=(P/'units/allmode-setup.service').read_text()
        self.assertIn('\nUser=allmode\n',text)
        self.assertIn('\nGroup=allmode\n',text)
        self.assertEqual([line for line in text.splitlines() if line.startswith('ExecStartPre=')],['ExecStartPre=/usr/bin/rm -f /run/allmode-favorites/recall.sock'])
        self.assertIn('/run/allmode-favorites',next(x for x in text.splitlines() if x.startswith('ReadWritePaths=')))
    def cleanup(self,path):
        # Same executable/options, isolated path; no host runtime/service mutation.
        subprocess.run(['/usr/bin/rm','-f',str(path)],check=True)
    def require_unix_socket(self):
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM):pass
        except PermissionError:self.skipTest("Executor denies Unix sockets; must run on native builder")
    def test_missing_socket_cleanup_then_bind(self):
        self.require_unix_socket()
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'recall.sock';self.cleanup(path)
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:s.bind(str(path))
    def test_stale_socket_cleanup_allows_restart(self):
        self.require_unix_socket()
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'recall.sock'
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:s.bind(str(path))
            self.assertTrue(path.is_socket())
            self.cleanup(path)
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:s.bind(str(path))
            self.assertTrue(path.is_socket())
    def test_cleanup_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target=pathlib.Path(d)/'keep';target.write_text('unchanged')
            path=pathlib.Path(d)/'recall.sock';path.symlink_to(target)
            self.cleanup(path);self.assertEqual(target.read_text(),'unchanged')
if __name__=='__main__':unittest.main()
