"""Tight 3-uniform CNF formulas on v variables with every literal exactly twice,
and their incidence graphs G(F).

Conventions (match counterexamples.json on the repo):
  variables 1..v; literal +j / -j
  literal vertex of +j is 2*(j-1), of -j is 2*(j-1)+1; pivot edges (2k, 2k+1)
  clause c (0-based) is vertex 2*v + c
"""
import itertools
import numpy as np
import networkx as nx
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, csr_matrix

V = 15
M = 20
NASSIGN = 1 << V
FULL = (1 << NASSIGN) - 1


def _build_masks(v=V):
    n = 1 << v
    a = np.arange(n, dtype=np.int64)
    masks = {}
    for j in range(1, v + 1):
        bits = ((a >> (j - 1)) & 1).astype(np.uint8)
        m = int.from_bytes(np.packbits(bits, bitorder="little").tobytes(), "little")
        masks[j] = m
        masks[-j] = FULL ^ m
    return masks


LIT_MASK = _build_masks()


def lit_vertex(lit):
    j = abs(lit)
    return 2 * (j - 1) + (0 if lit > 0 else 1)


def vertex_lit(u):
    return (u // 2 + 1) * (1 if u % 2 == 0 else -1)


def clause_mask(cl):
    m = 0
    for lit in cl:
        m |= LIT_MASK[lit]
    return m


def formula_mask(K):
    m = FULL
    for cl in K:
        m &= clause_mask(cl)
    return m


def models(K):
    return formula_mask(K).bit_count()


def is_tight(K, v=V):
    """3-uniform, every literal exactly twice, no repeated/complementary literals in a clause, distinct clauses."""
    if len(K) != 4 * v // 3:
        return False
    cnt = {}
    for cl in K:
        if len(cl) != 3 or len({abs(l) for l in cl}) != 3:
            return False
        for l in cl:
            cnt[l] = cnt.get(l, 0) + 1
    if any(cnt.get(s * j, 0) != 2 for j in range(1, v + 1) for s in (1, -1)):
        return False
    if len({tuple(sorted(cl)) for cl in K}) != len(K):
        return False
    return True


def is_mu(K):
    if models(K) != 0:
        return False
    cms = [clause_mask(cl) for cl in K]
    for i in range(len(K)):
        m = FULL
        for j, cm in enumerate(cms):
            if j != i:
                m &= cm
        if m == 0:
            return False
    return True


def incidence_graph(K, v=V):
    G = nx.Graph()
    n = 2 * v + len(K)
    G.add_nodes_from(range(n))
    for k in range(v):
        G.add_edge(2 * k, 2 * k + 1)
    for c, cl in enumerate(K):
        cv = 2 * v + c
        for lit in cl:
            G.add_edge(lit_vertex(lit), cv)
    return G


def cut_variables(K, v=V):
    """Variables whose two literal vertices disconnect G(F). Returns dict j -> sizes of the sides
    (list of (#literal vertices, #clause vertices) per component)."""
    G = incidence_graph(K, v)
    out = {}
    for j in range(1, v + 1):
        H = G.copy()
        H.remove_nodes_from([2 * (j - 1), 2 * (j - 1) + 1])
        comps = list(nx.connected_components(H))
        if len(comps) > 1:
            out[j] = sorted(
                (sum(1 for u in c if u < 2 * v), sum(1 for u in c if u >= 2 * v)) for c in comps
            )
    return out


def certificate(G):
    """pynauty canonical certificate of an unlabeled graph (bytes)."""
    from pynauty import Graph as NGraph, certificate as ncert

    n = G.number_of_nodes()
    adj = {u: [w for w in G.neighbors(u)] for u in range(n)}
    return ncert(NGraph(n, directed=False, adjacency_dict=adj))


def canon_key(K, v=V):
    return certificate(incidence_graph(K, v)).hex()


def canonical_formula(K, v=V):
    """A normalized clause list: clauses as sorted tuples, sorted."""
    return sorted(tuple(sorted(cl, key=lambda l: (abs(l), l < 0))) for cl in K)


# ---------------------------------------------------------------- ILP (HiGHS)

def _dom_matrix(G):
    n = G.number_of_nodes()
    A = lil_matrix((n, n))
    for u in range(n):
        A[u, u] = 1
        for w in G.neighbors(u):
            A[u, w] = 1
    return csr_matrix(A)


def domination_number(G, independent=False, time_limit=600):
    n = G.number_of_nodes()
    cons = [LinearConstraint(_dom_matrix(G), lb=np.ones(n), ub=np.full(n, np.inf))]
    if independent:
        E = list(G.edges())
        B = lil_matrix((len(E), n))
        for r, (u, w) in enumerate(E):
            B[r, u] = 1
            B[r, w] = 1
        cons.append(LinearConstraint(csr_matrix(B), lb=np.zeros(len(E)), ub=np.ones(len(E))))
    res = milp(
        c=np.ones(n),
        constraints=cons,
        integrality=np.ones(n),
        bounds=Bounds(0, 1),
        options={"time_limit": time_limit, "presolve": True},
    )
    if res.status != 0:
        raise RuntimeError(f"milp status {res.status}: {res.message}")
    x = np.round(res.x).astype(int)
    S = [u for u in range(n) if x[u]]
    return len(S), S


def min_maximal_matching(G, time_limit=600):
    E = list(G.edges())
    n = G.number_of_nodes()
    m = len(E)
    inc = {u: [] for u in range(n)}
    for r, (u, w) in enumerate(E):
        inc[u].append(r)
        inc[w].append(r)
    # matching: each vertex covered at most once
    A = lil_matrix((n, m))
    for u in range(n):
        for r in inc[u]:
            A[u, r] = 1
    # maximality: each edge dominated by a matching edge
    B = lil_matrix((m, m))
    for r, (u, w) in enumerate(E):
        for s in set(inc[u]) | set(inc[w]):
            B[r, s] = 1
    cons = [
        LinearConstraint(csr_matrix(A), lb=np.zeros(n), ub=np.ones(n)),
        LinearConstraint(csr_matrix(B), lb=np.ones(m), ub=np.full(m, np.inf)),
    ]
    res = milp(c=np.ones(m), constraints=cons, integrality=np.ones(m), bounds=Bounds(0, 1),
               options={"time_limit": time_limit})
    if res.status != 0:
        raise RuntimeError(f"milp status {res.status}: {res.message}")
    y = np.round(res.x).astype(int)
    return int(y.sum()), [E[r] for r in range(m) if y[r]]


def check_dominating(G, S):
    S = set(S)
    return all(u in S or any(w in S for w in G.neighbors(u)) for u in G.nodes())


def check_independent(G, S):
    return not any(u in S and w in S for u, w in G.edges())


# ---------------------------------------------------------------- SAT (CaDiCaL)

def sat_no_domset_at_most(G, k, independent=False):
    """True iff CaDiCaL proves there is no (independent) dominating set of size <= k."""
    from pysat.solvers import Cadical153
    from pysat.card import CardEnc, EncType

    n = G.number_of_nodes()
    clauses = []
    for u in range(n):
        clauses.append([u + 1] + [w + 1 for w in G.neighbors(u)])
    if independent:
        for u, w in G.edges():
            clauses.append([-(u + 1), -(w + 1)])
    card = CardEnc.atmost(lits=list(range(1, n + 1)), bound=k, top_id=n, encoding=EncType.seqcounter)
    clauses.extend(card.clauses)
    with Cadical153(bootstrap_with=clauses) as s:
        return s.solve() is False


def analyze(K, v=V, sat_check=True):
    """Full parameter set for a tight formula. Returns dict."""
    G = incidence_graph(K, v)
    n = G.number_of_nodes()
    assert n == 2 * v + len(K) and all(d == 3 for _, d in G.degree()), "not cubic"
    assert nx.is_connected(G)
    out = {"n": n, "models": models(K), "mu": is_mu(K)}
    piv = {(2 * k, 2 * k + 1) for k in range(v)}
    # pivot matching is maximal (all literal vertices matched; clause vertices only meet literals)
    out["mu_star"] = v  # ceil(|E|/5) lower bound = v when |E| = 5v; pivot matching attains it
    assert G.number_of_edges() == 5 * v
    g, Sg = domination_number(G, independent=False)
    i, Si = domination_number(G, independent=True)
    assert check_dominating(G, Sg) and check_dominating(G, Si) and check_independent(G, Si)
    out["gamma"], out["i"] = g, i
    out["gamma_set"], out["i_set"] = Sg, Si
    out["cut_variables"] = cut_variables(K, v)
    out["glue_free"] = len(out["cut_variables"]) == 0
    if sat_check:
        out["sat_gamma_gt_%d" % (g - 1)] = sat_no_domset_at_most(G, g - 1, independent=False)
        out["sat_i_gt_%d" % (i - 1)] = sat_no_domset_at_most(G, i - 1, independent=True)
    out["cert"] = canon_key(K, v)
    return out
