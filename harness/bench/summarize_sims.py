#!/usr/bin/env python3
"""Turn the output of sims.sh into a markdown table of rollouts/s and nodes/s.

rollouts = one candidate played out to the ply horizon.
  Macondo: iterationCt x 15 candidates (every candidate, every iteration; no pruning).
  MAGPIE:  Iters (total over candidates).
  wolges:  sum of the per-candidate `rollouts` column.
nodes = moves played in rollouts (candidate + ply moves).
  Macondo, MAGPIE: the engine's own node count.
  wolges: rollouts x 5 (candidate + 4 plies), an upper bound: rollouts that reach
  the end of the game stop early.
"""
import re
import sys

rows = []
cur = None
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    m = re.match(r"### (\w+) (pos-\d+)\.gcg threads=(\d+)", line)
    if m:
        cur = {"e": m[1], "p": m[2], "t": int(m[3])}
        rows.append(cur)
        continue
    if cur is None:
        continue
    if m := re.search(r"time taken: ([\d.]+), nps: ([\d.]+), nodes: (\d+)", line):
        cur["secs"], cur["nps"] = float(m[1]), float(m[2])
    if m := re.search(r"iterationCt:(\d+)", line):
        cur["roll"] = int(m[1]) * 15
    if m := re.match(r"Iters: (\d+)", line):
        cur["roll"] = int(m[1])
    if m := re.match(r"Time: ([\d.]+)", line):
        cur["secs"] = float(m[1])
    if m := re.match(r"Nps: (\d+)", line):
        cur["nps"] = float(m[1])
    if m := re.match(r"sim: \d+ more iterations, (\d+) ms", line):
        cur["secs"] = int(m[1]) / 1000
    if m := re.match(r"candidates_listed=\d+ rollouts_total=(\d+)", line):
        cur["roll"] = int(m[1])
        cur["nps"] = cur["roll"] * 5 / cur["secs"]

print("| Position | Threads | Macondo rollouts/s | MAGPIE rollouts/s | wolges rollouts/s | Macondo nodes/s | MAGPIE nodes/s | wolges nodes/s (≤) |")
print("| --- | --- | --- | --- | --- | --- | --- | --- |")
keys = sorted({(r["p"], r["t"]) for r in rows})
for p, t in keys:
    d = {r["e"]: r for r in rows if r["p"] == p and r["t"] == t}
    def f(e, k):
        r = d.get(e)
        if not r or k not in r:
            return "-"
        v = r[k] / r["secs"] if k == "roll" else r[k]
        return f"{v:,.0f}"
    print(f"| {p} | {t} | {f('macondo','roll')} | {f('magpie','roll')} | {f('wolges','roll')} | "
          f"{f('macondo','nps')} | {f('magpie','nps')} | {f('wolges','nps')} |")
