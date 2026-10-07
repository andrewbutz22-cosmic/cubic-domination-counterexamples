"""Twin-pair counts of all connected cubic graphs on 20 vertices (graphs/cub20.g6, from
`geng -c -d3 -D3 20`); writes those with at least four twin pairs to graphs/cub20_tw4.g6."""
import sys
from collections import Counter
from g6 import read_g6
cnt = Counter()
keep = []
for line in open('graphs/cub20.g6'):
    n, edges = read_g6(line)
    nb = [0] * n
    for a, b in edges:
        nb[a] |= 1 << b; nb[b] |= 1 << a
    seen = {}
    tw = 0
    for v in range(n):
        k = nb[v]
        if k in seen: tw += seen[k]
        seen[k] = seen.get(k, 0) + 1
    cnt[tw] += 1
    if tw >= 4: keep.append(line)
print(sorted(cnt.items()))
with open('graphs/cub20_tw4.g6', 'w') as out:
    out.writelines(keep)
print('with >=4 twin pairs:', len(keep))
