# Stockfish's move to NNUE, and what transfers to Scrabble

Research track R3, stage-1 plan step 4(i). Feeds decision (b), where a neural evaluation pays off.

**Sources and pins.**

- Code: official-stockfish/Stockfish at `5d03b6e578a5` and official-stockfish/nnue-pytorch at `8d30ed74a1db`
  (`reference/PINS.tsv`). Code refs below are `path:line` at those SHAs.
- Commit messages: `reference/history/stockfish/commits-full.txt`, cited by short SHA. PRs are cited as
  official-stockfish/Stockfish#n.
- Elo figures come from the parser output ([stockfish-commit-stats.md](stockfish-commit-stats.md),
  [data/stockfish-commits.tsv](data/stockfish-commits.tsv)) unless a commit message is quoted. There, "LTC Elo"
  is logistic Elo recomputed from W/L/D, and it is selected by SPRT, so it is biased upward (see that doc's
  "What the Elo numbers do and don't mean").
- MAGPIE and Macondo figures come from [magpie.md](../engines/magpie.md) and [macondo.md](../engines/macondo.md).
- One measurement is ours (Stockfish `bench` on our machine, see "Measured payoffs"). Everything else is quoted.

## Summary

- **Adding NNUE was the largest single gain in Stockfish's history:** +92.8 Elo at 10+0.1 on 1 thread and +89.5
  at 20+0.2 on 8 threads (84f3e867, fixed-games runs). The next largest single LTC gain in the parser output is
  +15.6.
- **NNUE's cost is mostly the first layer, and the first layer is updated, not recomputed.** One move changes a
  few input features. Each change adds or subtracts one weight row from an int16 accumulator, and the rest of
  the net is tiny. Today the accumulators are 1024 wide per perspective. A pairwise product cuts each to 512, so
  the first dense layer is 1024 × 32, then 32 → 32 → 1 (`src/nnue/nnue_architecture.h:45-63`;
  `src/nnue/nnue_feature_transformer.h:94, :267`).
- **After the switch, gains came from three places:** training data and new nets (105 net-update gain commits,
  summed LTC Elo 232.4), inference speed (the two largest speedups by STC Elo in the parser output, +10.4 and
  +10.0, are both NNUE work), and architecture changes (mostly +2 to +5 LTC each; some smaller, such as v14
  at +1.40 and v16 at +1.15).
- **Training data moved from "self-play scored by our own search" to "positions relabelled by a much stronger,
  slower net"** (Leela's BT4 transformer, 2026). That relabelling gave some of the largest recent net gains:
  +6.02 LTC (4488343c), and +3.85 LTC for 9fcd47a7, which was merged with its STC still running (LLR −0.01) and
  passed LTC on <0, 2> bounds.
- **For Scrabble,** a CPU NNUE value net at MAGPIE's sim leaf looks affordable. Our estimate is about 0.6–1.2 µs
  per leaf eval for a 256-wide first layer. A 2-ply rollout costs about 38 µs in a MAGPIE PR (hardware not
  stated) and 74–147 µs on our machine ([builds.md](../harness/builds.md)). Board, rack and unseen-pool
  features can all be updated incrementally, because a Scrabble move only adds tiles to the board. The
  arithmetic is in "What transfers to Scrabble".

## 1. Architecture over time

### Facts

The NNUE principles, as nnue-pytorch states them (`docs/nnue.md:137-151`):

1. few non-zero inputs (sparsity of about 0.1% in current nets);
2. inputs change little between successive evaluations;
3. the net is simple enough for low-precision integer inference.

The target is "million(s) of evaluations per second per thread" on a CPU, with no batching.

**Timeline** (sizes are feature transformer width × 2 perspectives → hidden layers → output; dates and SHAs from
nnue-pytorch `docs/nnue_architecture_history.md:29-227` and the commit messages):

| Version | Date | Commit | Features | Shape | What changed | Elo (parser; LTC unless noted) |
| --- | --- | --- | --- | --- | --- | --- |
| SFNNv1 | 2020-08-06 | 84f3e867 | HalfKP: (own king square, piece square, piece type, colour), kings excluded; 64 × 641 features per perspective (nnue-pytorch `docs/nnue.md:291-298`) | 256×2-32-32-1 | Port from shogi (nodchip). Hybrid with the classical eval | +92.8 (fixed games, 10+0.1, 1 thread) |
| hybrid | 2020-08-06 | 3dca13a9 | — | — | Use NNUE only in balanced-material positions; classical eval elsewhere, because it was faster | +11.3 |
| SFNNv2 | 2021-05-18 | e8d64af1 | HalfKAv2: kings included, packed 8% smaller than HalfKA; board flipped (not rotated) for Black | 512×2-16-32-1 | New PyTorch trainer. 8 PSQT outputs per feature fed straight to the output; 8 layer stacks ("subnetworks") chosen by `(piece count − 1) / 4`, only one evaluated per position. About 15–20% slower | +21.7 STC, +5.9 LTC (message) |
| SFNNv3 | 2021-08-15 | d61d3858 | HalfKAv2_hm: mirrored so the own king is on files e–h, which halves the feature transformer | 1024×2-8-32-1 | Second layer cut from 16 to 8 outputs for speed, "doesn't harm the strength much" | +3.87 |
| SFNNv4 | 2022-02-10 | cb9c2594 | same | 1024×2 accumulators → pairwise product (512 per perspective, 1024 in total) → 16 (15 + 1 skip) | Pairwise elementwise multiply of the two halves of each accumulator (a cheap non-linearity); one output skips to the end | +5.37 |
| SFNNv5 | 2022-05-14 | c079acc2 | same | 15 → 30 | Duplicated activation: squared clipped ReLU alongside clipped ReLU | +3.86 |
| SFNNv6–v9 | 2023-05-31 to 2024-04-02 | c1fff716, 91553218, 70ba9de8, 0716b845 | same | L1 1536, 2048, 2560, 3072 | Wider first layer, enabled by better data (c1fff716) and by the sparse-input first layer (38e61663) | +2.27 VLTC, +2.5 VLTC, mixed, +1.95 VVLTC |
| dual net | 2024-01-07 | 584d9efe | small net: HalfKAv2_hm, L1 128 | 128×2 | A second, small net used for positions with a large material imbalance (`abs(simple_eval) > 1000`), trained only on such positions | +2.04 |
| SFNNv10 | 2025-11-12 | 8e5392d7 | + Full Threat inputs: (piece, square) pairs where the second piece is attacked by the first | L1 back to 1024 | Feature transformer quantisation scale 255. "A huge effort spanning over half a year" | +3.83 |
| SFNNv11–v12 | 2026-02 | fac506bd, 83e42045 | threats to/from kings removed | same | Saves 13 MB and about 0.8 threat updates per incremental update (fac506bd) | non-regression |
| SFNNv13 | 2026-02-18 | a6d055d7 | same | L2 16 → 32 | Smaller L1 made a wider L2 affordable | +2.97 |
| SFNNv14–v16 | 2026-04 to 2026-07 | 5eeca739, e33bb26e, f4bcd404 | + opposed-pawn threats; + PP_3Wide pawn-pair features | same | v15 is mostly a new recipe and relabelled data | +1.40, +3.28, +1.15 |
| small net removed | 2026-05-04 | ab8f901d | — | — | Merged although it **failed** STC and VVLTC non-regression; the message blames the small net's lower eval quality (one VVLTC game shows a fortress misjudged because the position went to the small net) and the burden of maintaining two architectures | (non-regression failed) |
| SFNNv17 | 2026-09-30 | a17c0ce2 | — | — | PSQT path removed: simpler code, faster training | non-regression |
| SFNNv18 | 2026-10-13 | 5c4cef0b | K32Q2: own king (32 buckets) × opponent queen present (2) | layer stacks 8 → 32 | Feature transformer weights int8 | +3.60 |
| SFNNv19 | 2026-10-28 | ff7cee42 | K32H3: third block for "no rooks or queens" | same | — | +2.69 |
| SFNNv20 | 2026-11-09 | 26647279 | same | 192 layer stacks | Stack key adds pawn layout and "≥2 non-pawn pieces"; rare buckets pruned before training | +2.11 |

**Today** (`src/nnue/nnue_architecture.h:40-63`; `src/nnue/features/k32h3.h:36-37, 69-90, 108`;
`src/nnue/features/full_threats.h:43, 57`):

- **Inputs:** K32H3 piece-square features (67,584; at most 32 active), Full Threats (59,808; at most 256 active)
  and pawn pairs. Their rows are summed into one accumulator per perspective.
- **Layers:** a 1024-wide accumulator per perspective → pairwise product to 512 per perspective, 1024 in total
  (`nnue_feature_transformer.h:94, :267`) → sparse affine 1024 → 32 → squared clipped ReLU and clipped ReLU → 32
  → both activations → 1, plus a skip from the first dense layer (`nnue_architecture.h:57-63, :128-131`).
- **Buckets:** 192 layer stacks; one is selected per position.

### Inference

- **The direction of travel was wide first layer, tiny everything else.** Width went 256 → 3072 → 1024, and the
  later layers stayed at 8–32. Richer, derived inputs (threats) let the first layer shrink again. That is the
  pattern to copy: spend parameters where incremental updates make them cheap.
- **"Buckets" are cheap conditional capacity.** King buckets pick which first-layer weights apply. Layer stacks
  pick which small dense net runs. Only one is evaluated, so neither costs speed.
- **Stockfish removes things that stop paying.** Examples: the classical eval (af110e02, merged at about −2 Elo
  as "roughly 25% of SF"), the PSQT path, the small net. A second net is a maintenance cost, not just a speed
  question.

## 2. The accumulator

### Facts

- **What it is.** One int16 vector of width L1 per perspective (`src/nnue/nnue_accumulator.h:43-46`). Its value
  is bias + the sum of the weight rows of the active features. A feature turning on adds its row; turning off
  subtracts it (nnue-pytorch `docs/nnue.md:278-289`).
- **Stack, not copy.** Search pushes an accumulator state with each move and pops it on undo
  (`src/search.cpp:683-684`, `:704-706`). The state holds only the "dirty" changes and `computed` flags
  (`src/nnue/nnue_accumulator.cpp:85-99`). Undo is free: the parent's accumulator is still on the stack.
- **Lazy update.** Nothing is computed at `do_move`. Only `evaluate()` triggers the update
  (`src/nnue/nnue_feature_transformer.h:247-252`; e9997afb). It walks back to the last computed accumulator, or
  to the last move that forces a refresh (`nnue_accumulator.cpp:151-172`). It then applies the changes forward
  (`:174-190`). A position that is never evaluated (pruned) costs nothing.
- **Refresh.** A king move that changes the king bucket invalidates every feature for that perspective. Before
  2024 that meant summing all ~30 active rows from the biases.
- **Finny tables** (refresh cache; 49ef4c93, the idea credited to Luecx of Koivisto;
  `nnue_accumulator.h:49-88`, `nnue_accumulator.cpp:990-1026`). Per thread, keep one cached accumulator per
  (block, king square, colour), together with the piece placement it represents. On refresh, diff the current
  board against the cached board and apply only those changes, then copy. Since the board near a given king
  square changes slowly, the diff is small.
- **Backward updates** (e9997afb). After a refresh, the parent accumulators on the stack are also filled by
  updating backwards, so sibling nodes can update from them (`nnue_accumulator.cpp:144-145`, `:192-209`).
- **Other tricks.**
  - Update two plies in one pass and cancel a feature added then removed (fda269a2, +1.67 STC).
  - A "hybrid" king-move update that reuses the previous accumulator when the king stays in the same half
    (`nnue_accumulator.cpp:123-142`).
  - One merged accumulator for king-square and threat features, which halves the cache footprint (7c7fe322,
    +4.57 STC).
  - Process all changed weight rows tile by tile, so the partial sums stay in vector registers (8b8a510f, +10.4
    STC). Today's version also prefetches the next tile (`nnue_accumulator.cpp:346-353`; 9d24e938, +2.91 STC).
- **Sparse first dense layer** (38e61663, +10.0 STC, "speedup of up to 10%"). After clipping, most accumulator
  outputs are zero. The 1024 → 32 layer skips zero input blocks (`src/nnue/layers/affine_transform_sparse_input.h:42`;
  `NNZInfo` in `nnue_architecture.h:96-108`).

### Inference

- **Why it is cheap per node.** Take L1 = 1024 and int16 accumulators on AVX2 (16 lanes): one row is 64
  vector adds. A quiet move changes 2 king-square features (from-square off, to-square on) plus a handful of
  threat features, per perspective. That is a few hundred vector ops, against about 2 × 32 + 256 rows for a
  full rebuild. The dense layers after it are about 1024 × 32 + 64 × 32 + 64 ≈ 35k int8 multiply-adds (the
  first dense layer sees 1024 inputs after the pairwise product), and sparsity skips many of the first 32k.
- **Every one of these tricks is about avoiding work on positions that may never be evaluated,** or reusing
  work across siblings. All of it helps a tree search. A Scrabble rollout is a single line, so the stack and
  laziness matter less there. Reuse across rollouts from the same root (Finny-style caching) matters more (see
  section 6).

## 3. Quantisation and SIMD

### Facts

- **Types** (`src/nnue/nnue_common.h:59-71`): weights int8 (int16 for the feature transformer until SFNNv18,
  5c4cef0b), biases and accumulators int16, `FtMaxVal = 255`, `WeightScaleBits = 6` (a weight step of 1/64),
  output scaled to 600 × 16 internal units (`nnue_architecture.h:133-140`).
- **The scheme** (nnue-pytorch `docs/nnue.md:941-953`):
  - The accumulator is int16 because 30+ int8 rows would overflow int8.
  - Clipped ReLU takes it down to 8-bit.
  - Dense layers multiply int8 by int8 into int32 (`maddubs` / VNNI `dpbusd`), then clip back to int8.
- **Pairwise product in integers.** The feature transformer output multiplies pairs of clipped values and
  divides by 512. It uses `mulhi` plus `packus` to save instructions (`nnue_feature_transformer.h:287-317`).
- **Widening int8 rows.** Since int8 feature-transformer weights (SFNNv18), adding a row means widening int8 to
  int16. Pairing two rows per shuffle gave +7.0% (AVX-512 ICL), +5.2% (AVX2) and +10.7% (SSE4.1) nps
  (e08dfa80, +4.50 STC).
- **Targets.** Hand-written SIMD paths exist for SSE2/SSSE3, AVX2, AVX-512 (VNNI), NEON (dotprod), RISC-V
  vectors, LoongArch and wasm (`src/nnue/simd.h:22-63`; RISC-V paths in `src/nnue/nnue_accumulator.cpp:255-268`; 90890c5f, 8e711c29). Since 2026 the release is a universal
  binary that picks the best path at run time (c3bcf749; Stockfish 19 release notes, edb0d9db).
- **Quantisation-aware training (QAT)** is now part of the recipe (Stockfish 19 notes, edb0d9db; QAT warm-ups
  in 26647279).

### Inference

- Integer inference is not optional at this speed. nnue-pytorch says float "sacrifices too much speed for too
  little accuracy" (`docs/nnue.md:153-155`). The error stays negligible because the net is shallow.
- A large share of NNUE's Elo after 2020 came from making the same net faster: the top speedups in the
  parser's table are NNUE inference. A Scrabble net should be designed around int16 accumulators and int8
  dense layers from day one, not converted later.

## 4. Training data, loss and how nets were tested

### Facts: data

- **The format** is the training entry: position, move, int16 score, ply and game result
  (nnue-pytorch `data_loader/cpp/lib/training_data_entry.h:47-53`). "Binpack" files store a full packed entry,
  then a bit-packed chain of following (move, score) plies from the same game (`data_loader/cpp/lib/binpack.h:268-339`).
  The C++ loader builds whole sparse batches in worker threads (`docs/nnue.md:599-609`).
- **2020–2021: Stockfish self-play scored by Stockfish.** For example, SFNNv2's data was "64 billion positions
  (193GB total) generated and scored with the current master net", in datasets named d8, d9 and d10 (e8d64af1). A
  dataset named `nodes5000pv2_UHO` recurs in recipes (cb9c2594, c079acc2); by its name it is self-play at
  5,000 nodes from UHO openings (UNVERIFIED: the messages do not describe it).
- **2021 on: Leela data.** Recipes mix Leela Chess Zero training games (T60, T74–T80, "LeelaFarseer"; c1fff716,
  70ba9de8). The README credits Leela data under the ODbL (`README.md:125-126`).
- **2026: relabel with a stronger net.**
  - About 2 billion positions relabelled with the value head of Leela's `BT4-tf13tune` transformer, as a
    fine-tuning stage (9fcd47a7, +3.85 LTC). Caveat: its STC was still "Ongoing" at merge (LLR −0.01), and its
    LTC passed on <0, 2> bounds rather than the usual <0.5, 2.5>; a VLTC <0.5, 2.5> test passed.
  - 74 billion positions relabelled the same way (4488343c, +6.02 LTC, the largest net update since 2022).
  - The Stockfish 19 notes say "hundreds of billions of training positions … consistently rescored using a
    strong Leela net" (edb0d9db).
- **Search-tree samples.** The pinned head's own net (5d03b6e5, +3.11 LTC) adds 2 billion "search-tree"
  positions. Stockfish self-play ran at 200k nodes, quiet positions were sampled from *inside* the search tree,
  and the positions were relabelled by BT4. They make up 3% of the mix.
- **Filtering** (`data_loader/cpp/training_data_loader.cpp:1076-1099`). The loader skips:
  - positions with a capture or in check (non-quiet);
  - early plies;
  - a random fraction;
  - positions whose score disagrees with the game result (`wld_filtered`, keep probability = the score's implied
    result probability).

  Recipes add "early-fen-skipping" and minimised, deduplicated data (c1fff716, 70ba9de8).
- **Multi-stage training.** For example SFNNv6 (c1fff716):
  1. train from scratch at λ = 1.0;
  2. retrain three times on other datasets with λ decaying to 0.75 or 0.7;
  3. pick the best epoch at each stage by local games.

  Recipes now live in vondele/nettest (nnue-pytorch `docs/training.md:1-20`), which notes the full dataset
  needs 800+ GB.
- **Fine-tuning the output layers by SPSA after training.** 648 output-layer parameters were tuned at VVLTC
  (0716b845, SFNNv9).

### Facts: loss

`calculate_sf_loss` (nnue-pytorch `model/nnue.py:50-84`; defaults `model/config.py:53, 97-113`):

1. Map the net's output and the search score from centipawns to expected score:
   `q = 0.5·(1 + σ((x − 270)/340) − σ((−x − 270)/340))`. The search score uses scaling 380. This is a
   WDL-style curve, not a plain sigmoid.
2. Blend the target: `pt = λ·p_score + (1 − λ)·game_result` (`nnue.py:68-72`). λ = 1 trains on search scores
   only, λ = 0 on results only (`model/lambda_utils.py:11-13`). λ can be scheduled from a start value to an end
   value (`lambda_utils.py:30-44`). Search-tree samples have no result and use the score alone (`nnue.py:69-70`).
3. Loss: `|pt − q|^2.5` (`pow_exp = 2.5`), with optional asymmetry and weighting (off by default:
   `w1 = 0`).

Feature factorisation: during training, "virtual" coarse features (for example "piece on square, any king
square") share learning across the sparse real features. They are folded into the real weights at export
(`docs/nnue.md:745-758`).

### Facts: testing a net before merge

- **Locally:** play games at a fixed node count with c-chess-cli and rank checkpoints with ordo
  (nnue-pytorch `run_games.py:34-64`, `:109-128`, `:142-160`). Messages quote "Elo at 20k nodes per move"
  (d61d3858) or "25k nodes per move" (584d9efe) to pick epochs.
- **On fishtest:** upload `nn-<first 12 hex of sha256>.nnue`, point `EvalFileDefaultName` at it on a branch, then
  run normal STC and LTC SPRTs
  ([fishtest wiki, Creating my first test](https://github.com/official-stockfish/fishtest/wiki/Creating-my-first-test)).
  Net commits quote STC `<0.00,2.00>` and LTC `<0.50,2.50>` normalized-Elo bounds (for example 8e5392d7,
  584d9efe). Architecture changes that are meant as simplifications use non-regression bounds
  (`<-1.75,0.25>`; a17c0ce2, fac506bd). See [testing-method.md](testing-method.md).

### Inference

- **The biggest late lever was label quality, not architecture.** A slow, much stronger teacher (BT4) labels
  positions; a fast student (NNUE) learns them. Search-tree sampling then moves the training distribution
  towards the positions the search actually evaluates.
- **λ near 1 means "learn the search score".** Stockfish starts at λ = 1 and anneals to about 0.7–0.75. Game
  results act as a regulariser, not the main target.
- **Selection is by games, not loss.** Epochs are picked by fixed-node matches, and nets are merged only after
  SPRT.

## 5. Measured payoffs

### Facts (parser output and commit messages)

**The NNUE introduction** (84f3e867):

| Test | Games | Result |
| --- | --- | --- |
| 10+0.1, 1 thread | 60,000 | +92.77 ± 2.1 Elo |
| 20+0.2, 8 threads | 40,000 | +89.47 ± 2.0 Elo |

Its SPRTs were *non-regression* tests of the classical eval inside the new build, so the parser's LTC columns
miss it (see stockfish-commit-stats.md, "Known misclassifications and limits").

**The net-update series** (kind `net-update`, gain commits; parser):

| Year | Gain commits | With LTC Elo | Summed LTC Elo | Mean LTC Elo |
| --- | --- | --- | --- | --- |
| 2020 | 12 | 12 | 27.3 | 2.27 |
| 2021 | 31 | 30 | 68.2 | 2.27 |
| 2022 | 6 | 6 | 21.6 | 3.60 |
| 2023 | 17 | 15 | 30.6 | 2.04 |
| 2024 | 14 | 13 | 22.1 | 1.70 |
| 2025 | 4 | 4 | 9.0 | 2.26 |
| 2026 | 21 | 20 | 53.6 | 2.68 |
| all | 105 | 100 | 232.4 | median 2.00 |

The first three nets after the switch each gained +2.0 to +5.0 LTC within a week (857e045c, bcdf41da,
67e48418).

**The top NNUE speedups** (kind `speedup`, STC Elo; parser):

| Commit | Change | STC Elo |
| --- | --- | --- |
| 8b8a510f | Accumulator tiling (register-resident tiles) | +10.41 (an SPRT that stopped after 4,872 games; LTC +2.21) |
| 38e61663 | Block-sparse input for the first dense layer | +10.04 (+9.9% nps on a Ryzen 5700U, message) |
| 2046d5da | More incremental accumulator updates (look back further) | +5.12 |
| fff35786 | Bitset nnz representation | +4.58 |
| 7c7fe322 | Merge HalfKA and threat accumulators | +4.57 |
| e08dfa80 | Pair int8 weight rows in accumulator updates | +4.50 |
| 3ae76847 | Faster threat features | +4.30 |
| 485d517c | Large pages for NNUE weights | +3.92 |
| c065abdc | Incremental updates up to 2 plies back | +2.88 |
| fda269a2 | Double incremental updates | +1.67 |

The Finny-table commit (49ef4c93) links its STC tests but quotes no numbers in the message, so the parser has
no Elo for it.

**Our measurement.** Stockfish `bench` on this machine: see "Measured here" below.

### Inference

- **Speed is worth Elo at a measurable rate.** The block-sparse layer (38e61663) gave +9.9% nps and +10.0 Elo at
  STC; it had no LTC test. Tiling's +10.4 STC (8b8a510f) came from an SPRT that stopped after 4,872 games, so it
  is noisy and biased upward; its LTC was +2.2. Stockfish measures speedups at STC, where they show most.
- **Data and nets kept paying for six years at about +2 LTC per accepted net.** No single later change came
  near the initial +93. The switch itself was the payoff; the rest is compounding.

### Measured here

**Facts.**

- Setup: Stockfish at the pin, built `ARCH=x86-64-avx2` with g++ 15.2.0 and the default net
  `nn-bddd9d57eb87.nnue`, on our Intel i5-9500T (2.2 GHz, AVX2, no VNNI).
- Command: `bench 16 1 13`, run three times.
- Result: 611,738, 839,627 and 823,333 nodes/s on 1 thread. The first run was cold.
- Raw output: [data/stockfish-bench-i5-9500T.txt](data/stockfish-bench-i5-9500T.txt).

**Inference.**

- About 830k nodes/s means **~1.2 µs per node on our CPU**. That covers move generation, search bookkeeping and
  an NNUE evaluation (a 1024-wide accumulator with threat features, and a 138 MB net) at most nodes.
- So a full-size Stockfish NNUE eval with incremental updates runs at a per-node cost of the same order as
  ~1.2 µs on this machine.
- That is consistent with the ~0.6–1.2 µs estimate for a 256-wide Scrabble net in section 6. It is not a
  measurement of the Scrabble net.

## 6. What transfers to Scrabble

Context: leave tables look saturated, so gains must come from evaluation that sees the board and the bag
([research-plan.md, "Findings shaping stage 2"](../research-plan.md)). MAGPIE's natural call site is the sim
leaf (E4: one call per rollout). Its budget is about 38 µs per 2-ply rollout on one thread in a MAGPIE PR
(#894, PAT off, hardware not stated; about 1.1–1.5× that with PAT on). On our machine MAGPIE runs 6,817–13,510
2-ply rollouts/s on 1 thread, so **~74–147 µs per rollout** ([builds.md](../harness/builds.md)). Macondo's
CSW24 transformer is a one-ply ranker costing about 2 ms per gRPC request ([magpie.md](../engines/magpie.md),
"Neural evaluation"; [macondo.md](../engines/macondo.md), "Evaluation call sites").

Everything in this section is **Inference** unless it cites a source.

### Copy

- **Sparse one-hot inputs into a wide int16 accumulator, then a tiny int8 net.** For example
  2×256 → 16 → 32 → 1 at first, widening only if measured cheap. Use clipped ReLU, the pairwise product, and
  squared clipped ReLU (SFNNv4–v5).
- **Integer quantisation and QAT from the start.** Use int8 weights for the dense layers and int16 (or int8
  widened) rows for the first layer.
- **Layer stacks keyed by game phase.** The chess key is piece count. In Scrabble it would be tiles unseen
  (for example 8 buckets: bag 0, 1–7, 8–20, …). Only one stack runs, so it costs no speed.
- **Feature factorisation in training.** "Letter X on square s" is as sparse as HalfKP: Q or Z on most squares
  is rare. Add virtual coarse features, such as "letter X anywhere", "any tile on s" and "letter X on a
  premium-square type", and fold them in at export.
- **Labels from a stronger, slower evaluator, then fine-tune on search-tree samples.**
  - The teacher can be a deep MAGPIE sim's win% or Macondo's CSW24 transformer.
  - **Unlike chess, there is no BT4-class teacher.** Macondo's net plays about level with a 2-ply sim (49.0% ±
    1.6; macondo.md), and MAGPIE's 4-block student scored 46.32% ± 0.85 against that teacher (magpie.md,
    "Value-net branches"). Deep sims are the only stronger labeller, and they are expensive per label.
  - The student is the CPU NNUE.
  - Sample training positions from *inside* MAGPIE rollouts at the leaf, not only from game positions. That is
    Stockfish's search-tree data (5d03b6e5), and it is the fix for MAGPIE #528's pitfall: train on the same
    state the leaf sees.
  - Blend in game results with λ, starting at λ = 1 and annealing to about 0.75.
  - One caution from Macondo: "sim distillation does not help a ranker" (macondo.md). That result was for a
    one-ply ranker, not a leaf value, so it is a reason to test, not to skip.
- **Loss in win-probability space with a result blend.** Scrabble's natural score is P(win); add the spread as a
  second head, as Macondo does.
- **Select epochs by fixed-budget games, and merge only after a paired SPRT** (see testing-method.md).
- **Remove what stops paying.** Run non-regression tests on simplifications, including the net's own extras.

### Adapt: incremental updates in a Scrabble rollout

**What changes per move (facts of the game):**

- **Board:** a move adds 1–7 tiles. Tiles are never removed or moved. The only exception is a challenged-off
  phony, which does not happen in VOID autoplay.
- **Rack:** the mover loses the tiles played and draws as many from the bag. An exchange of k tiles changes
  2k rack entries and no board squares.
- **Bag and unseen pool:** from the mover's view, the unseen pool loses the tiles they drew. From the
  opponent's view, it loses the tiles the mover played. Bag size drops by the number drawn.
- **Score difference and bag size:** a few scalars.

**Proposed feature sets and their update cost per ply, per perspective:**

| Feature set | Size | Active | Changed per ply | Incremental? |
| --- | --- | --- | --- | --- |
| Board: (square, letter, blank?), 225 × 27, factorised | ~6,100 | up to ~90 mid-game | +1…7 adds, 0 removes | yes: add-only |
| Rack: (letter, count ≥ k), 27 × 7 | ~190 | ≤ 7 | ≤ 14 (≤ 7 off, ≤ 7 on) | yes |
| Unseen pool: (letter, count ≥ k), 27 × up to 12 | ~100–150 | ≤ ~60 | ≤ 7 | yes |
| Cross-sets / hooks: (square, letter fits in the cross-word) | 225 × 26 | many | squares next to the new word, ~2 × 7 + 2 | yes, but needs the lexicon |
| Score difference, bag size, turn | scalars | — | all | no: dense side inputs or bucket keys |

Notes on the table:

- **Cross-sets are the analogue of Stockfish's threat features.** They are derived, informative and change
  only locally. MAGPIE's move generator already keeps cross-sets for move generation (UNVERIFIED: not
  confirmed in its code during this study), so the delta may come nearly free.
- **Perspective.** Chess keeps two accumulators. A Scrabble value net should see only what a player sees: the
  board, their own rack, their unseen pool, the scores and the bag count. Inside a sim, the opponent's rack is
  sampled, so a net that took it as input would learn from information it will not have in play. At an
  even-ply leaf (MAGPIE #528 requires even plies; magpie.md), the root player is to move, so **one perspective
  is enough** for E4.
- **Board symmetry.** The premium layout has 8-fold dihedral symmetry. Stockfish mirrors so that the king is on
  e–h (SFNNv3). Canonical orientation would force refreshes when the orientation flips. Use symmetry for data
  augmentation instead, or for weight sharing in factorisation.
- **Bucketing on the rack** (the "king bucket" analogue) is a poor fit. Rack changes every turn, so every move
  would refresh. Bucket the dense layers on bag size instead, which changes slowly.

**Which features update inside a rollout.** A MAGPIE rollout starts from (root position + candidate move) and
plays 2–4 plies with the static policy.

- The accumulator for (root + candidate) is the same for every rollout of that candidate, apart from the root
  player's drawn tiles. Compute it once per candidate and cache it. This is the Finny-table idea: keep the
  accumulator per candidate, not per king square.
- Each rollout then applies, for the root player's perspective:
  - board adds for both plies (≤ 14, typically ~8);
  - rack changes from the root player's first draw (after the candidate) and their own second play and draw
    (≤ 21, typically ~11);
  - unseen-pool changes from the root player's draws and the opponent's played tiles (≤ 21, typically ~11).

  So **about 30 rows typical, 56 at most**, and no removals on the board side.
- A full refresh at the leaf (no caching) would be about 90 board + 7 rack + ~60 pool, so **~160 rows**.

**Cost target, with the arithmetic** (assumptions: AVX2, 16 int16 lanes per vector, about 1 vector add per cycle
from cache, a ~2–3 GHz core like our i5-9500T; weights int8 widened to int16). One caveat on "from cache": the
board table alone is ~6,100 rows × 256 B ≈ 1.5 MB at L1 = 256, which exceeds the i5-9500T's 256 KB L2 per core,
so most board rows come from L3. That is why the per-row time below is a range.

| L1 width | Rows | Vector adds (rows × L1 / 16) | Dense MACs (one perspective: L1·16 + 16·32 + 32) | Estimated time |
| --- | --- | --- | --- | --- |
| 256 | 30 (incremental) | 480 | ~5k | 0.3–0.8 µs adds + ~0.1 µs dense + ~0.2 µs feature extraction ≈ **0.6–1.2 µs** |
| 256 | 160 (refresh) | 2,560 | ~5k | ≈ 1.5–3 µs |
| 1024 | 30 | 1,920 | ~17k | ≈ 2–3.5 µs |
| 1024 | 160 | 10,240 | ~17k | ≈ 5–10 µs |

Against MAGPIE's budget, stated both ways:

- **MAGPIE PR figure** (magpie.md, "Budget per evaluation inside simulation"; hardware not stated): a 2-ply
  rollout ≈ 38 µs, so a 10% slowdown allows ~3.8 µs per leaf eval. **A 256-wide net with cached per-candidate
  accumulators fits (~1.6–3%).** A 1024-wide net fits at ~5–9%. Full refresh at 1024 does not fit the 10% target.
- **Our machine** (builds.md): 74–147 µs per 2-ply rollout, so 10% allows ~7–15 µs. The 256-wide net costs
  ~0.4–1.6%, and a 1024-wide net ~1.4–4.7%.
- 4-ply rollout ≈ 100 µs (PR figure): the same net is relatively cheaper.
- **Per-ply use as a rollout policy (E3) is the hard case.** A ply has about 16–19 µs of budget, and each
  candidate move needs its own delta (≤ 7 board adds + ≤ 14 rack + pool). Re-ranking the top 8 static moves at
  ~0.3–0.5 µs each costs about 2.5–4 µs per ply, roughly 15–25%. Scoring every generated move is out of reach,
  because move generation's bounds assume leave-only evaluation (magpie.md, E2/E3).
  MAGPIE's own branches show the cost of doing this with a big net: net replies on rollout ply 1 made sims
  165–460× slower (60,000 vs 130–363 it/s), with no detectable gain at equal iterations (50.67% ± 1.85%;
  magpie.md, "Value-net branches").
- **The other open use is the net as a sim candidate selector or prior.** It has the strongest measured
  signal (a 1-ply picker at +6.8 points of win rate over static), was built on MAGPIE's branches, and has never
  been played in a sim (research-plan.md, finding (b)). It needs only a few evals per decision, not per
  rollout, so even a slow net would do.
- **Compared with Macondo's transformer, per scored position:** about 0.12 ms in a match on an RTX 3070 Ti
  (macondo.md:386), or 16 ms per row on one Apple M5 CPU core (magpie.md). Against ~0.6–1.2 µs, that is roughly
  100–200× faster than the GPU path and over 10,000× faster than the CPU path. This is the "faster" edge the
  owner asked for. Whether a 256-wide net is *accurate enough* is the open question, and
  training data decides it.

These are estimates, not measurements. A micro-benchmark of a 256-wide int16 accumulator update on our CPU is
the first thing to build, before any training (see Open questions).

### Doesn't apply (or only weakly)

- **The hybrid "classical eval for lopsided positions" and the dual small net.** Stockfish dropped both.
  Scrabble has no cheap material count that settles a position. The table win% is the nearest analogue, and it
  is what the net replaces.
- **King-square buckets and refresh on king moves.** Scrabble has no piece whose position conditions everything.
  Its slow-moving state is the bag size, which is already a stack key.
- **Lazy accumulator updates for pruned nodes.** Rollouts are single lines with one eval at the end, so nothing
  is pruned between move and eval. Laziness does matter in the endgame and pre-endgame searches if a net is
  ever used there.
- **Leela data at Leela's scale.** There is no public Scrabble corpus of tens of billions of labelled positions.
  Self-play plus relabelling is the only route, and it is bounded by our CPU (see testing-method.md for
  throughput). GPU compute for training is an open decision (research-plan.md).

## Open questions

- What does a 256- and a 1024-wide int16 accumulator update actually cost on our i5-9500T, with 25 and 160
  rows? (Micro-benchmark; it replaces the estimate table.)
- Does MAGPIE keep cross-sets incrementally in a form a feature extractor can read cheaply? (Check
  `src/impl/move_gen.c` / board code at `b781018`.)
- How much do (root + candidate) accumulators differ between rollouts, given that the root player's draws vary?
  Should the draw be part of the cached state or of the per-rollout delta?
- Teacher choice: is a deep MAGPIE sim's win% or Macondo's CSW24 transformer the better label source, per CPU
  hour?
- Which Stockfish 2026 changes would most likely transfer as data recipes (search-tree sampling ratio, λ
  schedule, WDL filter)? Answering needs the nettest recipes (vondele/nettest), not read here.
