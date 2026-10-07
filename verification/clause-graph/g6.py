"""graph6 reader (from the clause-graph study's perD.py)."""


def read_g6(line):
    """graph6 -> (n, edge list) for small graphs (n < 63)."""
    s = line.strip()
    n = ord(s[0]) - 63
    bits = []
    for ch in s[1:]:
        x = ord(ch) - 63
        for k in range(5, -1, -1):
            bits.append((x >> k) & 1)
    edges = []
    k = 0
    for j in range(1, n):
        for i in range(j):
            if bits[k]:
                edges.append((i, j))
            k += 1
    return n, edges
