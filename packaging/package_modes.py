"""Deterministic archive modes. Never follow links or chmod outside staging."""
import os
import stat

HOOKS = {'DEBIAN/' + n for n in ('preinst', 'postinst', 'prerm', 'postrm')}
CORE_EXEC = HOOKS | {'usr/libexec/ara-allmode/' + n for n in
                       ('launch.py', 'backup.py', 'secure-dirs.py', 'maintenance-upgrade.py')}

def normalize(root, executables=()):
    executables = set(executables)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    def walk(fd, prefix, change):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            for name in os.listdir(fd):
                child = os.open(name, flags, dir_fd=fd)
                try:
                    walk(child, prefix + '/' + name if prefix else name, change)
                finally:
                    os.close(child)
            if change:
                os.fchmod(fd, 0o755)
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            if change:
                os.fchmod(fd, 0o755 if prefix in executables else 0o644)
        else:
            raise ValueError('Unsupported staging entry: ' + prefix)
    fd = os.open(root, flags | os.O_DIRECTORY)
    try:
        walk(fd, '', False)  # Reject links/special entries before changing modes.
        walk(fd, '', True)
    finally:
        os.close(fd)

def validate_archive(package):
    """Validate actual tar ownership and exact modes, including archive roots."""
    import io
    import subprocess
    import tarfile
    from pathlib import PurePosixPath
    count = 0
    for option, control in (('--fsys-tarfile', False), ('--ctrl-tarfile', True)):
        data = subprocess.check_output(['dpkg-deb', option, str(package)])
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            seen = set()
            for item in archive:
                path = PurePosixPath(item.name)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unsafe archive path: ' + item.name)
                name = str(path)
                if name in seen:
                    raise ValueError('Duplicate archive path: ' + name)
                seen.add(name)
                key = 'DEBIAN/' + name if control else name
                if item.isdir():
                    expected = 0o755
                elif item.isfile():
                    expected = 0o755 if key in CORE_EXEC else 0o644
                else:
                    raise ValueError('Unsupported archive entry: ' + name)
                if item.uid != 0 or item.gid != 0 or item.mode != expected:
                    raise ValueError('Unexpected archive ownership/mode: ' + name)
                count += 1
    return count

if __name__ == '__main__':
    import sys
    for package in sys.argv[1:]:
        print(package, validate_archive(package), 'entries: mode/owner policy PASS')
