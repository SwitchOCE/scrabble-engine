import math
# Pentanomial vs trinomial, dual-NNUE LTC test (584d9efe)
W, L, D = 16118, 15738, 32974
N = W + L + D
mu = (W + 0.5 * D) / N
var_t = (W + 0.25 * D) / N - mu * mu
p = [43, 7129, 17697, 7497, 49]
P = sum(p)
v = [0, 0.25, 0.5, 0.75, 1.0]
mu5 = sum(a * b for a, b in zip(p, v)) / P
var5 = sum(a * b * b for a, b in zip(p, v)) / P - mu5 ** 2
spg5 = math.sqrt(2 * var5)
print("games", N, "pairs", P, "mu", round(mu, 5), round(mu5, 5))
print("sigma_pg trinomial", round(math.sqrt(var_t), 4), "pentanomial", round(spg5, 4), "variance ratio", round(spg5 ** 2 / var_t, 3))
C = 800 / math.log(10)
print("Ce/t", round(C, 2))
print("nElo trinomial", round(C * (mu - .5) / math.sqrt(var_t), 2), "pentanomial", round(C * (mu5 - .5) / spg5, 2))
el = -400 * math.log10(1 / mu - 1)
print("logistic Elo", round(el, 2))
b = math.log(19)
print("D", round(C * C * b * b))
# Scrabble SPRT durations: worst case expected games T = b^2 sigma_pg^2 / dmu^2
print()
print("r(pairing gain) dmu_pp sigma_pg^2 games pairs")
for r in [1.0, 1.55, 3.0]:
    s2 = 0.25 / r
    for d in [1.0, 1.5, 2.0, 2.5, 3.0]:
        dm = d / 100
        T = b * b * s2 / dm ** 2
        print(r, d, round(s2, 4), round(T), round(T / 2))
print()
print("Elo per pp near 50%:", round(400 / math.log(10) * 4 * 0.01, 2))
# Macondo SE figures: 100k pairs SE 0.09 win points (percent)
se_unpaired = 0.5 / math.sqrt(200000) * 100
print("unpaired SE for 200k games, pct", round(se_unpaired, 4), "ratio^2", round((0.09 / se_unpaired) ** 2, 3))
# per-eval cost model
print()
for L1 in [256, 512, 1024]:
    vec = L1 // 16  # AVX2 int16 lanes per 256-bit vector
    for rows in [25, 160]:
        ops = rows * vec
        print("L1", L1, "rows", rows, "vector adds", ops, "row bytes(int8)", L1, "total KB", round(rows * L1 / 1024, 1))
    dense = 2 * L1 * 16 + 32 * 32 + 64
    print("  dense MACs (L1x2->16->32->1)", dense)
