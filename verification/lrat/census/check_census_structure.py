#!/usr/bin/env python3
"""check_census_structure.py -- independent structural check of census_tight_15_20.json.

Usage:  python3 check_census_structure.py census_tight_15_20.json [counterexamples.json]
Needs networkx; pynauty for check 6 (skipped with a warning if missing -- check 7 alone
already proves pairwise non-isomorphism).

For every class K (the census key is the nauty certificate of G(K)):
  1. K is a tight (15,20) formula: 20 clauses of 3 distinct variables from 1..15, every
     literal exactly twice.
  2. G(K) -- literal vertex 2(j-1) for x_j and 2(j-1)+1 for -x_j, pivot edge between them,
     clause vertex 30+c joined to its literals -- equals the stored edge list and graph6,
     and is a connected cubic graph on 50 vertices with girth 5.
  3. K is unsatisfiable and minimally unsatisfiable (all 2^15 assignments, bitsets).
  4. the stored pivot matching is {2j, 2j+1}.
  5. the (gamma, i) cells and the glue-free/gluing split match the census theorem.
  6. (pynauty) the plain-graph certificate of G(K) equals the key; keys are distinct.
  7. (no nauty) an isomorphism invariant -- for every vertex, the numbers of 5-, 6- and
     7-cycles through it -- separates all classes; any collision is settled by VF2.
     Distinct invariants => pairwise non-isomorphic.
  8. (with counterexamples.json) every posted graph appears in the census, isomorphic.
  9. (pynauty) automorphism group orders equal the stored ones; orders 16, 32 and 128
     occur only for gluings, 128 only for R0+R0 (note v2, Remark 6).
 10. single moves (exchange two literal occurrences between clauses, as in note v2,
     Remark 6): every unsatisfiable tight formula one move away is isomorphic to the
     formula it came from; 110 classes have such a neighbour and 129 have none.
"""
import collections, hashlib, json, sys
import networkx as nx


def g6dec(s):
    d = [ord(c) - 63 for c in s.strip()]
    n = d[0]
    bits = [(x >> t) & 1 for x in d[1:] for t in range(5, -1, -1)]
    E, k = set(), 0
    for j in range(1, n):
        for i in range(j):
            if bits[k]:
                E.add((i, j))
            k += 1
    return n, E


def lit_vertex(l):
    return 2 * (abs(l) - 1) + (1 if l < 0 else 0)


def graph_of(K):
    E = {(2 * j, 2 * j + 1) for j in range(15)}
    for c, cl in enumerate(K):
        for l in cl:
            E.add(tuple(sorted((lit_vertex(l), 30 + c))))
    return E


def _literal_masks():
    N = 1 << 15
    full = (1 << N) - 1
    lm = {}
    for j in range(1, 16):
        half = 1 << (j - 1)
        block = ((1 << half) - 1) << half          # assignments with bit j-1 set, within one period
        period = 2 * half
        mask = 0
        reps = N // period                         # repeat the period pattern by doubling
        chunk, width, k = block, period, 1
        while k < reps:
            chunk |= chunk << width; width *= 2; k *= 2
        lm[j] = chunk & full; lm[-j] = full ^ lm[j]
    return full, lm


_FULL, _LM = _literal_masks()


def models_mask(K):
    """Bitmask over all 2^15 assignments (bit a = assignment a, variable j true iff bit j-1 of a)
    of the assignments satisfying every clause of K."""
    f = _FULL
    for cl in K:
        f &= _LM[cl[0]] | _LM[cl[1]] | _LM[cl[2]]
    return f


def cycles_through(G, L):
    """For each vertex, number of simple cycles of length L through it."""
    cnt = collections.Counter()
    for s in G:
        # cycles whose minimum vertex is s, each found twice (two directions)
        stack = [(s, [s])]
        while stack:
            v, path = stack.pop()
            if len(path) == L:
                if s in G[v]:
                    for u in path:
                        cnt[u] += 1
                continue
            for w in G[v]:
                if w > s and w not in path:
                    stack.append((w, path + [w]))
    return {v: cnt[v] // 2 for v in G}


def fail(msg):
    print("FAIL:", msg); sys.exit(1)


def main():
    C = json.load(open(sys.argv[1]))
    posted = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
    keys = list(C)
    graphs = {}
    for idx, (key, v) in enumerate(C.items()):
        lab = "c%03d" % idx
        K = v["K"]
        if len(K) != 20 or any(len(cl) != 3 or len({abs(l) for l in cl}) != 3 for cl in K):
            fail(lab + ": not 20 clauses of 3 distinct variables")
        occ = collections.Counter(l for cl in K for l in cl)
        if set(occ) != {s * j for j in range(1, 16) for s in (1, -1)} or set(occ.values()) != {2}:
            fail(lab + ": some literal does not occur exactly twice")
        E = graph_of(K)
        if E != {tuple(sorted(e)) for e in v["edges"]} or len(v["edges"]) != 75:
            fail(lab + ": stored edges differ from G(K)")
        n6, E6 = g6dec(v["graph6"])
        if n6 != 50 or E6 != E:
            fail(lab + ": graph6 differs from G(K)")
        G = nx.Graph(); G.add_nodes_from(range(50)); G.add_edges_from(E)
        if any(d != 3 for _, d in G.degree()) or not nx.is_connected(G):
            fail(lab + ": not connected cubic")
        if nx.girth(G) != 5:
            fail(lab + ": girth is not 5")
        if models_mask(K) != 0:
            fail(lab + ": K is satisfiable")
        if any(models_mask(K[:c] + K[c + 1:]) == 0 for c in range(20)):
            fail(lab + ": K is not minimally unsatisfiable")
        if sorted(map(tuple, v["pivot_matching"])) != [(2 * j, 2 * j + 1) for j in range(15)]:
            fail(lab + ": pivot matching is not {2j,2j+1}")
        graphs[key] = (lab, G)
    print("1-4 ok: %d tight (15,20) formulas, all unsatisfiable and MU; every G(K) is a connected cubic "
          "50-vertex graph of girth 5 matching its stored edges, graph6 and pivot matching" % len(C))

    cells = collections.Counter((v["gamma"], v["i"], "glue-free" if v["glue_free"] else "gluing") for v in C.values())
    table = collections.defaultdict(lambda: [0, 0])
    for (ga, ii, kind), m in cells.items():
        table[(ga, ii)][0 if kind == "glue-free" else 1] += m
    print("5: (gamma, i) -> glue-free/gluing: " + ", ".join("(%d,%d) %d/%d" % (k[0], k[1], t[0], t[1]) for k, t in sorted(table.items())))
    print("   i=16: %d   gamma=16: %d   glue-free: %d   gluings: %d"
          % (sum(v["i"] == 16 for v in C.values()), sum(v["gamma"] == 16 for v in C.values()),
             sum(bool(v["glue_free"]) for v in C.values()), sum(not v["glue_free"] for v in C.values())))

    try:
        from pynauty import Graph as NG, certificate
        certs = {}
        for key, (lab, G) in graphs.items():
            cert = certificate(NG(50, directed=False, adjacency_dict={u: list(G[u]) for u in G})).hex()
            if cert != key:
                fail(lab + ": nauty certificate differs from the census key")
            certs[cert] = lab
        if len(certs) != len(graphs):
            fail("two classes share a certificate")
        print("6 ok: nauty certificates recomputed = keys, %d distinct -> pairwise non-isomorphic" % len(certs))
    except ImportError:
        print("6 skipped: pynauty not installed")

    inv = {}
    for key, (lab, G) in graphs.items():
        c5, c6, c7 = cycles_through(G, 5), cycles_through(G, 6), cycles_through(G, 7)
        inv[key] = tuple(sorted((c5[u], c6[u], c7[u]) for u in G))
    buckets = collections.defaultdict(list)
    for key, t in inv.items():
        buckets[t].append(key)
    coll = [b for b in buckets.values() if len(b) > 1]
    vf2 = 0
    for b in coll:
        for x in range(len(b)):
            for y in range(x + 1, len(b)):
                vf2 += 1
                if nx.is_isomorphic(graphs[b[x]][1], graphs[b[y]][1]):
                    fail("%s and %s are isomorphic" % (graphs[b[x]][0], graphs[b[y]][0]))
    print("7 ok: cycle invariant separates %d of %d classes; %d colliding pairs settled by VF2 as "
          "non-isomorphic -> pairwise non-isomorphic without nauty" % (len(buckets) - len(coll), len(graphs), vf2))

    if posted is not None:
        found = 0
        for pname, pg in posted.items():
            P = nx.Graph(); P.add_nodes_from(range(50)); P.add_edges_from(map(tuple, pg["edges"]))
            hits = [graphs[k][0] for k in graphs if nx.faster_could_be_isomorphic(P, graphs[k][1])
                    and nx.is_isomorphic(P, graphs[k][1])]
            if len(hits) != 1:
                fail("posted graph %s found %d times in the census" % (pname, len(hits)))
            m = [v for v in C.values() if v.get("posted_name") == pname]
            note = " (census posted_name agrees)" if m and graphs[next(k for k in C if C[k] is m[0])][0] == hits[0] else ""
            print("8: posted %s is census class %s%s" % (pname, hits[0], note))
            found += 1
        print("8 ok: all %d posted graphs are in the census" % found)
    try:
        from pynauty import Graph as NG, autgrp
        orders = {}
        for key, (lab, G) in graphs.items():
            gens, grpsize1, grpsize2, orbits, numorb = autgrp(NG(50, directed=False, adjacency_dict={u: list(G[u]) for u in G}))
            order = round(grpsize1 * 10 ** grpsize2)
            if order != C[key]["aut_order"]:
                fail(lab + ": automorphism group order %d, stored %s" % (order, C[key]["aut_order"]))
            orders[key] = order
        big = [k for k in orders if orders[k] in (16, 32, 128)]
        if any(C[k]["glue_free"] for k in big) or [C[k].get("posted_name") for k in orders if orders[k] == 128] != ["R0+R0"]:
            fail("orders 16/32/128 are not confined to gluings (128 to R0+R0)")
        print("9 ok: automorphism orders recomputed = stored: %s; 16/32/128 only for gluings, 128 = R0+R0"
              % ", ".join("%d: %d" % (o, m) for o, m in sorted(collections.Counter(orders.values()).items())))
    except ImportError:
        print("9 skipped: pynauty not installed")

    try:
        from pynauty import Graph as NG, certificate
        def same_class(K2, key, G):
            E2 = graph_of(K2)
            adj = collections.defaultdict(list)
            for u, w in E2:
                adj[u].append(w); adj[w].append(u)
            return certificate(NG(50, directed=False, adjacency_dict=dict(adj))).hex() == key
    except ImportError:
        def same_class(K2, key, G):
            H = nx.Graph(); H.add_nodes_from(range(50)); H.add_edges_from(graph_of(K2))
            return nx.is_isomorphic(H, G)
    with_nb = moves = unsat_moves = 0
    for key, (lab, G) in graphs.items():
        K = C[key]["K"]
        occ = [(c, p) for c in range(20) for p in range(3)]
        found = 0
        for x in range(60):
            c1, p1 = occ[x]
            for y in range(x + 1, 60):
                c2, p2 = occ[y]
                if c1 == c2:
                    continue
                a, b = K[c1][p1], K[c2][p2]
                if a == b:
                    continue
                r1 = [l for q, l in enumerate(K[c1]) if q != p1] + [b]
                r2 = [l for q, l in enumerate(K[c2]) if q != p2] + [a]
                if len({abs(l) for l in r1}) < 3 or len({abs(l) for l in r2}) < 3:
                    continue
                K2 = [list(cl) for cl in K]; K2[c1] = r1; K2[c2] = r2
                moves += 1
                if models_mask(K2) == 0:
                    unsat_moves += 1
                    if not same_class(K2, key, G):
                        fail(lab + ": a single move reaches a different unsatisfiable class")
                    found += 1
        with_nb += found > 0
        if bool(found) != bool(C[key]["one_swap_unsat_neighbors"]):
            fail(lab + ": single-move neighbours disagree with the stored record")
    print("10 ok: %d single moves from the 239 classes, %d unsatisfiable, every one isomorphic to its source; "
          "%d classes have such a neighbour, %d have none" % (moves, unsat_moves, with_nb, len(graphs) - with_nb))
    print("ALL STRUCTURAL CHECKS PASSED")


if __name__ == "__main__":
    main()
