#!/usr/bin/env python3
"""Control graphs with brute-force gamma and i (test-only; uses networkx to generate graphs)."""
import json, random, sys
import networkx as nx


def to_g6(n, E):
    bits = []
    for j in range(1, n):
        for i in range(j):
            bits.append(1 if (i, j) in E else 0)
    while len(bits) % 6:
        bits.append(0)
    out = chr(n + 63)
    for k in range(0, len(bits), 6):
        out += chr(63 + int("".join(map(str, bits[k:k + 6])), 2))
    return out


def brute(n, adj):
    closed = [(1 << v) | sum(1 << u for u in adj[v]) for v in range(n)]
    nbr = [sum(1 << u for u in adj[v]) for v in range(n)]
    full = (1 << n) - 1
    gamma = i = None
    for S in range(1 << n):
        dom = all(closed[v] & S for v in range(n))
        if not dom:
            continue
        sz = bin(S).count("1")
        if gamma is None or sz < gamma:
            gamma = sz
        if all(not (nbr[v] & S) for v in range(n) if S >> v & 1):
            if i is None or sz < i:
                i = sz
    return gamma, i


def main():
    out = sys.argv[1]
    random.seed(20261006)
    graphs = {}
    cand = [("petersen", nx.petersen_graph())]
    for n in (10, 12, 14, 16, 18):
        for t in range(3):
            cand.append(("rc%d_%d" % (n, t), nx.random_regular_graph(3, n, seed=random.randrange(10**9))))
    cand.append(("cycle9", nx.cycle_graph(9)))
    cand.append(("cube", nx.hypercube_graph(3)))
    ds = nx.Graph([(0, 1), (0, 2), (0, 3), (0, 4), (1, 5), (1, 6), (1, 7)])   # double star: gamma 2, i 4
    cand.append(("doublestar33", ds))
    iso = nx.path_graph(6); iso.add_node(6)                                     # isolated vertex
    cand.append(("path6_plus_isolated", iso))
    found = 0
    for t in range(400):                                                        # random graphs with gamma < i
        H = nx.gnp_random_graph(14, 0.22, seed=random.randrange(10**9))
        adj = {v: set(H[v]) for v in range(14)}
        ga, ii = brute(14, adj)
        if ga < ii:
            cand.append(("gnp14_%d" % t, H)); found += 1
            if found == 4:
                break
    for name, H in cand:
        H = nx.convert_node_labels_to_integers(H)
        n = H.number_of_nodes()
        E = {tuple(sorted(e)) for e in H.edges()}
        adj = {v: set(H[v]) for v in range(n)}
        gamma, i = brute(n, adj)
        graphs[name] = {"n": n, "edges": sorted(map(list, E)), "graph6": to_g6(n, E), "gamma": gamma, "i": i}
        print(name, n, "gamma", gamma, "i", i)
    json.dump(graphs, open(out, "w"), indent=0)


if __name__ == "__main__":
    main()
