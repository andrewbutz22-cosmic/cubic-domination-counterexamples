import json, time, sys
from tight import *
def aut_order(G):
    from pynauty import Graph as NGraph, autgrp
    n = G.number_of_nodes()
    gens, s1, s2, orbits, norb = autgrp(NGraph(n, directed=False, adjacency_dict={u: list(G.neighbors(u)) for u in range(n)}))
    return int(round(s1 * 10 ** s2))
budget = float(sys.argv[1]) if len(sys.argv) > 1 else 240
census = json.load(open('census.json'))
st = json.load(open('bfs_state.json'))
t0 = time.time(); n = 0
for cert, K in st["K"].items():
    if cert in census: continue
    if time.time() - t0 > budget: break
    assert is_tight(K) and canon_key(K) == cert
    r = analyze(K, sat_check=True)
    assert r["mu"] and r["models"] == 0
    g, i = r["gamma"], r["i"]
    assert r["sat_gamma_gt_%d" % (g-1)] and r["sat_i_gt_%d" % (i-1)], "ILP/SAT disagree"
    G = incidence_graph(K)
    census[cert] = {"K": canonical_formula(K), "gamma": g, "i": i, "mu_star": 15, "glue_free": r["glue_free"],
        "cut_variables": {str(k): v for k, v in r["cut_variables"].items()}, "gamma_set": r["gamma_set"], "i_set": r["i_set"],
        "girth": nx.girth(G), "aut": aut_order(G), "control": None, "hits": 0, "first_seen": None, "first_seed": None, "source": "bfs"}
    n += 1
    json.dump(census, open('census.json', 'w'))
remaining = sum(1 for c in st["K"] if c not in census)
print(f"verified {n} new classes in {time.time()-t0:.0f}s; census={len(census)}; remaining={remaining}")
