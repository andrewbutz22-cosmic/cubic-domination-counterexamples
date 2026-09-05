# Independent verification: i(G) > µ*(G) on the `counterexamples.json` graphs

Date: 2026-09-04. All code written from the definitions (`verify_ids.py`, `structural_check.py`); nothing from the JSON beyond the raw data (edge lists, graph6 strings, the pivot matching, the claimed values) was reused. Every witness set returned by any engine was re-checked against the bare definitions before being counted.

## Verdict

**The claim holds.** G₁ (= JSON entry `R3+R3`) is a simple connected 3-regular graph on 50 vertices with **i(G₁) = 16** (no independent dominating set of size ≤ 15 exists — certified by four independent exhaustive engines) and **µ*(G₁) = 15** (the pivot matching {0,1},…,{28,29} is a maximal matching of size 15, and 15 is a lower bound for every cubic graph with 75 edges). So i(G₁) = 16 > 15 = µ*(G₁): "i(G) ≤ µ*(G) for all r-regular graphs" is false, already at r = 3. The same certificate refutes the stronger "every maximal matching M of a connected cubic graph admits an IDS of size ≤ |M|" (the pivot matching has |M| = 15 < i(G₁)). The other five claimed graphs behave identically.

## Input notes (data discrepancies — none affect the claim)

* The graph6 string pasted in the task text is **204 characters, not a valid 50-vertex graph6 string** (n = 50 needs 1 + 205 = 206 chars; my decoder rejects it). It is the JSON's `R3+R3` string with the two `_` characters at positions 16 and 55 stripped — a markdown-italics artefact. Restoring them gives a byte-identical string, so G₁ = `R3+R3` and all G₁ numbers below come from the JSON edge list, which decodes from / re-encodes to that graph6 string exactly.
* For the six graphs with claimed i = 16, `graph6` and `edges` agree exactly (decode and re-encode both ways). For `R0+R0` the `graph6` string is a **relabelled copy** of the edge list (134 edges differ as labelled pairs; the two graphs are isomorphic, and both have i = 15, µ* = 15). Cosmetic.
* The JSON's own `ids` sets are valid independent dominating sets of the stated sizes (16 for the six, 15 for `R0+R0`).

## What was checked and how

1. **Graph sanity.** From the edge list: no loops, no repeated pairs, all endpoints in 0..49; degree multiset {3}; BFS reaches all 50 vertices. Own graph6 decoder/encoder (column-major upper triangle, 6-bit chunks + 63) round-trips all seven strings; as a side check it agrees with networkx on the seven strings and on 200 random graphs.
2. **Matching.** {2k, 2k+1}, k = 0..14: all 15 pairs are edges, pairwise vertex-disjoint, and every one of the 75 edges has an endpoint in {0..29} → maximal, so µ* ≤ 15. Also, in a cubic graph each edge of a maximal matching dominates at most 1 + 2·2 = 5 edges, so µ* ≥ ⌈75/5⌉ = 15 for every cubic graph on 50 vertices; µ* = 15 is therefore forced. Confirmed anyway by (a) an ILP over the 75 edges (matching constraints + every edge dominated; CBC) and (b) branch-and-bound on the line graph L(G) (75 vertices, 4-regular): a maximal matching of G is exactly an independent dominating set of L(G).
3. **i(G).** Four exhaustive engines, none seeded with the others' answers:
   * (a) ILP: x_v ∈ {0,1}, min Σx_v, x_u + x_v ≤ 1 per edge, x_v + Σ_{u∈N(v)} x_u ≥ 1 per vertex — solved with CBC (pulp) and separately with HiGHS (`scipy.optimize.milp`); plus an explicit CBC feasibility run with Σx_v ≤ i−1 (infeasible).
   * (b) Own bitset branch-and-bound: pick an undominated vertex with the fewest still-allowed vertices in its closed neighbourhood, branch on which one enters S (later branches forbid the earlier choice), forbid N[S], bound |S| + ⌈#undominated / max new coverage⌉. Run as an optimiser from scratch (upper bound n).
   * (c) SAT (CaDiCaL via pysat): independence and domination clauses + sequential-counter cardinality ≤ k. k = i−1 → UNSAT, k = i → SAT.
   * (d) Structural enumeration (`structural_check.py`): after verifying that vertices 30..49 are pairwise non-adjacent and that each vertex 2k has neighbours 2k+1 plus vertices ≥ 30, every IDS is determined by C = S ∩ {30..49} plus one forced/free choice per pair; all 2²⁰ sets C × all free choices are enumerated. Completely different search organisation from (b).
   * Engine validation: brute force over all 2ⁿ vertex subsets (12 random connected cubic graphs, n ≤ 20) and all 2ᵐ edge subsets (8 graphs, m ≤ 21) — 0 mismatches against (a)/(b)/(c) and the µ* engines; 30 further random connected cubic graphs (n = 20..36): all engines agree on i and µ*.

## Numbers

| graph | simple / 3-regular / connected | pivot matching maximal | i(G): CBC · HiGHS · B&B (nodes) · SAT ≤i−1 / ≤i · structural | µ*(G): ILP · L(G)-B&B (nodes) | claimed i / µ* | time, all engines |
|---|---|---|---|---|---|---|
| **R3+R3 = G₁** | yes / yes / yes | yes | **16** · 16 · 16 (61 034) · UNSAT / SAT · 16 | **15** · 15 (171) | 16 / 15 | 2.3 s + 1.9 s |
| R3+R6 | yes / yes / yes | yes | 16 · 16 · 16 (65 850) · UNSAT / SAT · 16 | 15 · 15 (257) | 16 / 15 | 2.7 s + 1.7 s |
| R3+R7 | yes / yes / yes | yes | 16 · 16 · 16 (72 075) · UNSAT / SAT · 16 | 15 · 15 (247) | 16 / 15 | 2.6 s + 1.8 s |
| R6+R6 | yes / yes / yes | yes | 16 · 16 · 16 (76 034) · UNSAT / SAT · 16 | 15 · 15 (453) | 16 / 15 | 3.5 s + 1.7 s |
| R6+R7 | yes / yes / yes | yes | 16 · 16 · 16 (83 877) · UNSAT / SAT · 16 | 15 · 15 (443) | 16 / 15 | 2.9 s + 1.7 s |
| R7+R7 | yes / yes / yes | yes | 16 · 16 · 16 (86 520) · UNSAT / SAT · 16 | 15 · 15 (314) | 16 / 15 | 2.8 s + 1.7 s |
| R0+R0 (not a counterexample) | yes / yes / yes | yes | 15 · 15 · 15 (4 606) · UNSAT / SAT · 15 | 15 · 15 (198) | 15 / 15 | 1.5 s + 1.3 s |
| Petersen (control) | yes / yes / yes | — | 3 · 3 · 3 (10) · UNSAT / SAT · — | 3 · 3 (13) | 3 / 3 | 0.9 s |
| K₄, K₃,₃, Q₃ (controls) | yes | — | 1, 3, 2 (all engines) | 2, 3, 3 (both engines) | — | < 0.1 s each |

Per-engine wall times on G₁: CBC 0.57 s, HiGHS 0.28 s, B&B 0.28 s, SAT (both calls) 0.53 s, µ* ILP 0.01 s, L(G) B&B < 0.01 s, structural enumeration 1.9 s. Whole battery (all graphs, controls, 30-graph random agreement sweep): 21 s wall, single core, Python 3.11.

Witnesses for G₁: IDS of size 16 from the B&B: {12, 16, 20, 28, 32, 33, 35, 36, 37, 39, 42, 44, 45, 46, 48, 49}; the JSON's {1, 3, 4, 7, 9, 11, 12, 15, 17, 19, 20, 23, 24, 27, 30, 40} is also valid. Minimum maximal matching of size 15: the pivot matching itself (returned by the ILP).

## Discrepancies

None between engines, and none between my numbers and the claimed values, on any graph. The only issues are the two data-file cosmetics above (the pasted string's missing underscores; `R0+R0`'s relabelled graph6). One observation worth recording: the mechanism is not just CNF-unsatisfiability. All seven `K` fields are 3-uniform CNFs on 15 variables / 20 clauses with every literal occurring exactly twice, and all seven are UNSAT (CaDiCaL and brute force over 2¹⁵ assignments agree), and each graph equals the literal/clause incidence graph of its `K` plus the 15 variable edges. Unsatisfiability rules out literal-only sets of size 15, but `R0+R0` still has i = 15 via a mixed set using three clause-side vertices (e.g. {5, 7, 10, 12, 15, 17, 18, 20, 22, 25, 26, 28, 32, 33, 40}); the six counterexamples are the ones where the exhaustive search over mixed sets also comes up empty.

## Files

`verify_ids.py` (all engines, controls, sweep; writes `results.json`), `structural_check.py` (engine d), `results.json` (every number and witness), `run.log` / `structural.log` (raw output), `pasted_g6.txt` (the string as pasted).

---

# Part 2 — domination number γ (no independence requirement)

Requested for `R6+R6`, `R6+R7`, `R7+R7`; computed for all seven graphs. Code: `verify_gamma.py` (engines, controls, validation), `paper_control.py` (external control, see below).

## Verdict

**γ = 16 for all three requested graphs; no dominating set of size 15 exists.** Five independent engines agree on every graph, and every witness was re-checked against the definition. Since µ* = γ_e = 15 (Part 1), each of `R6+R6`, `R6+R7`, `R7+R7` has **γ(G) = 16 > 15 = γ_e(G)**: they refute the Baste–Fürst–Henning–Mohr–Rautenbach conjecture (γ ≤ γ_e for every regular graph, DAM 2020) in the cubic case — the case that arXiv:2608.22498 (Aug 2026) explicitly leaves open after proving Δ ≥ 7 — not just the stronger TxGraffiti/DBP conjecture i ≤ γ_e. The other three claimed counterexamples do not: γ(`R3+R3`) = 14, γ(`R3+R6`) = γ(`R3+R7`) = 15 (they refute only i ≤ γ_e).

## Engines

* (a) ILP: min Σx_v s.t. x_v + Σ_{u∈N(v)} x_u ≥ 1 — CBC (pulp) and HiGHS (`scipy.optimize.milp`), plus an explicit CBC feasibility run with Σx_v ≤ γ−1 (infeasible every time).
* (b) Own bitset branch-and-bound: branch on an undominated vertex with the fewest still-allowed dominators (each candidate in turn, earlier candidates forbidden afterwards); bounds |S| + ⌈#undominated / max new coverage⌉ and |S| + (greedy packing of undominated vertices with pairwise-disjoint allowed-dominator sets). Run from scratch, upper bound n.
* (c) SAT (CaDiCaL via pysat): domination clauses + sequential-counter cardinality ≤ k; k = γ−1 UNSAT, k = γ SAT.
* (d) Structural enumeration: all 2²⁰ clause-side subsets C, then an exact hitting-set search on the literal side (every pair {2k,2k+1} not fully dominated by C, and every clause vertex outside C, must be hit); premises re-verified from the adjacency.
* Validation: brute force over all 2ⁿ subsets on 12 random connected cubic graphs (n ≤ 20) and an agreement sweep on 30 random connected cubic graphs (n = 20..36) — 0 mismatches; controls Petersen γ = 3, K₄ 1, K₃,₃ 2, Q₃ 2.
* **External control** (`paper_control.py`): the Theorem-2 graph of arXiv:2608.22498 rebuilt from the formula printed in its Appendix A (checked: every literal exactly twice, UNSAT). My engines reproduce every certified value there — γ = 14, γ_e = 15, the printed 14-vertex set dominates, and M is the unique maximal matching of size 15 — and I also get i = 15 for it. That graph is **isomorphic to `R0+R0`** (networkx VF2, diagnostic only), which is why `R0+R0` has γ = 14 and i = 15 here.

## Numbers

| graph | γ: CBC · HiGHS · B&B (nodes) · SAT ≤γ−1 / ≤γ · structural | CBC feasibility at γ−1 | γ_e = µ* | claimed / expected | engine times (CBC · feas · HiGHS · B&B · SAT · structural) |
|---|---|---|---|---|---|
| **R6+R6** | **16** · 16 · 16 (222 501) · UNSAT / SAT · 16 | infeasible | 15 | 16 | 0.84 · 1.48 · 0.42 · 2.06 · 0.72 · 1.3 s |
| **R6+R7** | **16** · 16 · 16 (231 037) · UNSAT / SAT · 16 | infeasible | 15 | 16 | 0.90 · 1.50 · 0.24 · 2.12 · 0.61 · 1.5 s |
| **R7+R7** | **16** · 16 · 16 (241 854) · UNSAT / SAT · 16 | infeasible | 15 | 16 | 0.83 · 1.37 · 0.21 · 2.23 · 0.84 · 1.6 s |
| R3+R3 | 14 · 14 · 14 (595) · UNSAT / SAT · 14 | infeasible | 15 | — | 0.03 · 0.03 · 0.09 · 0.01 · 0.47 · 0.4 s |
| R3+R6 | 15 · 15 · 15 (10 147) · UNSAT / SAT · 15 | infeasible | 15 | — | 0.36 · 0.36 · 0.06 · 0.12 · 0.42 · 0.5 s |
| R3+R7 | 15 · 15 · 15 (10 791) · UNSAT / SAT · 15 | infeasible | 15 | — | 0.37 · 0.45 · 0.05 · 0.11 · 0.34 · 0.5 s |
| R0+R0 (= arXiv:2608.22498 Thm 2 graph) | 14 · 14 · 14 (609) · UNSAT / SAT · 14 | infeasible | 15 | 14 (paper) | 0.02 · 0.02 · 0.08 · 0.01 · 0.15 · 0.3 s |
| Petersen | 3 · 3 · 3 (13) · UNSAT / SAT · — | infeasible | 3 | 3 | < 0.1 s |

Whole γ battery: 29 s wall (single core, Python 3.11). Minimum dominating sets of size 16: `R6+R6` {12, 26, 28, 29, 32, 33, 34, 35, 37, 39, 42, 43, 44, 45, 47, 49}; `R6+R7` {12, 21, 28, 29, 32, 33, 34, 35, 37, 39, 42, 43, 44, 45, 47, 49}; `R7+R7` {7, 21, 28, 29, 32, 33, 34, 35, 37, 39, 42, 43, 44, 45, 47, 49}. DIMACS files `ds_atmost15_<graph>.cnf` (575 vars, 1120 clauses; vertex v ↔ variable v+1) encode "dominating set of size ≤ 15" for the three graphs — any SAT solver should report UNSAT.

Also checked: in all seven graphs, and in the paper's, the pivot matching is the **unique** maximal matching of size 15 (SAT enumeration with blocking clauses), so it is the unique minimum maximal matching and the transversal reduction of arXiv:2608.22498 §2 fails on all of them (Φ(G, M) = K is UNSAT).

## Literature placement (from the paper text supplied, arXiv:2608.22498, and arXiv:1906.10420)

* Conjecture 1 [BFH+20]: γ(G) ≤ γ_e(G) for every Δ-regular G, Δ ≥ 1. Known true for cubic claw-free [BFH+20], claw-free δ ≥ 2 [CDY23], fork-free δ ≥ 2 [MP24], Δ ≥ 9 by combining bounds, and Δ ≥ 7 via the lopsided Local Lemma [2608.22498, Thm 1]; open for Δ ∈ {3,…,6}. Cubic graphs on ≤ 48 vertices satisfy it [2608.22498, Prop. 7, via µ(3,2,2) = 20 of ZPS24]. **So n = 50 is the least possible order of a cubic counterexample, and `R6+R6`, `R6+R7`, `R7+R7` are counterexamples of minimum order** (modulo the correctness of Prop. 7 / ZPS24).
* Consistency checks against proved statements: the multiplicative bound γ ≤ (7/6 − 1/204)·γ_e for cubic graphs [BFH+20] holds (16/15 = 1.067 < 1.162); the graphs are far from claw-free (all 50 vertices are induced-claw centres — every clause vertex has three pairwise non-adjacent literal neighbours), so the claw-free theorem is not contradicted; they contain forks. Theorem 2 of 2608.22498 says of its own instance "though the inequality holds there too" — true for that instance (`R0+R0`, γ = 14) and for `R3+R3`, `R3+R6`, `R3+R7`, but false for the three R6/R7 instances of the same construction.
* The stronger TxGraffiti/DBP conjecture i ≤ γ_e [DBP25], stated open for every Δ ≥ 3 in 2608.22498, is refuted at Δ = 3 by all six graphs of Part 1.

## Discrepancies

None: all engines agree on every graph; the three requested values match the expected 16; the external control reproduces the published certificate exactly.
