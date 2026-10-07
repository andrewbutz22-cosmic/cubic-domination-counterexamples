import json, itertools, collections
from tight import *
blocks = json.load(open('blocks710.json'))
def glue(A, B):
    K = []
    for cl in A:
        K.append(list(cl) + ([15] if len(cl) == 2 else []))
    for cl in B:
        cl2 = [ (l + 7 if l > 0 else l - 7) for l in cl ]
        K.append(cl2 + ([-15] if len(cl) == 2 else []))
    return K
posted = json.load(open('counterexamples.json'))
assert canonical_formula(glue(blocks[6], blocks[6])) == canonical_formula(posted['R6+R6']['K'])
census = json.load(open('census.json'))
rows = []
seen = {}
for a in range(8):
    for b in range(a, 8):
        K = glue(blocks[a], blocks[b])
        assert is_tight(K) and is_mu(K)
        cert = canon_key(K)
        if cert in seen:
            print('ISO DUPLICATE', (a,b), seen[cert]); continue
        seen[cert] = (a, b)
        r = analyze(K, sat_check=True)
        assert r['sat_gamma_gt_%d'%(r['gamma']-1)] and r['sat_i_gt_%d'%(r['i']-1)]
        rows.append((a, b, r['gamma'], r['i'], list(r['cut_variables'].keys()), cert in census))
        if cert not in census:
            G = incidence_graph(K)
            from tally import aut_order
            census[cert] = {"K": canonical_formula(K), "gamma": r['gamma'], "i": r['i'], "mu_star": 15,
                "glue_free": False, "cut_variables": {str(k): v for k, v in r['cut_variables'].items()},
                "gamma_set": r['gamma_set'], "i_set": r['i_set'], "girth": nx.girth(G), "aut": aut_order(G),
                "control": None, "hits": 0, "first_seen": None, "first_seed": None, "constructed": f"R{a}+R{b}"}
        else:
            census[cert]["constructed"] = f"R{a}+R{b}"
json.dump(census, open('census.json', 'w'))
print('distinct gluing classes:', len(seen))
print('i distribution:', collections.Counter(r[3] for r in rows), ' gamma:', collections.Counter(r[2] for r in rows))
print('already hit by SA:', sum(r[5] for r in rows))
print('cut variables per gluing (all should be [15] only):', set(tuple(r[4]) for r in rows))
sa_cut = [c for c in census.values() if not c['glue_free'] and c['hits'] > 0]
print('SA cut-variable classes:', len(sa_cut), 'all among gluings:', all('constructed' in c for c in sa_cut))
print('census total now:', len(census))
