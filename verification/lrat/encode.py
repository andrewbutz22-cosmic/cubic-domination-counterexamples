#!/usr/bin/env python3
"""encode.py -- write the CNF "G has a (independent) dominating set of size <= k".

Usage:  python3 encode.py GRAPHS.json NAME MODE K OUT.cnf
        MODE = ds   (dominating set)            -> UNSAT  <=>  gamma(G) > K
        MODE = ids  (independent dominating set) -> UNSAT  <=>  i(G)     > K

Reads the graph from the "edges" list of GRAPHS.json (vertices 0..n-1).

Variables
  x(v) = v + 1                          v = 0..n-1   (v is in the set)
  s(i,j) = n + (i-1)*K + j              i = 1..n-1, j = 1..K
           ("at least j of x(0..i-1) are true"; Sinz's sequential counter)
Clauses
  domination   : for every v,  OR_{u in N[v]} x(u)
  independence : for every edge uw (ids only),  -x(u) OR -x(w)
  at most K    : Sinz, "Towards an optimal CNF encoding of Boolean
                 cardinality constraints", CP 2005 (LT_SEQ), over x(0..n-1)

A sidecar OUT.ext.json records, for every auxiliary variable, the pair (i,j).
It is consumed by audit_cnf.py, which does NOT trust this file or this script:
it re-derives the soundness of the CNF from the CNF itself (see audit_cnf.py).
"""
import json, sys


def sinz_atmost(xs, k, first_aux):
    """Sinz LT_SEQ clauses for sum(xs) <= k. Returns (clauses, auxmap, next_var)."""
    n = len(xs)
    assert n >= 2 and 1 <= k < n
    s = {}
    v = first_aux
    for i in range(1, n):
        for j in range(1, k + 1):
            s[(i, j)] = v
            v += 1
    cl = []
    X = lambda i: xs[i - 1]          # 1-based x
    cl.append([-X(1), s[(1, 1)]])
    for j in range(2, k + 1):
        cl.append([-s[(1, j)]])
    for i in range(2, n):
        cl.append([-X(i), s[(i, 1)]])
        cl.append([-s[(i - 1, 1)], s[(i, 1)]])
        for j in range(2, k + 1):
            cl.append([-X(i), -s[(i - 1, j - 1)], s[(i, j)]])
            cl.append([-s[(i - 1, j)], s[(i, j)]])
        cl.append([-X(i), -s[(i - 1, k)]])
    cl.append([-X(n), -s[(n - 1, k)]])
    auxmap = {var: [i, j] for (i, j), var in s.items()}
    return cl, auxmap, v


def main():
    path, name, mode, k, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
    assert mode in ("ds", "ids")
    g = json.load(open(path))[name]
    n = g["n"]
    adj = {v: set() for v in range(n)}
    for a, b in g["edges"]:
        assert a != b
        adj[a].add(b); adj[b].add(a)
    x = lambda v: v + 1
    clauses = []
    for v in range(n):
        clauses.append(sorted(x(u) for u in adj[v] | {v}))
    if mode == "ids":
        for a, b in sorted({tuple(sorted(e)) for e in g["edges"]}):
            clauses.append([-x(a), -x(b)])
    card, auxmap, nxt = sinz_atmost([x(v) for v in range(n)], k, n + 1)
    clauses += card
    nvars = nxt - 1
    with open(out, "w") as f:
        f.write(f"c {name} {mode} at-most-{k}: x(v)=v+1 for v=0..{n-1}; aux = Sinz sequential counter\n")
        f.write(f"p cnf {nvars} {len(clauses)}\n")
        for c in clauses:
            f.write(" ".join(map(str, c)) + " 0\n")
    side = {"graph": name, "mode": mode, "k": k, "n": n,
            "x_var_of_vertex": "v+1",
            "aux": {str(var): ij for var, ij in sorted(auxmap.items())}}
    with open(out[:-4] + ".ext.json", "w") as f:
        json.dump(side, f, indent=0)


if __name__ == "__main__":
    main()
