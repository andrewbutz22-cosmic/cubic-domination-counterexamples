import json, time, networkx as nx
from tight import *
d = json.load(open('counterexamples.json'))
certs = {}
for name, g in d.items():
    K = g['K']
    t = time.time()
    assert is_tight(K)
    r = analyze(K, sat_check=True)
    # cross-check graph against posted edge list
    G = incidence_graph(K)
    E = set(tuple(sorted(e)) for e in g['edges'])
    assert E == set(map(lambda e: tuple(sorted(e)), G.edges())), name
    mm, _ = min_maximal_matching(G)
    ok = (r['gamma'], r['i'], mm) == (g['gamma'], g['i'], g['mu'])
    certs[name] = r['cert']
    print(f"{name:6s} gamma={r['gamma']} i={r['i']} mu*={mm} models={r['models']} MU={r['mu']} "
          f"cut={list(r['cut_variables'].keys())} sides={r['cut_variables'].get(15)} "
          f"sat_g={r['sat_gamma_gt_%d'%(r['gamma']-1)]} sat_i={r['sat_i_gt_%d'%(r['i']-1)]} "
          f"{'OK' if ok else 'MISMATCH'} {time.time()-t:.1f}s")
print('distinct certificates:', len(set(certs.values())), 'of', len(certs))
json.dump(certs, open('control_certs.json','w'), indent=1)
