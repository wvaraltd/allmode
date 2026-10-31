# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline build with an existing GCC-compatible compiler. No downloads/installs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
from prepare_vendor import SOURCES

ROOT = Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    ap.add_argument('--debug', action='store_true')
    args = ap.parse_args()
    os.chdir(ROOT)
    manifest = json.loads(Path('vendor/manifest.json').read_text())
    for name, digest in manifest['files'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise SystemExit('Vendor checksum mismatch: '+name)
    build = Path('build'); build.mkdir(exist_ok=True)
    inc = build/'include/mbelib-neo'; inc.mkdir(parents=True, exist_ok=True)
    (inc/'version.h').write_text('#define MBELIB_VERSION "2.6.2-dstar-subset-a3c7bbd"\n')
    log = (build/'commands.log').open('w', encoding='utf-8')
    def run(cmd):
        line = shlex.join([str(x) for x in cmd])
        print(line, flush=True); log.write('$ '+line+'\n'); log.flush()
        try:
            p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except FileNotFoundError:
            message='BLOCKED: C compiler not found. Supply an existing GCC-compatible compiler with --cc. No tools installed.\n'
            log.write(message); log.flush(); raise SystemExit(message)
        print(p.stdout, end=''); log.write(p.stdout); log.flush()
        if p.returncode: raise SystemExit(p.returncode)
    run([args.cc, '--version'])
    flags = ['-std=c99', '-O0' if args.debug else '-O2', '-g', '-ffp-contract=off',
             '-DMBE_STATIC', '-D_USE_MATH_DEFINES', '-D_DEFAULT_SOURCE', '-DPFFFT_STATIC_DEFINE', '-DPFFFT_SIMD_DISABLE=1',
             '-DPFFFT_DISABLE_FMA=1', '-Wall', '-Wextra',
             '-Ivendor/mbelib/include', '-Ivendor/mbelib/src/internal',
             '-Ivendor/pffft/include/pffft', '-Ibuild/include', '-Isrc']
    if os.name != 'nt': flags += ['-fPIC']
    replaced = {'core/mbelib.c', 'core/mbe_adaptive.c', 'core/mbe_unvoiced_fft.c'}
    sources = ['vendor/mbelib/src/'+s for s in SOURCES if s not in replaced]
    sources += ['src/bridge_core.c', 'src/bridge_noise.c', 'src/bridge_fft.c', 'src/allmode_dstar.c',
                'vendor/pffft/src/pffft.c', 'vendor/pffft/src/pffft_common.c']
    objects = []
    for source in sources:
        obj = str(build/(Path(source).stem+'.o')); objects.append(obj)
        run([args.cc, *flags, '-c', source, '-o', obj])
    dll = build/('allmode_dstar.dll' if os.name=='nt' else 'liballmode_dstar.so')
    run([args.cc, '-shared', *objects, '-lm', '-o', str(dll)])
    for name in ['test_ambe2400_encoder', 'test_ambe2400_frame_types', 'dstar_encode', 'dstar_decode']:
        folder = 'tests' if name.startswith('test_') else 'examples'
        exe = build/(name+('.exe' if os.name=='nt' else ''))
        run([args.cc, *flags, '-UNDEBUG', '-include', 'vendor/mbelib/tests/enable_assertions.h',
             f'vendor/mbelib/{folder}/{name}.c', *objects, '-lm', '-o', str(exe)])
    print('Build complete. Run: python -m unittest discover -s tests -v')

if __name__ == '__main__': main()
