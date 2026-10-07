"""Exhaustive 3-swap closure test around census formula #index.

Path F -> F1 -> F2 -> F3 of valid swaps. For every F2 (all valid 2-swap sequences, disjoint pairs once),
decide whether some valid swap (p,q) makes F3 UNSAT:
  model alpha of F2 is killed by the rewritten clause of p  iff  clause(p) is critical at p under alpha
  (p is its unique true literal) and the incoming literal l_q is false under alpha; the two clause events
  are disjoint, so  count(p,q) = (A^T Fneg)[p,q] + (A^T Fneg)[q,p]  must equal |m2| -- computed for all
  pairs at once by one 60x60 matrix product. Survivors get the exact bitset test. Also records the
  1- and 2-swap UNSAT endpoints and checks they are in the census.

Usage: python3 closure3b.py <census.json> <index> [budget_s]     (resumable via closure3b_state_<index>.json)
"""
import json, sys, time, os
import numpy as np
from tight import LIT_MASK as LM, FULL, M, canon_key, canonical_formula, is_tight, models
from sa import valid_swap, swap_energy, clause_masks, apply_swap, cm_of, NSLOT

NB = (1 << 15) // 8


def model_indices(m):
    bits = np.unpackbits(np.frombuffer(m.to_bytes(NB, "little"), dtype=np.uint8), bitorder="little")
    return np.flatnonzero(bits)


def third_swap_candidates(sl, m2):
    """Pairs (p,q), p<q, whose rewritten clauses kill every model of F2 (necessary condition)."""
    idx = model_indices(m2)
    n = len(idx)
    varidx = np.array([abs(l) - 1 for l in sl], dtype=np.int64)
    negf = np.array([l < 0 for l in sl])
    truth = ((idx[:, None] >> np.arange(15)[None, :]) & 1).astype(bool)      # n x 15
    LT = truth[:, varidx] ^ negf[None, :]                                    # n x 60 literal true
    cnt = LT.reshape(n, M, 3).sum(axis=2)                                    # n x 20 true literals per clause
    crit = np.repeat(cnt == 1, 3, axis=1)                                    # n x 60
    A = (LT & crit).astype(np.float32)
    Fn = (~LT).astype(np.float32)
    G = A.T @ Fn                                                             # 60 x 60
    C = G + G.T
    P, Q = np.nonzero(np.triu(C == n, 1))
    return list(zip(P.tolist(), Q.tolist()))


def run(index, path, budget):
    census = json.load(open(path))
    keys = list(census)
    key = keys[index]
    F = census[key]["K"]
    slots0 = [l for cl in F for l in cl]
    cms0 = clause_masks(slots0)
    st_path = f"closure3b_state_{index}.json"
    st = json.load(open(st_path)) if os.path.exists(st_path) else {
        "next_s": 0, "next_t": 1, "F1": 0, "F1_unsat": 0, "F2": 0, "F2_unsat": 0, "cand": 0, "F3_unsat": 0,
        "unsat_certs": {}, "outside": {}, "done": False, "elapsed": 0.0}
    t0 = time.time()
    unsat_certs = st["unsat_certs"]
    outside = st["outside"]

    def record(K, dist):
        K = [list(K[3 * c:3 * c + 3]) for c in range(M)]
        assert is_tight(K)
        cert = canon_key(K)
        unsat_certs[cert] = min(unsat_certs.get(cert, 9), dist)
        if cert not in census:
            outside[cert] = {"dist": dist, "K": canonical_formula(K)}

    s, t = st["next_s"], st["next_t"]
    while s < NSLOT:
        while t < NSLOT:
            if time.time() - t0 > budget:
                st.update(next_s=s, next_t=t, elapsed=st["elapsed"] + time.time() - t0)
                json.dump(st, open(st_path, "w"))
                return st
            if valid_swap(slots0, s, t):
                e1, ns, nt = swap_energy(slots0, cms0, s, t)
                sl1 = list(slots0); cm1 = list(cms0); apply_swap(sl1, cm1, s, t, ns, nt)
                st["F1"] += 1
                if e1 == 0:
                    st["F1_unsat"] += 1
                    record(sl1, 1)
                else:
                    for u in range(NSLOT):
                        for w in range(u + 1, NSLOT):
                            disjoint = len({s, t, u, w}) == 4
                            if disjoint and (u, w) < (s, t):
                                continue                 # commuting pair counted once
                            if (u, w) == (s, t) or not valid_swap(sl1, u, w):
                                continue
                            e2, nu, nw = swap_energy(sl1, cm1, u, w)
                            st["F2"] += 1
                            if e2 == 0:
                                sl2 = list(sl1); sl2[u], sl2[w] = sl2[w], sl2[u]
                                st["F2_unsat"] += 1
                                record(sl2, 2)
                                continue
                            sl2 = list(sl1); cm2 = list(cm1); apply_swap(sl2, cm2, u, w, nu, nw)
                            m2 = FULL
                            for c in cm2:
                                m2 &= c
                            for p, q in third_swap_candidates(sl2, m2):
                                if p // 3 == q // 3 or not valid_swap(sl2, p, q):
                                    continue
                                st["cand"] += 1
                                e3, _, _ = swap_energy(sl2, cm2, p, q)
                                if e3 == 0:
                                    sl3 = list(sl2); sl3[p], sl3[q] = sl3[q], sl3[p]
                                    st["F3_unsat"] += 1
                                    record(sl3, 3)
            t += 1
        s += 1; t = s + 1
    st.update(next_s=s, next_t=t, done=True, elapsed=st["elapsed"] + time.time() - t0)
    json.dump(st, open(st_path, "w"))
    return st


if __name__ == "__main__":
    path, index = sys.argv[1], int(sys.argv[2])
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 250
    st = run(index, path, budget)
    summary = {k: v for k, v in st.items() if k not in ("unsat_certs", "outside")}
    summary["index"] = index
    summary["distinct_unsat_classes_reached"] = len(st["unsat_certs"])
    summary["classes_outside_census"] = len(st["outside"])
    print(json.dumps(summary))
    if st["done"]:
        open("closure3b_results.jsonl", "a").write(json.dumps({**summary, "outside": st["outside"]}) + "\n")
