#!/usr/bin/env python3
"""For every control graph, mode and K = 1..n-1: the audit must PASS, and the CNF
must be SAT iff K >= brute-force value; every UNSAT case is also proved via LRAT
and checked by cake_lpr."""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.dirname(HERE)
graphs, cadical, cake = sys.argv[1], sys.argv[2], sys.argv[3]
env = dict(os.environ, CML_HEAP_SIZE="1000", CML_STACK_SIZE="500")
G = json.load(open(graphs))
tot = unsat = 0
with tempfile.TemporaryDirectory() as td:
    for name, g in G.items():
        for mode in ("ds", "ids"):
            val = g["gamma"] if mode == "ds" else g["i"]
            for K in range(1, g["n"]):
                cnf = os.path.join(td, "f.cnf"); ext = os.path.join(td, "f.ext.json")
                subprocess.run([sys.executable, "-I", os.path.join(UP, "encode.py"), graphs, name, mode, str(K), cnf], check=True)
                au = subprocess.run([sys.executable, "-I", os.path.join(UP, "audit_cnf.py"), graphs, name, mode, str(K), cnf, ext],
                                    capture_output=True, text=True)
                assert au.returncode == 0 and au.stdout.startswith("PASS"), (name, mode, K, au.stdout, au.stderr)
                prf = os.path.join(td, "f.lrat")
                p = subprocess.run([cadical, "-q", "--lrat", cnf, prf], capture_output=True, text=True)
                want = 10 if K >= val else 20
                assert p.returncode == want, (name, mode, K, val, p.returncode)
                if want == 20:
                    r = subprocess.run([cake, cnf, prf], capture_output=True, text=True, env=env)
                    assert r.stdout == "s VERIFIED UNSAT\n", (name, mode, K, r.stdout, r.stderr)
                    unsat += 1
                tot += 1
        print("  %-10s n=%2d gamma=%d i=%d  all K ok" % (name, g["n"], g["gamma"], g["i"]), flush=True)
print("sweep OK: %d (graph, mode, K) instances, %d UNSAT proofs verified by cake_lpr" % (tot, unsat))
