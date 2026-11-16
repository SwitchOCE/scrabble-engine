# Stockfish techniques ranked by measured Elo, and whether they transfer to Scrabble

Stage-1 plan step 4(iii). No new reading: the numbers come from the parser tables in
[stockfish-commit-stats.md](stockfish-commit-stats.md) (official-stockfish/Stockfish `5d03b6e578a5`). The
Scrabble-side status comes from [magpie.md](../engines/magpie.md) at jvc56/MAGPIE `b781018`.

## How to read the table

**Two kinds of number.**

- The two top rows are single commits, with the Elo of one test: a fixed-games run, or a multi-thread run.
- The other rows are keyword technique tags, ranked by **summed LTC Elo** of their gain commits. Summed Elo is
  only a ranking signal. Patches interact, gains shrink at longer time controls, and each passed SPRT is biased
  upward (stockfish-commit-stats.md, "What the Elo numbers do and don't mean").
- Tags overlap, and one commit often has 3–5 of them.
- `eval-classical` is a code-area tag (files touched), not a keyword tag. It stands for "hand-written
  evaluation terms".

**The Scrabble column** is our judgement (Inference):

- **transfers:** the idea applies as is;
- **partly:** it applies to one part (usually the endgame or pre-endgame search, which are alpha-beta like chess),
  or it needs a different mechanism;
- **doesn't:** it has no Scrabble analogue worth building.

## Table

| # | Technique | Measure | Gain commits (with LTC Elo) | Median LTC Elo | Scrabble | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Adding NNUE (84f3e867) | +92.8 single, fixed games 10+0.1 1 thread | 1 | — | **transfers** | The core bet: a cheap, incrementally updated value net at MAGPIE's sim leaf (see [nnue.md](nnue.md)) |
| 2 | Lazy SMP (ecc5ff66) | +44.8 single, multi-thread | 1 | — | partly | Sims are already parallel by rollout. The endgame uses ABDADA; MAGPIE tried Lazy SMP variants and closed them (#447, #455) |
| 3 | Hand-written eval terms (`eval-classical` area) | 329.8 summed | 107 (106) | 2.37 | doesn't | This is the chess analogue of leave tables and PAT, which look saturated in Scrabble. Stockfish deleted it in 2023 (af110e02) |
| 4 | SPSA parameter tuning (`tuning-spsa`) | 321.8 | 171 (136) | 1.90 | **transfers** | Tune sim, BAI, inference and time constants by self-play. Needs paired games, because the objective is noisy |
| 5 | Late-move reductions (`reductions-lmr`) | 307.4 | 159 (147) | 1.69 | partly | Endgame only. MAGPIE kept its endgame exact within depth and LMR "never landed" (#448) |
| 6 | History heuristics (`history`) | 277.9 | 128 (116) | 1.82 | partly | Move ordering in the endgame and PEG search; no role in sims |
| 7 | New nets (`nnue-net` tag; net-update kind: 105 commits, 232.4) | 252.6 | 120 (110) | 1.96 | **transfers** | The retraining loop: keep generating data, retraining and SPRT-testing nets. This is where the "better training data" edge would show |
| 8 | Transposition table | 135.2 | 80 (64) | 1.70 | partly | MAGPIE's endgame already has a bucketed, lockless TT. A rollout has no transpositions worth caching, but per-candidate accumulator caching is the analogue |
| 9 | Extensions | 131.8 | 74 (59) | 1.75 | doesn't | Check or capture extensions have no Scrabble meaning. Variable sim depth by phase is the nearest idea |
| 10 | Killers / counter-moves | 104.9 | 35 (33) | 2.59 | partly | Endgame move ordering only |
| 11 | NNUE architecture (`nnue-arch`) | 100.5 (STC 179.0) | 78 (44) | 2.05 | **transfers** | Feature sets, buckets, layer sizes: the design space for our own net |
| 12 | Futility pruning | 99.3 | 49 (48) | 1.69 | partly | Endgame/PEG pruning. In sims, BAI already drops hopeless candidates |
| 13 | Speedups (`speedup` tag) | 84.5 (STC 209.8) | 87 (32) | 1.81 | **transfers** | Speed is strength in a sim engine too: more rollouts per second. Test at a short budget, as Stockfish does |
| 14 | Eval scaling (by material, rule-50 etc.) | 73.7 | 41 (39) | 1.76 | partly | The analogue is shaping the value by bag size and spread. A net with bag-size layer stacks learns it |
| 15 | Move ordering (general) | 71.1 | 35 (32) | 1.73 | partly | Endgame only |
| 16 | Threads / SMP tuning | 67.6 | 45 (23) | 2.44 | partly | Thread scheduling of sims and endgame; MAGPIE already does both |
| 17 | Null-move pruning | 63.8 | 25 (24) | 1.77 | doesn't | A pass is a real Scrabble move with real consequences (stuck tiles), so the "free move" premise fails |
| 18 | Late-move pruning / move-count pruning | 57.2 | 24 (22) | 2.25 | partly | The analogue is the static-equity candidate cap in sims and the word pruning MAGPIE already does in the endgame |
| 19 | Quiescence search | 51.0 | 31 (29) | 1.47 | doesn't | No captures. The nearest analogue is MAGPIE's greedy-playout endgame leaf, which already exists |
| 20 | Singular extensions | 47.4 | 28 (24) | 1.81 | doesn't | Needs a deep alpha-beta tree with one forced move |
| 21 | ProbCut | 40.7 | 23 (21) | 1.65 | partly | "A shallow search predicts a deep cutoff" maps to "a 1-ply net predicts which sim candidates to drop" |
| 22 | NNUE inference (`nnue-inference`) | 37.1 (STC 119.7) | 53 (15) | 2.21 | **transfers** | Accumulator tiling, sparse first layer, int8 widening: all CPU work a Scrabble net would reuse directly |
| 23 | Static exchange evaluation (SEE) | 36.2 | 18 (15) | 1.80 | doesn't | No exchanges of material |
| 24 | Aspiration windows | 33.1 | 12 (11) | 1.97 | partly | Endgame. MAGPIE already uses ±25 windows |
| 25 | Time management | 29.9 (plus e6482b7d +7.7 STC; 77b5ee01 +24.3 at 5+0.05, +13.4 at 15+0.05, +5.3 at 60+0.05, a blitz-parameter fix whose gain shrinks with time) | 18 (16) | 1.59 | partly | "Move faster if the best move is stable" is close to what MAGPIE's best-arm (BAI) stopping already does; a clock-banking time manager is an open PR (jvc56/MAGPIE#637). What is left is allocating time by game phase |
| 26 | Correction history | 29.3 (single 60351b9d +8.7 LTC) | 21 (15) | 1.45 | partly | Learn the running error of the static eval against search results per pattern, and correct for it. In Scrabble: correct static equity against sim results by rack or board pattern, inside one game |
| 27 | Razoring | 21.3 | 10 (10) | 2.02 | doesn't | Depth-based pruning in alpha-beta; little use in a fixed-depth exact endgame |
| 28 | Internal iterative reductions (IIR) | 13.8 | 11 (8) | 1.58 | doesn't | Depends on TT-move ordering in a deep tree |
| 29 | Tablebases | 5.1 | 4 (3) | 1.55 | doesn't | No tablebases. The endgame solver plays that role, exactly, at bag 0 |

## Not in the Elo columns, but transfers

- **Non-regression tests for every simplification** (1,158 non-regression commits against 1,254 gain commits)
  (stockfish-commit-stats.md, "Inference"). See [testing-method.md](testing-method.md).
- **Relabelling training data with a stronger, slower evaluator** (BT4 relabel, 9fcd47a7 and 4488343c). These
  show up in row 7.

## Inference

- **Rows that transfer directly:** 1, 4, 7, 11, 13 and 22. They are the net itself, its training loop, its
  architecture, its inference speed, general speedups, and parameter tuning. The net-related rows overlap
  nnue.md's "Copy" section; SPSA tuning and general speedups are additions to it.
- **Most of Stockfish's search Elo** (rows 5, 6, 9, 10, 12, 15, 17–20, 23, 27, 28) is alpha-beta tree
  technique. It applies to Scrabble only in the endgame and pre-endgame, where MAGPIE already has an exact
  solver.
- **Where Stockfish's ideas work and ours don't yet:**
  - a learned evaluation inside search;
  - sequential, paired testing as a routine gate (MAGPIE has paired matches but no SPRT; magpie.md);
  - SPSA tuning of search constants;
  - a culture of deleting what stops paying.
