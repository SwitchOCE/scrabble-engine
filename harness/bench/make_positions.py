#!/usr/bin/env python3
"""Cut a full GCG into position files for the speed benchmark.

pos-NN.gcg holds the header, the first NN move events, and a `#rackK` line
giving the rack of the side to move (taken from event NN+1). Every engine we
test (Quackle, Macondo, MAGPIE, wolges) can load that, so they all see the
same board and rack.

Usage: make_positions.py FULL.gcg OUTDIR N [N ...]
"""
import os
import sys


def main():
    src, outdir, ns = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3:]]
    lines = open(src, encoding="utf-8").read().splitlines()
    header = [l for l in lines if l.startswith("#")]
    events = [l for l in lines if l.startswith(">")]
    nicks = [h.split()[1] for h in header if h.startswith("#player")]
    os.makedirs(outdir, exist_ok=True)
    for n in ns:
        nxt = events[n]  # e.g. ">p1: RAO?LUN O8 .ONsULAR +80 360"
        nick, rack = nxt[1:].split(":", 1)[0], nxt.split()[1]
        k = nicks.index(nick) + 1
        path = os.path.join(outdir, f"pos-{n:02d}.gcg")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(header + events[:n] + [f"#rack{k} {rack}"]) + "\n")
        print(path, f"to move: {nick} rack {rack}")


if __name__ == "__main__":
    main()
