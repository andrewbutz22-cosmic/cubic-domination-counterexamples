"""The clause graphs of the census (the numbers quoted in Remark 8 of the note).

Usage:  python3 clause_graphs.py ../../census_tight_15_20.json [graphs/cub20_tw4.g6] [graphs/block_census.json]

The clause graph D of a tight formula has a vertex per clause and an edge per literal, joining the two
clauses that contain it (a cubic graph on 20 vertices, simple by Lemma 7(a)).  For every class of the
census this script builds D, groups the classes by the nauty certificate of D and reports, per clause
graph: number of classes carried, connectedness, twin pairs (pairs of clauses with the same three
neighbours, i.e. induced K_{2,3}), |Aut(D)|, edge connectivity, and how many of its classes have
gamma = 16 resp. i = 16.  With the optional arguments it also checks that every connected clause graph
is among the connected cubic graphs on 20 vertices with at least four twin pairs (count_twins.py) and
that every disconnected one is the union of two of the three 10-vertex cubic graphs that carry the
blocks R0..R7 (block_census.py).  Needs networkx and pynauty."""
import sys, json, hashlib, itertools
from collections import Counter, defaultdict
import networkx as nx
import pynauty


def clause_graph(K):
    occ = {}
    for ci, C in enumerate(K):
        for l in C:
            occ.setdefault(l, []).append(ci)
    assert len(K) == 20 and len(occ) == 30 and all(len(v) == 2 for v in occ.values())
    return sorted(tuple(sorted(v)) for v in occ.values())


def cert(n, edges):
    adj = {v: [] for v in range(n)}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    g = pynauty.Graph(n, directed=False, adjacency_dict=adj)
    _, s1, s2, _, _ = pynauty.autgrp(g)
    return hashlib.sha256(pynauty.certificate(g)).hexdigest(), int(round(s1 * 10 ** s2))


def twins(n, edges):
    nb = defaultdict(set)
    for a, b in edges:
        nb[a].add(b)
        nb[b].add(a)
    return sum(1 for u, v in itertools.combinations(range(n), 2) if nb[u] == nb[v])


def read_g6(line):
    s = line.strip()
    n = ord(s[0]) - 63
    bits = []
    for ch in s[1:]:
        x = ord(ch) - 63
        bits.extend((x >> k) & 1 for k in range(5, -1, -1))
    edges, k = [], 0
    for j in range(1, n):
        for i in range(j):
            if bits[k]:
                edges.append((i, j))
            k += 1
    return n, edges


def main():
    data = json.load(open(sys.argv[1]))
    recs = list(data.values()) if isinstance(data, dict) else data
    groups = defaultdict(list)
    info = {}
    twin_dist = Counter()
    for r in recs:
        edges = clause_graph(r['K'])
        assert len(set(edges)) == 30, 'parallel edges (Lemma 7(a) fails)'
        c, aut = cert(20, edges)
        groups[c].append(r)
        if c not in info:
            G = nx.Graph(edges)
            comps = sorted(len(x) for x in nx.connected_components(G))
            info[c] = dict(edges=edges, aut=aut, twins=twins(20, edges), comps=comps,
                           ec=nx.edge_connectivity(G) if len(comps) == 1 else 0)
        twin_dist[info[c]['twins']] += 1
    print(f'classes: {len(recs)}   distinct clause graphs: {len(groups)}   '
          f'connected: {sum(1 for c in groups if len(info[c]["comps"]) == 1)}   '
          f'disconnected: {sum(1 for c in groups if len(info[c]["comps"]) > 1)}')
    print('twin pairs per class:', dict(sorted(twin_dist.items())))
    print(f'{"classes":>7} {"comps":>8} {"twins":>5} {"|Aut|":>6} {"edge-conn":>9} {"gamma=16":>8} {"i=16":>5}')
    for c in sorted(groups, key=lambda c: (-len(groups[c]), info[c]['comps'])):
        rs, x = groups[c], info[c]
        print(f'{len(rs):>7} {str(x["comps"]):>8} {x["twins"]:>5} {x["aut"]:>6} {x["ec"]:>9} '
              f'{sum(1 for r in rs if r["gamma"] == 16):>8} {sum(1 for r in rs if r["i"] == 16):>5}')
    print('min |Aut(D)|:', min(x['aut'] for x in info.values()),
          '  max edge connectivity:', max(x['ec'] for x in info.values()),
          '  min twin pairs:', min(x['twins'] for x in info.values()))
    if len(sys.argv) > 2:
        tw4 = {cert(*read_g6(l))[0] for l in open(sys.argv[2]) if l.strip()}
        conn = [c for c in groups if len(info[c]['comps']) == 1]
        print(f'{sys.argv[2]}: {len(tw4)} graphs; connected clause graphs in it: '
              f'{sum(1 for c in conn if c in tw4)} of {len(conn)}')
    if len(sys.argv) > 3:
        blocks = json.load(open(sys.argv[3]))
        bcert = {}
        for v in blocks.values():
            b = cert(10, [tuple(e) for e in v['edges']])[0]
            bcert.setdefault(b, 0)
            bcert[b] += 1
        print(f'{sys.argv[3]}: {len(blocks)} blocks on {len(bcert)} distinct 10-vertex cubic graphs '
              f'(blocks per graph {sorted(bcert.values())})')
        ok = 0
        disc = [c for c in groups if len(info[c]['comps']) > 1]
        for c in disc:
            G = nx.Graph(info[c]['edges'])
            parts = [cert(10, [(m[a], m[b]) for a, b in G.subgraph(S).edges()])[0]
                     for S in nx.connected_components(G) for m in [{v: i for i, v in enumerate(sorted(S))}]]
            ok += all(p in bcert for p in parts) and info[c]['comps'] == [10, 10]
        print(f'disconnected clause graphs that are unions of two block graphs: {ok} of {len(disc)}'
              f' (unordered pairs of {len(bcert)} graphs: {len(bcert) * (len(bcert) + 1) // 2})')


if __name__ == '__main__':
    main()
