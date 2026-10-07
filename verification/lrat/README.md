# Machine-checked lower bounds (LRAT proofs, formally verified checker)

Every domination and independent-domination number of the seven graphs in `counterexamples.json` is certified here, and so is every γ and i value of the 239 classes in `census_tight_15_20.json` (see [The census](#the-census-all-239-classes)). Each lower bound has an LRAT unsatisfiability proof, checked by **cake_lpr**, a proof checker whose machine code is formally verified in HOL4/CakeML [1, 2]. Each upper bound is an explicit witness set. µ\* = 15 follows from the pivot matching plus a counting bound. For the seven graphs, one command re-checks all of it in about six seconds. It needs no SAT solver, and it does not trust the code that generated the CNFs. The census check regenerates its proofs first; see below.

| graph | γ | i | µ\* = γ_e | γ > γ_e (A) | i > µ\* (B) |
|---|---|---|---|---|---|
| R0+R0 | 14 | 15 | 15 | – | – |
| R3+R3 | 14 | 16 | 15 | – | refuted |
| R3+R6 | 15 | 16 | 15 | – | refuted |
| R3+R7 | 15 | 16 | 15 | – | refuted |
| R6+R6 | 16 | 16 | 15 | refuted | refuted |
| R6+R7 | 16 | 16 | 15 | refuted | refuted |
| R7+R7 | 16 | 16 | 15 | refuted | refuted |

## Check it yourself

```sh
git clone https://github.com/tanyongkiam/cake_lpr ~/cake_lpr
cd ~/cake_lpr && git checkout a4323b2 && sha256sum -c cake_lpr.sha256 && make && cd -
# from the root of this repository:
python3 verification/lrat/check_all.py counterexamples.json verification/lrat/certs --cake ~/cake_lpr/cake_lpr
```

The output ends with `ALL CHECKS PASSED` and the table above. The script needs only Python 3 (standard library). It gives cake_lpr a 1 GB heap and a 0.5 GB stack, which is more than enough; `--heap`/`--stack` (in MB) change that. If your cake_lpr is built from July 2026 or later (commit a36874a onward), add `--cake-flags`. Note that cake_lpr exits with status 0 even when it rejects a proof. Success is the stdout line `s VERIFIED UNSAT`, and that line is what `check_all.py` tests.

## What a lower bound rests on

A lower bound such as γ(R6+R6) ≥ 16 says that no dominating set of size ≤ 15 exists. Two checks establish it:

1. **cake_lpr** parses `certs/cnf/R6_R6_ds_le15.cnf`, checks the LRAT proof `certs/proofs/R6_R6_ds_le15.lrat.xz`, and prints `s VERIFIED UNSAT`. Its correctness theorem states that it prints this only when the formula it parsed is unsatisfiable. What remains trusted there is the HOL4 logic, the assembler and linker that turn `cake_lpr.S` into a binary, the small C I/O wrapper `basis_ffi.c`, the OS, and the hardware.
2. **audit_cnf.py** (as run by `check_all.py`) first confirms that the clause list it audits is identical to cake_lpr's own parse of the file. Working from the CNF itself, it then proves this: every dominating set S with |S| ≤ K (independent as well, for i) gives a satisfying assignment. That assignment is x(v+1) = [v ∈ S], with each counter variable s(i,j) = [|S ∩ {0,…,i−1}| ≥ j]. The audit goes clause by clause, and each clause must pass one of three rules:
   - **D**: the clause contains x(u) for every u in some closed neighbourhood N[v]. Every dominating set makes it true.
   - **I** (i only): the clause contains ¬x(u) ∨ ¬x(w) for an edge uw. Every independent set makes it true.
   - **W**: a clause containing a counter variable may read at most five consecutive prefix counts. It is checked true in every possible state with all counts ≤ K.

   A clause that passes none of these rules is rejected. The graph is decoded from the graph6 string, not from the edge list that `encode.py` used. The sidecar `*.ext.json` only proposes which counter variable means what. A wrong sidecar can make the audit fail, but it can never make it pass wrongly.

Together, a verified UNSAT means no such S exists, so γ ≥ K + 1 (or i ≥ K + 1). `encode.py`, `run_all.py`, CaDiCaL and every earlier solver run are outside the trusted base. What remains is cake_lpr, `audit_cnf.py` (180 lines, with the argument above in its docstring), the witness checks in `check_all.py`, and the graph data.

## Evidence that the audit is not vacuous (`tests/`)

- `test_auditor_rejects.py counterexamples.json` applies 13 unsound edits, and the auditor rejects all of them:
  - a clause forbidding a vertex
  - a domination clause with one neighbour removed
  - an at-most-14 counter passed off as at-most-15
  - swapped counter labels
  - a non-edge "independence" clause
  - a unit clause capping a prefix count
  - an undeclared variable
  - a clause split across lines
  - a stray 0
  - a parse that differs from cake_lpr's
  - an i-CNF audited as a γ claim
  - the wrong graph, given two ways
- The same script applies 5 sound edits (shuffled, duplicated or deleted clauses, a superset clause, an identical parse), and the auditor accepts all of them.
- `test_sweep.py controls.json CADICAL CAKE_LPR` covers 24 control graphs with brute-force values: Petersen, the cube, C₉, random cubic graphs on 10–18 vertices, four random graphs with γ < i, a double star (γ = 2, i = 4), and a graph with an isolated vertex. For both problems and every K from 1 to n − 1, the audit passes and the CNF is satisfiable exactly when K ≥ the true value. That is 568 instances, and all 140 unsatisfiable ones were proved by LRAT and verified by cake_lpr.
- `crosscheck_totalizer_kissat.py counterexamples.json KISSAT` (needs networkx) re-derives every value by a different route. It uses networkx's graph6 decoder, a totalizer instead of the sequential counter, and Kissat instead of CaDiCaL. All 28 boundary instances agree: unsatisfiable at value − 1, satisfiable at the value, with each witness re-checked. This corroborates the results but is not part of the trusted chain.

## How the certificates were made

```sh
python3 verification/lrat/run_all.py counterexamples.json verification/lrat/certs \
    --cadical PATH/TO/cadical --cake PATH/TO/cake_lpr
```

The run used CaDiCaL 3.0.1 (tag `rel-3.0.1`, commit c607304) writing binary LRAT proofs. Solves took 0.2–1.2 s (11k–51k conflicts) and cake_lpr checks under 0.5 s. The CNF is the plain domination clauses, plus ¬x(u) ∨ ¬x(w) per edge for i, plus Sinz's sequential counter for "at most K" [3]. No symmetry breaking is used. The run is deterministic: reruns reproduce every CNF, sidecar, LRAT proof and `.xz` file byte for byte (SHA-256 values are in `certs/results.json`). `results.json` also pins the SHA-256 of `counterexamples.json`, so `check_all.py` refuses any other data file; if that file ever changes, rerun `run_all.py`. The γ witness sets were read off satisfying assignments at K = γ and are stored in `results.json`. `counterexamples.json` already contains a size-i independent dominating set for each graph.

## The census: all 239 classes

The same pipeline certifies γ and i for every class in `census_tight_15_20.json`. That is 478 LRAT proofs, each checked by cake_lpr, on CNFs audited exactly as above, plus a witness set for every upper bound. The resulting counts are exact:

| (γ, i) | glue-free | gluings | total |
|---|---|---|---|
| (14, 14) | 34 | 5 | 39 |
| (14, 15) | 50 | 15 | 65 |
| (14, 16) | 0 | 1 | 1 |
| (15, 15) | 58 | 10 | 68 |
| (15, 16) | 38 | 2 | 40 |
| (16, 16) | 23 | 3 | 26 |

So 67 classes refute (B) and 26 refute (A). Labels c000–c238 are positions in `census_tight_15_20.json`, in key order.

The census proofs total 0.9 GB compressed, so they are not in the repository. They are deterministic. `census/results.json` records the SHA-256 of every CNF, sidecar and proof, and regenerating them reproduces those hashes. To re-check from scratch (about 25 minutes on two cores; needs CaDiCaL 3.0.1 and cake_lpr):

```sh
python3 verification/lrat/run_all.py census_tight_15_20.json census_certs \
    --cadical PATH/TO/cadical --cake ~/cake_lpr/cake_lpr --jobs 4
python3 verification/lrat/census/compare_results.py verification/lrat/census/results.json census_certs/results.json
python3 verification/lrat/check_all.py census_tight_15_20.json census_certs --cake ~/cake_lpr/cake_lpr --jobs 4
```

`run_all.py` checks each proof with cake_lpr and audits each CNF as it goes. `compare_results.py` confirms the regenerated set is the published one. `check_all.py` then re-checks everything independently. CaDiCaL stays outside the trusted base: it only produces proofs, and cake_lpr checks them.

`census/check_census_structure.py census_tight_15_20.json counterexamples.json` checks the rest of the census claims from the definitions. It needs networkx; pynauty is optional.

- Every K is a tight (15, 20) formula, unsatisfiable and minimally unsatisfiable, over all 2^15 assignments.
- Every G(K) is a connected cubic 50-vertex graph of girth 5 that matches its stored edges, graph6 and pivot matching.
- The 239 graphs are pairwise non-isomorphic, shown two ways. Recomputed nauty certificates equal the census keys and are distinct. Separately, with no nauty, a cycle-count invariant plus VF2 on every colliding pair gives the same answer.
- All seven graphs of `counterexamples.json` are census classes: R0+R0 = c106, R3+R3 = c122, R3+R6 = c125, R3+R7 = c126, R6+R6 = c131, R6+R7 = c012, R7+R7 = c132.
- Automorphism group orders, recomputed with nauty, equal the stored ones. Orders 16, 32 and 128 occur only for gluings, and 128 only for R0+R0, as Remark 6 of the note says.
- Single moves, as in Remark 6 (exchange two literal occurrences between clauses): all 326,320 of them were tried from the 239 classes. Each of the 290 that give an unsatisfiable formula lands on a formula isomorphic to the one it came from. So 110 classes have such a neighbour and 129 have none, matching both Remark 6 and the census record.

`tests/test_census_structure_rejects.py census_tight_15_20.json` corrupts the census four ways: a flipped literal, a stale stored graph, a satisfiable class, and a relabelled duplicate class (the duplicate is run both with and without nauty). The checker rejects every one.

`census/results.json` pins the SHA-256 of `census_tight_15_20.json` (4bac6b60…). If that file is ever regenerated or edited, rerun `run_all.py` on the new file.

## Files

| path | what |
|---|---|
| `check_all.py` | referee script: hashes, cake_lpr parse, audit, cake_lpr proof check, witnesses, µ\* |
| `audit_cnf.py` | independent soundness audit of one CNF (shares no code with `encode.py`) |
| `encode.py` | writes the CNF and its counter-variable sidecar |
| `run_all.py` | produces `certs/` (needs CaDiCaL and cake_lpr) |
| `certs/cnf/` | the 14 CNFs (`<graph>_<ds or ids>_le<K>.cnf`) and their sidecars |
| `certs/proofs/` | the 14 LRAT proofs, binary LRAT, xz-compressed (17 MB; 36 MB uncompressed) |
| `certs/logs/` | CaDiCaL output for each proof run |
| `certs/results.json` | claims, hashes, timings, solver statistics, witness sets |
| `census/` | the census certificate record (`results.json`: hashes, timings, witness sets), `compare_results.py`, `check_census_structure.py` |
| `tests/` | mutation tests for the auditor and for the census checker; the control-graph sweep; the totalizer/Kissat cross-check |
| `PROVENANCE.txt` | exact tool versions and hashes |

[1] Y. K. Tan, M. J. H. Heule, M. O. Myreen. *cake_lpr: Verified Propagation Redundancy Checking in CakeML*. TACAS 2021, LNCS 12652, 223–241. doi:10.1007/978-3-030-72013-1_12

[2] Y. K. Tan, M. J. H. Heule, M. O. Myreen. *Verified Propagation Redundancy and Compositional UNSAT Checking in CakeML*. Int. J. Softw. Tools Technol. Transfer 25(2) (2023) 167–184. doi:10.1007/s10009-022-00690-y

[3] C. Sinz. *Towards an Optimal CNF Encoding of Boolean Cardinality Constraints*. CP 2005, LNCS 3709, 827–831. doi:10.1007/11564751_73
