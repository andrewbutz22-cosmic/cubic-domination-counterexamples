# Counterexamples to two conjectures on domination and minimum maximal matchings in regular graphs

Six connected cubic graphs on 50 vertices with independent domination number **i(G) = 16** and edge domination number (minimum maximal matching) **γ_e(G) = µ\*(G) = 15**. Three of them also have domination number **γ(G) = 16**.

**Version 2 (September 2026)** adds a census of the unsatisfiable *tight* formulas behind the construction (3-uniform, 15 variables, 20 clauses, every literal exactly twice): **at least 239** pairwise non-isomorphic connected cubic graphs of order 50 with µ\* = 15, of which **67 have i = 16** and **26 have γ = 16**. Exactly 36 of them have a cut variable — they are the 36 gluings of the eight blocks — and the other 203 are not gluings. The list is closed under one and two literal swaps, and under three swaps for the nine formulas tested exhaustively; whether it is complete is open. Every graph of this form has girth at least 5 (Lemma 7), and the 239 formulas live on only 15 distinct clause graphs, each with at least four pairs of twin clauses (Remark 8).

**Machine-checked (October 2026).** Every γ and i value of the seven graphs in `counterexamples.json` and of all 239 census classes is certified. Each lower bound has an LRAT unsatisfiability proof checked by cake_lpr, a proof checker formally verified in HOL4/CakeML, on a CNF that is independently audited to encode the claim. Each upper bound is an explicit witness set. See `verification/lrat/`.

They refute

- **(A)** Baste, Fürst, Henning, Mohr, Rautenbach, *Domination versus edge domination*, Discrete Applied Mathematics 285 (2020): γ(G) ≤ γ_e(G) for every regular graph of positive degree — false for cubic graphs (three graphs). By Proposition 7 of C. Gupta, arXiv:2608.22498, which proves (A) for all cubic graphs on at most 48 vertices, these are counterexamples of minimum possible order.
- **(B)** TxGraffiti Conjecture 3 (Davila, Brimkov, Pepper, arXiv:2507.17780, §2.3): i(G) ≤ µ\*(G) for every r-regular graph, r > 0 — false for cubic graphs (all six), and, via lexicographic products with edgeless graphs, for every r ≡ 0 (mod 3).

## Contents

| file | what |
|---|---|
| `counterexample_note.pdf` | the write-up: construction, proofs, table of the six graphs, adjacency list of G₁ |
| `counterexample_note.tex` | its source |
| `counterexamples.json` | all graphs (edge lists, graph6, the 15-edge maximal matching, a size-16 independent dominating set, i / γ / µ\*), plus the equality member R0+R0 |
| `blocks710.json` | the eight deficiency-3 formulas on seven variables from which the graphs are glued |
| `census_tight_15_20.json` | v2: all 239 classes — formula, edge list, graph6, γ / i / µ\* with witness sets, cut variables, automorphism order, nauty certificate |
| `census_tight_15_20_summary.tsv` | v2: one line per class |
| `verification/census/` | v2: search (`sa.py`), closure (`bfs2.py`), gluings, final verification, and `verify_census.py`, which re-checks every class from the definitions in about 15 minutes |
| `verification/clause-graph/` | v2: the clause-graph checks behind Lemma 7 and Remark 8 (twin pairs, automorphisms, the 217 + 563 twin-rich cubic graphs on 20 vertices) and an independent recomputation of the eight blocks R0–R7 |
| `verification/lrat/` | machine-checked certificates: LRAT proofs, checked by the formally verified checker cake_lpr, for every γ and i lower bound of the seven graphs and of the 239 census classes, with an independent audit of every CNF; and `census/check_census_structure.py`, a second from-the-definitions check of the census (tightness, unsatisfiability, girth, pairwise non-isomorphism, automorphism orders, single moves) |
| `verification/` | independent re-verification bundle: four scripts written from the definitions, results, logs, and DIMACS certificates (`ds_atmost15_*.cnf`) — any SAT solver reports UNSAT |

## The primary graph in one line

graph6 (50 vertices, cubic, connected):

```
q`?G?C??G??@????_???@?????G?????C??????G??????@????????_???????@?????????L????OS???QO_???WA???A@C???A@G???AS????@`?????aO????AI??????I?@????A_C???@GO?????oC?????OG_????@?c?????Cg??????KG??????PG??????CS????
```

The 15 edges {0,1}, {2,3}, …, {28,29} are a maximal matching (vertices 30–49 are pairwise non-adjacent), so µ\* ≤ 15; no independent dominating set of size 15 exists, so i = 16. For the graphs R6+R6, R6+R7, R7+R7 in the JSON, no dominating set of size 15 exists either.

## Check it yourself

```python
import networkx as nx, json
G = nx.from_graph6_bytes(open("g1.g6","rb").read().strip())   # or build from counterexamples.json
# then compute the independent domination number with your favourite exact method (ILP, SAT, brute force)
```

or, with no code of ours at all:

```
minisat verification/ds_atmost15_R6_R6.cnf     # prints UNSATISFIABLE
```

To reproduce every number in the note from the definitions (about two minutes):

```
cd verification
pip install pulp python-sat scipy numpy networkx
python3 verify_ids.py counterexamples.json
python3 verify_gamma.py counterexamples.json
python3 structural_check.py counterexamples.json
python3 paper_control.py
```

To re-verify the v2 census from the definitions (HiGHS + CaDiCaL + nauty, about 15 minutes):

```
pip install numpy scipy networkx pynauty python-sat
python3 verification/census/verify_census.py census_tight_15_20.json
```

and for the clause-graph statistics of Remark 8 (a few seconds; see `verification/clause-graph/CLAUSE_GRAPH_README.md`):

```
cd verification/clause-graph
python3 check_census.py ../../census_tight_15_20.json known_classes.json
python3 clause_graphs.py ../../census_tight_15_20.json graphs/cub20_tw4.g6 graphs/block_census.json
```

To re-check every γ and i value with the formally verified proof checker cake_lpr (see `verification/lrat/README.md`; the seven graphs take about six seconds with no SAT solver, and the census takes about 25 minutes because it regenerates its proofs):

```
python3 verification/lrat/check_all.py counterexamples.json verification/lrat/certs --cake PATH/TO/cake_lpr
python3 verification/lrat/census/check_census_structure.py census_tight_15_20.json counterexamples.json
```

## Construction

Take a minimally unsatisfiable 3-CNF in which every literal occurs exactly twice (15 variables, 20 clauses — the least possible, Zhang–Peitl–Szeider, SAT 2024). One pivot pair of adjacent vertices per variable, one vertex per clause joined to the endpoints named by its literals. The result is cubic; the pivot pairs form a maximal matching; unsatisfiability means no independent set of endpoints dominates the clause vertices. The formulas here are gluings of pairs of the eight deficiency-3 blocks in `blocks710.json`; which pairs give i = 16 (and which give γ = 16) is recorded in the note.

Gluing is sufficient but not necessary: of the 239 unsatisfiable tight formulas in the v2 census, only the 36 gluings have a cut variable, and counterexamples are if anything more frequent among the 203 that don't (61 with i = 16, 23 with γ = 16).

## Status

Emailed to the authors of (A) and (B) in September 2026. Comments and corrections welcome: andrew@cosmicbutz.com

## License

Code in `verification/`: MIT (see `LICENSE`). The note, the data files and this text: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
