"""Re-verify every class from scratch and write census_v2.json in the counterexamples.json conventions.
Resumable: skips classes already present in census_v2.json. Usage: python3 finalize.py [budget_seconds]"""
import json, os, sys, time, hashlib
import networkx as nx
from tight import *
from sa import valid_swap, swap_energy, clause_masks, NSLOT

budget = float(sys.argv[1]) if len(sys.argv) > 1 else 230
census = json.load(open("census.json"))
OUT = "census_v2.json"
final = json.load(open(OUT)) if os.path.exists(OUT) else {}
posted = json.load(open("counterexamples.json"))
posted_by_cert = {canon_key(v["K"]): k for k, v in posted.items()}


def aut_order(G):
    from pynauty import Graph as NGraph, autgrp
    n = G.number_of_nodes()
    gens, s1, s2, orbits, norb = autgrp(NGraph(n, directed=False, adjacency_dict={u: list(G.neighbors(u)) for u in range(n)}))
    return int(round(s1 * 10 ** s2))


def one_swap_unsat_neighbors(K):
    slots = [l for cl in K for l in cl]
    cms = clause_masks(slots)
    out = set()
    for s in range(NSLOT):
        for t in range(s + 1, NSLOT):
            if valid_swap(slots, s, t):
                e, _, _ = swap_energy(slots, cms, s, t)
                if e == 0:
                    K1 = list(slots); K1[s], K1[t] = K1[t], K1[s]
                    out.add(canon_key([K1[3 * i:3 * i + 3] for i in range(20)]))
    return out


t0 = time.time(); n = 0
for cert, c in census.items():
    if cert in final:
        continue
    if time.time() - t0 > budget:
        break
    K = [list(cl) for cl in c["K"]]
    assert is_tight(K), cert
    assert models(K) == 0 and is_mu(K), cert
    assert canon_key(K) == cert, cert
    G = incidence_graph(K)
    assert G.number_of_nodes() == 50 and G.number_of_edges() == 75 and all(d == 3 for _, d in G.degree())
    assert nx.is_connected(G)
    g, Sg = domination_number(G, independent=False)
    i, Si = domination_number(G, independent=True)
    assert check_dominating(G, Sg) and check_dominating(G, Si) and check_independent(G, Si)
    assert sat_no_domset_at_most(G, g - 1, independent=False), ("gamma lower bound", cert)
    assert sat_no_domset_at_most(G, i - 1, independent=True), ("i lower bound", cert)
    mm, Mset = min_maximal_matching(G)
    assert mm == 15
    cut = cut_variables(K)
    nb1 = one_swap_unsat_neighbors(K)
    final[cert] = {
        "K": canonical_formula(K), "n": 50,
        "edges": sorted(tuple(sorted(e)) for e in G.edges()),
        "pivot_matching": [[2 * k, 2 * k + 1] for k in range(15)],
        "gamma": g, "gamma_set": sorted(Sg), "i": i, "ids": sorted(Si), "mu": mm, "mmm": sorted(map(list, Mset)),
        "graph6": nx.to_graph6_bytes(G, header=False).decode().strip(),
        "certificate_sha256": hashlib.sha256(bytes.fromhex(cert)).hexdigest(),
        "cut_variables": {str(k): v for k, v in cut.items()}, "glue_free": len(cut) == 0,
        "constructed": c.get("constructed"), "posted_name": posted_by_cert.get(cert),
        "girth": nx.girth(G), "aut_order": aut_order(G),
        "one_swap_unsat_neighbors": sorted(hashlib.sha256(bytes.fromhex(x)).hexdigest() for x in nb1),
        "discovered_by": "gluing" if c.get("constructed") else ("bfs" if c.get("source") == "bfs" else "sa"),
    }
    n += 1
    json.dump(final, open(OUT, "w"))
print(f"verified {n} classes in {time.time()-t0:.0f}s; finalized {len(final)} of {len(census)}")
