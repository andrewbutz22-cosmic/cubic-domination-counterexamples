"""SA search for UNSAT tight 3-uniform (v=15, m=20) formulas, every literal exactly twice.

State: 60 slots; clause c = slots[3c:3c+3]. Move: swap two slots in different clauses
(keeps every literal at exactly two occurrences). Energy: number of satisfying assignments.
"""
import argparse, json, math, random, time, sys
from tight import LIT_MASK, FULL, V, M, is_tight, is_mu, canon_key, canonical_formula

NSLOT = 3 * M


def random_state(rng):
    lits = [s * j for j in range(1, V + 1) for s in (1, -1) for _ in range(2)]
    while True:
        rng.shuffle(lits)
        if all(len({abs(l) for l in lits[3 * c:3 * c + 3]}) == 3 for c in range(M)):
            return lits


def clause_masks(slots):
    return [LIT_MASK[slots[3 * c]] | LIT_MASK[slots[3 * c + 1]] | LIT_MASK[slots[3 * c + 2]] for c in range(M)]


def energy_from(cms):
    m = FULL
    for cm in cms:
        m &= cm
    return m.bit_count()


def valid_swap(slots, s, t):
    cs, ct = s // 3, t // 3
    if cs == ct:
        return False
    a, b = slots[s], slots[t]
    if a == b:
        return False
    # variable of b must be new to clause cs (other two slots), and vice versa
    va, vb = abs(a), abs(b)
    for k in range(3 * cs, 3 * cs + 3):
        if k != s and abs(slots[k]) == vb:
            return False
    for k in range(3 * ct, 3 * ct + 3):
        if k != t and abs(slots[k]) == va:
            return False
    return True


def cm_of(slots, c):
    return LIT_MASK[slots[3 * c]] | LIT_MASK[slots[3 * c + 1]] | LIT_MASK[slots[3 * c + 2]]


def swap_energy(slots, cms, s, t):
    """Energy after swapping slots s,t (not applied)."""
    cs, ct = s // 3, t // 3
    slots[s], slots[t] = slots[t], slots[s]
    ns, nt = cm_of(slots, cs), cm_of(slots, ct)
    slots[s], slots[t] = slots[t], slots[s]
    m = ns & nt
    for c in range(M):
        if c != cs and c != ct:
            m &= cms[c]
    return m.bit_count(), ns, nt


def apply_swap(slots, cms, s, t, ns, nt):
    slots[s], slots[t] = slots[t], slots[s]
    cms[s // 3], cms[t // 3] = ns, nt


def full_scan(slots, cms, E):
    """Best single swap; returns (E', s, t, ns, nt) or None if none strictly improves."""
    best = None
    for s in range(NSLOT):
        for t in range(s + 1, NSLOT):
            if not valid_swap(slots, s, t):
                continue
            e, ns, nt = swap_energy(slots, cms, s, t)
            if e < E and (best is None or e < best[0]):
                best = (e, s, t, ns, nt)
                if e == 0:
                    return best
    return best


def anneal(slots, cms, rng, steps, T0, T1, scan_below, stats, deadline=None):
    E = energy_from(cms)
    best = E
    lam = math.log(T1 / T0) / max(1, steps)
    last_scan_E, last_scan_k = None, -10**9
    for k in range(steps):
        T = T0 * math.exp(lam * k)
        if E == 0:
            stats["best"] = 0
            return 0
        if deadline and (k & 1023) == 0 and time.time() > deadline:
            break
        if E <= scan_below and (last_scan_E is None or E < last_scan_E or k - last_scan_k > 3000):
            last_scan_E, last_scan_k = E, k
            mv = full_scan(slots, cms, E)
            stats["scans"] += 1
            if mv is not None:
                e, s, t, ns, nt = mv
                apply_swap(slots, cms, s, t, ns, nt)
                E = e
                best = min(best, E)
                last_scan_E = None  # allow immediate rescan at the new low
                continue
        s = rng.randrange(NSLOT)
        t = rng.randrange(NSLOT)
        if not valid_swap(slots, s, t):
            continue
        e, ns, nt = swap_energy(slots, cms, s, t)
        stats["moves"] += 1
        if e <= E or rng.random() < math.exp(-(e - E) / T):
            apply_swap(slots, cms, s, t, ns, nt)
            E = e
            if E < best:
                best = E
    stats["best"] = min(stats.get("best", 10**9), best)
    stats["last_best"] = best
    return E


def perturb(slots, cms, rng, k):
    done = 0
    while done < k:
        s, t = rng.randrange(NSLOT), rng.randrange(NSLOT)
        if valid_swap(slots, s, t):
            e, ns, nt = swap_energy(slots, cms, s, t)
            apply_swap(slots, cms, s, t, ns, nt)
            done += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--time", type=float, default=600)
    ap.add_argument("--out", default="hits.jsonl")
    ap.add_argument("--steps", type=int, default=60000)
    ap.add_argument("--T0", type=float, default=20.0)
    ap.add_argument("--T1", type=float, default=0.4)
    ap.add_argument("--scan-below", type=int, default=6)
    ap.add_argument("--hops", type=int, default=20, help="basin hops after each hit before restart")
    ap.add_argument("--kick", type=int, default=6, help="random swaps per basin hop")
    ap.add_argument("--hop-steps", type=int, default=15000)
    ap.add_argument("--hop-T0", type=float, default=3.0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    t0 = time.time()
    stats = {"moves": 0, "scans": 0, "anneals": 0, "hits": 0, "hops": 0, "hop_hits": 0}
    seen = set()
    out = open(args.out, "a")

    def record(slots, how):
        K = [list(slots[3 * c:3 * c + 3]) for c in range(M)]
        assert is_tight(K), K
        assert is_mu(K), K  # implied by ZPS24 (mu(3,2,2)=20) but check anyway
        cert = canon_key(K)
        new = cert not in seen
        seen.add(cert)
        rec = {"t": round(time.time() - t0, 1), "seed": args.seed, "how": how, "new_in_run": new,
               "cert": cert, "K": canonical_formula(K)}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        stats["hits"] += 1
        return new

    while time.time() - t0 < args.time:
        slots = random_state(rng)
        cms = clause_masks(slots)
        stats["anneals"] += 1
        E = anneal(slots, cms, rng, args.steps, args.T0, args.T1, args.scan_below, stats, deadline=t0 + args.time)
        if args.verbose:
            print(f"anneal {stats['anneals']} best={stats.get('last_best')} final={E} t={time.time()-t0:.0f}s moves={stats['moves']}", flush=True)
        if E != 0:
            continue
        record(slots, "anneal")
        # basin hopping around the hit
        for h in range(args.hops):
            if time.time() - t0 >= args.time:
                break
            saved = list(slots)
            perturb(slots, cms, rng, args.kick)
            stats["hops"] += 1
            E = anneal(slots, cms, rng, args.hop_steps, args.hop_T0, args.T1, args.scan_below, stats, deadline=t0 + args.time)
            if E == 0:
                stats["hop_hits"] += 1
                if record(slots, "hop"):
                    pass
            else:
                slots = saved
                cms = clause_masks(slots)
    el = time.time() - t0
    print(json.dumps({"seed": args.seed, "elapsed": round(el, 1), "distinct_certs": len(seen),
                      **stats, "moves_per_s": round(stats["moves"] / el)}))


if __name__ == "__main__":
    main()
