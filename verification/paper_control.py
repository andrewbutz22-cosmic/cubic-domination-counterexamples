#!/usr/bin/env python3
"""
External control: the Theorem-2 graph of arXiv:2608.22498 (Appendix A), built here from its printed
formula f (20 clauses, 15 variables, every literal exactly twice) by the same incidence construction:
vertex 2(i-1) = x_i, 2(i-1)+1 = not x_i, M-edge between them, clause j -> vertex 29+j joined to its
three literal vertices.  The paper certifies gamma = 14, gamma_e = 15, a unique minimum maximal
matching, and prints a dominating set of order 14.
"""
import json, time
from verify_ids import (Graph, degrees, is_connected, is_dominating, is_independent, is_maximal_matching,
                        ilp_ids_cbc, min_ids_bb, sat_ids_atmost, ilp_mmm_cbc, line_graph, bits_to_list,
                        sat_cnf_satisfiable, g6_encode)
from verify_gamma import ilp_ds_cbc, ilp_ds_highs, min_ds_bb, sat_ds_atmost, structural_gamma

# clauses 1..20, numbered down the columns, first display then second (Appendix A)
f = [
    [1, 4, -6], [2, -4, 5], [2, -5, 6], [4, 5, 6], [-4, -5, -6],            # 1-5
    [1, 7, -9], [-2, -7, 8], [-2, -8, 9], [7, 8, 9], [-7, -8, -9],          # 6-10
    [-1, 10, -12], [3, -10, 11], [3, -11, 12], [10, 11, 12], [-10, -11, -12],   # 11-15
    [-1, 13, -15], [-3, -13, 14], [-3, -14, 15], [13, 14, 15], [-13, -14, -15], # 16-20
]
from collections import Counter
occ = Counter(l for c in f for l in c)
assert sorted(set(occ.values())) == [2] and len(occ) == 30, occ
assert all(len({abs(l) for l in c}) == 3 for c in f)
sat, _ = sat_cnf_satisfiable(f)
print("f: 15 vars, 20 clauses, every literal exactly twice, satisfiable =", sat)

def lit_vertex(l):
    return 2 * (abs(l) - 1) + (0 if l > 0 else 1)
edges = [(2 * i, 2 * i + 1) for i in range(15)]
for j, c in enumerate(f):
    for l in c:
        edges.append((lit_vertex(l), 30 + j))
G = Graph(50, edges)
print("paper graph: n=50 m=%d degrees=%s connected=%s" % (len(G.edges), sorted(set(degrees(G))), is_connected(G)))
print("graph6:", g6_encode(50, G.edges))

# the printed dominating set: v1, v1bar, v2bar, v3, v3bar, v4bar, v5, v6, w9, w10, w14, w15, w19, w20
D14 = [lit_vertex(1), lit_vertex(-1), lit_vertex(-2), lit_vertex(3), lit_vertex(-3), lit_vertex(-4),
       lit_vertex(5), lit_vertex(6)] + [30 + j - 1 for j in (9, 10, 14, 15, 19, 20)]
print("printed 14-set dominates:", is_dominating(G, D14), "| independent:", is_independent(G, D14))
M = [(2 * i, 2 * i + 1) for i in range(15)]
print("M maximal matching:", is_maximal_matching(G, M))

t = time.time(); g_c, _ = ilp_ds_cbc(G); g_h, _ = ilp_ds_highs(G); g_b, Sb, nodes = min_ds_bb(G.n, G.cnb)
u1, _ = sat_ds_atmost(G, g_b - 1); u2, _ = sat_ds_atmost(G, g_b); g_s, _, _ = structural_gamma(G, g_b)
print(f"gamma: CBC={g_c} HiGHS={g_h} B&B={g_b} (nodes {nodes}) SAT<={g_b-1}:{'SAT' if u1 else 'UNSAT'} SAT<={g_b}:{'SAT' if u2 else 'UNSAT'} structural={g_s}  [{time.time()-t:.1f}s]")
t = time.time(); i_c, _ = ilp_ids_cbc(G); i_b, Si, nodes_i = min_ids_bb(G.n, G.cnb)
v1, _ = sat_ids_atmost(G, i_b - 1); v2, _ = sat_ids_atmost(G, i_b)
print(f"i:     CBC={i_c} B&B={i_b} (nodes {nodes_i}) SAT<={i_b-1}:{'SAT' if v1 else 'UNSAT'} SAT<={i_b}:{'SAT' if v2 else 'UNSAT'}  [{time.time()-t:.1f}s]  witness={bits_to_list(Si)}")
t = time.time(); mu_c, Mc = ilp_mmm_cbc(G); LG, E = line_graph(G); mu_b, _, _ = min_ids_bb(LG.n, LG.cnb)
print(f"mu*:   ILP={mu_c} L(G)-B&B={mu_b}  [{time.time()-t:.1f}s]")

# uniqueness of the minimum maximal matching: enumerate all maximal matchings of size 15 with SAT + blocking clauses
def count_min_maximal_matchings(G, k, limit=1000):
    from pysat.card import CardEnc, EncType
    from pysat.solvers import Solver
    E = G.edges; m = len(E); idx = {e: i for i, e in enumerate(E)}
    inc = [[] for _ in range(G.n)]
    for e in E:
        inc[e[0]].append(idx[e]); inc[e[1]].append(idx[e])
    clauses = []
    for v in range(G.n):                                  # matching: at most one chosen edge per vertex
        L = inc[v]
        for a in range(len(L)):
            for b in range(a + 1, len(L)):
                clauses.append([-(L[a] + 1), -(L[b] + 1)])
    for e in E:                                           # maximal: every edge dominated
        clauses.append(sorted({i + 1 for i in inc[e[0]]} | {i + 1 for i in inc[e[1]]}))
    card = CardEnc.atmost(lits=list(range(1, m + 1)), bound=k, top_id=m, encoding=EncType.seqcounter)
    clauses.extend(card.clauses)
    sols = []
    with Solver(name="cadical153", bootstrap_with=clauses) as s:
        while s.solve() and len(sols) < limit:
            model = s.get_model()
            chosen = [i for i in range(m) if model[i] > 0]
            sols.append([E[i] for i in chosen])
            s.add_clause([-(i + 1) for i in chosen])      # block this solution
    return sols

sols = count_min_maximal_matchings(G, 15)
print("maximal matchings of size 15 in the paper graph:", len(sols), "| equals M:", [sorted(s) for s in sols] == [M] if len(sols) == 1 else None)

data = json.load(open("counterexamples.json"))
for key, rec in data.items():
    H = Graph(rec["n"], rec["edges"])
    sols = count_min_maximal_matchings(H, 15)
    print(f"  {key}: maximal matchings of size 15 = {len(sols)}" + ("  (= the pivot matching)" if len(sols) == 1 and sorted(sols[0]) == M else ""))

# diagnostic only: is the paper's graph isomorphic to any of the JSON graphs?  (needs networkx; skipped if absent)
try:
    import networkx as nx
    PG = nx.Graph(G.edges)
    for key, rec in data.items():
        if nx.is_isomorphic(PG, nx.Graph(Graph(rec["n"], rec["edges"]).edges)):
            print("paper graph isomorphic to", key)
    print("isomorphism check against the seven JSON graphs done")
except ImportError:
    print("networkx not installed; isomorphism check skipped")
