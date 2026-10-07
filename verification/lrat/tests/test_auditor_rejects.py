#!/usr/bin/env python3
"""Mutation tests for audit_cnf.py: unsound CNFs must be rejected, sound edits accepted.

Usage: python3 test_auditor_rejects.py GRAPHS.json
"""
import json, os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); UP = os.path.dirname(HERE)
graphs = sys.argv[1]
random.seed(7)


def enc(name, mode, K, path):
    subprocess.run([sys.executable, "-I", os.path.join(UP, "encode.py"), graphs, name, mode, str(K), path], check=True)


def audit(name, mode, K, cnf, ext, dump=None):
    cmd = [sys.executable, "-I", os.path.join(UP, "audit_cnf.py"), graphs, name, mode, str(K), cnf, ext]
    if dump:
        cmd.append(dump)
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode == 0 and p.stdout.startswith("PASS"), (p.stdout + p.stderr).strip().splitlines()[-1:]


def read(path):
    L = open(path).read().splitlines()
    hdr = [i for i, l in enumerate(L) if l.startswith("p ")][0]
    nv = int(L[hdr].split()[2])
    return L[:hdr], nv, [list(map(int, l.split()[:-1])) for l in L[hdr + 1:]]


def write(path, pre, nv, cl):
    with open(path, "w") as f:
        f.write("\n".join(pre) + ("\n" if pre else ""))
        f.write("p cnf %d %d\n" % (nv, len(cl)))
        for c in cl:
            f.write(" ".join(map(str, c)) + " 0\n")


ok = True
def expect(label, want, got):
    global ok
    res, why = got
    flag = "ok " if res == want else "BAD"
    if res != want:
        ok = False
    print("  [%s] %-62s -> %s %s" % (flag, label, "accepted" if res else "rejected", "" if res else why))


with tempfile.TemporaryDirectory() as td:
    J = lambda f: os.path.join(td, f)
    name = "R6+R6"
    enc(name, "ds", 15, J("ds.cnf")); enc(name, "ids", 15, J("ids.cnf")); enc(name, "ds", 14, J("ds14.cnf"))
    pre, nv, cl = read(J("ds.cnf")); _, nvi, cli = read(J("ids.cnf"))
    ext, exti = J("ds.ext.json"), J("ids.ext.json")
    expect("baseline ds K=15", True, audit(name, "ds", 15, J("ds.cnf"), ext))
    expect("baseline ids K=15", True, audit(name, "ids", 15, J("ids.cnf"), exti))

    print(" unsound edits (must be rejected):")
    write(J("m.cnf"), pre, nv, cl + [[-5]])
    expect("add unit clause -x(5) (forbids a vertex)", False, audit(name, "ds", 15, J("m.cnf"), ext))
    c2 = [list(c) for c in cl]; c2[0] = c2[0][1:]
    write(J("m.cnf"), pre, nv, c2)
    expect("drop one literal from a domination clause", False, audit(name, "ds", 15, J("m.cnf"), ext))
    e14 = json.load(open(J("ds14.ext.json"))); e14["k"] = 15; json.dump(e14, open(J("m14.ext.json"), "w"))
    expect("at-most-14 CNF presented as at-most-15", False, audit(name, "ds", 15, J("ds14.cnf"), J("m14.ext.json")))
    expect("ids CNF audited as a ds claim", False, audit(name, "ds", 15, J("ids.cnf"), J("ds.ext.json")))
    nonedge = None
    G = json.load(open(graphs))[name]; E = {tuple(sorted(e)) for e in G["edges"]}
    for a in range(50):
        for b in range(a + 1, 50):
            if (a, b) not in E and nonedge is None:
                nonedge = (a, b)
    write(J("m.cnf"), pre, nvi, cli + [[-(nonedge[0] + 1), -(nonedge[1] + 1)]])
    expect("ids CNF plus a non-edge 'independence' clause", False, audit(name, "ids", 15, J("m.cnf"), exti))
    e = json.load(open(ext)); ks = list(e["aux"]); a1, a2 = ks[100], ks[217]
    e["aux"][a1], e["aux"][a2] = e["aux"][a2], e["aux"][a1]; json.dump(e, open(J("sw.ext.json"), "w"))
    expect("two aux declarations swapped in the sidecar", False, audit(name, "ds", 15, J("ds.cnf"), J("sw.ext.json")))
    aux_of = {tuple(v): int(k) for k, v in json.load(open(ext))["aux"].items()}
    write(J("m.cnf"), pre, nv, cl + [[-aux_of[(10, 3)]]])
    expect("add unit clause -s(10,3) (caps a prefix count)", False, audit(name, "ds", 15, J("m.cnf"), ext))
    write(J("m.cnf"), pre, nv + 1, cl + [[1, nv + 1]])
    expect("clause using an undeclared variable", False, audit(name, "ds", 15, J("m.cnf"), ext))
    txt = open(J("ds.cnf")).read().replace("\n1 2 31 34 0\n", "\n1 2\n31 34 0\n").replace("p cnf %d %d" % (nv, len(cl)), "p cnf %d %d" % (nv, len(cl) + 1))
    open(J("m.cnf"), "w").write(txt)
    expect("a clause split across two lines", False, audit(name, "ds", 15, J("m.cnf"), ext))
    open(J("m.cnf"), "w").write(open(J("ds.cnf")).read().replace("\n1 2 31 34 0\n", "\n1 2 0 31 34 0\n"))
    expect("a stray 0 inside a clause line", False, audit(name, "ds", 15, J("m.cnf"), ext))
    write(J("dump.txt"), [], nv, cl[1:] + cl[:1])
    expect("checker parse differs from the audited file", False, audit(name, "ds", 15, J("ds.cnf"), ext, J("dump.txt")))
    expect("wrong graph (R3+R3) for an R6+R6 CNF", False, audit("R3+R3", "ds", 15, J("ds.cnf"), ext))
    e = json.load(open(ext)); e["graph"] = "R3+R3"; json.dump(e, open(J("rg.ext.json"), "w"))
    expect("R6+R6 CNF with sidecar relabelled as R3+R3", False, audit("R3+R3", "ds", 15, J("ds.cnf"), J("rg.ext.json")))

    print(" sound edits (must be accepted):")
    c3 = cl[:]; random.shuffle(c3)
    write(J("m.cnf"), pre, nv, c3)
    expect("clauses shuffled", True, audit(name, "ds", 15, J("m.cnf"), ext))
    write(J("m.cnf"), pre, nv, cl + cl[:40])
    expect("40 clauses duplicated", True, audit(name, "ds", 15, J("m.cnf"), ext))
    write(J("m.cnf"), pre, nv, [c for c in cl if random.random() < 0.7])
    expect("30% of clauses deleted (weaker formula)", True, audit(name, "ds", 15, J("m.cnf"), ext))
    c4 = [list(c) for c in cl]; c4[0] = c4[0] + [7]
    write(J("m.cnf"), pre, nv, c4)
    expect("extra literal added to a domination clause", True, audit(name, "ds", 15, J("m.cnf"), ext))
    write(J("dump.txt"), [], nv, cl)
    expect("checker parse identical", True, audit(name, "ds", 15, J("ds.cnf"), ext, J("dump.txt")))

print("mutation tests:", "ALL AS EXPECTED" if ok else "UNEXPECTED RESULT")
sys.exit(0 if ok else 1)
