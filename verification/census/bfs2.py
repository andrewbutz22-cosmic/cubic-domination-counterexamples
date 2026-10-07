"""BFS over UNSAT tight formulas under 2-swap adjacency. State in bfs_state.json."""
import json, time, sys, os
from tight import *
from sa import valid_swap, swap_energy, clause_masks, apply_swap, cm_of, NSLOT, M

def slots_of(K): return [l for cl in K for l in cl]

def dist2_fast(slots):
    found = {}
    cms = clause_masks(slots)
    pairs = [(s, t) for s in range(NSLOT) for t in range(s+1, NSLOT) if valid_swap(slots, s, t)]
    for (s, t) in pairs:
        e1, ns, nt = swap_energy(slots, cms, s, t)
        if e1 == 0:
            K1 = list(slots); K1[s], K1[t] = K1[t], K1[s]
            K1 = [K1[3*i:3*i+3] for i in range(M)]
            found[canon_key(K1)] = K1
            continue
        sl = list(slots); cm = list(cms)
        apply_swap(sl, cm, s, t, ns, nt)
        # models of the intermediate
        m1 = FULL
        for c in cm: m1 &= c
        cs, ct = s // 3, t // 3
        for u in range(NSLOT):
            cu = u // 3
            for w in range(u+1, NSLOT):
                cw = w // 3
                if cu == cw: continue
                disjoint = cu != cs and cu != ct and cw != cs and cw != ct
                if disjoint and (u, w) < (s, t):
                    continue  # commuting pair, counted once
                if not valid_swap(sl, u, w): continue
                # cheap necessary test: every intermediate model must be killed by a new clause
                sl[u], sl[w] = sl[w], sl[u]
                nu, nw = cm_of(sl, cu), cm_of(sl, cw)
                sl[u], sl[w] = sl[w], sl[u]
                if m1 & nu & nw:
                    continue
                e2, _, _ = swap_energy(sl, cm, u, w)
                if e2 == 0:
                    sl2 = list(sl); sl2[u], sl2[w] = sl2[w], sl2[u]
                    K2 = [sl2[3*i:3*i+3] for i in range(M)]
                    found[canon_key(K2)] = K2
    return found

if __name__ == "__main__":
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 240
    census = json.load(open('census.json'))
    st = json.load(open('bfs_state.json')) if os.path.exists('bfs_state.json') else {"done": [], "frontier": {}, "K": {}}
    done = set(st["done"])
    frontier = st["frontier"]          # cert -> K for classes not yet expanded
    allK = st.get("K", {})             # cert -> K for every class discovered
    for k, c in census.items():
        allK.setdefault(k, c["K"])
        if k not in done and k not in frontier:
            frontier[k] = c["K"]
    for k, K in frontier.items():
        allK.setdefault(k, K)
    t0 = time.time(); expanded = 0; newc = 0
    while frontier and time.time() - t0 < budget:
        k, K = next(iter(frontier.items()))
        nb = dist2_fast(slots_of(K))
        for k2, K2 in nb.items():
            if k2 not in allK:
                allK[k2] = canonical_formula(K2); newc += 1
            if k2 not in done and k2 not in frontier:
                frontier[k2] = allK[k2]
        del frontier[k]; done.add(k); expanded += 1
        json.dump({"done": sorted(done), "frontier": frontier, "K": allK}, open('bfs_state.json', 'w'))
    print(json.dumps({"expanded": expanded, "new_classes": newc, "done": len(done), "frontier": len(frontier), "total_known": len(allK),
                      "elapsed": round(time.time()-t0), "s_per_class": round((time.time()-t0)/max(1,expanded), 1)}))
