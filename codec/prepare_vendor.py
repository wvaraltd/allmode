# SPDX-License-Identifier: GPL-2.0-or-later
"""Make a source-only D-Star subset from the pinned, sparse inspection checkout."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent
UP = ROOT.parent / '.source-cache/mbelib'
SHA = 'a3c7bbdae9eb21cbfab57006c1a5daca7bdcba7f'
PFFFT_SHA = '77a7ecda1f58f041168636c99be3e6e968d984d7'
SOURCES = ['ambe/ambe3600x2400.c', 'ambe/ambe3600x2400_enc.c',
           'ambe/dstar_frame.c', 'ambe/ambe_common.c', 'ambe/ambe_encoder.c',
           'ecc/ecc.c', 'ecc/ecc_const.c', 'ecc/ecc_soft.c', 'ecc/ecc_soft_search.c',
           'core/mbelib.c', 'core/mbe_adaptive.c', 'core/mbe_unvoiced_fft.c',
           'core/mbe_cpu.c', 'core/mbe_voiced.c', 'core/mbe_pcm_convert.c',
           'core/mbe_encoder.c', 'core/mbe_speech_analysis.c',
           'core/mbe_tone_detect.c', 'core/mbe_tone_fit.c']

def main():
    assert subprocess.check_output(['git', '-C', str(UP), 'rev-parse', 'HEAD'], text=True).strip() == SHA
    files = {'src/' + s for s in SOURCES}
    files.update(['include/mbelib-neo/mbelib.h', 'LICENSE', 'LICENSES/GPL-2.0-or-later.txt',
                  'LICENSES/ISC.txt', 'LICENSES/LicenseRef-PFFFT.txt',
                  'tests/test_ambe2400_encoder.c', 'tests/test_ambe2400_frame_types.c',
                  'tests/enable_assertions.h', 'tests/encoder_test_support.h',
                  'tests/test_dstar_examples.py', 'examples/dstar_encode.c', 'examples/dstar_decode.c',
                  'legal/status.md', 'legal/component-table.md', 'legal/patents.md',
                  'legal/implementation-provenance.md', 'legal/reference-data.md'])
    # Transitive quoted headers only; no TETRA/IMBE/2450 codebooks.
    pending = list(files)
    while pending:
        name = pending.pop()
        for inc in re.findall(r'^\s*#include\s+"([^"]+)"', (UP/name).read_text(encoding='utf-8'), re.M):
            candidates = [str(Path(name).parent/inc).replace('\\','/'), 'src/internal/'+inc, 'include/'+inc]
            found = next((c for c in candidates if (UP/c).is_file()), None)
            if found and found not in files:
                files.add(found); pending.append(found)
    assert not any('tetra' in f.lower() or '2450_const' in f or 'imbe7200' in f for f in files)
    manifest = {'mbelib_commit': SHA, 'pffft_commit': PFFFT_SHA, 'files': {}}
    for name in sorted(files):
        dest = ROOT/'vendor/mbelib'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(UP/name, dest)
        manifest['files'][str(dest.relative_to(ROOT)).replace('\\','/')] = hashlib.sha256(dest.read_bytes()).hexdigest()
    archive = ROOT.parent/'.source-cache/pffft-source.tar.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '4de67b1d528d48e52921c3a821d1cff9de2c4ff99ff7affcb67e2b9e47a88422'
    with tarfile.open(archive) as tar:
        members={'/'.join(m.name.split('/')[1:]):m for m in tar.getmembers() if m.isfile()}
        selected={'src/pffft.c','src/pffft_common.c','LICENSE.txt','AGENTS.md'}
        pending=list(selected)
        while pending:
            name=pending.pop()
            data=tar.extractfile(members[name]).read().decode('utf-8')
            for inc in re.findall(r'^\s*#\s*include\s+"([^"]+)"',data,re.M):
                candidates=[str(Path(name).parent/inc).replace('\\','/'),'src/'+inc,'include/pffft/'+inc]
                found=next((c for c in candidates if c in members),None)
                if found and found not in selected: selected.add(found); pending.append(found)
        # Prune only individually verified generated files in this vendored directory.
        base=(ROOT/'vendor/pffft').resolve()
        if base.exists():
            for old in base.rglob('*'):
                if old.is_file() and str(old.relative_to(base)).replace('\\','/') not in selected:
                    assert old.resolve().is_relative_to(base)
                    old.unlink()
        for member in tar.getmembers():
            name = '/'.join(member.name.split('/')[1:])
            if name not in selected:
                continue
            assert '..' not in Path(name).parts
            dest = ROOT/'vendor/pffft'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(tar.extractfile(member).read())
            manifest['files'][str(dest.relative_to(ROOT)).replace('\\','/')] = hashlib.sha256(dest.read_bytes()).hexdigest()
    (ROOT/'vendor/manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(f'Preserved {len(files)} mbelib source/notice files; TETRA and OP25 excluded.')

if __name__ == '__main__': main()
