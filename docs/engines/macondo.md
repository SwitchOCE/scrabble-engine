# Macondo

- Source: https://github.com/domino14/macondo, commit `9c33baa636258ce1a2add1e843f9c8ce1a939436` (from `pins.tsv`, 2026-11-16)
- Licence: GPL-3.0 (`LICENSE.md`)
- Language / build: Go (`go.mod` says `go 1.26.1`), `make`. The value nets need ONNX Runtime 1.29 through cgo
  (CPU), or Triton plus TensorRT on an NVIDIA GPU (`README.md:39-82`, `README.md:152-176`).
- How to drive it headless: shell commands, autoplay and the external-engine hook. See
  [../harness/reuse-check.md](../harness/reuse-check.md); not repeated here.

**This dossier is a diff from [magpie.md](magpie.md).** It covers only what Macondo does differently, its
defaults, its evaluation call sites, and what matters for using its autoplay as our referee.

**Citation convention.** A `path:line` with no repo prefix is domino14/macondo at `9c33baa`. Lines were read
from the working tree of `reference/macondo`, which is at the pin. PRs and issues are
`domino14/macondo#n` and were read from `reference/history/macondo/prs.json` and `issues.json`. MAGPIE
refs are jvc56/MAGPIE at `b781018`, taken from its dossier. Most of the numbers below come from Macondo's
own lab notebooks: `pytorch/RUNS.md`, `pytorch/experiments.md`, `pytorch/SHELVED.md` and
`docs/inference_experiments.md`. We measured none of them.

## Summary

- **Macondo ships a CSW24 value net, and MAGPIE does not.** It is a transformer that scores the top 50 static
  moves, used only as a one-ply ranker (`FAST_ML_BOT`). In NWL23 it plays level with a 2-ply, 100-candidate
  sim and below 3- and 5-ply sims, at a few ms per move. The only CSW24 result is against the static
  HastyBot.
- **Inference is a Bayesian likelihood, not a cutoff.** Each candidate leave gets a 2-ply mini-sim, a
  softmax over the log-odds of win probability, and a temperature fitted to real games by bag size. Against
  the same sim without it: +0.82 win points over 53k pairs, on a lab build (see Measurements). MAGPIE
  accepts a leave if the play was within 5 points of best (magpie.md). The two have never been matched head
  to head.
- **The sim stopping rule is older:** uniform allocation with UCB/LCB elimination, a Stop99 confidence
  level and an iteration cap. MAGPIE uses top-two BAI. An open PR (#538) ports MAGPIE's BAI and move
  generator into Macondo.
- **The pre-endgame is weaker:** the bot runs the PEG only with 1 tile in the bag (n>1 has been broken since
  2024, issue #325). With 2–7 in the bag it sims to the end of the game and, at bag ≤2, searches the
  endgames its rollouts reach (#568).
- **What we would take:** the value-net program (recipe, ablations, negative results) and the inference
  model. The engine code itself is converging on MAGPIE's.

## What Macondo does differently

### Value net (CSW24 and NWL23)

**Facts.**

- **Models.** Three nets are published on Hugging Face (`domino14/macondo-value-nets`), and not in the repo
  (`README.md:84-117`, `README.md:119-150`):
  - `macondo-tf` and `macondo-tf-csw`: 12 layers, width 256, 9.6M parameters, trained on 81M HastyBot
    self-play games;
  - `macondo-tf-selfplay`: 8 × 192, 3.7M parameters.

  Each net has one token per square, gets the opponent's last play as input, and outputs P(win) − P(loss)
  plus a spread head (`README.md:86-92`; `pytorch/README.md`, "Heads, weights, epochs";
  `game/mlhelper.go:22-24`, `game/mlhelper.go:37-55`).
- **Where it is used: one place in play.** `FAST_ML_BOT` generates the top 50 moves by static equity, sends
  them to the net in one batch, and plays the highest value (`ai/bot/bot_player.go:409-438`). Two
  refinements:
  - In decided games (|value| ≥ 0.97), near-ties within 0.01 are ranked by expected final spread
    (`ai/bot/mlrank.go:14-33`). This is win-neutral and adds +7.3 spread per game (`pytorch/RUNS.md`, "Bot
    changes").
  - With an empty bag the bot plays the static best move, or a quick 2-ply search in autoplay
    (`ai/bot/bot_player.go:406-414`).

  The net is not used in sims, inference or the endgame. The enum `SIMMING_WITH_ML_EVAL_BOT = 16` exists
  (`api/proto/macondo/macondo.proto:154`), but no bot code handles it: grep finds it only in
  `shell/autocomplete.go:40`.
- **Strength.** 95% intervals, NWL23 unless marked; pair counts as given:

  | Opponent | Result | Source |
  | --- | --- | --- |
  | HastyBot (static), 100k pairs | `macondo-tf` 58.42 ± 0.18; `macondo-tf-csw` 58.55 ± 0.18 in CSW24 | `README.md:94-100` |
  | 2-ply sim (`SIMMING_BOT_NO_EG`, 100 candidates, Stop99), head to head | earlier `streamopen` net 49.04 ± 1.56 (1,250 pairs), i.e. level | `pytorch/experiments.md:1929-1940` |

  The sim ladder against HastyBot (no endgame solver): ML net (`streamopen`) 57.65 over 100k pairs; sims
  over 1,250 pairs each (SE about 0.82): 2-ply 58.62, 3-ply 60.10, 4-ply 60.04, 5-ply 62.80, 6-ply 62.32
  (`pytorch/experiments.md:2112-2122`). Only 2 → 5 ply (+4.2, about 3.6 SE) is clear; 2 → 3 ply (+1.48) is
  about 1.3 SE, within noise. The net plays "at
  a few ms per move against ~8 s" for the 2-ply sim (`pytorch/experiments.md:1905-1917`). By phase, against
  a 5-ply sim, the net is strong in the opening (gives up 0.09 win points per move) and weak late, with 9–29
  unseen (1.32) (`pytorch/experiments.md:2220-2238`). `pytorch/TRAINING.md:120-121` says HastyBot is
  "relatively stronger in CSW" and expects a smaller margin there, but the CSW net's 58.55 is in fact above
  the NWL23 net's 58.42. No CSW24 net-vs-sim match was found.
- **What made the gain** (`pytorch/TRAINING.md:10-36`):
  - four per-square "spatial" auxiliary heads, used in training only: **+4.0** (53.13 → 57.17);
  - streamed training (a fresh position per game on each of 6 passes): +0.55;
  - gradient-balanced auxiliary heads: +0.86.
  - Doubling the games from 27M to 54M added nothing (53.10 → 53.13). For the 8 × 192 nets, 54M → 81M games
    gave +0.49 against HastyBot (57.65 → 58.14) and 50.63 ± 0.16 head to head (+0.63); 108M CSW games added
    nothing (#552 body).
- **Tried and shelved** (`pytorch/SHELVED.md`, PR #540): built, measured and removed.
  - Rollout labels (16 2-ply rollouts with the net at the leaf): 52.03 against 53.19.
  - Sim distillation (fine-tune on 1.26M positions labelled by a 5-ply sim, four loss variants): 56.97 to
    57.52 against 57.65 ("ranking a full list of 50 by a noisy sim teaches noise").
  - Ownership heads: +0.
  - Ising board-energy features: +0.
  - **MAGPIE's 6-layer distilled student** (jvc56/MAGPIE@569cfe09): 55.80 against HastyBot, 48.07 head to
    head against its teacher, and only 6% faster here, because the GPU was not the bottleneck.
- **Configuration choices** (`pytorch/SHELVED.md`, "Measured, nothing to remove"; the knobs stay): top 100
  candidates instead of 50: +0, at 1.9× the time; self-play data from scratch is worse than HastyBot data
  (54.45 vs 55.39), but helps as a fine-tune.
- **Speed.** The model alone (3070 Ti, TensorRT fp16) runs 13,123 positions/s at batch 50. Through Triton in
  matches it delivers about 8,500/s end to end, limited by serving, not the GPU
  (`pytorch/experiments.md:1942-1960`).

**Inference.**

- A one-ply net equal to a 2-ply sim, at about 1/1000 of the time, is a strong data point.
- So is the shelved list: for this net, more data, distilling from a sim, and extra heads beyond the spatial
  ones were all dead ends.
- The open question for us is whether the net helps *inside* a search: at the sim leaf, or as the rollout
  policy. Not in Macondo; built on MAGPIE branches; no strength result found here (see magpie.md). A 5-ply
  sim is still about 5 points above the net against HastyBot.

### Rack inference

**Facts.**

- **Likelihood.** For each feasible opponent leave, a 2-ply mini-sim (top 10 static plays plus the play
  actually made; 200 iterations by default) gives win probabilities. The likelihood is a softmax over their
  log-odds at temperature tau (`rangefinder/inference.go:41-49`, `rangefinder/inference.go:177-215`,
  `rangefinder/inference.go:600-621`).
- **Temperature.** Tau follows a curve fitted by maximum likelihood to 16,550 BestBot turns on Woogles
  (`rangefinder/inference.go:488-550`, count at `rangefinder/inference.go:554`; #506). It is capped at 0.1 by default (`ai/bot/elite.go:374-379`;
  #567).
- **Coverage.** Leaves that were not measured get imputed likelihoods (Möbius inversion of
  containment-marginal lifts), so the posterior covers every leave (`rangefinder/imputation.go`;
  `docs/leave_imputation.md`; #507). The sim then samples opponent racks from that posterior
  (`ai/bot/elite.go:328-341`; `montecarlo/montecarlo.go:1042-1049`).
- **Budget.** Live play gives inference a 20 s wall clock by default (`ai/bot/elite.go:273-276`). Game-pairs
  mode uses a leaf budget of 200 instead, which costs "about 94 seconds a turn" on one thread
  (`rangefinder/enumerate.go:33-36`, `rangefinder/enumerate.go:41`).
- **Strength** (2-ply, paired, `SIMMING_INFER_BOT_NO_EG` vs `SIMMING_BOT_NO_EG` on lab build `f4e4300b`, which
  runs on the MAGPIE engine, not stock master; `docs/inference_experiments.md:7-27`, `docs/inference_experiments.md:198-204`,
  `docs/inference_experiments.md:720-724`):
  - **50.82 ± 0.19** over 53,155 pairs, seven seeds (`docs/inference_experiments.md:1150-1180`).
  - At 5 ply: 50.95 ± 0.70 over 5,000 pairs (`docs/inference_experiments.md:83-94`).
  - Ceiling: an oracle told the true leave scored 53.34 ± 1.11 at 5-ply (unpaired;
    `docs/inference_experiments.md:31-63`).
  - Reads are well calibrated but carry little information (0.39–0.85 bits over the prior;
    `docs/inference_experiments.md:1253-1264`).
- **Inference vs the value net.** The value net, which sees the last play, reads it as well as the inference
  bot does and holds no extra information: net vs inference bot +0.002 ± 0.012 win points per turn
  (`docs/inference_experiments.md:1266-1279`).
- **Tried and kept as options, with no measurable gain:** two-turn reads ("carry", +0.03 ± 0.23), bigger
  leaf budgets (500 leaves on MAGPIE's engine: 50.73 ± 0.87), quieter mini-sims, a confidence gate
  (`docs/inference_experiments.md:142-158`, `docs/inference_experiments.md:1150-1180`). The lab tooling sits
  on an open branch (#541, no body). The method is written up in the Woogles blog post the notebook names,
  `2026-04-26-bayesian-inference-scrabble.md` (`docs/inference_experiments.md:38`); its URL,
  https://blog.woogles.io/posts/2026-04-26-bayesian-inference-scrabble, is UNVERIFIED (not fetched).

**Inference.**

- This inference model is a likelihood where MAGPIE's is a cutoff, which looks better founded. But no
  head-to-head of the two exists, and the +0.82 was measured on a lab build, not on master. MAGPIE has an
  open softmax PR (#938, magpie.md).
- Its gain is real but under 1 win point. The oracle ceiling (about 3 points at 5-ply) bounds what any read
  can add.
- That the net reads the last play as well as inference suggests a learned evaluator given the last move can
  replace explicit inference.

### Simulation and stopping

**Facts.**

- **Allocation.** In each iteration every candidate still in play gets one rollout, all with the same
  opponent rack drawn once for that iteration (`montecarlo/montecarlo.go:1034-1099`).
- **Rollouts.** Each ply plays the top static-equity move (`montecarlo/montecarlo.go:1117-1172`,
  `montecarlo/montecarlo.go:1249-1265`).
- **Leaf value.** The win% table on spread + leftover leaves, flipped for even plies
  (`montecarlo/montecarlo.go:1174-1199`).
- **Stopping** (`montecarlo/stopping_condition.go:16-33`, `montecarlo/stopping_condition.go:101-116`,
  `montecarlo/stopping_condition.go:228-260`):
  - every 128 iterations, drop arm i when its UCB < the leader's LCB, with c = √(2 ln(K/δ)) (Bonferroni over
    K live arms) and δ = 0.01 for Stop99;
  - stop when one arm is left;
  - hard cap at 2000 + 625 × plies iterations;
  - after 750 iterations, a play "materially similar" to the leader (same tiles, same square) is pruned
    (`montecarlo/stopping_condition.go:31`, `montecarlo/stopping_condition.go:270-274`);
  - if the leader's win% is under 0.5% or near 100%, fall back to an equity tie-break.

  MAGPIE uses top-two IDS with a GK16 GLR stopping test on the paired variance (magpie.md).
- **Endgame leaves inside sims** (#568, merged 2026-11-10): at bag ≤2, a rollout that empties the bag and
  leaves a margin within 60 points gets a 2-ply result-only endgame search (100 ms cap, cached per sim) in
  place of static play-out (`montecarlo/endgame_leaf.go:17-35`). Results:
  - bag 2: 50.55 ± 0.47 over 2,150 pairs;
  - bag 3: 49.92 ± 0.67, so it is not enabled there;
  - cost: about 3× per bag-2 decision.

  These were measured on a "MAGPIE lab build" with both sides solving endgames, not on stock master (#568
  body).
- **Speed.** Sims got 2.2× faster in #572 (2026-11-16, the pin day) by porting MAGPIE-style move-generation
  shortcuts. Macondo's own leave map "mirrors MAGPIE's LeaveMap" (`leavemap/leavemap.go:6`), and its
  cross-set cache is "MAGPIE's" idea (`cross_set/cache.go:28`).
- **Open PR #538 (2026-10-15)** would replace all of this: MAGPIE as the move generator via cgo, MAGPIE's
  BAI as the stopper, MAGPIE's win% tables, and MAGPIE's static evaluation. Its body reports:
  - MAGPIE's own sim and the ported BAI pick the same move 96% of the time (44 positions × 5 seeds);
  - sims 1.8–3.7× faster;
  - "all HastyBot match baselines need re-running".
- **Fitted end-of-line win model** in place of the win% table: 50.79 ± 0.84 over 2,500 pairs (1.8 SE).
  `pytorch/SHELVED.md` calls it "the most promising thing on this list" (section "Fitted end-of-line win
  model").
- **Issue #386 (open):** "Need something in between monte carlo and full peg"; the sim was badly wrong at 9
  unseen.

**Inference.**

- On search technique, MAGPIE leads and Macondo follows it.
- Macondo's distinct contributions to simulation are two:
  - the measured sim-depth ladder: 5 plies clearly beats 2, 6 adds nothing over 5, and the steps between
    are within noise;
  - the endgame-leaf trick at bag ≤2.

### Pre-endgame and endgame

**Facts.**

- **Stage dispatch in the bot** (`ai/bot/elite.go:47-67`), by unseen tiles (bag + opponent rack):
  - ≤7: endgame;
  - exactly 8 (1 in the bag): PEG;
  - 9–14 (2–7 in the bag): a sim of `unseen` plies, i.e. roughly to the end of the game
    (`ai/bot/elite.go:109-119`).
- **PEG limits.** The PEG solver accepts up to 6 in the bag (`preendgame/peg.go:36`,
  `preendgame/peg.go:731-735`) but only considers plays that leave at most 1 in the bag by default
  (`preendgame/peg.go:515`). Issue #325 (open since 2024-03): "n-peg for n > 1 is broken for non-bag-emptying
  plays." #410 "N peg": its author commented on 2025-08-18 "we likely want to throw this PR away"; it was closed
  on 2026-11-12. MAGPIE's PEG
  covers 1–4 in the bag and beat Macondo on speed in all 27 positions both finished (magpie.md).
- **PEG settings.** The bot's PEG uses an endgame depth of 2–5 depending on spread (≥100 → 2, ≥75 → 3,
  ≥50 → 4, else 5), with iterative deepening and early cutoff (`ai/bot/elite.go:219-238`). The model is
  pessimistic: any possible loss counts as a loss (`preendgame/README.md:7-9`).
- **Endgame.**
  - Depth: the bot solves to `max(2, unseen + onRack − 1)` plies, i.e. near full depth
    (`ai/bot/elite.go:121-130`). MAGPIE's PlayChooser asks for unlimited depth by default; its CLI default is
    6 (magpie.md).
  - Leaf: the greedy leaf playout and the stuck-tile heuristics are credited to MAGPIE
    (`endgame/negamax/solver.go:329-330`).
  - Parallel search: "auto" is PV-splitting when threads > 1 (`endgame/negamax/solver.go:558-560`). The
    comment at `ai/bot/elite.go:170` ("ABDADA for 300+ moves, otherwise LazySMP") is stale.
  - Bug fixed: a multi-threaded TT bug giving wrong values (issue #549, fixed by #550 from olaugh).
  - Autoplay caps the endgame at 15 s (`automatic/game_runner.go:33`).

**Inference.**

- Neither the pre-endgame nor the endgame is better than MAGPIE's.
- For 2–7 in the bag, the "sim to the end" approach is a weak spot that both engines' authors acknowledge.

### Leaves

**Facts.**

- **Two generators sit in the tree.**
  - The older notebook pipeline: `notebooks/superleaves/autogenerate_superleaves.py` and
    `notebooks/superleaves/generate_superleaves.ipynb`, plus smoothing and comparison notebooks.
  - The Go self-play method in `automatic/calculate_leaves.go:3-11`. Its steps: collect (rack, score, bag)
    from millions of autoplay turns; normalise to the average score; weight each rack by draw probability;
    give each sub-rack its expected value; repeat until the values converge. This is the rack-based method
    MAGPIE's `leavegen` also implements (magpie.md, "How leaves are trained").
- **No census generator.** MAGPIE's census, ported from wolges, has no Macondo counterpart.
- **Shipped files.** Commit `faffb80` (2025-06-01, "add better CSW24 and NWL23 leaves") is dated one day
  before the Woogles post on BestBot's new rack-based leaves, which says they were made with MAGPIE
  ([New leave values for BestBot](https://blog.woogles.io/posts/2025-06-02-new-leaves), cited in
  magpie.md). At the pin the CSW24 leaves are not in the tree (`data/strategy/` holds only `default`); they
  are fetched next to the word graph (#513, #529).
- **`cmd/leaveval`** only prints the engine's leave value for each leave read from stdin, for inference
  diagnostics (`cmd/leaveval/main.go`). It is not a generator.

**Inference.** The method is the same family as MAGPIE's self-play leavegen and differs from wolges'
census. The timing of `faffb80` suggests BestBot's CSW24 leaves came from the MAGPIE run, but whether the
files are byte-identical is not checked (see Open questions).

## Defaults

| Setting | Macondo (bot: `SIMMING_BOT` / `SIMMING_INFER_BOT`) | Macondo shell | MAGPIE (magpie.md) |
| --- | --- | --- | --- |
| Candidates simmed | 100 (`ai/bot/elite.go:93-102`; autoplay `-simplays1/2`, `shell/specs.go:302`) | from the last `gen` | 100 CLI (`config.c:10737`); 15 PlayChooser |
| Sim plies, midgame (>14 unseen) | 2, or `minSimPlies` if larger (`ai/bot/elite.go:109-119`) | `sim`: 2 (`shell/sim.go:174-175`); `explain`: 5 (`shell/api.go:2315`) | 5 CLI (`config.c:16959`); 2 PlayChooser |
| Sim plies, 2–7 in bag | `unseen` (9–14) unless `-fixedsimplies` (`ai/bot/elite.go:113-114`) | as midgame | as midgame |
| Stopping rule | Stop99 UCB/LCB elimination (`ai/bot/elite.go:312`) | `sim`: none, runs until stopped (`shell/sim.go:31`); `explain`: Stop99 | BAI top-two IDS + GK16 GLR, δ = 0.01 |
| Iteration cap | 2000 + 625 × plies (`montecarlo/stopping_condition.go:29-30`, `:113-115`) | same | min 500 per arm; `-tlim` 60 s |
| Sim time limit | 30 s in autoplay, none in pairs mode (`automatic/game_runner.go:32`; reuse-check.md) | none | 60 s |
| Inference | `SIMMING_INFER_BOT` only; 20 s or 200 leaves in pairs (`ai/bot/elite.go:273`; `rangefinder/enumerate.go:41`) | `infer` command | on by default, 5-point cutoff |
| Endgame-leaf search in sims | bag ≤2, margin 60, 2-ply, 100 ms (`montecarlo/endgame_leaf.go:30-35`) | on | no |
| Pre-endgame trigger | 1 in bag (`ai/bot/elite.go:62`) | `peg`, ≤6 in bag | 1–4 in bag (PlayChooser/autoplay) |
| PEG endgame plies | 2–5 by spread (`ai/bot/elite.go:222-231`) | flag | 3 (`-pegplies`) |
| Endgame trigger / depth | ≤7 unseen; `max(2, unseen + onRack − 1)` (`ai/bot/elite.go:47`, `:128-130`) | `endgame`: 4 (`shell/api.go:48`) | bag empty; 6 (`-eplies`) |
| Value-net bot | top 50 (`ai/bot/mlrank.go:33`), decided rule at 0.97 / 0.01 (`ai/bot/mlrank.go:26-28`) | `mleval` | none |

## Evaluation call sites

| Site | What Macondo uses | Adding a neural eval |
| --- | --- | --- |
| Leave | KLV `.klv2` lookup (`equity/combined.go:68`; leavemap) | Same as MAGPIE (E1). |
| Static move | score + leave + pre-endgame table + opening placement; endgame ±rack adjustment (`equity/combined.go:54-81`). No PAT | Same constraint as MAGPIE (E2). |
| Rollout policy | top static move, or a stochastic static move as an option (`montecarlo/montecarlo.go:1249-1265`) | Not tried in Macondo; built on MAGPIE branches; no strength result found here (see magpie.md). |
| Sim leaf | win% table on spread + leftover and unseen count (`montecarlo/montecarlo.go:1188-1198`); endgame search at bag ≤2 | One call per rollout, like MAGPIE's E4. A Triton client already exists. Not tried in Macondo; built on MAGPIE branches; no strength result found here (see magpie.md). The fitted logistic replacement gave +0.79 (1.8 SE). |
| Inference | 2-ply mini-sim per leave, softmax over log-odds (`rangefinder/inference.go:199-215`) | The mini-sim's win% could come from the net, one batch per leave. Measured: the net already reads the last play as well as inference does. |
| Endgame leaf | greedy playout (`endgame/negamax/solver.go:73-85`, `:329-330`) | Same as MAGPIE (E6). |
| **Root ranking** | **`FAST_ML_BOT`: net over the top 50** (`ai/bot/bot_player.go:409-438`) | Exists. This is a site MAGPIE has no counterpart for. |

**Inference** (effort estimates).

- **Net at Macondo's sim leaf.** A few days of Go: the Triton/ONNX client, feature builder and batching
  exist (`game/mlhelper.go:37-55`).
- **Rollout speed.** A rollout is one synchronous call chain, so the serving overhead (about 2 ms per request
  through Triton) would dominate. A 5-ply rollout costs about 203 µs on one thread (#572), so one unbatched
  request per rollout would make it about 11× slower (2 ms ÷ 203 µs), before counting the model's own time.
- **Where to do it.** Re-ranking at the root with a short sim over the net's top-k is cheaper and is not
  tested either. Doing either in MAGPIE's C loop, with a CPU net, avoids gRPC but needs a small net; the
  6-layer student is the existing attempt.

## Autoplay as referee: what reuse-check.md doesn't cover

**Facts.**

- **Experiment knobs per player** (`shell/specs.go:298-346`; `shell/helptext/autoplay.txt:143-146`):
  - `-fixedsimplies1/2` (every sim exactly N plies, late game included);
  - `-simplays1/2`;
  - `-tritonmodel1/2` (net vs net);
  - `-quickendgame N` (2-ply search in close endgames for bots without a solver; #556);
  - `-inferencebudget1/2`.
- **No-endgame bot codes.** `SIMMING_BOT_NO_EG` and `SIMMING_INFER_BOT_NO_EG` isolate midgame quality
  (`api/proto/macondo/macondo.proto:155-161`).
- **`FAST_ML_BOT` as a seat.** It can be a fixed-strength reference opponent in CSW24. It needs either
  Triton on an NVIDIA GPU or ONNX Runtime on the CPU (`README.md:152-176`). It fails at start-up if its
  Triton model is not served (`ai/bot/bot_player.go:210-243`; #544).
- **Cost of a sim match.** A fixed 2-ply sim bot used about 111 CPU-s per game in a pilot. The 1,250-pair
  2-ply run took 7.5 h on 10 threads; 3-ply took 12.2 h on 14 threads (`pytorch/experiments.md:1875-1927`).
- **Pair statistics.** The SE of a 100k-pair match is 0.09 win points, and of the difference of two matches
  0.13 (`pytorch/RUNS.md:6-8`). Pairing is "worth about 3x the games" (`docs/inference_experiments.md:77-81`).
- **Decision-quality tools.**
  - `cmd/decidelab` (master): grades a bot's choices with a long sim that knows the true leave.
  - `cmd/simlabel select|sim|check`: measures agreement with a 5-ply sim by phase.
  - `cmd/mlreads`.

  `docs/inference_experiments.md:22-27` says the screening judges are on branch `claude/inference-experiments`;
  `pytorch/SHELVED.md` covers `simlabel`.
- **Moving target.** If #538 merges, Macondo's static evaluation, move generator and stopper become
  MAGPIE's, the wasm target is dropped, and cgo becomes mandatory (#538 body).

**Inference.**

- Pin Macondo at `9c33baa` for the referee and do not track #538 mid-study. A merge would change both
  built-in bots and baselines.
- Match throughput on our 6 cores, from those costs (sim bot vs HastyBot; HastyBot is nearly free):
  - 2-ply: 6 × 86,400 CPU-s ÷ 111 CPU-s per game ≈ 4,700 games ≈ **2,300 pairs/day**;
  - 3-ply: 12.2 h × 14 threads ÷ 2,500 games ≈ 246 CPU-s per game ≈ **1,000 pairs/day**;
  - 4–5 ply: 4-ply ran about 60 pairs/h on 14 threads (`pytorch/experiments.md:1939-1940`), about 420 CPU-s
    per game, so **a few hundred pairs/day**.

  A sim-vs-sim match costs about twice that per pair. An inference bot adds about 94 s per turn on one
  thread in pairs mode (`rangefinder/enumerate.go:33-36`). At 1,000–2,300 pairs/day a ±1-point interval
  (about 10k pairs) takes a week or more. Plan matches with SPRT or against a cheap static opponent.

## Everything else

- **Move generation:** Go GADDAG/KWG with a WMP and MAGPIE-derived shortcuts. Slower than MAGPIE, and #538
  would replace it with MAGPIE.
- **Leaves / formats:** same `.kwg`/`.klv2` as MAGPIE; per-lexicon leaves next to the word graph (#513). See
  "Leaves" above.
- **Build:** Go plus optional cgo for ONNX; go 1.26.1 (reuse-check.md says ≥1.24).
- **Threading:** goroutines per sim iteration and endgame worker. In pairs mode a sim must use 1 thread
  (reuse-check.md).
- **UI / other:** a shell with an analyzer, an LLM "explainer", puzzles, a Woogles bot, Lambda deploy. Not
  relevant here.
- **Exchange / pass:** same model as MAGPIE (leave-only equity). Inference models an exchange by its leave
  value (#537).

## Measurements

None measured by us. Quoted:

| What | Number | Settings | Hardware | Source | Measured by |
| --- | --- | --- | --- | --- | --- |
| Value net vs HastyBot, CSW24 | 58.55 ± 0.18% | `macondo-tf-csw`, 100k pairs | not stated | `README.md:98` | Macondo authors |
| Value net vs 2-ply sim, head to head | 49.04 ± 1.56% | NWL23, `streamopen` net, top 50, 1,250 pairs | not stated | `pytorch/experiments.md:1929-1940` | Macondo authors |
| Sim ladder vs HastyBot | 58.62 / 60.10 / 60.04 / 62.80 / 62.32% (2–6 ply) | NWL23, 100 candidates, Stop99, no endgame solver, 1,250 pairs each | not stated | `pytorch/experiments.md:2112-2122` | Macondo authors |
| Inference vs no inference | 50.82 ± 0.19% | 2-ply, 53,155 pairs, `_NO_EG` bots, lab build `f4e4300b` on the MAGPIE engine, not master | deb192, 2× EPYC 7K62 (`docs/inference_experiments.md:31-36`, `:720-724`) | `docs/inference_experiments.md:1176-1180` | Macondo authors |
| Endgame-leaf search in sims, bag 2 | 50.55 ± 0.47% | 2,150 pairs from bag-2 positions, "MAGPIE lab build", not master | not stated | #568 body | Macondo authors |
| Net throughput, model alone | 13,123 pos/s (3.81 ms per batch of 50) | TensorRT fp16, random inputs | RTX 3070 Ti | `pytorch/experiments.md:1942-1960` | Macondo authors |
| Net throughput, in match | ~8,500 pos/s (~5.8 ms per 50-candidate request) | via Triton gRPC | RTX 3070 Ti | `pytorch/experiments.md:1952-1955` | Macondo authors |
| Sim rollouts | 4,922 / 31,551 / 45,216 per s (1 / 8 / 16 threads) | 60 positions, 15 candidates, 5 plies, WMP on | i5-12600K | #572 body | Macondo authors |
| 2-ply sim bot cost | ~111 CPU-s per game | fixed 2-ply pilot, 6 pairs | not stated | `pytorch/experiments.md:1875-1893` | Macondo authors |

Derived budgets, with denominators:

- In-match net cost ≈ 5.8 ms ÷ 50 candidates ≈ **0.12 ms per scored position**, on a 3070 Ti.
- Macondo 1-thread rollout ≈ 1 s ÷ 4,922 rollouts ≈ **203 µs per 5-ply rollout** (i5-12600K). MAGPIE's
  dossier gives about 100 µs per 4-ply rollout, on unstated hardware, so the two are not directly
  comparable.

## History

- 2025-06 to 2025-10: CNN value nets, one-ply, NWL18 (`pytorch/experiments.md:3-880`). The best was about
  52.5% against HastyBot.
Dates are merge dates.

- 2026-04: Bayesian inference with a tau sweep, on a branch (`docs/inference_experiments.md:31-63`).
- 2026-07-25: fitted tau (#506). 2026-07-30: greedy-playout endgame leaf from MAGPIE (#509).
- 2026-08-16: complete posterior (#507).
- 2026-09-18: game pairs (#522).
- 2026-10-19: external-engine autoplay (#504), transformer nets (#535), shelved experiments (#540).
  2026-10-25: nets per lexicon, including CSW (#552). #538 (MAGPIE port) opened 2026-10-15, still open.
- 2026-11-10: tau cap (#567), sim endgame leaves (#568). 2026-11-12 and 11-14: MAGPIE endgame speedups (#569,
  #571). 2026-11-16: sims 2.2× faster (#572).
- **Dropped or stalled** (closed unless marked; one line each):
  - Endgame #195 (2022): sort endgame plays by alpha estimate; closed with "i believe this doesn't apply
    anymore?".
  - Endgame #198 (2022): generate a pass at the last ply only after an opponent pass; closed the same day,
    no comment.
  - Endgame #201 (2022): better hash uniqueness; "closing as this code is gone".
  - Endgame #204 (2022): first transposition table; closed with no body (a TT landed later).
  - Endgame #360 (2024-09, closed 2026-11-12): temporarily disable LazySMP deeper searching; no body.
  - PEG #410 "N peg": debug-only (see above).
  - PEG #482 (2026-04): debug tracing for the PEG solver; "i think this was cherry picked away".
  - Sim #385: "sim avoid-prune option"; no body.
  - Movegen #433 (2025-12, closed 2026-03): "Shadow movegen" in Go; closed with "nope". Shadow ideas
    arrived later through #572 and #538.
  - Movegen #403 (open since 2025-06): "start on a magpie interface"; no body, superseded in practice by #538.
  - Referee stats #498 (open since 2026-07): replaces the Wald interval in `autoanalyze` with a Wilson
    interval "to avoid overshoots". This bears on our referee statistics; check which interval
    `autoanalyze` prints before quoting its CIs.
  - #558: superseded by publishing the nets on Hugging Face.
  - The `SHELVED.md` list above.

## Inference

- Macondo's value now lies in its experiments more than in its engine. The engine is becoming a Go shell
  around MAGPIE (#538). The lab notebooks are an unusually complete record of what does and does not help a
  learned evaluator, with paired, large-N results.
- The headline net result (one ply equals a 2-ply sim) sets a floor for what a learned eval inside a search
  must beat. A 5-ply static-rollout sim is still about 5 points stronger against HastyBot.
- Development, like MAGPIE's, is heavily AI-agent driven (Claude Code footers, `claude/` branches). Expect
  churn.

## Relevance to the three decisions

**1. What to fork.**

- Macondo is not a better fork base than MAGPIE: it is slower, its PEG is limited to 1 in the bag, its
  stopper is older, and it is moving onto MAGPIE's core.
- What to reuse is its *training pipeline and results*: `cmd/mlproducer`, `pytorch/training.py`, the recipe
  in `pytorch/TRAINING.md` and the published CSW24 net. Both are GPL-3.0, so this is the same licence
  question as MAGPIE. The net weights' licence is not stated in the files read.

**2. Where a neural eval pays off.**

- Macondo has measured the root-ranking use: equal to a 2-ply sim and weak late in the game.
- Macondo has not put the net inside a sim, at the leaf or as the rollout policy. That work is built on
  MAGPIE branches; no strength result found here (see magpie.md). A CSW24 net exists to test it with no
  training.
- Its negative results narrow the training work:
  - sim distillation does not help a ranker;
  - more of the same data saturates;
  - spatial auxiliary heads are worth about 4 points.

**3. How we prove we're stronger.**

- Use the same method: game pairs, a 95% interval on the paired win share, tens of thousands of pairs for
  sub-point effects, and a ladder of fixed opponents (HastyBot, fixed N-ply sims, `FAST_ML_BOT`).
- On 6 CPU cores, sim matches reach about 2,300 pairs/day at 2-ply, 1,000 at 3-ply and a few hundred at 4–5
  ply (see "Autoplay as referee"). Strength claims at ±1 point need either
  much more compute or cheap proxies, such as `decidelab` and `simlabel`-style agreement with a deep sim.

## Open questions

- How does `macondo-tf-csw` do against a 2-ply and a 5-ply sim **in CSW24**? Only the HastyBot number
  exists.
- Does the net help as a sim leaf or a rollout policy? Not tried in Macondo; built on MAGPIE branches; no
  strength result found here (see magpie.md).
- What does the net cost on our CPU through ONNX Runtime, per 50-candidate batch? (To measure.)
- What licence do the Hugging Face weights carry? (Check the model card.)
- Will #538 merge, and when? It changes the referee's built-in bots.
- Was the 81M-game CSW training set generated by HastyBot with CSW24 leaves? (`pytorch/TRAINING.md` says
  HastyBot self-play; check `pytorch/results/`.)
- Does the fitted end-of-line win model (+0.79, 1.8 SE) hold up over a longer match? Nobody reran it.
- Are Macondo's fetched CSW24 `leaves.klv2` and MAGPIE-DATA's CSW24 `.klv2` the same file? Compare
  checksums once both are downloaded.
- Which interval does `autoanalyze` print at the pin, Wald or Wilson (#498 open)?
- Does Macondo's 2–7-in-bag "sim to the end" lose measurably to MAGPIE's 2–4-in-bag PEG? Not measured.
- What does Sheppard 2002 (Maven) say about pre-endgame and simulation design? UNVERIFIED, not read.
