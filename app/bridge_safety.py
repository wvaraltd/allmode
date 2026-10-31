"""Systemd stop hook: a stopped console must not leave a cross-network bridge running."""
import re, subprocess, sys
import digital
class Node:
 def __init__(self,node):self.node=node
 def run_cli(self,command):
  result=subprocess.run(['/usr/sbin/asterisk','-rx',command],capture_output=True,text=True,timeout=5)
  if result.returncode:raise RuntimeError('Asterisk unavailable')
  return result.stdout
if __name__=='__main__':
 node=sys.argv[1]
 if not re.fullmatch(r'[0-9]{4,10}',node):raise SystemExit('Invalid node')
 data=digital.load('bridge.json',{})
 if data.get('enabled'):
  controller=Node(node)
  digital.forwarding(controller,False)
  for row in data.get('connections',[]):
   peer=digital.peer(row['mode'],digital.validate(row['mode'],row['target'],node))
   controller.run_cli(f'rpt cmd {node} ilink 1 {peer}')
  for mode in digital.load('digital-modes.json',['DMR']):
   if mode in digital.PROFILES:digital.unlink(mode)
  digital.request(['DMR'])
