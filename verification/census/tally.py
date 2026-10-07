import json, os, sys, time, collections
from tight import analyze, canon_key, incidence_graph
import networkx as nx

HITS = sys.argv[1] if len(sys.argv) > 1 else "hits.jsonl"
CENSUS = "census.json"
census = json.load(open(CENSUS)) if os.path.exists(CENSUS) else {}
controls = json.load(open("control_certs.json"))
ctrl_by_cert = {v: k for k, v in controls.items()}

hits = []
for l in open(HITS):
    try:
        if l.strip(): hits.append(json.loads(l))
    except json.JSONDecodeError:
        pass  # partial last line while SA is writing
by_cert = collections.defaultdict(list)
for h in hits:
    by_cert[h["cert"]].append(h)

def aut_order(G):
    from pynauty import Graph as NGraph, autgrp
    n = G.number_of_nodes()
    gens, s1, s2, orbits, norb = autgrp(NGraph(n, directed=False, adjacency_dict={u: list(G.neighbors(u)) for u in range(n)}))
    return int(round(s1 * 10 ** s2))

t0 = time.time()
new = 0
for cert, c in census.items():
    if c.get("aut") is None:
        c["aut"] = aut_order(incidence_graph(c["K"]))
for cert, hs in by_cert.items():
    if cert in census:
        census[cert]["hits"] = len(hs)
        continue
    K = hs[0]["K"]
    assert canon_key(K) == cert
    r = analyze(K, sat_check=True)
    assert r["cert"] == cert and r["mu"] and r["models"] == 0
    g, i = r["gamma"], r["i"]
    assert r["sat_gamma_gt_%d" % (g - 1)] and r["sat_i_gt_%d" % (i - 1)], "ILP/SAT disagree"
    G = incidence_graph(K)
    census[cert] = {
        "K": K, "gamma": g, "i": i, "mu_star": r["mu_star"],
        "glue_free": r["glue_free"], "cut_variables": {str(k): v for k, v in r["cut_variables"].items()},
        "gamma_set": r["gamma_set"], "i_set": r["i_set"],
        "girth": nx.girth(G), "aut": aut_order(G),
        "control": ctrl_by_cert.get(cert), "hits": len(hs), "first_seen": hs[0]["t"], "first_seed": hs[0]["seed"],
    }
    new += 1
    json.dump(census, open(CENSUS, "w"))

json.dump(census, open(CENSUS, "w"))
n = len(census)
cnt = collections.Counter((c["gamma"], c["i"], c["glue_free"]) for c in census.values())
print(f"hits={len(hits)} classes={n} new_this_pass={new} ({time.time()-t0:.0f}s)")
print("gamma  i  glue_free  classes")
for (g, i, gf), k in sorted(cnt.items()):
    print(f"{g:5d} {i:3d}  {str(gf):9s} {k:5d}")
ce_A = sum(1 for c in census.values() if c["gamma"] > 15)
ce_B = sum(1 for c in census.values() if c["i"] > 15)
gf = sum(1 for c in census.values() if c["glue_free"])
print(f"gamma>15 (refute A): {ce_A}   i>15 (refute B): {ce_B}   glue-free: {gf}   "
      f"controls recovered: {[c['control'] for c in census.values() if c['control']]}")
sides = collections.Counter(tuple(map(tuple, list(c["cut_variables"].values())[0])) for c in census.values() if not c["glue_free"])
print("cut-variable side profiles:", dict(sides))
singletons = sum(1 for c in census.values() if c["hits"] == 1)
auts = collections.Counter(c["aut"] for c in census.values())
print("automorphism group orders:", dict(sorted(auts.items())))
print(f"classes seen once: {singletons} of {n}  (Chao1 lower-bound estimate of total: "
      f"{n + (singletons*(singletons-1))/(2*max(1,sum(1 for c in census.values() if c['hits']==2)+1)):.0f})")
