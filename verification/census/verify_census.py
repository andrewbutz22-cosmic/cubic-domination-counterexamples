"""Re-verify census_tight_15_20.json from the definitions.

For every class: the formula is 3-uniform on 15 variables with 20 clauses and every literal exactly twice;
it is unsatisfiable (all 2^15 assignments) and minimally so; G(F) is a connected cubic graph on 50 vertices
with 75 edges that matches the stored edge list and graph6; the stored dominating set / independent dominating
set / maximal matching are what they claim and have the stored sizes; no (independent) dominating set one
smaller exists (HiGHS ILP, and CaDiCaL on an independent encoding); no maximal matching of size 14 exists;
cut variables, girth and automorphism order are as stored; and all certificates are pairwise distinct.

    pip install numpy scipy networkx pynauty python-sat
    python3 verify_census.py census_tight_15_20.json        # ~15 minutes on one core
    python3 verify_census.py census_tight_15_20.json 50 100 # optional: 50 classes starting at index 100

Prints the summary counts that appear in Theorem 5 of the note and exits 0 iff everything checks.
"""
import json, sys, time, collections, itertools
import numpy as np
import networkx as nx
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, csr_matrix

V, M = 15, 20
N = 1 << V
FULL = (1 << N) - 1


def lit_masks():
    a = np.arange(N, dtype=np.int64)
    out = {}
    for j in range(1, V + 1):
        m = int.from_bytes(np.packbits(((a >> (j - 1)) & 1).astype(np.uint8), bitorder="little").tobytes(), "little")
        out[j], out[-j] = m, FULL ^ m
    return out


LM = lit_masks()


def models(K):
    m = FULL
    for cl in K:
        m &= LM[cl[0]] | LM[cl[1]] | LM[cl[2]]
    return m.bit_count()


def graph(K):
    G = nx.Graph()
    G.add_nodes_from(range(2 * V + M))
    for k in range(V):
        G.add_edge(2 * k, 2 * k + 1)
    for c, cl in enumerate(K):
        for l in cl:
            G.add_edge(2 * (abs(l) - 1) + (l < 0), 2 * V + c)
    return G


def ilp_dom(G, independent):
    n = G.number_of_nodes()
    A = lil_matrix((n, n))
    for u in range(n):
        A[u, u] = 1
        for w in G.neighbors(u):
            A[u, w] = 1
    cons = [LinearConstraint(csr_matrix(A), lb=np.ones(n), ub=np.full(n, np.inf))]
    if independent:
        E = list(G.edges())
        B = lil_matrix((len(E), n))
        for r, (u, w) in enumerate(E):
            B[r, u] = B[r, w] = 1
        cons.append(LinearConstraint(csr_matrix(B), lb=np.zeros(len(E)), ub=np.ones(len(E))))
    res = milp(c=np.ones(n), constraints=cons, integrality=np.ones(n), bounds=Bounds(0, 1))
    assert res.status == 0, res.message
    return int(round(res.fun))


def ilp_mmm(G):
    E = list(G.edges()); n = G.number_of_nodes(); m = len(E)
    inc = collections.defaultdict(list)
    for r, (u, w) in enumerate(E):
        inc[u].append(r); inc[w].append(r)
    A = lil_matrix((n, m)); B = lil_matrix((m, m))
    for u in range(n):
        for r in inc[u]:
            A[u, r] = 1
    for r, (u, w) in enumerate(E):
        for s in set(inc[u]) | set(inc[w]):
            B[r, s] = 1
    cons = [LinearConstraint(csr_matrix(A), lb=np.zeros(n), ub=np.ones(n)),
            LinearConstraint(csr_matrix(B), lb=np.ones(m), ub=np.full(m, np.inf))]
    res = milp(c=np.ones(m), constraints=cons, integrality=np.ones(m), bounds=Bounds(0, 1))
    assert res.status == 0, res.message
    return int(round(res.fun))


def sat_none_at_most(G, k, independent):
    from pysat.solvers import Cadical153
    from pysat.card import CardEnc, EncType
    n = G.number_of_nodes()
    cls = [[u + 1] + [w + 1 for w in G.neighbors(u)] for u in range(n)]
    if independent:
        cls += [[-(u + 1), -(w + 1)] for u, w in G.edges()]
    cls += CardEnc.atmost(lits=list(range(1, n + 1)), bound=k, top_id=n, encoding=EncType.seqcounter).clauses
    with Cadical153(bootstrap_with=cls) as s:
        return s.solve() is False


def dominating(G, S):
    S = set(S)
    return all(u in S or any(w in S for w in G.neighbors(u)) for u in G.nodes())


def independent(G, S):
    S = set(S)
    return not any(u in S and w in S for u, w in G.edges())


def maximal_matching(G, Mset):
    Mset = [tuple(e) for e in Mset]
    used = [v for e in Mset for v in e]
    if len(used) != len(set(used)) or not all(G.has_edge(*e) for e in Mset):
        return False
    used = set(used)
    return all(u in used or w in used for u, w in G.edges())


def cut_variables(G):
    out = {}
    for j in range(1, V + 1):
        H = G.copy(); H.remove_nodes_from([2 * (j - 1), 2 * (j - 1) + 1])
        if not nx.is_connected(H):
            out[j] = True
    return out


def nauty_cert_and_aut(G):
    from pynauty import Graph as NG, certificate, autgrp
    n = G.number_of_nodes()
    g = NG(n, directed=False, adjacency_dict={u: list(G.neighbors(u)) for u in range(n)})
    gens, s1, s2, orb, norb = autgrp(g)
    return certificate(g), int(round(s1 * 10 ** s2))


def main(path, limit=None, start=0):
    F = json.load(open(path))
    items = list(F.items())[start:start + limit] if limit else list(F.items())[start:]
    t0 = time.time(); certs = {}; cells = collections.Counter(); ok = True
    for idx, (key, c) in enumerate(items):
        K = [tuple(cl) for cl in c["K"]]
        try:
            assert len(K) == M and all(len(cl) == 3 and len({abs(l) for l in cl}) == 3 for cl in K)
            cnt = collections.Counter(l for cl in K for l in cl)
            assert all(cnt[s * j] == 2 for j in range(1, V + 1) for s in (1, -1))
            assert models(K) == 0
            assert all(models(K[:r] + K[r + 1:]) > 0 for r in range(M))
            G = graph(K)
            assert G.number_of_nodes() == 50 and G.number_of_edges() == 75 and all(d == 3 for _, d in G.degree())
            assert nx.is_connected(G)
            assert set(map(tuple, c["edges"])) == {tuple(sorted(e)) for e in G.edges()}
            assert nx.to_graph6_bytes(G, header=False).decode().strip() == c["graph6"]
            g, i, mu = c["gamma"], c["i"], c["mu"]
            assert dominating(G, c["gamma_set"]) and len(c["gamma_set"]) == g
            assert dominating(G, c["ids"]) and independent(G, c["ids"]) and len(c["ids"]) == i
            assert maximal_matching(G, c["mmm"]) and len(c["mmm"]) == mu == 15
            assert maximal_matching(G, [[2 * k, 2 * k + 1] for k in range(V)])
            assert ilp_dom(G, False) == g and ilp_dom(G, True) == i and ilp_mmm(G) == 15
            assert sat_none_at_most(G, g - 1, False) and sat_none_at_most(G, i - 1, True)
            cv = cut_variables(G)
            assert set(map(str, cv)) == set(c["cut_variables"]) and c["glue_free"] == (not cv)
            assert nx.girth(G) == c["girth"] == 5
            cert, aut = nauty_cert_and_aut(G)
            assert cert.hex() == key and aut == c["aut_order"]
            assert cert not in certs, "isomorphic duplicate"
            certs[cert] = key
            cells[(g, i, c["glue_free"])] += 1
        except AssertionError as e:
            ok = False
            print("FAIL", key[:16], e)
        if (idx + 1) % 25 == 0:
            print(f"  {idx + 1}/{len(items)} ({time.time() - t0:.0f}s)", flush=True)
    n = len(items)
    print(f"{n} classes verified in {time.time() - t0:.0f}s; all certificates distinct: {len(certs) == n}")
    print("gamma i glue_free count")
    for k, v in sorted(cells.items()):
        print(*k, v)
    tot = lambda f: sum(v for k, v in cells.items() if f(*k))
    print(f"i=16: {tot(lambda g, i, gf: i == 16)}  gamma=16: {tot(lambda g, i, gf: g == 16)}  "
          f"no cut variable: {tot(lambda g, i, gf: gf)}  gluings: {tot(lambda g, i, gf: not gf)}")
    return ok


if __name__ == "__main__":
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else None
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else "census_tight_15_20.json", lim, start) else 1)
