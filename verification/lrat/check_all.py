#!/usr/bin/env python3
"""check_all.py -- referee script: re-check every certificate and witness.

Usage:  python3 check_all.py GRAPHS.json CERTDIR --cake PATH_TO_cake_lpr [--jobs N]

Needs only Python 3, the xz-compressed proofs in CERTDIR, and cake_lpr
(https://github.com/tanyongkiam/cake_lpr, commit a4323b2, `make`).  No SAT solver,
and no trust in encode.py or run_all.py:

  lower bounds  each CNF is (1) parsed by cake_lpr, (2) audited by audit_cnf.py
                against that parse (every (independent) dominating set of size
                <= K satisfies the CNF), (3) proved UNSAT by cake_lpr
                ("s VERIFIED UNSAT") from its LRAT proof;
  upper bounds  explicit witness sets, checked here from the definitions;
  mu* = 15      the 15 pivot edges form a maximal matching, and every edge of a
                cubic graph dominates at most 5 of the 75 edges, so every edge
                dominating set (in particular every maximal matching) has >= 15.
"""
import argparse, collections, hashlib, json, lzma, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha(path):
    return sha_bytes(open(path, "rb").read())


def g6(s):
    d = [ord(c) - 63 for c in s.strip()]
    n = d[0]
    bits = [(x >> t) & 1 for x in d[1:] for t in range(5, -1, -1)]
    E, k = set(), 0
    for j in range(1, n):
        for i in range(j):
            if bits[k]:
                E.add((i, j))
            k += 1
    return n, E


def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)


def check_cert(c, a, cake, env):
    """Re-check one lower-bound certificate; returns an error string or None."""
    cnf = os.path.join(a.certdir, c["cnf"]); ext = os.path.join(a.certdir, c["ext"])
    prf = os.path.join(a.certdir, c["proof"])
    if sha(cnf) != c["cnf_sha256"] or sha(ext) != c["ext_sha256"] or sha(prf) != c["proof_sha256_xz"]:
        return "hash mismatch for " + c["cnf"]
    with tempfile.TemporaryDirectory() as td:
        raw = lzma.open(prf).read()
        if sha_bytes(raw) != c["proof_sha256_uncompressed"]:
            return "proof hash mismatch after decompression: " + c["proof"]
        pf = os.path.join(td, "proof.lrat"); open(pf, "wb").write(raw)
        dump = os.path.join(td, "parse.txt")
        q = subprocess.run(cake + [cnf], capture_output=True, text=True, env=env)
        open(dump, "w").write(q.stdout)
        au = subprocess.run([sys.executable, "-I", os.path.join(HERE, "audit_cnf.py"), a.graphs,
                             c["graph"], c["mode"], str(c["K"]), cnf, ext, dump],
                            capture_output=True, text=True)
        if au.returncode != 0 or not au.stdout.startswith("PASS"):
            return "audit failed for %s: %s%s" % (c["cnf"], au.stdout, au.stderr)
        r = subprocess.run(cake + [cnf, pf], capture_output=True, text=True, env=env)
        if r.stdout != "s VERIFIED UNSAT\n":
            return "cake_lpr did not verify %s: %r %r" % (c["proof"], r.stdout, r.stderr)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graphs"); ap.add_argument("certdir"); ap.add_argument("--cake", required=True)
    ap.add_argument("--heap", default="1000"); ap.add_argument("--stack", default="500")
    ap.add_argument("--cake-flags", action="store_true",
                    help="pass heap/stack as --CML_HEAP_SIZE=/--CML_STACK_SIZE= flags (cake_lpr builds "
                         "from July 2026 on); default: environment variables (commit a4323b2)")
    ap.add_argument("--jobs", type=int, default=1, help="certificates checked in parallel")
    a = ap.parse_args()
    env = dict(os.environ, CML_HEAP_SIZE=a.heap, CML_STACK_SIZE=a.stack)
    cake = [a.cake] + (["--CML_HEAP_SIZE=" + a.heap, "--CML_STACK_SIZE=" + a.stack] if a.cake_flags else [])
    G = json.load(open(a.graphs))
    R = json.load(open(os.path.join(a.certdir, "results.json")))
    if sha(a.graphs) != R["graphs_sha256"]:
        fail("graphs file differs from the one the certificates were made for")
    label = {name: lab for lab, name in R.get("labels", {}).items()}
    lab = lambda name: label.get(name, name)

    lower = {}
    print("Lower bounds (cake_lpr-verified LRAT proofs of audited CNFs):")
    certs = R["certificates"]
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        errors = list(ex.map(lambda c: check_cert(c, a, cake, env), certs))
    for c, err in zip(certs, errors):
        if err:
            fail(err)
        lower[(c["graph"], c["mode"])] = c["K"] + 1
        print("  %-7s %-3s K=%-2d audit PASS, cake_lpr: s VERIFIED UNSAT  =>  %s"
              % (lab(c["graph"]), c["mode"], c["K"], c["claim"]))

    print("\nGraphs, upper bounds, mu*:")
    rows = []
    for name, g in G.items():
        n, E = g6(g["graph6"])
        El = {tuple(sorted(e)) for e in g["edges"]}
        if n != g["n"] or E != El or len(El) != len(g["edges"]):
            fail(lab(name) + ": graph6 and edge list disagree")
        adj = {v: set() for v in range(n)}
        for u, w in E:
            adj[u].add(w); adj[w].add(u)
        if any(len(adj[v]) != 3 for v in range(n)):
            fail(lab(name) + ": not cubic")
        seen, stack = {0}, [0]
        while stack:
            for w in adj[stack.pop()] - seen:
                seen.add(w); stack.append(w)
        if len(seen) != n:
            fail(lab(name) + ": not connected")
        M = [tuple(sorted(e)) for e in g["pivot_matching"]]
        cov = {v for e in M for v in e}
        if len(M) != 15 or len(cov) != 30 or not set(M) <= E:
            fail(lab(name) + ": pivot edges are not a 15-edge matching of G")
        if any(u not in cov and w not in cov for u, w in E):
            fail(lab(name) + ": pivot matching is not maximal")
        dom_per_edge = max(len(adj[u]) + len(adj[w]) - 1 for u, w in E)
        mu_lower = -(-len(E) // dom_per_edge)
        if mu_lower != 15:
            fail(lab(name) + ": counting bound is not 15")

        def dominating(S):
            return all(v in S or adj[v] & S for v in range(n))

        def independent(S):
            return all(not (adj[v] & S) for v in S)

        W = R["witnesses"].get(name, {})
        ids = set(g["ids"])
        if not (dominating(ids) and independent(ids) and len(ids) == g["i"]):
            fail(lab(name) + ": published IDS witness invalid")
        ds = set(W.get("ds", []))
        if not (dominating(ds) and len(ds) == g["gamma"]):
            fail(lab(name) + ": dominating-set witness invalid")
        ids2 = set(W.get("ids", []))
        if not (dominating(ids2) and independent(ids2) and len(ids2) == g["i"]):
            fail(lab(name) + ": solver IDS witness invalid")
        if lower.get((name, "ds")) != g["gamma"] or lower.get((name, "ids")) != g["i"]:
            fail(lab(name) + ": missing lower-bound certificate")
        A = g["gamma"] > 15
        B = g["i"] > 15
        rows.append((lab(name), g["gamma"], g["i"], A, B))
        print("  %-7s cubic, connected, n=%d, |E|=%d; gamma <= %d (witness), i <= %d (witness); "
              "mu* = 15 (pivot matching + ceil(%d/%d))" % (lab(name), n, len(E), len(ds), len(ids), len(E), dom_per_edge))

    print("\n  graph    gamma   i   mu*   gamma > gamma_e (A)   i > mu* (B)")
    for name, ga, ii, A, B in rows:
        print("  %-7s  %4d  %3d   %3d   %-20s  %s" % (name, ga, ii, 15, "REFUTES (A)" if A else "-", "REFUTES (B)" if B else "-"))
    if len(rows) > 7:
        cells = collections.Counter((ga, ii) for _, ga, ii, _, _ in rows)
        print("\n  %d graphs; (gamma, i) counts: %s" % (len(rows), ", ".join("(%d,%d): %d" % (k[0], k[1], v) for k, v in sorted(cells.items()))))
        print("  refuting (A) gamma > gamma_e: %d    refuting (B) i > mu*: %d"
              % (sum(r[3] for r in rows), sum(r[4] for r in rows)))
    print("\nALL CHECKS PASSED: every gamma and i value above is exact, with machine-checked lower bounds.")


if __name__ == "__main__":
    main()
