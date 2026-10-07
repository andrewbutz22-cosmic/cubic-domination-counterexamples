#!/usr/bin/env python3
"""Independent cross-check (corroboration only, not part of the trusted chain).

Usage: python3 crosscheck_totalizer_kissat.py counterexamples.json PATH/TO/kissat   (needs networkx)

Re-derives gamma and i of every graph by a route sharing no code with
verification/lrat: networkx decodes the graph6 string, "at most K" is a
totalizer (Bailleux-Boufkhad) instead of Sinz's sequential counter, and Kissat
replaces CaDiCaL.  For each value it checks UNSAT at value-1 and SAT at value,
and re-checks the SAT witness with networkx.
"""
import json, os, subprocess, sys, tempfile
import networkx as nx

KISSAT = sys.argv[2]
D = json.load(open(sys.argv[1]))


def totalizer(lits, K, nxt):
    cl = []
    def build(xs):
        nonlocal nxt
        if len(xs) == 1:
            return [xs[0]]
        A = build(xs[:len(xs) // 2]); B = build(xs[len(xs) // 2:])
        m = min(len(A) + len(B), K + 1)
        R = list(range(nxt, nxt + m)); nxt += m
        for a in range(len(A) + 1):
            for b in range(len(B) + 1):
                if a + b == 0:
                    continue
                c = ([-A[a - 1]] if a else []) + ([-B[b - 1]] if b else [])
                cl.append(c + [R[min(a + b, m) - 1]])
        return R
    root = build(lits)
    return cl, root, nxt


def solve(G, mode, K, td):
    n = G.number_of_nodes()
    x = lambda v: v + 1
    cl = [[x(u) for u in [v] + list(G[v])] for v in G]
    if mode == "ids":
        cl += [[-x(u), -x(w)] for u, w in G.edges()]
    tc, root, nxt = totalizer([x(v) for v in range(n)], K, n + 1)
    cl += tc + [[-root[K]]]
    path = os.path.join(td, "t.cnf")
    with open(path, "w") as f:
        f.write("p cnf %d %d\n" % (nxt - 1, len(cl)))
        f.writelines(" ".join(map(str, c)) + " 0\n" for c in cl)
    p = subprocess.run([KISSAT, "-q", path], capture_output=True, text=True)
    model = [int(t) for ln in p.stdout.splitlines() if ln.startswith("v") for t in ln[1:].split()]
    return p.returncode, {l - 1 for l in model if 0 < l <= n}


all_ok = True
with tempfile.TemporaryDirectory() as td:
    for name, g in D.items():
        G = nx.from_graph6_bytes(g["graph6"].encode())
        ok = sorted(map(sorted, G.edges())) == sorted(map(sorted, g["edges"]))
        ok &= all(d == 3 for _, d in G.degree()) and nx.is_connected(G)
        ok &= len(g["pivot_matching"]) == 15 and nx.is_maximal_matching(G, {tuple(e) for e in g["pivot_matching"]})
        ids = set(g["ids"])
        ok &= nx.is_dominating_set(G, ids) and G.subgraph(ids).number_of_edges() == 0 and len(ids) == g["i"]
        for mode, val in (("ds", g["gamma"]), ("ids", g["i"])):
            r1, _ = solve(G, mode, val - 1, td)
            r2, S = solve(G, mode, val, td)
            ok &= r1 == 20 and r2 == 10 and len(S) <= val and nx.is_dominating_set(G, S)
            ok &= mode == "ds" or G.subgraph(S).number_of_edges() == 0
        all_ok &= ok
        print("  %-6s gamma=%d i=%d: %s" % (name, g["gamma"], g["i"],
              "UNSAT at value-1 and SAT at value for both, witnesses valid" if ok else "MISMATCH"))
print("cross-check:", "ALL AGREE" if all_ok else "DISAGREEMENT")
sys.exit(0 if all_ok else 1)
