"""Check the structural observations on a census file (e.g. census_tight_15_20.json).

Usage:  python check_census.py census_tight_15_20.json [known_classes.json]
With a second file (needs pynauty): reports which of its classes are / are not in the first,
by nauty certificate of G(F) (clause and literal vertices coloured apart).

For every class (any JSON list/dict whose entries carry a 'K' = list of 20 clauses):
  - verifies it is a tight unsat (15,20) formula (bitset over 2^15 assignments),
  - clause graph D (one vertex per clause, one edge per literal) : simple? edge connectivity,
    number of twin clause pairs (two clauses with the same three D-neighbours),
  - merging variables: x and -x lie in clauses that share a literal,
  - Lemma 2 (sign-pattern rule) violations,
  - |Aut(D)| if pynauty is installed.
Prints the distributions and flags every class with < 4 twin pairs (conjecture T),
< 12 merging variables, or a 3-edge-connected clause graph.
Needs numpy + networkx (pynauty optional)."""
import sys, json, itertools
from collections import Counter
import numpy as np
import networkx as nx


def classes(obj):
    if isinstance(obj, dict):
        if 'K' in obj and isinstance(obj['K'], list):
            yield obj
            return
        for k, v in obj.items():
            for c in classes(v):
                c.setdefault('_key', k)
                yield c
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            for c in classes(v):
                c.setdefault('_key', i)
                yield c


def unsat(K):
    a = np.arange(1 << 15)
    bits = [((a >> j) & 1).astype(bool) for j in range(15)]
    ok = np.ones(1 << 15, dtype=bool)
    for C in K:
        s = np.zeros(1 << 15, dtype=bool)
        for l in C:
            s |= bits[abs(l) - 1] if l > 0 else ~bits[abs(l) - 1]
        ok &= s
    return not ok.any()


def analyse(K):
    occ = {}
    for ci, C in enumerate(K):
        for l in C:
            occ.setdefault(l, []).append(ci)
    assert len(K) == 20 and all(len(set(C)) == 3 for C in K)
    assert all(len(v) == 2 for v in occ.values()) and len(occ) == 30, 'not tight'
    edges = {l: tuple(v) for l, v in occ.items()}               # literal -> clause pair
    simple = len({frozenset(e) for e in edges.values()}) == 30
    G = nx.MultiGraph()
    G.add_nodes_from(range(20))
    G.add_edges_from(edges.values())
    Gs = nx.Graph(G)
    nb = [set(Gs[v]) for v in range(20)]
    twins = sum(1 for u, v in itertools.combinations(range(20), 2) if nb[u] == nb[v])
    ec = nx.edge_connectivity(Gs) if nx.is_connected(Gs) else 0
    # merging: some clause of x shares a literal with some clause of -x
    lits_of = [set(C) for C in K]
    merging = 0
    for x in range(1, 16):
        if any(lits_of[c] & lits_of[d] for c in occ[x] for d in occ[-x]):
            merging += 1
    # Lemma 2: {a,b} and {-a,-b} in clauses => {a,-b} or {-a,b} in a clause
    def together(p, q):
        return any(p in C and q in C for C in lits_of)
    viol = 0
    for x, y in itertools.combinations(range(1, 16), 2):
        for a, b in ((x, y), (x, -y)):
            if together(a, b) and together(-a, -b) and not (together(a, -b) or together(-a, b)):
                viol += 1
    aut = None
    try:
        import pynauty
        adj = {v: sorted(Gs[v]) for v in range(20)}
        g = pynauty.Graph(20, directed=False, adjacency_dict=adj)
        _, s1, s2, _, _ = pynauty.autgrp(g)
        aut = int(round(s1 * 10 ** s2))
    except Exception:
        pass
    return dict(unsat=unsat(K), simple=simple, twins=twins, ec=ec, merging=merging,
                lemma2_violations=viol, aut=aut, components=sorted(len(c) for c in nx.connected_components(Gs)))


def cert(K):
    import hashlib, pynauty
    occ = {}
    for ci, C in enumerate(K):
        for l in C:
            occ.setdefault(l, []).append(ci)
    lits = sorted(occ, key=lambda l: (abs(l), -l))
    idx = {l: 20 + i for i, l in enumerate(lits)}
    adj = {v: [] for v in range(50)}
    for l in lits:
        for c in occ[l]:
            adj[c].append(idx[l])
            adj[idx[l]].append(c)
        if l > 0:
            adj[idx[l]].append(idx[-l])
            adj[idx[-l]].append(idx[l])
    g = pynauty.Graph(50, directed=False, adjacency_dict=adj,
                      vertex_coloring=[set(range(20)), set(range(20, 50))])
    return hashlib.sha256(pynauty.certificate(g)).hexdigest()


def main():
    data = json.load(open(sys.argv[1]))
    rows = []
    for c in classes(data):
        r = analyse(c['K'])
        r['key'] = c.get('_key')
        rows.append(r)
    print(f'classes read: {len(rows)}')
    print('all unsat:', all(r['unsat'] for r in rows), '  all D simple (Lemma 1):', all(r['simple'] for r in rows),
          '  Lemma 2 violations:', sum(r['lemma2_violations'] for r in rows))
    for key in ('twins', 'merging', 'ec', 'aut', 'components'):
        print(f'{key:>10}:', sorted(Counter(str(r[key]) for r in rows).items()))
    bad = [r for r in rows if r['twins'] < 4 or r['merging'] < 12 or r['ec'] >= 3]
    print('classes breaking a pattern (twins<4, merging<12 or 3-edge-connected D):', len(bad))
    for r in bad:
        print('  ', r)
    if len(sys.argv) > 2:
        census = {cert(c['K']) for c in classes(json.load(open(sys.argv[1])))}
        other = list(classes(json.load(open(sys.argv[2]))))
        missing = [c.get('name', c.get('_key')) for c in other if cert(c['K']) not in census]
        print(f'{sys.argv[2]}: {len(other) - len(missing)} of {len(other)} classes are in {sys.argv[1]};'
              f' not in it: {missing}')


if __name__ == '__main__':
    main()
