"""Repair only known old package-private directory modes; no shared parents."""
import os
import stat
import subprocess

PATHS = {
    'ara-allmode-dvswitch-guard': 'usr/lib/systemd/system/mmdvm_bridge.service.d',
    'ara-allmode-dvswitch': 'usr/share/doc/ara-allmode-dvswitch',
    'ara-allmode-meter': 'usr/share/doc/ara-allmode-meter',
}

def repair(root, relative):
    if relative not in PATHS.values():
        raise ValueError('Not a package-private directory')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = relative.split('/')
        for i, part in enumerate(parts):
            info = os.fstat(fd)
            if info.st_uid != 0 or info.st_gid != 0 or info.st_mode & 0o022:
                raise ValueError('Untrusted directory ancestor')
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        info = os.fstat(fd)
        if info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) not in (0o755, 0o775):
            raise ValueError('Unexpected package-private directory ownership/mode')
        if stat.S_IMODE(info.st_mode) == 0o775:
            os.fchmod(fd, 0o755)
            os.fsync(fd)
    finally:
        os.close(fd)

def migrate(package):
    relative = PATHS[package]
    expected = package + ': /' + relative
    owners = subprocess.check_output(['dpkg-query', '-S', '/' + relative], text=True).splitlines()
    if owners != [expected]:
        raise ValueError('Directory is not exclusively owned by expected package')
    repair('/', relative)
