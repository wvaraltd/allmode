import importlib.util
import os
import pathlib
import subprocess
import tempfile
import unittest
P = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_modes', P/'package_modes.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class PackageModes(unittest.TestCase):
    def test_normalize_both_umasks_and_root(self):
        for mask in (0o002, 0o077):
            with self.subTest(mask=mask), tempfile.TemporaryDirectory() as td:
                old = os.umask(mask)
                try:
                    root=pathlib.Path(td)/'stage'; (root/'DEBIAN').mkdir(parents=True)
                    (root/'DEBIAN/preinst').write_text('#!/bin/sh\n')
                    (root/'ordinary').write_text('x'); (root/'ordinary').chmod(0o777)
                    (root/'secret-looking-name').write_text('generic only')
                    m.normalize(root,m.HOOKS)
                    self.assertEqual(root.stat().st_mode&0o7777,0o755)
                    self.assertEqual((root/'DEBIAN').stat().st_mode&0o7777,0o755)
                    self.assertEqual((root/'DEBIAN/preinst').stat().st_mode&0o7777,0o755)
                    self.assertEqual((root/'ordinary').stat().st_mode&0o7777,0o644)
                finally: os.umask(old)

    def test_links_and_specials_refused_without_target_chmod(self):
        for kind in ('symlink','hardlink','fifo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                base=pathlib.Path(td); target=base/'target';target.write_text('x');target.chmod(0o600)
                root=base/'stage';root.mkdir(); link=root/'unsafe'
                if kind=='symlink':link.symlink_to(target)
                elif kind=='hardlink':os.link(target,link)
                else:os.mkfifo(link)
                with self.assertRaises((ValueError,OSError)):m.normalize(root)
                self.assertEqual(target.stat().st_mode&0o777,0o600)

    def test_real_addon_archives_under_both_umasks(self):
        for mask in ('002','077'):
            with self.subTest(mask=mask), tempfile.TemporaryDirectory() as td:
                subprocess.run(['sh','-c','umask "$1"; exec python3 "$2" --output "$3"',
                                'test',mask,str(P/'build-dvswitch-addon.py'),td],check=True,capture_output=True)
                for package in pathlib.Path(td).glob('*.deb'):
                    self.assertGreater(m.validate_archive(package),0)
                stage=pathlib.Path(td)/'guard-stage'
                (stage/'usr/lib/systemd/system/mmdvm_bridge.service.d').chmod(0o775)
                bad=pathlib.Path(td)/'bad.deb'
                subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(bad)],check=True,capture_output=True)
                with self.assertRaisesRegex(ValueError,'ownership/mode'):m.validate_archive(bad)

if __name__=='__main__':unittest.main()
