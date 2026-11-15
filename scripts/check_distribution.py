"""Offline release checks. Does not upload files or inspect the user's machine."""
from pathlib import Path
import re
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pura_refresh.image import load_image

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '.venv', '__pycache__', '.build', 'build', 'dist'}


def jpeg_metadata(path):
    blob = path.read_bytes()
    if blob[:2] != bytes.fromhex('ffd8'):
        raise ValueError(f'Not a JPEG: {path.name}')
    pos = 2
    while pos < len(blob):
        if blob[pos] != 255:
            raise ValueError(f'Invalid JPEG marker: {path.name}')
        while blob[pos] == 255:
            pos += 1
        marker = blob[pos]
        pos += 1
        if marker in (0xda, 0xd9):
            return
        size = struct.unpack_from('>H', blob, pos)[0]
        if size < 2 or pos + size > len(blob):
            raise ValueError(f'Truncated JPEG: {path.name}')
        if marker in (0xe1, 0xe2, 0xed, 0xfe):
            raise ValueError(f'Embedded metadata/profile/comment in {path.name}')
        pos += size
    raise ValueError(f'Missing JPEG scan: {path.name}')


def main():
    for board in ('v2', 'v3'):
        load_image(board)
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if not path.is_file() or any(part in SKIP or part.endswith('.egg-info') for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f'Distribution must not contain symlinks: {rel}')
        if path.suffix.lower() in ('.heic', '.elf', '.map', '.log') or path.name.endswith('access.json'):
            raise ValueError(f'Private/raw build artifact: {rel}')
        if path.suffix.lower() in ('.jpg', '.jpeg'):
            jpeg_metadata(path)
        # Upstream licenses retain their original authors and attribution.
        if rel.parts[0] == 'third_party_licenses':
            continue
        blob = path.read_bytes()
        if re.search(rb'/(?:Users|home)/[A-Za-z][A-Za-z0-9_.-]+/', blob):
            raise ValueError(f'Personal filesystem path: {rel}')
        if re.search(rb'192[.]168[.](?:2|3)[.][0-9]+', blob):
            raise ValueError(f'Private deployment address: {rel}')
        if path.suffix in ('.md', '.txt'):
            text = blob.decode('utf-8')
            for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)', text):
                target = match[1].split('#')[0]
                if not target or '://' in target or target.startswith('mailto:'):
                    continue
                if not (path.parent / target).exists():
                    raise ValueError(f'Broken local link in {rel}: {target}')
    print('Both firmware bundles, distribution paths, local links and JPEG metadata checks passed.')


if __name__ == '__main__':
    main()
