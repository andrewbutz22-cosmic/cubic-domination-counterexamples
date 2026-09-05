#!/usr/bin/env python3
"""
Fourth, structurally different exhaustive computation of i(G) for the JSON graphs.

Premises (each VERIFIED from the adjacency before use):
  P1  vertices 30..49 ("clause vertices") are pairwise non-adjacent;
  P2  for k = 0..14, vertex 2k is adjacent to 2k+1, and every other neighbour of 2k, 2k+1 is a clause vertex.

Given P1/P2, an independent dominating set S is determined by C = S ∩ {30..49} (any C is independent)
plus one choice per "free" pair:  for pair {2k,2k+1} let N(C) be the literal vertices adjacent to C;
  - both endpoints in N(C): neither may be in S, both are dominated               -> contributes 0
  - exactly one endpoint in N(C): the other endpoint MUST be in S (nothing else can dominate it) -> 1
  - neither endpoint in N(C): exactly one of the two must be in S                  -> 1 (a free choice)
So |S| = |C| + 15 - #(pairs fully inside N(C)), and S exists iff the forced + free literal choices
dominate every clause vertex outside C.  We enumerate all 2^20 sets C and, for each, all free choices.
"""
import json, sys, time

def run(name, n, edges):
    adj = [set() for _ in range(n)]
    for u, v in edges:
        adj[u].add(v); adj[v].add(u)
    nb = [sum(1 << u for u in adj[v]) for v in range(n)]
    LIT = (1 << 30) - 1
    CL = ((1 << 50) - 1) ^ LIT
    # premises
    assert n == 50
    for c in range(30, 50):
        assert nb[c] & CL == 0, "P1 fails"
    for k in range(15):
        a, b = 2 * k, 2 * k + 1
        assert (nb[a] >> b) & 1 and (nb[b] >> a) & 1, "P2 fails (pair edge)"
        assert (nb[a] & LIT) == (1 << b) and (nb[b] & LIT) == (1 << a), "P2 fails (literal neighbours)"
    EVEN = sum(1 << (2 * k) for k in range(15))
    cl_nb_lit = [nb[30 + j] & LIT for j in range(20)]           # literal neighbours of clause j
    lit_nb_cl = [(nb[v] & CL) >> 30 for v in range(30)]          # clause neighbours (as 20-bit mask) of literal v
    ALLCL = (1 << 20) - 1
    best = 99; best_wit = None
    t0 = time.time()
    NC = [0] * (1 << 20)
    for C in range(1, 1 << 20):
        low = C & -C
        NC[C] = NC[C ^ low] | cl_nb_lit[low.bit_length() - 1]
    for C in range(1 << 20):
        nc = NC[C]
        e = nc & EVEN
        o = (nc >> 1) & EVEN
        full = e & o
        size = bin(C).count("1") + 15 - bin(full).count("1")
        if size > best or size > 16:
            continue                        # cannot beat / we only care about <=16
        # forced literals: pair with only 2k in N(C) -> 2k+1 forced; only 2k+1 in N(C) -> 2k forced
        forced = ((e & ~o) << 1) | (o & ~e)
        free = EVEN & ~e & ~o               # bit 2k marks a free pair
        dom = C
        f = forced
        while f:
            lw = f & -f; f ^= lw
            dom |= lit_nb_cl[lw.bit_length() - 1]
        need = ALLCL & ~dom
        # choose one literal per free pair to cover `need`
        fp = []
        g = free
        while g:
            lw = g & -g; g ^= lw
            k = lw.bit_length() - 1
            fp.append((lit_nb_cl[k], lit_nb_cl[k + 1], k))
        found = None
        for mask in range(1 << len(fp)):
            d = 0; S = forced
            for i, (A, B, k) in enumerate(fp):
                if mask >> i & 1:
                    d |= B; S |= 1 << (k + 1)
                else:
                    d |= A; S |= 1 << k
            if d & need == need:
                found = S; break
        if found is not None and size < best:
            best = size
            best_wit = sorted([v for v in range(30) if found >> v & 1] + [30 + j for j in range(20) if C >> j & 1])
    return best, best_wit, time.time() - t0

if __name__ == "__main__":
    data = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "counterexamples.json"))
    for key, rec in data.items():
        best, wit, dt = run(key, rec["n"], rec["edges"])
        # re-check witness from the bare definitions
        adj = [set() for _ in range(rec["n"])]
        for u, v in rec["edges"]:
            adj[u].add(v); adj[v].add(u)
        W = set(wit)
        ind = all(not (adj[v] & W) for v in W)
        dom = all(v in W or (adj[v] & W) for v in range(rec["n"]))
        print(f"{key}: i(G) = {best} (search capped at 16: {'no set of size <= 15 exists' if best == 16 else 'size-15 set found'})  "
              f"witness valid={ind and dom} |W|={len(W)}  {dt:.1f}s  witness={wit}")
