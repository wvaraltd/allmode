"""Run exact installed Asterisk with no channel/network modules, synthetic input only."""
import pathlib, subprocess, time
root=pathlib.Path(__file__).resolve().parent
isolated=root/'isolated'
for name in ('etc','run','log','spool','var','db','keys','modules','data'):(isolated/name).mkdir(parents=True,exist_ok=True)
docs=isolated/'data/documentation'
if not docs.exists():docs.symlink_to('/usr/share/asterisk/documentation',target_is_directory=True)
conf='[directories]\n'+''.join(f'{key} => {isolated/value}\n' for key,value in {
 'astetcdir':'etc','astmoddir':'modules','astvarlibdir':'var','astdbdir':'db',
 'astkeydir':'keys','astdatadir':'data','astagidir':'data','astspooldir':'spool',
 'astrundir':'run','astlogdir':'log'}.items())+'\n[options]\nverbose = 0\ndebug = 0\n'
(isolated/'etc/asterisk.conf').write_text(conf)
(isolated/'etc/modules.conf').write_text('[modules]\nautoload=no\nload=format_allmode_meter.so\n')
(isolated/'etc/logger.conf').write_text('[logfiles]\nconsole=error,warning,notice\n')
log=root/'isolated-test.log'
with log.open('w') as out:
 proc=subprocess.Popen(['/usr/sbin/asterisk','-f','-n','-C',str(isolated/'etc/asterisk.conf')],stdout=out,stderr=out)
 try:
  end=time.monotonic()+15
  while time.monotonic()<end:
   time.sleep(.1)
   text=log.read_text(errors='replace')
   if 'Asterisk Ready.' in text:break
   if proc.poll() is not None:raise RuntimeError('Isolated Asterisk exited; inspect isolated-test.log')
  else:raise RuntimeError('Self-test did not complete; inspect isolated-test.log')
  invoke=subprocess.run(['/usr/sbin/asterisk','-C',str(isolated/'etc/asterisk.conf'),'-rx','allmode meter selftest'],capture_output=True,text=True,timeout=3)
  time.sleep(.1);text=log.read_text(errors='replace')
  if 'ALLMODE_SELFTEST_PASS' not in text:raise RuntimeError('Module test failed: '+invoke.stdout)
  query=subprocess.run(['/usr/sbin/asterisk','-C',str(isolated/'etc/asterisk.conf'),'-rx','module show'],capture_output=True,text=True,timeout=3)
  print(query.stdout)
  print(next(line for line in text.splitlines() if 'ALLMODE_SELFTEST_PASS' in line))
 finally:
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
