#!/usr/bin/env python3
"""audit_cnf.py -- independent soundness audit of a domination CNF.

Usage:  python3 audit_cnf.py GRAPHS.json NAME MODE K FILE.cnf FILE.ext.json [CAKE_DUMP.txt]

Shares no code with encode.py.  The graph is decoded from the graph6 string in
GRAPHS.json (encode.py reads the "edges" list instead), and the CNF is read from
disk.  The audit proves, by finite exhaustive checks on the file itself:

  (*) every dominating set S of G with |S| <= K   (MODE=ds), or
      every independent dominating set S with |S| <= K   (MODE=ids)
      gives a satisfying assignment of FILE.cnf, namely
          x-variable v+1 := [v in S]                       (v = 0..n-1)
          aux variable a := [c_i >= j]   where (i,j) is a's entry in FILE.ext.json
                                         and c_i = |S intersect {0,...,i-1}|.

So if FILE.cnf is unsatisfiable (cake_lpr: "s VERIFIED UNSAT"), no such S
exists, i.e. gamma(G) > K (ds) or i(G) > K (ids).  The sidecar is untrusted: it
only proposes the extension; a wrong sidecar can make the audit FAIL, never pass
wrongly.

Clause rules (each clause must satisfy one; anything else is rejected):
  D  no aux variable, and the positive literals contain x(u) for all u in N[v],
     for some vertex v                     -> true for every dominating S
  I  (ids only) no aux variable, and the clause contains -x(u), -x(w) for some
     edge uw                               -> true for every independent S
  W  contains an aux variable: the clause only reads prefix counts c_lo..c_hi
     (hi - lo <= 4); enumerate every c_lo in [0, min(lo,K)] and every bit
     pattern on positions lo+1..hi with c_q <= min(q,K); the clause must be
     true in every enumerated state.  Every set S with |S| <= K produces one of
     the enumerated states, so the clause is true for all of them.

If CAKE_DUMP.txt (the output of `cake_lpr FILE.cnf`, i.e. the formula as the
verified checker parsed it) is given, it must equal the audited clause list
exactly, so the audited formula is the one cake_lpr certified.
"""
import json, sys
from itertools import product


def decode_graph6(s):
    data = [ord(ch) - 63 for ch in s.strip()]
    assert all(0 <= d < 64 for d in data), "bad graph6 character"
    assert data[0] < 63, "only n < 63 supported"
    n = data[0]
    bits = []
    for d in data[1:]:
        bits.extend((d >> t) & 1 for t in range(5, -1, -1))
    need = n * (n - 1) // 2
    assert len(bits) >= need and not any(bits[need:]), "bad graph6 padding"
    E = set()
    k = 0
    for j in range(1, n):
        for i in range(j):
            if bits[k]:
                E.add((i, j))
            k += 1
    return n, E


def parse_dimacs_strict(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    pos = 0
    while pos < len(lines) and lines[pos].startswith("c"):
        pos += 1
    hdr = lines[pos].split(" ")
    if len(hdr) != 4 or hdr[0] != "p" or hdr[1] != "cnf":
        raise ValueError("bad header line: %r" % lines[pos])
    nv, nc = int(hdr[2]), int(hdr[3])
    body = lines[pos + 1:]
    if len(body) != nc:
        raise ValueError("header says %d clauses, file has %d lines" % (nc, len(body)))
    clauses = []
    for ln in body:
        toks = ln.split(" ")
        if not toks or toks[-1] != "0":
            raise ValueError("clause line not terminated by ' 0': %r" % ln)
        lits = [int(t) for t in toks[:-1]]
        if not lits or any(l == 0 or abs(l) > nv for l in lits):
            raise ValueError("bad literal in %r" % ln)
        if str(lits[0]) != toks[0] or any(str(l) != t for l, t in zip(lits, toks)):
            raise ValueError("non-canonical integer in %r" % ln)
        clauses.append(lits)
    return nv, clauses


def main():
    gpath, name, mode, K, cnfp, extp = sys.argv[1:7]
    dump = sys.argv[7] if len(sys.argv) > 7 else None
    K = int(K)
    assert mode in ("ds", "ids")
    g = json.load(open(gpath))[name]
    n, E = decode_graph6(g["graph6"])
    assert n == g["n"]
    N = {v: {v} for v in range(n)}
    for a, b in E:
        N[a].add(b); N[b].add(a)

    nv, clauses = parse_dimacs_strict(open(cnfp).read())

    if dump is not None:
        nv2, cl2 = parse_dimacs_strict(open(dump).read())
        if nv2 != nv or cl2 != clauses:
            sys.exit("FAIL: cake_lpr's parse of the CNF differs from the audited parse")

    ext = json.load(open(extp))
    if ext.get("graph") != name or ext.get("mode") != mode or ext.get("k") != K or ext.get("n") != n:
        sys.exit("FAIL: sidecar header does not match the claim being audited")
    aux = {}
    for var, (i, j) in ext["aux"].items():
        var = int(var)
        if var <= n or not (1 <= i <= n) or j < 1:
            sys.exit("FAIL: bad aux declaration %s -> (%s,%s)" % (var, i, j))
        aux[var] = (i, j)

    counts = {"D": 0, "I": 0, "W": 0}
    max_width = 0
    for idx, cl in enumerate(clauses, 1):
        for l in cl:
            if abs(l) > n and abs(l) not in aux:
                sys.exit("FAIL: clause %d uses undeclared variable %d" % (idx, abs(l)))
        auxlits = [l for l in cl if abs(l) > n]
        if not auxlits:
            pos = {l - 1 for l in cl if l > 0}
            neg = {-l - 1 for l in cl if l < 0}
            if any(N[v] <= pos for v in range(n)):
                counts["D"] += 1
                continue
            if mode == "ids" and any((min(a, b), max(a, b)) in E for a in neg for b in neg if a < b):
                counts["I"] += 1
                continue
            sys.exit("FAIL: clause %d %s is not a domination/independence clause" % (idx, cl))
        # rule W
        idxs = []
        for l in cl:
            v = abs(l)
            if v > n:
                idxs.append(aux[v][0])
            else:
                idxs += [v - 1, v]          # x(vertex v-1) = c_v - c_{v-1}
        lo, hi = min(idxs), max(idxs)
        if hi - lo > 4:
            sys.exit("FAIL: clause %d is not local (width %d)" % (idx, hi - lo))
        max_width = max(max_width, hi - lo)
        for c_lo in range(0, min(lo, K) + 1):
            for bits in product((0, 1), repeat=hi - lo):
                c = {lo: c_lo}
                ok = True
                for q in range(lo + 1, hi + 1):
                    c[q] = c[q - 1] + bits[q - lo - 1]
                    if c[q] > min(q, K):
                        ok = False
                        break
                if not ok:
                    continue
                def val(l):
                    v = abs(l)
                    if v > n:
                        i, j = aux[v]
                        t = c[i] >= j
                    else:
                        t = (c[v] - c[v - 1]) == 1
                    return t if l > 0 else not t
                if not any(val(l) for l in cl):
                    sys.exit("FAIL: clause %d %s is false in state c_%d=%d bits=%s"
                             % (idx, cl, lo, c_lo, bits))
        counts["W"] += 1

    what = "dominating set" if mode == "ds" else "independent dominating set"
    print("PASS %s %s K=%d: %d clauses (D=%d, I=%d, W=%d, max window %d), %d vars%s"
          % (name, mode, K, len(clauses), counts["D"], counts["I"], counts["W"], max_width, nv,
             ", parse identical to cake_lpr" if dump else ""))
    print("  => every %s of size <= %d satisfies this CNF; if it is UNSAT, %s(G) >= %d"
          % (what, K, "gamma" if mode == "ds" else "i", K + 1))


if __name__ == "__main__":
    main()
