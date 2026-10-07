"""Block census via clause graphs (correctness gate).
An R-block = MU formula on 7 variables, 10 clauses (8 of size 3, 2 of size 2), every literal
exactly twice.  Adding the glue literal to its two 2-clauses gives a cubic (multi)graph D10
on 10 vertices with a marked edge g (the glue literal); the other 14 edges are paired.
Enumerate: every loopless cubic multigraph on 10 vertices x every edge g x every pairing of
E - g into non-adjacent pairs; keep those with no rainbow cover of all 10 vertices (unsat),
check MU, dedupe by nauty certificate of the block formula."""
import sys, json, hashlib, itertools
from collections import defaultdict
import pynauty
sys.path.insert(0, '..')
from core import formula_to_DP, DP_to_formula

FULL = (1 << 128) - 1
# assignment a in 0..127 ; bit j of a = choice in pair j
PICK = []
for j in range(7):
    m0 = m1 = 0
    for a in range(128):
        if (a >> j) & 1:
            m1 |= 1 << a
        else:
            m0 |= 1 << a
    PICK.append((m0, m1))


def read_multi(path):
    out = []
    for line in open(path):
        t = list(map(int, line.split()))
        if not t:
            continue
        nv, ne = t[0], t[1]
        edges = []
        for k in range(ne):
            a, b, m = t[2 + 3 * k: 5 + 3 * k]
            edges += [(a, b)] * m
        out.append((nv, edges))
    return out


def pairings(items, adj):
    """all perfect matchings of items (list of edge ids) with non-adjacent partners"""
    if not items:
        yield []
        return
    e = items[0]
    rest = items[1:]
    for i, f in enumerate(rest):
        if not adj[e][f]:
            for p in pairings(rest[:i] + rest[i + 1:], adj):
                yield [(e, f)] + p


def block_cert(nv, edges, g, P):
    lit = [e for e in range(len(edges)) if e != g]
    idx = {e: nv + i for i, e in enumerate(lit)}
    N = nv + len(lit)
    adjd = {i: [] for i in range(N)}
    def add(a, b):
        adjd[a].append(b); adjd[b].append(a)
    for e in lit:
        u, v = edges[e]
        add(u, idx[e]); add(v, idx[e])
    for (e, f) in P:
        add(idx[e], idx[f])
    G = pynauty.Graph(N, directed=False, adjacency_dict=adjd,
                      vertex_coloring=[set(range(nv)), set(range(nv, N))])
    return hashlib.sha256(pynauty.certificate(G)).hexdigest()


def cover_masks(nv, edges, g, P):
    """per vertex: set of assignments (as int bitmask) under which it is covered"""
    pick = {}
    for j, (e, f) in enumerate(P):
        pick[e] = PICK[j][0]
        pick[f] = PICK[j][1]
    cov = [0] * nv
    for e, (u, v) in enumerate(edges):
        if e == g:
            continue
        cov[u] |= pick[e]
        cov[v] |= pick[e]
    return cov


def main():
    graphs = read_multi(sys.argv[1])
    found = {}
    stats = defaultdict(int)
    for gi, (nv, edges) in enumerate(graphs):
        m = len(edges)
        adj = [[e != f and bool(set(edges[e]) & set(edges[f])) for f in range(m)] for e in range(m)]
        for g in range(m):
            others = [e for e in range(m) if e != g]
            for P in pairings(others, adj):
                cov = cover_masks(nv, edges, g, P)
                allc = FULL
                for c in cov:
                    allc &= c
                stats['pairings'] += 1
                if allc:
                    continue
                stats['unsat'] += 1
                # MU: dropping any clause w must make it satisfiable
                mu = True
                for w in range(nv):
                    x = FULL
                    for v in range(nv):
                        if v != w:
                            x &= cov[v]
                    if not x:
                        mu = False
                        break
                if not mu:
                    stats['unsat_not_mu'] += 1
                    continue
                stats['mu'] += 1
                c = block_cert(nv, edges, g, P)
                if c not in found:
                    simple = len(set(tuple(sorted(e)) for e in edges)) == len(edges)
                    found[c] = dict(graph=gi, g=g, P=P, edges=edges, simple=simple)
        print(f'graph {gi+1}/{len(graphs)} done: {dict(stats)} classes={len(found)}', flush=True)
    json.dump({k: v for k, v in found.items()}, open('block_census.json', 'w'))
    print('MU block classes:', len(found))
    print('on simple graphs:', sum(v['simple'] for v in found.values()))


if __name__ == '__main__':
    main()
