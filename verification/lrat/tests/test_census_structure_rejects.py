#!/usr/bin/env python3
"""Mutation tests for census/check_census_structure.py: each corrupted census must FAIL.

Usage: python3 test_census_structure_rejects.py census_tight_15_20.json   (a few minutes)
  m1  one literal sign flipped                    (no longer tight)
  m2  two literals swapped, stored graph left     (G(K) differs from the stored edges)
  m3  a class replaced by a satisfiable tight formula, graph data rebuilt consistently
  m4  a class replaced by a relabelled copy of another class, data rebuilt consistently
      (run twice: with pynauty if available, and with nauty disabled, so the VF2 route
       must catch the duplicate on its own)
"""
import copy, itertools, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(os.path.dirname(HERE), "census", "check_census_structure.py")
C = json.load(open(sys.argv[1])); keys = list(C)


def lit_vertex(l):
    return 2 * (abs(l) - 1) + (1 if l < 0 else 0)


def rebuild(v, K):
    E = {(2 * j, 2 * j + 1) for j in range(15)} | {tuple(sorted((lit_vertex(l), 30 + c))) for c, cl in enumerate(K) for l in cl}
    bits = [1 if (i, j) in E else 0 for j in range(1, 50) for i in range(j)]
    while len(bits) % 6:
        bits.append(0)
    v["K"] = K; v["edges"] = sorted(map(list, E))
    v["graph6"] = chr(113) + "".join(chr(63 + int("".join(map(str, bits[t:t + 6])), 2)) for t in range(0, len(bits), 6))


def satisfiable(K):
    return any(all(any(((a >> (abs(l) - 1)) & 1) == (l > 0) for l in cl) for cl in K) for a in range(1 << 15))


muts = {}
m = copy.deepcopy(C); m[keys[5]]["K"][0][0] *= -1; muts["m1 literal flipped"] = m
m = copy.deepcopy(C); K = m[keys[7]]["K"]
for c1, c2 in itertools.combinations(range(20), 2):
    a, b = K[c1][0], K[c2][0]
    if a != b and abs(a) not in map(abs, K[c2]) and abs(b) not in map(abs, K[c1]):
        K[c1][0], K[c2][0] = b, a
        break
muts["m2 stale stored graph"] = m
m = copy.deepcopy(C); K = m[keys[9]]["K"]; found = False
for c1, c2 in itertools.combinations(range(20), 2):
    for p1, p2 in itertools.product(range(3), repeat=2):
        a, b = K[c1][p1], K[c2][p2]
        if a == b or abs(a) in map(abs, K[c2]) or abs(b) in map(abs, K[c1]):
            continue
        K2 = [list(cl) for cl in K]; K2[c1][p1], K2[c2][p2] = b, a
        if satisfiable(K2):
            rebuild(m[keys[9]], K2); found = True; break
    if found:
        break
assert found
muts["m3 satisfiable class"] = m
m = copy.deepcopy(C); v = copy.deepcopy(C[keys[10]])
rebuild(v, [[(1 if l > 0 else -1) * (abs(l) % 15 + 1) for l in cl] for cl in v["K"]])
m[keys[11]] = v
muts["m4 duplicate class"] = m

ok = True
with tempfile.TemporaryDirectory() as td:
    runs = [(name, mm, False) for name, mm in muts.items()] + [("m4 duplicate class, nauty disabled", muts["m4 duplicate class"], True)]
    for name, mm, no_nauty in runs:
        f = os.path.join(td, "c.json"); json.dump(mm, open(f, "w"))
        cmd = [sys.executable, "-I"]
        if no_nauty:   # hide pynauty so only the invariant + VF2 route can catch the duplicate
            cmd += ["-c", "import sys; sys.modules['pynauty'] = None; sys.argv = sys.argv[1:]; exec(open(sys.argv[0]).read())", CHECK, f]
        else:
            cmd += [CHECK, f]
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
        verdict = next((l for l in out.splitlines() if l.startswith("FAIL") or l.startswith("ALL")), "no verdict")
        good = verdict.startswith("FAIL")
        ok &= good
        print("  [%s] %-38s -> %s" % ("ok " if good else "BAD", name, verdict))
print("census mutation tests:", "ALL REJECTED AS EXPECTED" if ok else "UNEXPECTED RESULT")
sys.exit(0 if ok else 1)
