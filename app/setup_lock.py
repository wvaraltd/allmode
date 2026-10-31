"""Cross-process lock shared by wizard saves and codec selection."""
from contextlib import contextmanager
from pathlib import Path
import os
@contextmanager
def setup_lock(path):
    import fcntl
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path.with_name('.station-setup.lock'),os.O_CREAT|os.O_RDWR,0o600)
    try:
        if os.geteuid()==0 and path==Path('/var/lib/allmode/station-setup.json'):
            import pwd
            account=pwd.getpwnam('allmode');os.fchown(fd,account.pw_uid,account.pw_gid)
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
