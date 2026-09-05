#!/usr/bin/env python3
"""
Independent verification of claimed counterexamples to  i(G) <= mu*(G)  (r-regular G).

Everything below is written from the bare definitions:
  * graph6 decoder / encoder (McKay's format), no networkx in the pipeline
  * simplicity / regularity / connectivity checks
  * maximal-matching check
  * i(G)   = min |S|, S independent and dominating           -- three engines:
        (a) ILP, CBC via pulp;  (a') same ILP, HiGHS via scipy.optimize.milp
        (b) own bitset branch-and-bound (exhaustive)
        (c) SAT with a cardinality constraint (pysat / CaDiCaL): |S| <= k
  * mu*(G) = min size of a maximal matching (= edge domination number) -- two engines:
        (a) ILP over edges (matching + edge-domination constraints), CBC
        (b) the same branch-and-bound applied to the line graph L(G)
            (a maximal matching of G is exactly an independent dominating set of L(G))
Every witness set returned by any engine is re-checked against the definitions.
"""
import json, sys, time, math, random
from collections import deque

# ----------------------------------------------------------------------------- graph6
def g6_decode(s):
    s = s.strip()
    if s.startswith('>>graph6<<'):
        s = s[10:]
    data = [ord(c) - 63 for c in s]
    if not data or not all(0 <= x <= 63 for x in data):
        raise ValueError("invalid graph6 character")
    if data[0] <= 62:
        n, pos = data[0], 1
    elif data[1] <= 62:
        n, pos = (data[1] << 12) | (data[2] << 6) | data[3], 4
    else:
        n = (data[2] << 30) | (data[3] << 24) | (data[4] << 18) | (data[5] << 12) | (data[6] << 6) | data[7]
        pos = 8
    bits = []
    for x in data[pos:]:
        for k in range(5, -1, -1):
            bits.append((x >> k) & 1)
    need = n * (n - 1) // 2
    if len(bits) < need or len(bits) - need >= 6:
        raise ValueError(f"graph6 length mismatch: n={n} needs {need} bits ({(need+5)//6} chars after the size), "
                         f"string supplies {len(bits)} bits ({len(data)-pos} chars)")
    if any(bits[need:]):
        raise ValueError("non-zero padding bits")
    edges, idx = [], 0
    for j in range(1, n):            # column-major upper triangle: (0,1),(0,2),(1,2),(0,3),...
        for i in range(j):
            if bits[idx]:
                edges.append((i, j))
            idx += 1
    return n, edges

def g6_encode(n, edges):
    assert n <= 62
    es = {(min(u, v), max(u, v)) for u, v in edges}
    bits = []
    for j in range(1, n):
        for i in range(j):
            bits.append(1 if (i, j) in es else 0)
    while len(bits) % 6:
        bits.append(0)
    out = [chr(n + 63)]
    for k in range(0, len(bits), 6):
        v = 0
        for b in bits[k:k + 6]:
            v = (v << 1) | b
        out.append(chr(v + 63))
    return ''.join(out)

# ----------------------------------------------------------------------------- basic graph
class Graph:
    def __init__(self, n, edges):
        self.n = n
        self.edges = sorted({(min(u, v), max(u, v)) for u, v in edges})
        self.adj = [set() for _ in range(n)]
        for u, v in self.edges:
            self.adj[u].add(v); self.adj[v].add(u)
        self.nb = [sum(1 << u for u in self.adj[v]) for v in range(n)]          # open nbhd bitmask
        self.cnb = [self.nb[v] | (1 << v) for v in range(n)]                    # closed nbhd bitmask

def check_simple(n, raw_edges):
    """raw_edges as given (list of pairs). Returns list of problems (empty = simple)."""
    problems = []
    seen = set()
    for e in raw_edges:
        if len(e) != 2:
            problems.append(f"bad edge {e}"); continue
        u, v = e
        if not (0 <= u < n and 0 <= v < n):
            problems.append(f"vertex out of range in {e}")
        if u == v:
            problems.append(f"loop {e}")
        key = (min(u, v), max(u, v))
        if key in seen:
            problems.append(f"repeated edge {e}")
        seen.add(key)
    return problems

def degrees(G):
    return [len(G.adj[v]) for v in range(G.n)]

def is_connected(G):
    if G.n == 0:
        return True
    seen = {0}; dq = deque([0])
    while dq:
        v = dq.popleft()
        for u in G.adj[v]:
            if u not in seen:
                seen.add(u); dq.append(u)
    return len(seen) == G.n

# ----------------------------------------------------------------------------- definitions as predicates
def is_independent(G, S):
    S = set(S)
    return all(not (G.adj[v] & S) for v in S)

def is_dominating(G, S):
    S = set(S)
    return all(v in S or (G.adj[v] & S) for v in range(G.n))

def is_matching(G, M):
    es = set(G.edges)
    used = set()
    for u, v in M:
        if (min(u, v), max(u, v)) not in es:
            return False, f"{(u,v)} is not an edge"
        if u in used or v in used:
            return False, f"vertex reuse at {(u,v)}"
        used.add(u); used.add(v)
    return True, "ok"

def is_maximal_matching(G, M):
    ok, why = is_matching(G, M)
    if not ok:
        return False, why
    covered = {x for e in M for x in e}
    bad = [e for e in G.edges if e[0] not in covered and e[1] not in covered]
    return (not bad), (f"edges with no endpoint in V(M): {bad[:5]}" if bad else "maximal")

# ----------------------------------------------------------------------------- engine (b): branch and bound
def min_ids_bb(n, cnb, ub=None, node_limit=None):
    """Exact minimum independent dominating set by branch-and-bound on bitsets.
    State: S chosen, F forbidden (neighbours of S, or branched away), D dominated.
    Branch on an undominated vertex v with the fewest allowed vertices in N[v]:
    one of them must enter S. Bound: |S| + ceil(#undominated / max_new_coverage) < best.
    Returns (size, set-bitmask, nodes). ub: only sets of size <= ub are sought (None = n)."""
    full = (1 << n) - 1
    best = [(n if ub is None else ub) + 1, None]
    nodes = [0]
    sys.setrecursionlimit(10000)

    def rec(S, F, D, k):
        nodes[0] += 1
        if node_limit and nodes[0] > node_limit:
            raise RuntimeError("node limit")
        if D == full:
            if k < best[0]:
                best[0], best[1] = k, S
            return
        if k + 1 >= best[0]:
            return
        und = full & ~D
        allowed = full & ~F
        # choose branching vertex + check feasibility
        bv_c, bv_cnt = None, 1 << 30
        it = und
        while it:
            low = it & -it; it ^= low
            v = low.bit_length() - 1
            c = cnb[v] & allowed
            cnt = c.bit_count()
            if cnt == 0:
                return                       # v can never be dominated
            if cnt < bv_cnt:
                bv_cnt, bv_c = cnt, c
                if cnt == 1:
                    break
        # lower bound on the number of further vertices needed
        maxcov = 0
        it = allowed
        while it:
            low = it & -it; it ^= low
            u = low.bit_length() - 1
            cov = (cnb[u] & und).bit_count()
            if cov > maxcov:
                maxcov = cov
        if maxcov == 0:
            return
        if k + (-(-und.bit_count() // maxcov)) >= best[0]:
            return
        # branch: try candidates with the largest new coverage first
        cands = []
        c = bv_c
        while c:
            low = c & -c; c ^= low
            u = low.bit_length() - 1
            cands.append(((cnb[u] & und).bit_count(), u))
        cands.sort(reverse=True)
        Fl = F
        for _, u in cands:
            rec(S | (1 << u), Fl | cnb[u], D | cnb[u], k + 1)
            Fl |= (1 << u)                   # later branches: u is not in S

    rec(0, 0, 0, 0)
    return best[0], best[1], nodes[0]

def bits_to_list(mask):
    out = []
    while mask:
        low = mask & -mask; mask ^= low
        out.append(low.bit_length() - 1)
    return out

# ----------------------------------------------------------------------------- engine (a): ILP (CBC via pulp)
def ilp_ids_cbc(G):
    import pulp
    prob = pulp.LpProblem("ids", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x{v}", cat="Binary") for v in range(G.n)]
    prob += pulp.lpSum(x)
    for u, v in G.edges:
        prob += x[u] + x[v] <= 1                       # independent
    for v in range(G.n):
        prob += x[v] + pulp.lpSum(x[u] for u in G.adj[v]) >= 1   # dominated
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
    assert pulp.LpStatus[status] == "Optimal", pulp.LpStatus[status]
    S = [v for v in range(G.n) if x[v].value() > 0.5]
    return int(round(pulp.value(prob.objective))), S

def ilp_ids_feasible_cbc(G, k):
    """Feasibility ILP: is there an independent dominating set of size <= k?"""
    import pulp
    prob = pulp.LpProblem("ids_feas", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x{v}", cat="Binary") for v in range(G.n)]
    prob += 0
    for u, v in G.edges:
        prob += x[u] + x[v] <= 1
    for v in range(G.n):
        prob += x[v] + pulp.lpSum(x[u] for u in G.adj[v]) >= 1
    prob += pulp.lpSum(x) <= k
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
    return pulp.LpStatus[status]

def ilp_ids_highs(G):
    import numpy as np
    from scipy.optimize import milp, LinearConstraint, Bounds
    n = G.n
    rows, lb, ub = [], [], []
    for u, v in G.edges:
        r = np.zeros(n); r[u] = 1; r[v] = 1
        rows.append(r); lb.append(-np.inf); ub.append(1)
    for v in range(n):
        r = np.zeros(n); r[v] = 1
        for u in G.adj[v]:
            r[u] = 1
        rows.append(r); lb.append(1); ub.append(np.inf)
    res = milp(c=np.ones(n), constraints=LinearConstraint(np.array(rows), lb, ub),
               integrality=np.ones(n), bounds=Bounds(0, 1))
    assert res.status == 0, res.message
    S = [v for v in range(n) if res.x[v] > 0.5]
    return int(round(res.fun)), S

def ilp_mmm_cbc(G):
    """Minimum maximal matching: y_e binary; matching constraints; every edge dominated
    (shares an endpoint with a chosen edge, or is chosen)."""
    import pulp
    E = G.edges
    idx = {e: i for i, e in enumerate(E)}
    inc = [[] for _ in range(G.n)]
    for e in E:
        inc[e[0]].append(idx[e]); inc[e[1]].append(idx[e])
    prob = pulp.LpProblem("mmm", pulp.LpMinimize)
    y = [pulp.LpVariable(f"y{i}", cat="Binary") for i in range(len(E))]
    prob += pulp.lpSum(y)
    for v in range(G.n):
        if inc[v]:
            prob += pulp.lpSum(y[i] for i in inc[v]) <= 1
    for e in E:
        nbrs = set(inc[e[0]]) | set(inc[e[1]])          # contains e itself
        prob += pulp.lpSum(y[i] for i in nbrs) >= 1
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
    assert pulp.LpStatus[status] == "Optimal", pulp.LpStatus[status]
    M = [E[i] for i in range(len(E)) if y[i].value() > 0.5]
    return int(round(pulp.value(prob.objective))), M

# ----------------------------------------------------------------------------- engine (c): SAT
def sat_ids_atmost(G, k, solver_name="cadical153"):
    """Is there an independent dominating set of size <= k?  Returns (bool, witness)."""
    from pysat.card import CardEnc, EncType
    from pysat.solvers import Solver
    n = G.n
    clauses = []
    for u, v in G.edges:
        clauses.append([-(u + 1), -(v + 1)])
    for v in range(n):
        clauses.append([v + 1] + [u + 1 for u in G.adj[v]])
    card = CardEnc.atmost(lits=list(range(1, n + 1)), bound=k, top_id=n, encoding=EncType.seqcounter)
    clauses.extend(card.clauses)
    with Solver(name=solver_name, bootstrap_with=clauses) as s:
        ok = s.solve()
        if ok:
            model = set(l for l in s.get_model() if l > 0)
            return True, [v for v in range(n) if (v + 1) in model]
        return False, None

def sat_cnf_satisfiable(K, solver_name="cadical153"):
    from pysat.solvers import Solver
    with Solver(name=solver_name, bootstrap_with=[list(c) for c in K]) as s:
        ok = s.solve()
        return ok, (s.get_model() if ok else None)

# ----------------------------------------------------------------------------- line graph
def line_graph(G):
    E = G.edges
    idx = {e: i for i, e in enumerate(E)}
    inc = [[] for _ in range(G.n)]
    for e in E:
        inc[e[0]].append(idx[e]); inc[e[1]].append(idx[e])
    ledges = set()
    for v in range(G.n):
        L = inc[v]
        for a in range(len(L)):
            for b in range(a + 1, len(L)):
                ledges.add((min(L[a], L[b]), max(L[a], L[b])))
    return Graph(len(E), sorted(ledges)), E

# ----------------------------------------------------------------------------- full battery for one graph
def analyse(name, G, pivot=None, K=None, claimed=None, do_highs=True, do_sat=True, do_linegraph=True):
    R = {"name": name, "n": G.n, "m": len(G.edges)}
    t0 = time.time()
    deg = degrees(G)
    R["degrees"] = sorted(set(deg))
    R["regular"] = (len(set(deg)) == 1)
    R["connected"] = is_connected(G)
    if pivot is not None:
        ok, why = is_maximal_matching(G, pivot)
        R["pivot_matching_size"] = len(pivot)
        R["pivot_is_maximal_matching"] = ok
        R["pivot_note"] = why
        covered = {x for e in pivot for x in e}
        R["all_edges_touch_V(M)"] = all(e[0] in covered or e[1] in covered for e in G.edges)
    # trivial bounds from the definitions (each vertex dominates <= Delta+1 vertices,
    # each edge dominates <= 2*Delta-1 edges)
    Delta = max(deg)
    R["trivial_lb_i"] = -(-G.n // (Delta + 1))
    R["trivial_lb_mu"] = -(-len(G.edges) // (2 * Delta - 1))

    # ---- i(G): ILP / CBC
    t = time.time(); v_cbc, S_cbc = ilp_ids_cbc(G); R["i_ilp_cbc"] = v_cbc; R["t_i_ilp_cbc"] = time.time() - t
    assert is_independent(G, S_cbc) and is_dominating(G, S_cbc) and len(S_cbc) == v_cbc
    R["i_ilp_cbc_witness"] = S_cbc
    # feasibility at one less (explicit "no set of size i-1")
    t = time.time(); R["i_ilp_cbc_feas_at_minus1"] = ilp_ids_feasible_cbc(G, v_cbc - 1); R["t_i_ilp_cbc_feas"] = time.time() - t
    # ---- i(G): ILP / HiGHS
    if do_highs:
        t = time.time(); v_h, S_h = ilp_ids_highs(G); R["i_ilp_highs"] = v_h; R["t_i_ilp_highs"] = time.time() - t
        assert is_independent(G, S_h) and is_dominating(G, S_h) and len(S_h) == v_h
    # ---- i(G): branch and bound (standalone, no upper bound seeded)
    t = time.time(); v_bb, S_bb_mask, nodes = min_ids_bb(G.n, G.cnb); R["i_bb"] = v_bb; R["t_i_bb"] = time.time() - t
    R["i_bb_nodes"] = nodes
    S_bb = bits_to_list(S_bb_mask)
    assert is_independent(G, S_bb) and is_dominating(G, S_bb) and len(S_bb) == v_bb
    R["i_bb_witness"] = S_bb
    # ---- i(G): SAT, |S| <= i-1 must be UNSAT, |S| <= i must be SAT
    if do_sat:
        t = time.time()
        unsat_ok, _ = sat_ids_atmost(G, v_bb - 1)
        sat_ok, S_sat = sat_ids_atmost(G, v_bb)
        R["t_i_sat"] = time.time() - t
        R["sat_atmost_i_minus_1"] = "SAT" if unsat_ok else "UNSAT"
        R["sat_atmost_i"] = "SAT" if sat_ok else "UNSAT"
        if sat_ok:
            assert is_independent(G, S_sat) and is_dominating(G, S_sat) and len(S_sat) <= v_bb
    # ---- mu*(G): ILP over edges
    t = time.time(); v_mu, M_mu = ilp_mmm_cbc(G); R["mu_ilp_cbc"] = v_mu; R["t_mu_ilp_cbc"] = time.time() - t
    okm, whym = is_maximal_matching(G, M_mu)
    assert okm and len(M_mu) == v_mu, whym
    R["mu_ilp_witness"] = M_mu
    # ---- mu*(G): B&B on the line graph
    if do_linegraph:
        LG, E = line_graph(G)
        t = time.time(); v_mul, M_mask, nodes_l = min_ids_bb(LG.n, LG.cnb); R["mu_bb_linegraph"] = v_mul; R["t_mu_bb_linegraph"] = time.time() - t
        R["mu_bb_nodes"] = nodes_l
        M_l = [E[i] for i in bits_to_list(M_mask)]
        okm, whym = is_maximal_matching(G, M_l)
        assert okm and len(M_l) == v_mul, whym
    # ---- optional: the CNF K and the literal/clause structure
    if K is not None:
        R["K_vars"] = max(abs(l) for c in K for l in c)
        R["K_clauses"] = len(K)
        # every literal exactly twice?
        from collections import Counter
        cnt = Counter(l for c in K for l in c)
        R["K_literal_occurrences"] = sorted(set(cnt.values()))
        ok, model = sat_cnf_satisfiable(K)
        R["K_satisfiable"] = ok
        # does G equal the literal/clause incidence construction?  literal x -> vertex 2(x-1), -x -> 2x-1;
        # clause j -> vertex 2*vars + j; plus the variable edges (2x-2, 2x-1)
        nv = R["K_vars"]
        cons = set()
        for x in range(1, nv + 1):
            cons.add((2 * x - 2, 2 * x - 1))
        for j, c in enumerate(K):
            for l in c:
                lv = 2 * abs(l) - 2 if l > 0 else 2 * abs(l) - 1
                cv = 2 * nv + j
                cons.add((min(lv, cv), max(lv, cv)))
        R["G_equals_literal_clause_construction"] = (sorted(cons) == G.edges) and (G.n == 2 * nv + len(K))
    if claimed:
        R["claimed"] = claimed
    R["t_total"] = time.time() - t0
    return R

# ----------------------------------------------------------------------------- named graphs
def petersen():
    from itertools import combinations
    V = list(combinations(range(5), 2))
    idx = {p: i for i, p in enumerate(V)}
    edges = [(idx[a], idx[b]) for a in V for b in V if a < b and not (set(a) & set(b))]
    return Graph(10, edges)

def random_cubic(n, rng):
    """Pairing (configuration) model, rejecting loops/multi-edges."""
    while True:
        pts = [v for v in range(n) for _ in range(3)]
        rng.shuffle(pts)
        edges = set(); ok = True
        for i in range(0, len(pts), 2):
            u, v = pts[i], pts[i + 1]
            if u == v or (min(u, v), max(u, v)) in edges:
                ok = False; break
            edges.add((min(u, v), max(u, v)))
        if ok:
            G = Graph(n, edges)
            if is_connected(G):
                return G

def summary_line(R):
    parts = [f"{R['name']:8s} n={R['n']} m={R['m']} deg={R['degrees']} conn={R['connected']}"]
    if "pivot_is_maximal_matching" in R:
        parts.append(f"pivot maximal={R['pivot_is_maximal_matching']} (|M|={R['pivot_matching_size']})")
    parts.append(f"i: CBC={R['i_ilp_cbc']} HiGHS={R.get('i_ilp_highs','-')} BB={R['i_bb']} (nodes {R['i_bb_nodes']}) "
                 f"SAT<=i-1:{R.get('sat_atmost_i_minus_1','-')} SAT<=i:{R.get('sat_atmost_i','-')} CBC-feas(i-1):{R['i_ilp_cbc_feas_at_minus1']}")
    parts.append(f"mu*: ILP={R['mu_ilp_cbc']} BB(L(G))={R.get('mu_bb_linegraph','-')} (nodes {R.get('mu_bb_nodes','-')})")
    if "K_satisfiable" in R:
        parts.append(f"K: {R['K_vars']} vars/{R['K_clauses']} clauses, lit-occ={R['K_literal_occurrences']}, SAT={R['K_satisfiable']}, G==construction:{R['G_equals_literal_clause_construction']}")
    parts.append(f"times: i_cbc={R['t_i_ilp_cbc']:.2f}s i_highs={R.get('t_i_ilp_highs',0):.2f}s i_bb={R['t_i_bb']:.2f}s i_sat={R.get('t_i_sat',0):.2f}s mu_ilp={R['t_mu_ilp_cbc']:.2f}s mu_bb={R.get('t_mu_bb_linegraph',0):.2f}s")
    return "\n    ".join(parts)

if __name__ == "__main__":
    random.seed(1)
    results = {}
    data = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "counterexamples.json"))

    # ---- 0. the pasted graph6 string
    import os
    if os.path.exists("pasted_g6.txt"):
        pasted = open("pasted_g6.txt").read().strip()
        print("== pasted graph6 string (from the task text) ==")
        print("   length", len(pasted))
        try:
            n_p, e_p = g6_decode(pasted)
            print("   decodes to n =", n_p, "m =", len(e_p))
        except ValueError as ex:
            print("   DECODE ERROR:", ex)
        fixed = pasted[:16] + "_" + pasted[16:54] + "_" + pasted[54:]
        print("   with the two '_' restored (positions 16, 55) == JSON R3+R3 graph6:", fixed == data["R3+R3"]["graph6"])
    else:
        print("== pasted_g6.txt not present; skipping the pasted-string check ==")

    # ---- controls
    print("\n== controls ==")
    P = petersen()
    Rp = analyse("Petersen", P)
    print(summary_line(Rp)); results["Petersen"] = Rp
    for cname, cg in [("K4", Graph(4, [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)])),
                      ("K3,3", Graph(6, [(a, b) for a in range(3) for b in range(3, 6)])),
                      ("Q3", Graph(8, [(a, a ^ (1 << k)) for a in range(8) for k in range(3) if a < a ^ (1 << k)]))]:
        Rc = analyse(cname, cg); print(summary_line(Rc)); results[cname] = Rc

    # ---- the JSON graphs
    print("\n== JSON graphs ==")
    for key, rec in data.items():
        n = rec["n"]
        probs = check_simple(n, rec["edges"])
        n6, e6 = g6_decode(rec["graph6"])
        G = Graph(n, rec["edges"])
        same = (n6 == n and sorted({(min(u,v),max(u,v)) for u,v in e6}) == G.edges)
        reenc = (g6_encode(n, rec["edges"]) == rec["graph6"])
        pivot = [tuple(e) for e in rec["pivot_matching"]]
        R = analyse(key, G, pivot=pivot, K=rec["K"], claimed={"i": rec["i"], "mu": rec["mu"]})
        R["simple_problems"] = probs
        R["graph6_decodes_to_edge_list"] = same
        R["edge_list_reencodes_to_graph6"] = reenc
        R["pivot_is_first_15_pairs"] = (pivot == [(2*k, 2*k+1) for k in range(15)])
        # the JSON's own claimed IDS
        ids = rec["ids"]
        R["json_ids_valid"] = is_independent(G, ids) and is_dominating(G, ids)
        R["json_ids_size"] = len(ids)
        print(summary_line(R))
        print(f"    simple={not probs} g6==edges:{same} edges->g6==g6:{reenc} pivot==[(0,1)..(28,29)]:{R['pivot_is_first_15_pairs']} "
              f"json ids valid={R['json_ids_valid']} (size {len(ids)}) claimed i={rec['i']} mu={rec['mu']}")
        results[key] = R

    # ---- method-agreement sweep on random connected cubic graphs
    print("\n== random cubic agreement sweep ==")
    rng = random.Random(2026)
    disagreements = 0; tot = 0
    for trial in range(30):
        n = rng.choice([20, 24, 30, 36])
        G = random_cubic(n, rng)
        v_cbc, _ = ilp_ids_cbc(G)
        v_bb, _, _ = min_ids_bb(G.n, G.cnb)
        u1, _ = sat_ids_atmost(G, v_bb - 1); u2, _ = sat_ids_atmost(G, v_bb)
        v_mu, _ = ilp_mmm_cbc(G)
        LG, E = line_graph(G)
        v_mul, _, _ = min_ids_bb(LG.n, LG.cnb)
        tot += 1
        if not (v_cbc == v_bb and (not u1) and u2 and v_mu == v_mul):
            disagreements += 1
            print("   DISAGREEMENT on", g6_encode(G.n, G.edges), v_cbc, v_bb, u1, u2, v_mu, v_mul)
    print(f"   {tot} random connected cubic graphs (n in 20..36): {tot - disagreements} full agreements, {disagreements} disagreements")
    results["random_sweep"] = {"graphs": tot, "disagreements": disagreements}

    json.dump(results, open("results.json", "w"), indent=1)
    print("\nwrote results.json")
