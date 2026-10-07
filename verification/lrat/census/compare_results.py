#!/usr/bin/env python3
"""compare_results.py -- confirm a regenerated certificate set is the published one.

Usage:  python3 compare_results.py PUBLISHED_results.json REGENERATED_results.json

The census proofs (about 1 GB) are not stored in the repository. They are deterministic:
run_all.py with CaDiCaL 3.0.1 regenerates every CNF and LRAT proof byte for byte (and
checks each with cake_lpr and the audit as it goes).  This script checks that the
regenerated set has exactly the SHA-256 values recorded in the published results.json,
and the same witness sets.  Then check_all.py on the regenerated directory is the full
referee check.
"""
import json, sys

A = json.load(open(sys.argv[1])); B = json.load(open(sys.argv[2]))
if A["graphs_sha256"] != B["graphs_sha256"]:
    sys.exit("FAIL: made from different graph files")
key = lambda c: (c["graph"], c["mode"], c["K"])
fa = {key(c): c for c in A["certificates"]}; fb = {key(c): c for c in B["certificates"]}
if set(fa) != set(fb):
    sys.exit("FAIL: different certificate sets (%d vs %d)" % (len(fa), len(fb)))
fields = ("cnf_sha256", "ext_sha256", "proof_sha256_uncompressed")
bad = [k for k in fa if any(fa[k][f] != fb[k][f] for f in fields)]
if bad:
    sys.exit("FAIL: %d certificates differ, e.g. %s" % (len(bad), fa[bad[0]]["cnf"]))
if A["witnesses"] != B["witnesses"]:
    sys.exit("FAIL: witness sets differ")
print("IDENTICAL: %d certificates (CNF, sidecar and LRAT proof SHA-256) and all witness sets match" % len(fa))
