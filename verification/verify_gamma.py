#!/usr/bin/env python3
"""
Domination number gamma(G) = min |S| with N[S] = V (no independence requirement), from the definition.

Engines (none seeded with another's answer):
  (a)  ILP: min sum x_v, x_v + sum_{u in N(v)} x_u >= 1  -- CBC (pulp) and HiGHS (scipy.optimize.milp),
       plus an explicit CBC feasibility run with sum x_v <= gamma-1
  (b)  own bitset branch-and-bound: branch on an undominated vertex with the fewest allowed dominators,
       lower bounds = ceil(#undominated / max new coverage)  and  a greedy packing of undominated vertices
       whose allowed-dominator sets are pairwise disjoint (each chosen vertex dominates at most one of them)
  (c)  SAT (CaDiCaL via pysat): domination clauses + sequential-counter cardinality <= k
  (d)  structural enumeration for the JSON graphs: all 2^20 clause-side subsets C, then an exact
       hitting-set search for the literal-side part (pairs not fully dominated by C + clauses outside C)
Every witness is re-checked with is_dominating().
"""
import json, sys, time, random
from verify_ids import (Graph, g6_decode, g6_encode, degrees, is_connected, is_dominating,
                        petersen, random_cubic, bits_to_list)

# ----------------------------------------------------------------------------- (b) branch and bound
def min_ds_bb(n, cnb, ub=None):
    full = (1 << n) - 1
    best = [(n if ub is None else ub) + 1, None]
    nodes = [0]
    sys.setrecursionlimit(10000)

    def rec(S, F, D, k):
        nodes[0] += 1
        if D == full:
            if k < best[0]:
                best[0], best[1] = k, S
            return
        if k + 1 >= best[0]:
            return
        und = full & ~D
        allowed = full & ~F
        # allowed dominators of every undominated vertex; pick the least flexible one to branch on
        lst = []
        it = und
        while it:
            low = it & -it; it ^= low
            v = low.bit_length() - 1
            c = cnb[v] & allowed
            cnt = c.bit_count()
            if cnt == 0:
                return                          # v can no longer be dominated
            lst.append((cnt, c))
        lst.sort(key=lambda t: t[0])
        bv_c = lst[0][1]
        # bound 1: coverage
        maxcov = 0
        it = allowed
        while it:
            low = it & -it; it ^= low
            u = low.bit_length() - 1
            cov = (cnb[u] & und).bit_count()
            if cov > maxcov:
                maxcov = cov
        if k + (-(-und.bit_count() // maxcov)) >= best[0]:
            return
        # bound 2: greedy packing (disjoint allowed-dominator sets)
        used = 0; pack = 0
        for cnt, c in lst:
            if c & used == 0:
                used |= c; pack += 1
        if k + pack >= best[0]:
            return
        # branch on the dominators of the least flexible undominated vertex, best coverage first
        cands = []
        c = bv_c
        while c:
            low = c & -c; c ^= low
            u = low.bit_length() - 1
            cands.append(((cnb[u] & und).bit_count(), u))
        cands.sort(reverse=True)
        Fl = F
        for _, u in cands:
            rec(S | (1 << u), Fl, D | cnb[u], k + 1)
            Fl |= (1 << u)                      # later branches: u is not in S

    rec(0, 0, 0, 0)
    return best[0], best[1], nodes[0]

# ----------------------------------------------------------------------------- (a) ILP
def ilp_ds_cbc(G, atmost=None):
    import pulp
    prob = pulp.LpProblem("ds", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x{v}", cat="Binary") for v in range(G.n)]
    prob += pulp.lpSum(x)
    for v in range(G.n):
        prob += x[v] + pulp.lpSum(x[u] for u in G.adj[v]) >= 1
    if atmost is not None:
        prob += pulp.lpSum(x) <= atmost
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
    st = pulp.LpStatus[status]
    if atmost is not None:
        return st, None
    assert st == "Optimal", st
    S = [v for v in range(G.n) if x[v].value() > 0.5]
    return int(round(pulp.value(prob.objective))), S

def ilp_ds_highs(G):
    import numpy as np
    from scipy.optimize import milp, LinearConstraint, Bounds
    n = G.n
    A = np.zeros((n, n))
    for v in range(n):
        A[v, v] = 1
        for u in G.adj[v]:
            A[v, u] = 1
    res = milp(c=np.ones(n), constraints=LinearConstraint(A, np.ones(n), np.full(n, np.inf)),
               integrality=np.ones(n), bounds=Bounds(0, 1))
    assert res.status == 0, res.message
    S = [v for v in range(n) if res.x[v] > 0.5]
    return int(round(res.fun)), S

# ----------------------------------------------------------------------------- (c) SAT
def sat_ds_atmost(G, k, solver_name="cadical153"):
    from pysat.card import CardEnc, EncType
    from pysat.solvers import Solver
    n = G.n
    clauses = [[v + 1] + [u + 1 for u in G.adj[v]] for v in range(n)]
    card = CardEnc.atmost(lits=list(range(1, n + 1)), bound=k, top_id=n, encoding=EncType.seqcounter)
    clauses.extend(card.clauses)
    with Solver(name=solver_name, bootstrap_with=clauses) as s:
        ok = s.solve()
        if ok:
            model = set(l for l in s.get_model() if l > 0)
            return True, [v for v in range(n) if (v + 1) in model]
        return False, None

# ----------------------------------------------------------------------------- (d) structural enumeration
def hitting_set_min(sets, budget):
    """Smallest set of elements (bit positions) hitting every set in `sets` (bitmasks), if it has size
    <= budget; returns (size, mask) or (None, None).  Branch on the smallest unhit set; greedy disjoint
    packing as the lower bound."""
    best = [budget + 1, None]

    def rec(H, F, k):
        unhit = [s for s in sets if s & H == 0]
        if not unhit:
            if k < best[0]:
                best[0], best[1] = k, H
            return
        if k + 1 >= best[0]:
            return
        av = []
        for s in unhit:
            c = s & ~F
            if c == 0:
                return
            av.append((c.bit_count(), c))
        av.sort(key=lambda t: t[0])
        used = 0; pack = 0
        for _, c in av:
            if c & used == 0:
                used |= c; pack += 1
        if k + pack >= best[0]:
            return
        c = av[0][1]
        Fl = F
        while c:
            low = c & -c; c ^= low
            rec(H | low, Fl, k + 1)
            Fl |= low

    rec(0, 0, 0)
    return (best[0], best[1]) if best[1] is not None else (None, None)

def structural_gamma(G, cap):
    """Exact gamma for the literal/clause graphs, restricted to sets of size <= cap; returns (gamma or None, witness, seconds).
    Premises verified: vertices 30..49 pairwise non-adjacent; vertex 2k adjacent to 2k+1, all other
    neighbours of 2k, 2k+1 are >= 30."""
    n = G.n; nb = G.nb
    assert n == 50
    LIT = (1 << 30) - 1
    CL = ((1 << 50) - 1) ^ LIT
    for c in range(30, 50):
        assert nb[c] & CL == 0
    for k in range(15):
        a, b = 2 * k, 2 * k + 1
        assert (nb[a] & LIT) == (1 << b) and (nb[b] & LIT) == (1 << a)
    EVEN = sum(1 << (2 * k) for k in range(15))
    cl_nb_lit = [nb[30 + j] & LIT for j in range(20)]
    t0 = time.time()
    NC = [0] * (1 << 20)
    for C in range(1, 1 << 20):
        low = C & -C
        NC[C] = NC[C ^ low] | cl_nb_lit[low.bit_length() - 1]
    best = cap + 1; wit = None
    for C in range(1 << 20):
        nc = NC[C]
        e = nc & EVEN
        o = (nc >> 1) & EVEN
        fullpairs = (e & o).bit_count()
        csize = bin(C).count("1")
        lb = csize + 15 - fullpairs            # every pair not fully dominated by C needs a literal vertex
        if lb >= best:
            continue
        sets = []
        pp = EVEN & ~(e & o)
        while pp:
            low = pp & -pp; pp ^= low
            sets.append(low | (low << 1))        # {2k, 2k+1}
        for j in range(20):
            if not (C >> j) & 1:
                sets.append(cl_nb_lit[j])       # clause j must be dominated by a literal vertex
        size, H = hitting_set_min(sets, best - 1 - csize)
        if size is not None and csize + size < best:
            best = csize + size
            wit = sorted(bits_to_list(H) + [30 + j for j in range(20) if (C >> j) & 1])
    return (best if wit is not None else None), wit, time.time() - t0

# ----------------------------------------------------------------------------- battery
def analyse_gamma(name, G, structural=False, cap=None):
    R = {"name": name, "n": G.n, "m": len(G.edges), "degrees": sorted(set(degrees(G))), "connected": is_connected(G)}
    t = time.time(); g_cbc, S_cbc = ilp_ds_cbc(G); R["gamma_ilp_cbc"] = g_cbc; R["t_ilp_cbc"] = time.time() - t
    assert is_dominating(G, S_cbc) and len(S_cbc) == g_cbc
    t = time.time(); R["cbc_feasible_at_minus1"], _ = ilp_ds_cbc(G, atmost=g_cbc - 1); R["t_ilp_cbc_feas"] = time.time() - t
    t = time.time(); g_h, S_h = ilp_ds_highs(G); R["gamma_ilp_highs"] = g_h; R["t_ilp_highs"] = time.time() - t
    assert is_dominating(G, S_h) and len(S_h) == g_h
    t = time.time(); g_bb, S_bb, nodes = min_ds_bb(G.n, G.cnb); R["gamma_bb"] = g_bb; R["t_bb"] = time.time() - t; R["bb_nodes"] = nodes
    S_bb = bits_to_list(S_bb)
    assert is_dominating(G, S_bb) and len(S_bb) == g_bb
    R["bb_witness"] = S_bb
    t = time.time()
    u1, _ = sat_ds_atmost(G, g_bb - 1); u2, S_sat = sat_ds_atmost(G, g_bb)
    R["t_sat"] = time.time() - t
    R["sat_atmost_gamma_minus_1"] = "SAT" if u1 else "UNSAT"
    R["sat_atmost_gamma"] = "SAT" if u2 else "UNSAT"
    if u2:
        assert is_dominating(G, S_sat) and len(S_sat) <= g_bb
    if structural:
        g_s, S_s, dt = structural_gamma(G, cap if cap is not None else g_bb)
        R["gamma_structural"] = g_s; R["t_structural"] = dt
        if S_s is not None:
            assert is_dominating(G, S_s) and len(S_s) == g_s
            R["structural_witness"] = S_s
    return R

def line(R):
    s = (f"{R['name']:8s} n={R['n']} deg={R['degrees']} conn={R['connected']}  gamma: CBC={R['gamma_ilp_cbc']} "
         f"(feasible at {R['gamma_ilp_cbc']-1}: {R['cbc_feasible_at_minus1']}) HiGHS={R['gamma_ilp_highs']} "
         f"B&B={R['gamma_bb']} (nodes {R['bb_nodes']}) SAT<=g-1:{R['sat_atmost_gamma_minus_1']} SAT<=g:{R['sat_atmost_gamma']}")
    if "gamma_structural" in R:
        s += f" structural={R['gamma_structural']}"
    s += (f"\n         times: cbc={R['t_ilp_cbc']:.2f}s cbc-feas={R['t_ilp_cbc_feas']:.2f}s highs={R['t_ilp_highs']:.2f}s "
          f"bb={R['t_bb']:.2f}s sat={R['t_sat']:.2f}s")
    if "t_structural" in R:
        s += f" structural={R['t_structural']:.1f}s"
    return s

if __name__ == "__main__":
    data = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "counterexamples.json"))
    results = {}
    print("== controls ==")
    for cname, cg in [("Petersen", petersen()),
                      ("K4", Graph(4, [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)])),
                      ("K3,3", Graph(6, [(a, b) for a in range(3) for b in range(3, 6)])),
                      ("Q3", Graph(8, [(a, a ^ (1 << k)) for a in range(8) for k in range(3) if a < a ^ (1 << k)]))]:
        R = analyse_gamma(cname, cg); print(line(R)); results[cname] = R

    print("\n== brute-force validation of the gamma engines (all 2^n subsets) ==")
    rng = random.Random(99); bad = 0; cnt = 0; t0 = time.time()
    for trial in range(12):
        n = rng.choice([12, 14, 16, 18, 20])
        G = random_cubic(n, rng); full = (1 << n) - 1; best = n
        for S in range(1 << n):
            if bin(S).count("1") >= best:
                continue
            D = 0; m = S
            while m:
                low = m & -m; m ^= low; D |= G.cnb[low.bit_length() - 1]
            if D == full:
                best = bin(S).count("1")
        g_bb, _, _ = min_ds_bb(G.n, G.cnb); g_c, _ = ilp_ds_cbc(G); g_h, _ = ilp_ds_highs(G)
        u1, _ = sat_ds_atmost(G, best - 1); u2, _ = sat_ds_atmost(G, best)
        cnt += 1
        if not (best == g_bb == g_c == g_h and (not u1) and u2):
            bad += 1; print("   MISMATCH", g6_encode(n, G.edges), best, g_bb, g_c, g_h, u1, u2)
    print(f"   {cnt} graphs (n<=20), {bad} mismatches, {time.time()-t0:.1f}s")

    print("\n== random connected cubic agreement sweep (n=20..36) ==")
    rng = random.Random(2027); bad = 0; cnt = 0; t0 = time.time()
    for trial in range(30):
        n = rng.choice([20, 24, 30, 36]); G = random_cubic(n, rng)
        g_bb, _, _ = min_ds_bb(G.n, G.cnb); g_c, _ = ilp_ds_cbc(G); g_h, _ = ilp_ds_highs(G)
        u1, _ = sat_ds_atmost(G, g_bb - 1); u2, _ = sat_ds_atmost(G, g_bb)
        cnt += 1
        if not (g_bb == g_c == g_h and (not u1) and u2):
            bad += 1; print("   DISAGREEMENT", g6_encode(n, G.edges), g_bb, g_c, g_h, u1, u2)
    print(f"   {cnt} graphs, {bad} disagreements, {time.time()-t0:.1f}s")
    results["validation"] = {"brute_force_mismatches": bad, "sweep_disagreements": bad}

    print("\n== JSON graphs ==")
    order = ["R6+R6", "R6+R7", "R7+R7", "R3+R3", "R3+R6", "R3+R7", "R0+R0"]
    for key in order:
        rec = data[key]
        G = Graph(rec["n"], rec["edges"])
        R = analyse_gamma(key, G, structural=True)
        R["requested"] = key in ("R6+R6", "R6+R7", "R7+R7")
        print(line(R)); print("         witness:", R["bb_witness"])
        results[key] = R
    json.dump(results, open("results_gamma.json", "w"), indent=1)
    print("\nwrote results_gamma.json")
