import importlib.util
import pathlib
import subprocess
import tempfile
import unittest
P=pathlib.Path(__file__).resolve().parents[1]

class StaticDirectoryMigration(unittest.TestCase):
    def test_namespace_leaf_repair_and_refusals(self):
        capability=subprocess.run(['unshare','-Ur','true'],capture_output=True)
        if capability.returncode:self.skipTest('User namespace unavailable; native disposable root test required')
        program=r'''
import importlib.util,pathlib,tempfile,os
s=importlib.util.spec_from_file_location('migration',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
for relative in m.PATHS.values():
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);leaf=root/relative;leaf.mkdir(parents=True)
  for p in leaf.parents:
   if p==root:break
   p.chmod(0o755)
  leaf.chmod(0o775);m.repair(root,relative);assert leaf.stat().st_mode&0o7777==0o755
  m.repair(root,relative)
  leaf.chmod(0o700)
  try:m.repair(root,relative)
  except ValueError:pass
  else:raise AssertionError('unexpected private mode accepted')
  leaf.chmod(0o775);leaf.parent.chmod(0o775)
  try:m.repair(root,relative)
  except ValueError:pass
  else:raise AssertionError('writable shared parent accepted')
  assert leaf.parent.stat().st_mode&0o777==0o775
  leaf.parent.chmod(0o755);leaf.rmdir();target=root/'outside';target.mkdir(mode=0o775);target.chmod(0o775);leaf.symlink_to(target)
  try:m.repair(root,relative)
  except OSError:pass
  else:raise AssertionError('symlink accepted')
  assert target.stat().st_mode&0o777==0o775
'''.replace('SOURCE',repr(str(P/'static_dir_migration.py')))
        subprocess.run(['unshare','-Ur','python3','-c',program],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
