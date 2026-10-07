"""Match the classes found by block_census.py (graphs/block_census.json) against R0..R7
from blocks710.json (repository root, or a path given as the second argument) by nauty certificate of the block formula."""
import json, sys, hashlib
import pynauty


def cert_block_formula(K):
    """K: block with two 2-clauses. Glue literal 99 added to them; the glue literal is NOT a
    literal vertex of the block (it pairs with the other block), so it is dropped from G."""
    KK = [list(C) + ([99] if len(C) == 2 else []) for C in K]
    occ = {}
    for ci, C in enumerate(KK):
        for l in C:
            occ.setdefault(l, []).append(ci)
    lits = [l for l in sorted(occ, key=lambda l: (abs(l), -l)) if abs(l) != 99]
    nv = len(KK)
    idx = {l: nv + i for i, l in enumerate(lits)}
    N = nv + len(lits)
    adj = {i: [] for i in range(N)}

    def add(a, b):
        adj[a].append(b)
        adj[b].append(a)
    for l in lits:
        u, v = occ[l]
        add(u, idx[l])
        add(v, idx[l])
    for l in lits:
        if l > 0:
            add(idx[l], idx[-l])
    G = pynauty.Graph(N, directed=False, adjacency_dict=adj,
                      vertex_coloring=[set(range(nv)), set(range(nv, N))])
    return hashlib.sha256(pynauty.certificate(G)).hexdigest()


if __name__ == '__main__':
    blocks = json.load(open(sys.argv[2] if len(sys.argv) > 2 else '../../blocks710.json'))
    found = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'graphs/block_census.json'))
    known = {cert_block_formula(K): f'R{i}' for i, K in enumerate(blocks)}
    print('known R-blocks, pairwise distinct:', len(known))
    print('census classes:', len(found), '->', sorted(known.get(c, 'NEW') for c in found))
