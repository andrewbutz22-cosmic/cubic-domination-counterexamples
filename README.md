# Counterexamples to two conjectures on domination and minimum maximal matchings in regular graphs

Six connected cubic graphs on 50 vertices with independent domination number **i(G) = 16** and edge domination number (minimum maximal matching) **γ_e(G) = µ\*(G) = 15**. Three of them also have domination number **γ(G) = 16**.

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

## Construction

Take a minimally unsatisfiable 3-CNF in which every literal occurs exactly twice (15 variables, 20 clauses — the least possible, Zhang–Peitl–Szeider, SAT 2024). One pivot pair of adjacent vertices per variable, one vertex per clause joined to the endpoints named by its literals. The result is cubic; the pivot pairs form a maximal matching; unsatisfiability means no independent set of endpoints dominates the clause vertices. The formulas here are gluings of pairs of the eight deficiency-3 blocks in `blocks710.json`; which pairs give i = 16 (and which give γ = 16) is recorded in the note.

## Status

Emailed to the authors of (A) and (B) in September 2026. Comments and corrections welcome: andrew@cosmicbutz.com

## License

Code in `verification/`: MIT (see `LICENSE`). The note, the data files and this text: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
