#!/usr/bin/python3
"""No-follow, fd-relative directory setup; never chown through service-user links."""
import grp,os,pwd

def ensure_directory(path,uid,gid,mode):
 if not path.startswith('/') or '..' in path.split('/'):raise ValueError('Absolute normalized path required')
 fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for component in filter(None,path.split('/')):
   try:os.mkdir(component,0o755,dir_fd=fd)
   except FileExistsError:pass
   child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
   os.close(fd);fd=child
  os.fchown(fd,uid,gid);os.fchmod(fd,mode)
 finally:os.close(fd)

def main():
 if os.geteuid()!=0:raise SystemExit('Root required')
 uid=pwd.getpwnam('allmode').pw_uid;gid=grp.getgrnam('allmode').gr_gid
 for path,owner,group,mode in [
  ('/var/lib/allmode',uid,gid,0o750),('/var/lib/allmode/locks',uid,gid,0o750),
  ('/var/lib/asterisk/allmode',uid,gid,0o750),('/var/lib/allmode-system',0,0,0o700),
  ('/var/lib/allmode/directories',uid,gid,0o755),('/opt/allmode-dmr/hosts',uid,gid,0o755)]:
  ensure_directory(path,owner,group,mode)
if __name__=='__main__':main()
