# Census of unsatisfiable tight (15,20) formulas — data for v1.1.0

`census_tight_15_20.json` — 239 isomorphism classes of unsatisfiable 3-uniform CNF formulas on 15 variables with 20 clauses in which every literal occurs exactly twice (hence MU, since µ(3,2,2)=20 [ZPS24]). Keyed by the hex nauty certificate of G(F). Per class:
`K` (clauses, signed variables 1..15), `n`=50, `edges`, `pivot_matching`, `gamma`, `gamma_set`, `i`, `ids` (an independent dominating set of size i), `mu` (=µ*=γ_e=15), `mmm` (a minimum maximal matching), `graph6`, `certificate_sha256`, `cut_variables` (variable → sizes of the sides), `glue_free`, `constructed` (R_a+R_b when the formula is a gluing), `posted_name` (name in counterexamples.json, if any), `girth`, `aut_order`, `one_swap_unsat_neighbors` (sha256 of the classes reachable by a single literal swap — always the class itself), `discovered_by` (sa / bfs / gluing).
Vertex convention as in counterexamples.json: variable j → vertices 2(j-1) (positive), 2(j-1)+1 (negative); clause c → vertex 30+c.

`census_tight_15_20_summary.tsv` — one line per class.

Totals: 239 classes; i=16: 67; gamma=16: 26; no cut variable: 203 (i=16: 61, gamma=16: 23); cut variable: 36 = the 36 gluings R_a+R_b, 0<=a<=b<=7. All graphs have girth 5. Automorphism group orders: 1:96, 2:97, 3:2, 4:22, 6:1, 8:14, 16:3, 24:1, 32:2, 128:1.

Code (Python 3.12, numpy/scipy/networkx, pynauty, python-sat):
`tight.py` core (bitset model counting over 2^15 assignments, MU test, G(F), cut variables, nauty certificates, HiGHS ILP for gamma/i/µ*, CaDiCaL cross-check);
`sa.py` simulated annealing search (swap moves, energy = #models, exhaustive single-swap scan at <=6 models, basin hopping);
`bfs2.py` closure under one and two swaps; `merge_bfs.py` verifies closure finds into the census; `gluings.py` the 36 R-block gluings;
`closure3b.py` (+ `closure3b_driver.py`, results in `closure3b_results.jsonl`) exhaustive 3-swap closure test per formula — every valid 2-swap endpoint, exact matrix test for a killing third swap, bitset confirmation; run on 9 formulas (indices 0, 14, 46, 53, 200, 222 glue-free; 12 = R6+R7, 122 = R3+R3, 106 = R0+R0), 134,571 UNSAT 3-swap endpoints, none outside the census;
`tally.py` aggregation; `finalize.py` independent re-verification of every class and emission of the data file; `controls.py` reproduces the seven posted graphs.
`hits.jsonl` raw SA hits (seeded census); `hits_test.jsonl` 92 post-closure SA hits from fresh seeds, all inside the census.

Verification per class (finalize.py): tight; models=0; MU by deleting each clause; certificate recomputed; cubic connected order 50, 75 edges; gamma and i by HiGHS with the optimal sets checked by definition; no (independent) dominating set of size gamma-1 (i-1) by CaDiCaL 1.5.3 (sequential counter); µ*=15 by ILP over maximal matchings.
