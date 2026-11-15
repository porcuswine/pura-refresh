"""Validate supplied binary STLs using only Python's standard library."""
from collections import Counter, defaultdict
from pathlib import Path
import math
import struct

ROOT = Path(__file__).resolve().parents[1]


def check(path):
    blob = path.read_bytes()
    count = struct.unpack_from('<I', blob, 80)[0]
    if len(blob) != 84 + count * 50:
        raise ValueError(f'Invalid binary STL size: {path.name}')
    edges = Counter()
    adjacency = defaultdict(set)
    volume = 0.0
    for offset in range(84, len(blob), 50):
        values = struct.unpack_from('<12fH', blob, offset)
        a, b, c = [tuple(values[i:i+3]) for i in (3,6,9)]
        if len({a,b,c}) != 3 or not all(math.isfinite(v) for v in values[:12]):
            raise ValueError(f'Invalid triangle: {path.name}')
        for x, y in ((a,b),(b,c),(c,a)):
            edges[tuple(sorted((x,y)))] += 1
            adjacency[x].add(y)
            adjacency[y].add(x)
        volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2]) + a[2]*(b[0]*c[1]-b[1]*c[0]))/6
    if not edges or any(n != 2 for n in edges.values()):
        raise ValueError(f'Open or non-manifold edges: {path.name}')
    seen = set()
    pending = [next(iter(adjacency))]
    while pending:
        node = pending.pop()
        if node not in seen:
            seen.add(node)
            pending.extend(adjacency[node] - seen)
    if len(seen) != len(adjacency) or volume <= 0:
        raise ValueError(f'Disconnected or inverted mesh: {path.name}')
    print(f'{path.name}: {count} triangles; closed, connected mesh; volume {volume:.2f} mm^3')


if __name__ == '__main__':
    for path in sorted((ROOT/'hardware/case/v7/print-files').glob('*.stl')):
        check(path)
