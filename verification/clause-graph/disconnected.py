"""All disconnected cubic graphs on 20 vertices (as unions of connected ones), with twin counts."""
import itertools
from collections import Counter
from g6 import read_g6
comp = {}
for n in (4, 6, 8, 10, 12, 14, 16):
    comp[n] = [read_g6(l)[1] for l in open(f'graphs/cub{n}.g6')]
def twins(n, edges):
    nb = [0] * n
    for a, b in edges: nb[a] |= 1 << b; nb[b] |= 1 << a
    c = Counter(nb); return sum(k * (k - 1) // 2 for k in c.values())
def partitions(total, minpart=4):
    if total == 0: yield []; return
    for p in range(minpart, total + 1, 2):
        for rest in partitions(total - p, p): yield [p] + rest
out = []
for parts in partitions(20):
    if len(parts) < 2: continue
    # multiset of graphs per part size
    cnt = Counter(parts)
    choices = []
    for size, k in sorted(cnt.items()):
        choices.append([(size, combo) for combo in itertools.combinations_with_replacement(range(len(comp[size])), k)])
    for pick in itertools.product(*choices):
        edges = []; off = 0; tw = 0
        for size, combo in pick:
            for gi in combo:
                e = comp[size][gi]
                edges += [(a + off, b + off) for a, b in e]
                tw += twins(size, e); off += size
        out.append((tw, edges))
print('disconnected cubic graphs on 20 vertices:', len(out))
print('twin distribution:', sorted(Counter(t for t, _ in out).items()))
with open('dis_tw4.txt', 'w') as f:
    for tw, e in out:
        if tw >= 4: f.write(f"20 30 " + " ".join(f"{a} {b}" for a, b in e) + "\n")
print('with >=4 twins:', sum(1 for t, _ in out if t >= 4))
