#!/usr/bin/env python3
"""run_all.py -- produce the certificates (needs CaDiCaL and cake_lpr).

Usage:  python3 run_all.py GRAPHS.json OUTDIR --cadical PATH --cake PATH [--names A,B,...] [--jobs N]

For every graph with claimed values gamma and i:
  ds  K=gamma-1 and ids K=i-1 : encode, solve with CaDiCaL writing an LRAT proof,
                                check the proof with cake_lpr ("s VERIFIED UNSAT"),
                                audit the CNF against cake_lpr's own parse of it;
  ds  K=gamma   and ids K=i   : solve, extract a witness set, verify it directly.
Writes OUTDIR/cnf/*.cnf, *.ext.json, OUTDIR/proofs/*.lrat.xz, OUTDIR/logs/*,
OUTDIR/results.json.  Referees re-check everything with check_all.py
(no solver needed).

File names use the graph's name when it is short (e.g. R6+R6 -> R6_R6), and
c000, c001, ... (position in GRAPHS.json) otherwise -- e.g. for the census file,
whose keys are 800-character nauty certificates.
"""
import argparse, hashlib, json, lzma, os, re, subprocess, sys, tempfile, time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CAKE_ENV = dict(os.environ, CML_HEAP_SIZE="1000", CML_STACK_SIZE="500")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def label_of(name, idx):
    if re.fullmatch(r"[A-Za-z0-9+._-]{1,40}", name):
        return name.replace("+", "_")
    return "c%03d" % idx


def run(cmd, **kw):
    t = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return p, time.time() - t


def do_graph(job):
    a, idx, name = job
    G = json.load(open(a.graphs))
    g = G[name]
    lab = label_of(name, idx)
    n = g["n"]
    adj = {v: set() for v in range(n)}
    for u, w in g["edges"]:
        adj[u].add(w); adj[w].add(u)
    certs, wit, lines = [], {}, []
    for mode, val in (("ds", g["gamma"]), ("ids", g["i"])):
        for K, expect in ((val - 1, "unsat"), (val, "sat")):
            base = "%s_%s_le%d" % (lab, mode, K)
            cnf = os.path.join(a.out, "cnf", base + ".cnf")
            ext = cnf[:-4] + ".ext.json"
            subprocess.run([sys.executable, "-I", os.path.join(HERE, "encode.py"),
                            a.graphs, name, mode, str(K), cnf], check=True)
            if expect == "sat":
                p, dt = run([a.cadical, "-q", cnf])
                assert p.returncode == 10, (base, p.returncode)
                model = [int(t) for ln in p.stdout.splitlines() if ln.startswith("v")
                         for t in ln[1:].split()]
                S = sorted(l - 1 for l in model if 0 < l <= n)
                Sset = set(S)
                assert len(S) <= K
                assert all(adj[v] & Sset or v in Sset for v in range(n)), "not dominating"
                if mode == "ids":
                    assert all(not (adj[v] & Sset) for v in S), "not independent"
                wit[mode] = S
                os.remove(cnf); os.remove(ext)
                lines.append("  %-28s SAT    witness size %d" % (base, len(S)))
                continue
            proof = os.path.join(a.out, "proofs", base + ".lrat")
            p, t_solve = run([a.cadical, "--lrat", cnf, proof])
            open(os.path.join(a.out, "logs", base + ".cadical.log"), "w").write(p.stdout + p.stderr)
            assert p.returncode == 20, (base, p.returncode)
            with tempfile.TemporaryDirectory() as td:
                dump = os.path.join(td, "parse.txt")   # the formula as cake_lpr parsed it
                q, _ = run([a.cake, cnf], env=CAKE_ENV)
                open(dump, "w").write(q.stdout)
                r, t_check = run([a.cake, cnf, proof], env=CAKE_ENV)
                assert r.stdout == "s VERIFIED UNSAT\n", (base, r.stdout, r.stderr)
                s_, _ = run([sys.executable, "-I", os.path.join(HERE, "audit_cnf.py"),
                             a.graphs, name, mode, str(K), cnf, ext, dump])
                assert s_.returncode == 0 and s_.stdout.startswith("PASS"), (base, s_.stdout, s_.stderr)
            conflicts = None
            for ln in p.stdout.splitlines():
                if ln.startswith("c conflicts:"):
                    conflicts = int(ln.split()[2])
            rec = {"graph": name, "label": lab, "mode": mode, "K": K,
                   "claim": "%s(G) >= %d" % ("gamma" if mode == "ds" else "i", K + 1),
                   "cnf": "cnf/" + base + ".cnf", "cnf_sha256": sha(cnf),
                   "ext": "cnf/" + base + ".ext.json", "ext_sha256": sha(ext),
                   "proof": "proofs/" + base + ".lrat.xz", "proof_format": "binary LRAT",
                   "proof_sha256_uncompressed": sha(proof),
                   "proof_bytes_uncompressed": os.path.getsize(proof),
                   "cadical_conflicts": conflicts,
                   "solve_seconds": round(t_solve, 2), "check_seconds": round(t_check, 2),
                   "cake_lpr": r.stdout.strip(), "audit": s_.stdout.splitlines()[0]}
            with open(proof, "rb") as f, lzma.open(proof + ".xz", "wb", preset=9) as z:
                z.write(f.read())
            os.remove(proof)
            rec["proof_sha256_xz"] = sha(proof + ".xz")
            certs.append(rec)
            lines.append("  %-28s UNSAT  %s  (solve %.2fs, cake_lpr %.2fs, %d conflicts)"
                         % (base, rec["cake_lpr"], t_solve, t_check, conflicts or -1))
    return idx, name, lab, certs, wit, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graphs"); ap.add_argument("out")
    ap.add_argument("--cadical", required=True); ap.add_argument("--cake", required=True)
    ap.add_argument("--names", default=None)
    ap.add_argument("--jobs", type=int, default=1)
    a = ap.parse_args()
    G = json.load(open(a.graphs))
    order = list(G)
    names = a.names.split(",") if a.names else order
    for d in ("cnf", "proofs", "logs"):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)
    ver = subprocess.run([a.cadical, "--version"], capture_output=True, text=True).stdout.strip()
    results = {"graphs_file": os.path.basename(a.graphs), "graphs_sha256": sha(a.graphs),
               "cadical_version": ver, "labels": {}, "certificates": [], "witnesses": {}}
    jobs = [(a, order.index(nm), nm) for nm in names]
    done = {}
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for idx, name, lab, certs, wit, lines in ex.map(do_graph, jobs):
            print("\n".join(lines), flush=True)
            done[idx] = (name, lab, certs, wit)
    for idx in sorted(done):
        name, lab, certs, wit = done[idx]
        results["labels"][lab] = name
        results["certificates"] += certs
        results["witnesses"][name] = wit
    json.dump(results, open(os.path.join(a.out, "results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
