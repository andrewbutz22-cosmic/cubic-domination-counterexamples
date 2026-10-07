"""Core objects for the clause-graph view of tight (3,2,2)-formulas.

A tight formula F (every clause 3 distinct literals, every literal exactly twice)
is the same thing as a pair (D, P):
  D = clause graph: one vertex per clause, one edge per literal joining the two
      clauses that contain it (loopless cubic multigraph),
  P = pairing of E(D) into complementary pairs {e_x, e_-x}; paired edges are
      never adjacent (else a clause would contain x and -x).
An assignment picks one edge from every pair (the true literal); it satisfies F
iff the picked edges cover every vertex.  So
      F unsat  <=>  D has no rainbow edge cover under P
(rainbow = at most one edge from each pair).
"""
import itertools
import numpy as np


# ---------------------------------------------------------------- formulas

def formula_to_DP(K):
    """K: list of clauses (lists of nonzero ints). Returns (nv, edges, pairs, lit_of_edge).
    edges[i] = (u, v) clause indices; pairs = list of (edge_pos, edge_neg)."""
    occ = {}
    for ci, C in enumerate(K):
        assert len(set(C)) == len(C)
        for l in C:
            occ.setdefault(l, []).append(ci)
    for l, cs in occ.items():
        assert len(cs) == 2, ("literal not exactly twice", l, cs)
        assert -l in occ, ("pure literal", l)
    lits = sorted(occ, key=lambda l: (abs(l), -l))
    edge_of = {}
    edges = []
    for l in lits:
        edge_of[l] = len(edges)
        edges.append(tuple(occ[l]))
    pairs = []
    for x in sorted({abs(l) for l in lits}):
        pairs.append((edge_of[x], edge_of[-x]))
    return len(K), edges, pairs, lits


def DP_to_formula(nv, edges, pairs):
    """Inverse: variable j+1 is pair j, literal +(j+1) is pairs[j][0]."""
    K = [[] for _ in range(nv)]
    for j, (a, b) in enumerate(pairs):
        for (e, lit) in ((a, j + 1), (b, -(j + 1))):
            u, v = edges[e]
            K[u].append(lit)
            K[v].append(lit)
    return [sorted(C, key=abs) for C in K]


# ---------------------------------------------------------------- sat by bitset

_bitcache = {}


def _bits(nvar):
    if nvar not in _bitcache:
        a = np.arange(1 << nvar, dtype=np.int64)
        _bitcache[nvar] = [((a >> j) & 1).astype(bool) for j in range(nvar)]
    return _bitcache[nvar]


def models_formula(K, nvar=None):
    """Boolean array over all 2^nvar assignments: True = model. Bit j = value of var j+1."""
    if nvar is None:
        nvar = max(abs(l) for C in K for l in C)
    B = _bits(nvar)
    ok = np.ones(1 << nvar, dtype=bool)
    for C in K:
        s = np.zeros(1 << nvar, dtype=bool)
        for l in C:
            s |= B[abs(l) - 1] if l > 0 else ~B[abs(l) - 1]
        ok &= s
    return ok


def models_DP(nv, edges, pairs, skip_vertices=(), banned_edges=()):
    """Rainbow edge covers, as assignments: bit j = 1 picks pairs[j][1], 0 picks pairs[j][0].
    banned_edges are never usable (e.g. a glue edge whose partner lives elsewhere).
    Vertices in skip_vertices need not be covered."""
    npair = len(pairs)
    B = _bits(npair)
    pick = {}
    for j, (a, b) in enumerate(pairs):
        pick[a] = ~B[j]
        pick[b] = B[j]
    inc = [[] for _ in range(nv)]
    for e, (u, v) in enumerate(edges):
        inc[u].append(e)
        inc[v].append(e)
    ok = np.ones(1 << npair, dtype=bool)
    skip = set(skip_vertices)
    banned = set(banned_edges)
    for v in range(nv):
        if v in skip:
            continue
        s = np.zeros(1 << npair, dtype=bool)
        for e in inc[v]:
            if e in banned:
                continue
            if e in pick:
                s |= pick[e]
        ok &= s
    return ok


# ---------------------------------------------------------------- graph helpers

def incidence(nv, edges):
    inc = [[] for _ in range(nv)]
    for e, (u, v) in enumerate(edges):
        inc[u].append(e)
        inc[v].append(e)
    return inc


def edge_adjacency(nv, edges):
    m = len(edges)
    adj = np.zeros((m, m), dtype=bool)
    for e in range(m):
        for f in range(m):
            if e != f and set(edges[e]) & set(edges[f]):
                adj[e, f] = True
    return adj


def is_simple(edges):
    seen = set()
    for (u, v) in edges:
        k = (min(u, v), max(u, v))
        if u == v or k in seen:
            return False
        seen.add(k)
    return True


def perfect_matchings(nv, edges):
    """All perfect matchings as sorted tuples of edge indices (multigraph-safe)."""
    inc = incidence(nv, edges)
    out = []
    covered = [False] * nv
    cur = []

    def rec():
        try:
            v = covered.index(False)
        except ValueError:
            out.append(tuple(sorted(cur)))
            return
        covered[v] = True
        for e in inc[v]:
            a, b = edges[e]
            w = b if a == v else a
            if not covered[w]:
                covered[w] = True
                cur.append(e)
                rec()
                cur.pop()
                covered[w] = False
        covered[v] = False

    rec()
    return out


def minimal_edge_covers(nv, edges, max_count=None):
    """All minimal edge covers (spanning star forests where every edge has a leaf end).
    Returned as sorted tuples of edge indices."""
    inc = incidence(nv, edges)
    m = len(edges)
    out = set()
    # brute-force via recursion on vertices: choose for each uncovered vertex an edge
    chosen = []
    cnt = [0] * nv

    def is_minimal(S):
        c = [0] * nv
        for e in S:
            u, v = edges[e]
            c[u] += 1
            c[v] += 1
        for e in S:
            u, v = edges[e]
            if c[u] >= 2 and c[v] >= 2:
                return False
        return True

    def rec():
        if max_count is not None and len(out) >= max_count:
            return
        try:
            v = cnt.index(0)
        except ValueError:
            S = tuple(sorted(chosen))
            if is_minimal(S):
                out.add(S)
            return
        for e in inc[v]:
            if e in chosen:
                continue
            a, b = edges[e]
            chosen.append(e)
            cnt[a] += 1
            cnt[b] += 1
            # prune: an edge both of whose ends are covered twice is redundant -> any
            # completion is non-minimal (counts only grow)
            bad = False
            for f in chosen:
                x, y = edges[f]
                if cnt[x] >= 2 and cnt[y] >= 2:
                    bad = True
                    break
            if not bad:
                rec()
            cnt[a] -= 1
            cnt[b] -= 1
            chosen.pop()

    rec()
    return sorted(out)


# ---------------------------------------------------------------- lemma checks

def diagonal_violations(nv, edges, pairs):
    """Substitution lemma (needs mu(3,2,2) > 18): for pairs X={e,f}, Y={g,h},
    if e~g and f~h (one diagonal fully adjacent) then e~h or f~g.
    Returns list of violating (X, Y) index pairs."""
    adj = edge_adjacency(nv, edges)
    bad = []
    for i, j in itertools.combinations(range(len(pairs)), 2):
        e, f = pairs[i]
        g, h = pairs[j]
        for (g2, h2) in ((g, h), (h, g)):
            if adj[e, g2] and adj[f, h2] and not adj[e, h2] and not adj[f, g2]:
                bad.append((i, j))
    return bad


# ---------------------------------------------------------------- canonical form

def G_of_DP(nv, edges, pairs):
    """The cubic graph G(F): clause vertices 0..nv-1, literal vertex nv+e for edge e,
    literal-clause edges, and variable edges between paired literal vertices."""
    E = []
    for e, (u, v) in enumerate(edges):
        E.append((u, nv + e))
        E.append((v, nv + e))
    for (a, b) in pairs:
        E.append((nv + a, nv + b))
    return nv + len(edges), E


def cert_DP(nv, edges, pairs, colored=True):
    """nauty certificate of G(F) (as bytes). colored=True keeps clause/literal classes apart."""
    import pynauty
    N, E = G_of_DP(nv, edges, pairs)
    adj = {i: [] for i in range(N)}
    for (a, b) in E:
        adj[a].append(b)
        adj[b].append(a)
    col = [set(range(nv)), set(range(nv, N))] if colored else []
    g = pynauty.Graph(N, directed=False, adjacency_dict=adj, vertex_coloring=col)
    return pynauty.certificate(g)
