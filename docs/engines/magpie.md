# MAGPIE

- Source: https://github.com/jvc56/MAGPIE, commit `b78101815898641c5f449a7d8b51101b58a2caf0` (from `pins.tsv`, 2026-11-15)
- Licence: GPL-3.0 (`LICENSE.md`; README.md:1023-1025)
- Language / build: C, `make` (GCC or Clang). Release builds are `-O3 -flto -march=native` plus Clang
  profile-guided optimisation; board size and rack size are compile-time constants (docs/building.md:10-31, 67-73;
  Makefile:253). Data (lexica, leaves, win% tables, about 195 MB) is a separate download from
  `jvc56/MAGPIE-DATA` (README.md:227-240, 787-795).
- How to drive it headless: script mode (`./bin/magpie <command> <settings>`), the interactive prompt in
  `-mode sync`, or the C library `libmagpie` (string-in, string-out command API) (README.md:888-944;
  src/impl/cmd_api.h:16-29). Engine-vs-engine and self-play: `autoplay` with game pairs (README.md:645-737).

**Citation convention.** Every `path:line` without a repo prefix is jvc56/MAGPIE at `b781018` (full SHA above).
Line numbers were read from the clone in `reference/magpie`; its history export
(`reference/history/magpie/commits.tsv`) tops out at `b781018`, matching the pin. PRs are `jvc56/MAGPIE#n`
(remote: `https://github.com/jvc56/MAGPIE.git`), with the merge or squash commit's short SHA where
`commits.tsv` has one. Macondo refs are domino14/macondo at `9c33baa`; wolges refs are andy-k/wolges at
`be00002`. Speed numbers are quoted from PR descriptions, with their settings; none were measured by us.

## Summary

- **Does well:** a fast, heavily engineered C core: shadow-pruned GADDAG move generation plus anagram word maps
  (WMP) and per-rack precomputed leave tables (RIT); a modern simulation driven by best-arm identification
  (top-two sampling, GLR stopping, common random numbers, bag cycling); a full parallel endgame (ABDADA, TT,
  iterative deepening) and a 1–4-in-bag pre-endgame solver. Strong testing tools: seeded autoplay with game
  pairs, timed PlayChooser matches, and a distributed-compute client (birdtest).
- **Does badly / weak spots:** evaluation is still hand-built tables: leave values that ignore the board, a
  linear positional term (PAT), a pre-endgame bag adjustment, and a win% table keyed only by spread and tile
  counts. Rollouts play greedy static-equity moves. Inference is a hard cutoff ("within 5 equity of best"),
  not a likelihood. The default endgame is depth-limited (6 plies plus greedy playouts), not exact.
- **Moving fast:** 784 PRs (numbered up to #995), about 400 of them opened since June 2026, many by one contributor (olaugh). Defaults
  changed in the week before the pin (PAT on by default, #987; census-steered sims, #949). Any fork lands
  on a moving target.
- **What we would take:** the movegen and its tables, the BAI sim framework, the endgame and PEG solvers,
  the census leave generator and the autoplay/game-pair harness. The places a learned evaluator would plug in
  are few and well isolated (see "Neural evaluation").
- **Relation to Macondo:** started in 2023 as a C rewrite of Macondo; now ahead of it in speed and in
  several algorithms, sharing its formats and data.

## Pipeline

From "here is a position" to "here is a move" in the default CLI flow (`gsimulate`, then `tcommit`):

1. **Load position.** GCG or CGP (README.md:350-365). Each player carries its own KWG, KLV, WMP/RIT/WIT,
   PAT weights and pre-endgame table (`players_data`; src/impl/config.c:17072-17095).
2. **Generate candidates.** `generate_moves` with `MOVE_RECORD_ALL`, sorted by static equity, keeping the top
   `-numplays` (100 by default; src/impl/config.c:10737) (src/impl/simmer.c:259-277).
3. **Look up leaves once per rack.** At the start of every generation, the values of all 2^7 sub-racks go into
   a 128-entry `LeaveMap`, from the RIT if present, else by walking the KLV; exchanges are recorded in the same
   walk (src/impl/move_gen.c:3681-3751, 431-480).
4. **Score each move.** `static_eval_get_move_equity_with_leave_value` = score + leave + pre-endgame adjustment
   + PAT (+ opening placement penalty); with an empty bag, ±2× rack instead of leave (src/ent/static_eval.h:103-114,
   160-185).
5. **Infer the opponent's leave** from their last play, if `-sinfer true` (default; src/impl/config.c:17021)
   (src/impl/simmer.c:177-191; src/impl/inference.c:448-538).
6. **Simulate** with BAI over the candidates: each sample is a rollout (or a bag-cycled group of rollouts),
   valued by a win% table lookup blended with a sigmoid of spread (src/impl/simmer.c:210-234;
   src/impl/random_variable.c:565-723; src/ent/sim_args.h:172-209).
7. **Choose** the best arm by mean utility (src/ent/sim_results.c:1018-1039).

With an empty bag the `endgame` command (or PlayChooser's ENDGAME mode) runs instead; with 1–4 in the bag,
`peg` (or PlayChooser's PEG mode). In the plain sim path an empty bag makes the sim play every candidate out
once to the end of the game (src/impl/simmer.c:201-205). PlayChooser picks the mode by bag size
(src/impl/play_chooser.c:330-344).

## Move generation

MAGPIE generates moves on a GADDAG stored as a KWG (the wolges format; README.md:842-846, 960-963), with
"shadow playing": each anchor first gets an upper bound on the best equity any of its moves can reach, from
the best leave value of each leave size (`best_leaves`) and a score bound, and anchors are searched best-bound
first, so a best-move-only generation (`MOVE_RECORD_BEST`) can stop early (src/ent/static_eval.h:116-154;
src/impl/move_gen.c:1860-1993). On top of that: the **WMP** word map, an anagram index of words by length with blank
variants, inspired by the González Romero et al. anagram method (src/ent/wmp.h:24-54; README.md:991-996);
the **RIT**, a per-full-rack table holding all 128 sub-rack leave values and playthrough letter masks
(src/ent/rack_info_table.h:22-36); the **WIT**, letter masks for words containing a given block
(src/ent/word_info_table.h:13-29); and in simulations a **best-move carry**, which remembers each rack's best
move and per-lane bounds across rollouts so later generations skip lanes that cannot beat it
(src/ent/best_move_carry.h:17-31; #824 `d94346d9`). The endgame uses word-pruned KWGs (only words formable
from unseen tiles, also filtered by cross-checks; src/impl/word_prune.h:20-36; #689) and incremental move
lists that regenerate only lanes touched by the last moves (#693 `c107f4ea`). Speed: RIT plus movegen caching
gave 1.27× sim throughput from caching alone and 1.34× with the RIT (#514 `00bb5126`, title).

**Inference.** The shadow bound needs every non-score term of equity to have a cheap upper bound
(src/ent/static_eval.h:116-125 states this as an invariant). This is the main constraint on putting a board-aware
learned evaluator inside move generation.

## Static evaluation and leaves

### Representation and lookup

- **Equity** is an `int32_t` in millipoints (`EQUITY_RESOLUTION = 1000`) (src/ent/equity.h:11;
  src/def/equity_defs.h:6-16).
- **KLV** (from wolges): a KWG whose words are leaves, plus one float per leave; the leave's index is its rank
  in the word graph, computed with per-node word counts (src/ent/klv.h:19-38, 112-146, 291-357). Floats are
  read from the `.klv2` file and rounded to millipoints at load (src/ent/klv.h:190-242). A leave not in the KLV is
  worth 0 (src/ent/klv.h:89-95).
- **LeaveMap**: at the start of each move generation, the 128 sub-rack values of the current rack are put in an
  array indexed by a bitmask of which rack tiles are kept; as the generator places and removes tiles, the index
  changes one bit at a time, so each move's leave lookup is O(1) (src/ent/leave_map.h:11-25, 76-92;
  src/impl/move_gen.c:3681-3751).
- **RIT**: for full racks, the 128 values (packed to 24 bits) and the best leave per size are precomputed and
  copied in, skipping the KLV walk (src/impl/move_gen.c:3703-3751; src/ent/rack_info_table.h:22-36).

### The static equity function

`static_eval_get_move_equity_with_leave_value` (src/ent/static_eval.h:160-185):

- bag not empty: `score + leave + peg_adjustment + PAT penalty` (+ an opening vowel-placement penalty on an
  empty board, src/ent/static_eval.h:25-62, 168-172; `OPENING_HOTSPOT_PENALTY` −0.7, src/def/static_eval_defs.h:6);
- bag empty: `score − 2×(own remaining tiles) − 10` if not going out, `score + 2×(opponent's rack)` if going
  out (src/ent/static_eval.h:64-81; src/def/static_eval_defs.h:7).

Three extra terms beyond Macondo/Quackle-style "score + leave":

- **Pre-endgame adjustment** (`-pegadjust`): a table indexed by tiles left in the bag after the play plus
  `RACK_SIZE`, laid out as Quackle's was; fitted to static play's outcomes (src/ent/peg_adjust.h:9-24; #930
  `0e11dcf1`, #931 `f21e1c62`); each lexicon's table on by default since #989 `a1cd6c22`.
- **PAT (Positional Adjustment Term)**: trained linear penalties on the opponent's access to empty premium
  squares, binned by how many tiles a word reaching the square must use, with hook, floater, through-word and
  double-double window features (src/def/pat_defs.h:6-80; src/ent/pat.h:14). Opt-in from #713 `d646a8d1`;
  on by default since #987 `30ab2f31` (2026-11-13, two days before the pin). PAT in rollouts costs speed:
  1-thread 4-ply 10,457 → 6,911 iterations/s (0.66×; #747, open PR's measurement, Apple M4), and 0.69–0.89×
  at the TUI's 9-thread 4-ply defaults (#993).

### How leaves are trained

Three generators and a blender, all in-tree:

1. **`leavegen` (self-play, "rack-based")** (#240 `a6b44ea5`, #299 `d7d5a848`, #310 `21943381`).
   During autoplay every turn records `(full rack, equity of the best move)`; to cover rare racks, each turn
   also plays a forced "rare" rack that is under its target count and records it too
   (src/impl/autoplay.c:1176-1227; src/impl/rack_list.h:12-25; #244 `e8455638`). At the end of a generation, each full rack's
   mean best equity is spread to every leave it contains, weighted by the number of ways to draw the rest of
   the rack, and the overall average is subtracted:
   `value(L) = Σ_{R ⊇ L} w(R|L)·mean_equity(R) / Σ w(R|L) − average` (src/impl/rack_list.c:520-605).
   Each generation's leaves are used to play the next.
2. **`census`** (port of wolges' leave census; src/impl/census.h:13-26; #921–#923 `b3125ea7`, `044a8c56`,
   `2630c272`). On one board, for every full rack R the pool can deal, `best(R) = max over splits R = P + K of
   play_score(P) + leave(K)` (previous generation's leaves); every sub-rack S of R accumulates `w(R)·best(R)`;
   a leave's value is its mean over boards minus the empty leave's mean (src/impl/census.h:299-305;
   src/impl/census_gen.c:640-655). The catalogue is the full multiset lattice, 5,379,616 entries for English
   (src/impl/census.h:22-26). Boards come from greedy games stopped at fill levels spread over the game; recipe
   `3x256,2048` is wolges' measured best (src/impl/census_gen.h:10-24).
3. **`leaveblend`** mixes two tables leave by leave; wolges measured census and self-play tables mixed 50/50
   beating both by about a tenth of a win-percentage point (src/impl/leave_blend.h:6-14; README.md:769-776;
   wolges `lab/leavegen.txt:38-46` at `be00002`).

Win% tables (used at sim leaves, below) are trained the same way, from self-play (`autoplay winpct`, then
`convert winpct`, which picks the smoothing by cross-predicting two halves of the record) (README.md:854-881;
#703 `35cd2922`).

Literature: the Woogles post on BestBot's 2025 leaves describes the rack-based method (from Gilles of
Ortograf), reimplemented in MAGPIE, "six generations, each pitting 200 million game pairs against the
previous best", for 50.0% → 50.4% head-to-head on CSW24
([New leave values for BestBot](https://blog.woogles.io/posts/2025-06-02-new-leaves), 2025-06-02).
wolges reports the census "clear, immediate win is runtime, not a proven jump in play strength"
(`lab/leavegen.txt:553-563`).

**Contextual leaves tried (#630, open draft since 2026-07-27).** "KLV3" adds to the KLV2 value a small
additive model conditioned on the public unseen pool and the draw count:
`V(L,U,N,d) = KLV2(L) + Σ_h L[h]·(bias[pool_bin(N),d,h] + Σ_u weight[d,h,u]·U[u]/N)`. Trained on 50,000
static games (977,465 full-rack rows) and tested in 250,000 paired static games: **+0.4421 points/game,
"roughly +1.1 Elo"**. Runtime: exact KLV3 ran at **0.8296× KLV2 sim throughput** (no-PGO, 10 threads). In
sims, KLV3 throughout rollouts showed "no evidence that paying the throughput cost for contextual KLV3
throughout rollouts helps" (13,074 positions, utility delta −0.000420, p ≈ 0.14). As a **candidate selector**
for otherwise-KLV2 sims it was more promising: on the positions where the KLV2 and KLV3 top-15 lists differed,
KLV3's unique candidates won 283–217 (p = 0.0036). The PR calls that "a marginal-candidate result, not an
end-to-end strength estimate" (all from the #630 description).

**Which leaves ship.** MAGPIE-DATA `data-20260925` was rebuilt in place on 2026-11-02 (MAGPIE-DATA#18) with
census-blended leaves. Its `CSW24.klv2` sha256 changed from `b0ef5f66…` (the original, still used by birdtest's
CSW24 jobs) to `1937df3f…`, and the version name stayed the same (issue jvc56/MAGPIE#982, closed 2026-11-13).
Earlier leave issues: #326 (open) proposes "dynamic leaves" valued against the actual unseen pool; #259 "Apply
dampening to leavegen" (closed, title only); #32 "Biased vs Unbiased estimator for inference and simming"
(closed, title only).

**Inference.** Leaves are board-independent and pool-independent (only bag-empty vs not), and the training
target is one-move best equity. Everything positional is pushed into PAT, a linear model with hand-designed
features. That is the gap a learned evaluator would fill. Leave tables of this form look close to saturated.
Six retraining generations of 200M game pairs each gave 50.0% → 50.4%, and #630's pool-aware leaves gave about
+1 Elo.

## Simulation

### Candidates

The CLI simulates the top `-numplays` moves by static equity (default 100; src/impl/config.c:10737), all of them, with
no separate pre-pruning (src/impl/simmer.c:259-283; src/impl/random_variable.c:1007). PlayChooser (the timed player) uses 15
candidates and 2 plies (src/impl/play_chooser.c:43-44); its 4-ply default is an open PR (#716). Nominating candidates
from other sources (PAT, blocking, setups, exchanges) is an open PR that "did not help a 300 ms sim at equal
time" (#745, as quoted in #747).

### One rollout

`sim_rollout` (src/impl/random_variable.c:565-723):

1. Seed the bag from the sample's seed; every arm gets the same seed sequence, so arm k's n-th sample sees
   the same draws for every k: **common random numbers** (src/impl/random_variable.c:573-593, 859-866).
2. Give the opponent a rack: sampled from the inference result by the alias method when inference is on and
   the opponent's rack is unknown, else the known part plus random tiles (src/impl/random_variable.c:595-612,
   1048-1050).
3. Play the candidate, then `-plies` plies (default 5; src/impl/config.c:16959), each the **top static-equity move**
   found by best-only movegen with the best-move carry (`get_top_equity_move_with_carry`, src/impl/gameplay.c:914-926),
   or by the census-steered generator, which finds the same move faster (src/impl/random_variable.c:637-673).
4. **Leaf value.** `leftover` = leave values of the last two plies' moves (+ for the simmer, − for the
   opponent; for a 1-ply sim, the candidate's leave) (src/impl/random_variable.c:614-625, 663-671). Then:
   - equity stat: spread change + leftover (+ the table's expected final swing if `-smargin`; off by default,
     src/impl/config.c:17023) (src/impl/random_variable.c:685-701);
   - win%: game over → 1/0.5/0; otherwise `win_pct_get(spread + leftover, bag, on-turn rack, off-turn rack)`,
     a table lookup, flipped for even plies (src/ent/sim_results.c:805-837; src/ent/win_pct.c:42-54);
   - **sample utility** = `(w_win·win% + w_spread·sigmoid(spread/100)) / (w_win + w_spread)`, default weights
     1.0 and 0.5 (src/ent/sim_args.h:172-209; src/impl/config.c:10745-10747; #537 `5d6bc3cc`, #582 `da023c88`). The spread term
     is the horizon spread without leftover unless `-smargin` (src/impl/random_variable.c:709-713).
5. Undo by restoring only the squares the rollout changed (#883).

**Bag cycling** (default on; src/impl/config.c:17024; #764 `dce39163`): one sample = one rollout per rotation of the
shuffled bag by 7 tiles, so every unseen tile starts on the opponent's rack once (⌈unseen/7⌉ rollouts, 14 on
an opening rack); BAI sees their mean as one sample (src/impl/random_variable.c:725-775; src/impl/simmer.c:69-89).

### Allocation and stopping: best-arm identification

`bai()` (src/impl/bai.h), implementing Jourdan, Degenne and Kaufmann, *Dealing with Unknown Variances in
Best-Arm Identification* (ALT 2023, [arXiv:2210.00974](https://arxiv.org/abs/2210.00974)) and You et al.,
*Information-Directed Selection for Top-Two Algorithms* (COLT 2023,
[arXiv:2205.12086](https://arxiv.org/abs/2205.12086)) (src/impl/bai.h:1-15; README.md:977-987):

- **Initial phase:** every arm gets `-minplayiterations` samples (default 500; src/impl/config.c:10739) round-robin;
  PlayChooser uses 30 (src/impl/play_chooser.c:45-47; #762 `5405ca0a`, which found 1 sample let an unlucky
  candidate never be resampled).
- **Sampling rule:** top-two with information-directed selection (default; src/impl/config.c:17006): the leader
  `a*` and a challenger minimising `Z + log N` share each round in the IDS proportion
  (src/impl/bai.h:795-880; #300 `b99270a8`, #396 `5eb420bd`).
- **Stopping rule:** GK16 threshold (default; src/impl/config.c:17007): stop when every non-similar arm's GLR
  statistic against `a*` exceeds `log((log t + 1)/δ)`, `δ = 1 − scond/100`, `scond` default 99
  (src/impl/bai.h:755-793; src/ent/sim_args.h:135-143; src/impl/config.c:10740). Since #774 `9ce01aa8` the test uses the paired
  (covariance-corrected) variance, because arms share seeds; it stopped 11–14% sooner with the same choice
  (src/impl/bai.h:695-753; #774 body).
- **Other stops:** time limit (`-tlim`, default 60 s; src/impl/config.c:10741), sample limit, user stop.
- **Similar arms** (same tiles in the same place, by a similarity key) are never compared against each other
  (src/ent/sim_results.c:990-1016; src/impl/bai.h:770-772).
- **Selection:** best mean utility; with zero spread weight, ties within a win% cutoff (default 0.005) break
  by mean equity (src/ent/sim_results.c:1018-1039; src/impl/config.c:10748; #585 `16829395`).
- **Determinism:** rounds of 32 draws are scheduled from committed statistics only, with fixed lags, and sums
  are fixed-point, so a multi-threaded sim reproduces a single-threaded one (src/impl/bai.h:41-128; #756).

### Threading

Within one sim, threads each run whole rollouts on their own game copy and pull work from BAI's round
schedule; idle threads speculate on likely next slots (src/impl/bai.h:68-128; src/impl/random_variable.c:515-537). In autoplay,
`-mtmode pgp` (default) runs one game per thread with one-thread sims; `igp` gives one game all threads
(README.md:697-710; src/impl/config.c:17061).

### Rack inference and how it feeds the sim

`infer` (src/impl/inference.c), run before each sim when `-sinfer true`:

- Enumerates every multiset of tiles the opponent could have kept, drawn from the unseen pool
  (src/impl/inference.c:773-804).
- For each, rebuilds the full rack (kept + played tiles), finds that rack's best static equity by move
  generation (or, from 5 unknown tiles up, from a census of the board's play scores; src/def/inference_defs.h:9-14;
  #939 `5c041c90`), and **accepts the leave if the actual play was within `-imargin` (default 5 points) of
  best** (src/impl/inference.c:448-487; src/impl/config.c:10742, 16987). Exchanges are handled by the best exchange of that size
  (#837 `fb8addf8`).
- Each accepted leave is weighted by its number of draws from the pool (src/impl/inference.c:163-174, 518-527) and
  added to an alias-method sampler that the rollouts draw opponent racks from (src/impl/random_variable.c:596-605).

So inference is a hard filter with uniform-in-draws weights, not a likelihood that a play was chosen. An open
PR adds a softmax ("static softmax inference") with quality benchmarks (#938). Inference was first wired into
the sim in #379 `818e1126` (2025-09). The BestBot post notes Macondo's inference is "not totally
mathematically sound" and gave no measurable edge in BestBot matches
([Mathematics and algorithms behind BestBot](https://blog.woogles.io/posts/2025-05-04-the-mathematics-and-algorithms-behind-bestbot),
2025-05-04).

**Inference.** The sim is statistically careful (CRN, paired stopping, bag cycling) but its rollouts are greedy
static players and its leaf is a 3-key table plus spread. Search quality is now limited by the evaluation, not
by the sampling. That is where a learned evaluator pays (see below).

## Endgame

`endgame` (src/impl/endgame.c, 6.5k lines; #282 `41589515` by Macondo's author, #288 `cba2ad90`):

- **Search:** negamax alpha-beta with iterative deepening, aspiration windows (±25), PVS at the root, a
  Zobrist-keyed 4-way bucketed transposition table (default 25% of RAM), lazy move ordering with hash move,
  going out and early pass first (src/impl/endgame.c:58-100; README.md:583-587; #625, #741/#743).
- **Parallelism:** ABDADA (Weill 1996) on all threads, with a lockless TT and per-thread jitter
  (src/impl/endgame.c:66-69; #459 `8f8c207b`, #460, #470 `1b3766ff`). PEG lends idle cores to endgame solves
  as ABDADA workers (#836 `f3c0fa85`).
- **Depth and leaves:** default `-eplies 6` (src/impl/config.c:16962). A depth-0 node is valued by a **greedy playout**
  to game end with a "conservation" bonus for keeping tiles when the opponent is stuck, plus stuck-tile
  detection and caches; through ID depth 1 the playout is capped at one move (src/impl/endgame.c:95-98, 3182-3203,
  3747-3760). With `use_heuristics` off the leaf is the current spread. So a 6-ply solve is exact only if the
  game ends within the horizon.
- **Move generation:** word-pruned KWGs (#476 `0e1790f0`, #689), incremental per-path move lists (#693),
  forced passes free of depth (#872).
- **Time:** soft and hard limits; after each depth, stop if past the soft limit or if the next depth, estimated
  from the branching factor, would overrun the hard one (src/impl/endgame.h:182-190; PlayChooser passes
  0.9×budget as soft, src/impl/play_chooser.c:586-587; PlayChooser asks for unlimited depth by default,
  src/impl/play_chooser.c:544-549).
- **Speed:** a code comment gives "~100K nodes/s/thread" (src/impl/endgame.c:71); the README example solves depth 6 in
  0.209 s (README.md:575-581). Not measured by us.

## Pre-endgame

`peg` (src/impl/peg.c, 5.5k lines; #549 `7c3d8259`, branch name `peg-solver-port`):

- **Triggers:** 1–4 tiles in the bag (5–7 allowed if every candidate leaves ≤4) (src/def/peg_defs.h:13-14;
  src/impl/peg.h:18-24). PlayChooser's PEG mode and `analyze` (≤ `-apegmaxbag`, default 1) call it; autoplay uses it
  with `-pegbag1/2` (README.md:620-626, 712-737).
- **Scenarios:** for each candidate, every ordering of the unseen tiles (bag + unknown opponent tiles),
  weighted exactly (src/impl/peg.h:26-51).
- **Leaves:** a scenario where the candidate empties the bag is solved with the endgame solver to `-pegplies`
  (default 3; src/impl/config.c:131; `end` = to game end, exact); one where the opponent still draws is scored by a
  greedy playout, or by one nested pre-endgame then playout (nested caps 8, 4, 2; depth 1)
  (src/impl/peg.h:47-51; src/def/peg_defs.h:31; src/impl/config.c:5053; #569 `6efb32b4`).
- **Opponent model:** pessimistic by default (the opponent replies as if it could see the mover's rack and
  the bag order), so by default PEG finds guaranteed wins; `-pegpess false` gives a rational opponent
  (README.md:518-523; src/impl/config.c:16977). The header comment calls RATIONAL the default (src/impl/peg.h:67-68), which
  disagrees with config.c.
- **Cascade:** without a time limit every candidate is solved, cutting a candidate once its losses show it
  cannot reach the best. With `-pegtlim` or `-pegtopk`: greedy stage 0 over all candidates, then halving
  stages 32→16→8→4→2, each one ply deeper (README.md:512-562; src/impl/peg.h:26-46; #897 `a2b24248` made complete,
  untimed solves the default).
- **Threads:** a work-stealing pool with help-while-waiting (#548), shared endgame TT (#831 `09ed3b60`).
- **Versus Macondo** (MAGPIE's own doc, 41 positions, 10 threads, 15 min cap): same play or same win% on all
  26 positions both finished; MAGPIE faster on all 27 where Macondo finished; win% differences traced to
  Macondo's greedy playout ignoring the going-out bonus (docs/peg-vs-macondo.md:14-55).
- Macondo's page: "Macondo can fully solve a 1-in-the-bag pre-endgame", 3 plies by default
  ([How does Macondo work?](https://domino14.github.io/macondo/howitworks.html)).

Between the PEG range and the midgame, the static `-pegadjust` table and a sim are all there is.

## Exchange / pass

Exchanges come from the same sub-rack walk that fills the LeaveMap: each kept subset is an exchange whose
equity is its leave value (plus the PAT non-placement baseline), with no score. They are allowed when bag +
opponent rack ≥ 14 tiles (src/impl/move_gen.c:353-372, 431-480, 3695-3701). For a best-only generation with an RIT the
single best exchange is read from the table (src/impl/move_gen.c:3752-3755). Exchanges then compete in the sim like any
candidate. Passes are generated as a move (sentinel equity) and handled in the endgame/PEG; the endgame orders
an "early pass" first among moves (src/impl/endgame.c:77-82). Inference handles an opponent's exchange by its margin
from the best exchange of that size (#837).

## Time management and threading

**Time.** The CLI uses fixed limits per solver: sim `-tlim` 60 s, endgame and PEG unlimited unless
`-etlim`/`-pegtlim` (src/impl/config.c:10741, 17001-17002; README.md:543-562, 583-587). PlayChooser (timed autoplay)
splits the remaining clock evenly over an estimate of remaining own plays, ⌈unplayed tiles / 8⌉, minus small
reserves; untimed default 5 s; in overtime it spends only the current started penalty period
(src/impl/play_chooser.c:43-61, 346-423). No position-dependent allocation (for example, spending more on close
decisions) beyond what BAI's stopping rule gives. A clock-banking TimeManager is an open PR (#637).

**Threading.** Sims: rollout-level parallelism under BAI (above). Endgame: ABDADA. PEG: work-stealing pool
lending cores to endgame solves. Inference: workers claim leaves by atomic counter (#830 `9e5ba114`, 2.1× in
18-thread sim autoplay). Autoplay: per-game (`pgp`) or intra-game (`igp`) (src/def/autoplay_defs.h:11-12).
Threads default to the core count (src/impl/config.c:17003).

## Build

C99-style C with a large `compat/` layer; Linux, macOS, Windows (cross-compiled), and WebAssembly
(docs/building.md:129-157). Release: Clang with LTO, `-march=native` and PGO trained on short static games,
with focused PGO profiles for leavegen, sim, PEG and endgame (docs/building.md:10-50). `BOARD_DIM` (15 or 21)
and `RACK_SIZE` are compile-time (docs/building.md:67-73). CI runs formatting, cppcheck, clang-tidy, a
portability check, the Windows cross-compile and unit tests (README.md:946-952). The data download is separate
and versioned (README.md:787-795). Build and measurement on our machine: to be measured in
`docs/harness/builds.md`.

## Interfaces

- **CLI** with settings that persist between commands, async `status`/`stop`, script mode and sync mode
  (README.md:265-322, 888-915).
- **Formats:** GCG load/export (cross-tables, Woogles, files), CGP positions, `.kwg`/`.klv2` from wolges, plus
  MAGPIE's own `.wmp`, `.rit`, `.wit`, `winpct_*.csv` (README.md:350-365, 838-881). Output is
  machine-readable by default; sim output follows Macondo's UCGI style (#35 "Infer ucgi"; #505
  `feat: extend UCGI sim output`).
- **C library** `libmagpie` with sync/async runs, status and stop (README.md:917-944).
- **Autoplay:** static or simming players, per-player settings (`-s1/-s2`, `-l1/-l2`, leaves, plies),
  game pairs with identical draws, timed PlayChooser games with overtime penalties, endgame/PEG solving per
  player (README.md:645-737).
- **TUI** (`tui/`) and a browser build at magpie.birdtest.org (README.md:222-225).
- **birdtest:** `contribute` claims tasks from a server, runs them and submits results, a fishtest-like
  distributed compute client (README.md:781-785; src/impl/contribute.h:4-12).

## Tuning and testing

- **Strength tests** are autoplay matches with game pairs, reported as win% ± error and spread per pair. PRs
  routinely quote these: e.g. uspread 0.5 gave "+8–13 points of margin per game pair at no measurable win-rate
  cost" (#582); static prior in sims "cleanly null" at 5 samples per arm (#632, closed).
- **Speed tests** are on-demand harnesses: `simbench` (one fixed game, timed sim per turn, iters/s;
  test/sim_benchmark_test.c:1-14), endgame and PEG benchmarks (test/benchmark_endgame_test.c,
  test/benchmark_peg_test.c), `censusrolloutbench`. Results are not stored in the repo; they live in PR
  descriptions.
- **Determinism** is a design goal: seeded sims reproduce across thread counts (#756); clocked games are not
  reproducible (README.md:684-695).
- No SPRT or sequential test procedure appears in the code or docs read (UNVERIFIED for birdtest's server,
  which is a separate repo).

## Measurements

None by us yet: to be measured in `docs/harness/builds.md`. Figures quoted by the project:

| What | Number | Settings | Hardware | Measured by | Source |
| --- | --- | --- | --- | --- | --- |
| Sim, 2 plies, 1 thread | 25,191 → 26,104 iters/s | `simbench`: one CSW24 game, WMP+RIT, 2 s sim per turn, played move pinned; before #987, so PAT off | not stated | olaugh (PR author) | #894; settings from #883 |
| Sim, 4 plies, 1 thread | 9,717 / 9,428 → 9,868 / 9,728 iters/s | as above | not stated | olaugh | #889 |
| Sim, 17 threads, 50 candidates, CSW24 | 1.05M nodes/s (2 ply), 0.88M (4 ply); with census 1.74M / 1.27M | CLI set up as the TUI, no PAT, no bag cycle; node = one move played in a rollout (src/impl/random_variable.c:633, 662) | not stated | olaugh | #951 |
| Sim, TUI defaults | 66,990–97,416 iters/s | 9 threads, 4 plies, 100 candidates, census, with/without PAT | not stated | olaugh | #993 |
| Sim, 1 thread, 4 plies, 15 candidates | 10,457 iters/s (no PAT), 6,911 (PAT) | geometric mean over 6 positions | Apple M4 | olaugh | #747 (open PR) |
| Census rollout steering | 1.97× (2 ply), 1.25× (6 ply) | 1 thread, 8 candidates | Apple M5 Max | olaugh | #945 |
| KLV3 vs KLV2 sim throughput | 0.8296× | no-PGO build, 10 threads | not stated | olaugh | #630 (open PR) |
| Endgame | ~100K nodes/s/thread | code comment | not stated | MAGPIE authors | src/impl/endgame.c:71 |
| Endgame, README example | depth 6 in 0.209 s | threads not stated | not stated | MAGPIE authors | README.md:575-581 |
| PEG vs Macondo | MAGPIE faster on all 27 positions Macondo finished | 10 threads, 15 min cap | not stated | MAGPIE authors | docs/peg-vs-macondo.md:36-44 |
| MAGPIE vs Macondo overall | "potentially between 5 to 10 times faster" | no method given | not stated | cesar (Woogles) | BestBot blog post, 2025-05-04 |

## History

Only what explains the three deep parts. Full PR list in `reference/history/magpie/prs-index.tsv`.

**Simulation.**
- 2023: Macondo's author adds Monte Carlo sim and its first stopping condition (#18 closed, re-done as #23
  `1404fcfe`).
- 2025-05: best-arm identification replaces the old stopping rule (#300 `b99270a8`); top-two IDS (#396
  `5eb420bd`); inference results feed rollouts (#379 `818e1126`); win% cutoff (#436 `db656bf9`).
- 2026-05 to 07: utility blends win% and sigmoid spread (#537); default spread weight 0.5 (#582); a selection
  bug where pure-win% utility lost all gradient in decided games, fixed by equity tie-break (#585).
- 2026-09: win% tables keyed by full game state and predicting final margin; data version 20260925 (#703).
- 2026-10: PlayChooser gives each candidate 30 rollouts before adapting (#762); bag cycling on by default
  (#764); stopping test uses the covariance from shared seeds, 11–14% earlier stops (#774); best-move carry and
  lane skipping (#824, #832).
- 2026-11: census of the position steers rollout movegen (#945 `923f4137`), auto by default (#949
  `3db8cad9`); board-only PAT in rollouts (#986 `226fc204`); PAT on by default (#987).
- **Tried and dropped or still open:**
  - #486 (closed): nested-sim rollout policy (mini-rollouts per rollout move) and multi-fidelity BAI.
  - #632 (closed): static evaluation as a Bayesian prior on arms. Most of its gain came from giving each arm
    3–5 real samples, and at 5 samples the prior was "cleanly null". Its own recommendation was a
    PlayChooser minimum-samples PR, and #762 (30 samples per arm) followed. That #762 grew out of #632 is
    our inference.
  - #946 (closed): exhaustive one-ply "census sim". It matched `sim -plies 1` and came out even against static
    in 100 pairs. The closing comment: "census_sim itself isn't being pursued".
  - #630 (open): contextual "KLV3" leaves in rollouts. +0.44 points/game (about +1.1 Elo) in 250,000 paired
    static games, but 0.83× sim throughput and "no evidence that paying the throughput cost … throughout
    rollouts helps". It was promising as a candidate selector (see "How leaves are trained").
  - #747 (open): "static-ish" rollouts (a stronger rollout policy) run about 1,000–2,500× fewer
    iterations/s; whether that helps any sim decision is untested.
  - #745 (open): candidate nomination from PAT, blocking, setups and exchanges. It "did not help a 300 ms sim
    at equal time".
  - #527/#528 (open, 2026-04): **OutcomeModel**, a linear model (12 features, logistic win head plus OLS
    spread head, trained with numpy from autoplay dumps) replacing the win% table at sim leaves. #528 found
    the first version evaluated at a different state from training and requires even plies.
  - Branch `vn-nnue-m5` (not in main; mentioned only in #920's description): a "cached value net" with
    attention layers (MPSGraph on an Apple M5 Max GPU), used "on both rollout plies". In `simbench` (2 plies,
    15 root plays, 16 threads) the GPU was 91–96% busy and limited throughput. No strength result is given.

**Leaves.** Leave map (#12 `9abda55b`, 2023); self-play leavegen (#240, 2024-08) with forced rare racks
(#244); rack-based leavegen (#299, 2025-04) weighted by draw probability (#310, 2025-05); census, census play
scores and leave blending (#921–#924, 2026-10-31); contextual "KLV3" leave values (#630, open since
2026-07-27: about +1.1 Elo static, 0.83× sim throughput); a compact-leaves small-lexicon toolkit (#572, open).
The shipped CSW24 leaves were swapped for census-blended ones inside the same data version on 2026-11-02
(issue #982). Issues: #326 dynamic pool-aware leaves (open), #259 leavegen dampening (closed).

**Inference.** v1 (#16 `498615b3`, 2023); cutoff optimisation (#430, #838); exchange inference by margin
(#837); census play scores (#939); softmax inference (#938, open); PEG opponent-leave inference (#586, open).
Issue #32 "Biased vs Unbiased estimator for inference and simming" (2023, closed, title only).

**Endgame.** Negamax with alpha-beta, ID and negascout by Macondo's author (#282, 2025-01) and TT (#288).
2026-01/02, several parallel designs were tried and closed: YBWC (#444), Lazy SMP with staggered depths
(#447), LMR plus aspiration (#448; LMR "may find slightly suboptimal lines"), ABDADA + Lazy SMP (#455). Plain
ABDADA was merged (#459), then ABDADA + lockless TT + stuck-tile heuristics + multi-PV (#470). LMR never landed
(the endgame stays exact within its depth). Later: word pruning (#476, #689), incremental movegen (#693, #696),
analytic scoring of outplays tried and closed (#626), a stuck-tile Monte Carlo endgame sampler open (#639).

**Pre-endgame.** Four 1- and 2-in-bag PEG attempts closed (#503, #507, #508, #533); a BAI/PUCT adaptive PEG
with progressive widening closed (#532, with its work-stealing follow-up #534); the unified cascade solver
merged (#549, 2026-06); nested lookahead (#569); complete untimed solves by default (#897); pre-endgame
adjustment table fitted and loaded (#930, #931) and on by default (#989).

## Provenance and relation to Macondo

- **Facts.** The name is "Macondo Accordant Game Program and Inference Engine"; the README says it "started as
  a C rewrite of Macondo" and credits wolges for shadow playing, KWG/KLV and the leave census
  (README.md:1-3, 19-21, 957-963). The first commit is 2023-02-03 by jvc56 (`1767eab6`). Macondo's author
  (domino14) wrote the original Monte Carlo sim (#18, #23), the endgame (#282) and its TT (#288). The BestBot
  post (2025-05) said MAGPIE then lacked a multi-threaded endgame and a pre-endgame and that the team hoped to
  move BestBot's backend to MAGPIE; both solvers have since been written (#459/#470, #549).
- **Shared formats:** `.kwg` and `.klv2` (wolges formats, used by MAGPIE and by Macondo:
  macondo `dataloaders/leaves.go:20`), GCG, CGP, UCGI-style output, and Macondo-style win% tables (since
  replaced in MAGPIE by state-keyed tables, #703).
- **Algorithmic divergence** from Macondo's documented design: BAI top-two/GLR versus Macondo's periodic
  Welch t-test pruning (BestBot post); PEG to 4 in the bag versus Macondo's documented 1 (fully) and 2
  (harder) (Macondo how-it-works page); Macondo's documented default sim depth is 2 plies, MAGPIE's CLI default
  is 5.

**Inference.** MAGPIE and Macondo are now siblings in one ecosystem (same people, data, formats), with MAGPIE
the faster and more actively developed one. A fork of MAGPIE inherits Woogles' formats and data and stays
compatible with Macondo tooling.

## Neural evaluation: how hard, and where

**Where evaluation happens today** (all calls are narrow):

| # | Site | Function | Calls per… |
| --- | --- | --- | --- |
| E1 | Leave value | `klv_get_leave_value` / LeaveMap fill (src/impl/move_gen.c:3681-3751; src/ent/klv.h:347-357) | 128 sub-racks per move generation (or one RIT copy) |
| E2 | Static move equity | `static_eval_get_move_equity_with_leave_value` (src/ent/static_eval.h:160-185), plus PAT (`pat_eval_move_penalty`) | every generated move; bounded by `static_eval_get_shadow_equity` for pruning (src/ent/static_eval.h:116-154) |
| E3 | Rollout policy | `get_top_equity_move_with_carry` (src/impl/gameplay.c:914-926), i.e. E1+E2 with `MOVE_RECORD_BEST` | every rollout ply |
| E4 | Sim leaf | `simmed_play_add_win_pct_stat` → `win_pct_get` (src/ent/sim_results.c:805-837; src/ent/win_pct.c:42-54), plus `leftover` leaves (src/impl/random_variable.c:663-671) | once per rollout |
| E5 | Inference | best static equity per hypothesised rack (src/impl/inference.c:448-487) | once per possible leave |
| E6 | Endgame/PEG leaf | greedy playout (src/impl/endgame.c:3747-3760); PEG non-emptier playouts | once per depth-0 node |

**Difficulty, easiest first.**

1. **E4, sim leaf value net:** replace one function. Inputs available at that point: board, both racks
   (the opponent's is sampled), scores, bag. #527/#528 already wired a model (`players_data` type `OCM`) at
   exactly this call. Cost is one eval per rollout. Main pitfall from #528: train on the same state the
   leaf sees.
2. **E1, rack-only leave net:** no code change at all if distilled into a `.klv2`. A net conditioned on the
   unseen pool or the bag size could fill the 128-entry LeaveMap per generation (128 evals, batchable, and
   racks recur across rollouts; src/ent/best_move_carry.h:17-23). #630 built exactly this with a linear
   pool-conditioned model ("KLV3"), including shadow bounds and WMP leaves. Result: about +1.1 Elo in static
   play, 0.83× sim throughput, and no measurable sim gain from using it in rollouts.
3. **E3, policy/value net in rollouts:** possible as a re-rank of the top-k static moves, but the generator's
   pruning relies on cheap upper bounds (src/ent/static_eval.h:116-125), so per-move board-aware terms break
   best-only generation unless they come with a bound. The `vn-nnue-m5` branch did this on a GPU and was
   GPU-bound (#920).
4. **E2 inside all movegen:** hardest, for the same bound reason and because it runs on every generated move.

**Budget per evaluation inside simulation** (from the project's numbers above, not measured by us; hardware
not stated):

- 2-ply sim, 1 thread: about 26,000 rollouts/s, so **~38 µs per rollout** (#894).
- 4-ply: about 9,800 rollouts/s, so **~100 µs per rollout**, about 30 µs per extra ply (#889).
- 17 threads: about 1.05M rollout moves/s, so about **16 µs of thread time per rollout move** (#951).

Two caveats on these figures:

- The µs figures are **upper bounds** on rollout cost: whole-game wall time (inference, candidate generation,
  scheduling included) divided by rollouts.
- They **predate PAT on by default** (#987, 2026-11-13) and were taken with PAT off. With PAT in rollouts,
  throughput is 0.66–0.89× of that (#747: 0.66× at 1 thread, 4 plies; #993: 0.69–0.89× at 9 threads, 4 plies),
  so today's default per-rollout time is about 1.1–1.5× longer.

### Inference

From those numbers:

- A leaf net (E4) costing 4 µs per eval on one CPU core would slow a 2-ply sim by about 10%, and 40 µs would
  halve it. This is the realistic CPU budget for a small NNUE-style net. Batching across a thread's rollouts is
  not possible in the current loop (one synchronous rollout per sample) without restructuring.
- A per-ply net (E3) gets about 1–2 µs per ply for a 10% cost, so it needs NNUE-style incremental updates or
  re-ranking only a handful of moves.
- The difficulty ranking above (E4 < E1 < E3 < E2) is our judgement from the code structure.
- Verdict (the effort estimates are ours): adding a leaf value net is easy (days; the plumbing exists in #527).
  Adding a learned leave table is trivial, and #630 suggests it buys about 1 Elo. Adding a learned rollout
  policy or a board-aware equity inside move generation is a research project, because MAGPIE's speed rests
  on bound-based pruning that assumes leave-only evaluation.

## Inference

- MAGPIE has moved from "Macondo in C" to the reference open engine for search technique. Its developers
  measure carefully (paired runs, CIs, regret against high-budget references) and publish the numbers in PRs,
  not in the repo.
- The remaining hand-built parts (leave table, PAT, pre-endgame table, win% table) are each a small learned
  model in disguise. The project is replacing them one by one with fitted tables rather than one shared
  evaluator. A single learned value function could replace E4 and inform E1/E2.

## Relevance to the three decisions

**1. What to fork.** For MAGPIE as a base:

- the fastest open movegen and sim we know of, by its own and Woogles' account;
- complete endgame and pre-endgame solvers;
- strong testing tools: seeded autoplay with game pairs and timed play;
- isolated evaluation call sites;
- the census leave generator.

Against:

- GPL-3.0, while the owner prefers MIT;
- a very large, fast-moving C codebase (`src/impl/config.c` alone is 18,489 lines; about 400 PRs in five and a
  half months), so tracking upstream will be costly;
- much of it is engineering for speed that a learned evaluator may partly obsolete.

The fork hypothesis stands on strength and features. It must be weighed against wolges (MIT) in step 5.

**2. Where a neural evaluation pays off.** First at the sim leaf (E4): today that is a table lookup on spread and
three tile counts, so it ignores the board, the racks and positional factors, and the sim's statistics are
already strong enough that leaf bias, not noise, is the likely limit. Second, as a rollout policy (E3). The
project itself is exploring both (#527, `vn-nnue-m5`) without published strength results. Leaves alone look
saturated: six generations gave 50.0% → 50.4%, and #630's pool-aware leaves about +1.1 Elo at 0.83× sim
throughput. PEG and endgame are exact or nearly exact searches where a net helps only the greedy leaf
playouts.

- Difficulty, easiest first (our judgement): sim leaf E4 (one call, plumbing in #527), then leave table E1,
  then rollout policy E3, then equity inside movegen E2 (breaks shadow-bound pruning).
- Budget (upper bounds, PAT off): about 38 µs per 2-ply rollout on one thread, so about 4 µs per leaf eval for
  a 10% slowdown and 1–2 µs per rollout ply. With PAT on by default these are about 1.1–1.5× longer.

**3. How we prove we are stronger.** MAGPIE's autoplay with game pairs (identical draws, alternating first
player) and its timed PlayChooser mode give a ready baseline and method. Two cautions: game pairs lose their
variance reduction under clocks (README.md:684-695), and `pgp`/`igp` threading changes how much search a
clock buys (README.md:697-710). The baseline must be pinned to a SHA **and to the sha256 of each data file,
not just a data version**. Defaults changed days before our pin (#987, #989, #949), and MAGPIE-DATA
`data-20260925` was rebuilt in place on 2026-11-02 with different CSW24 leaves (issue #982). The birdtest
contribute protocol is a candidate for distributed testing.

## Open questions

- Which method and recipe produced the current `winpct_english.csv`, PAT weights and pre-endgame table in
  MAGPIE-DATA `data-20260925`? The CSW24 `.klv2` is census-blended since 2026-11-02 (issue #982); the recipe and
  the self-play table it was blended with are not stated. (Check the MAGPIE-DATA repo.)
- What strength does each default add? No single table of autoplay results per feature (inference, bag cycle,
  PAT, uspread, census) was found. Collect them from PR descriptions, or measure.
- Did the `vn-nnue-m5` value net or the #527 OutcomeModel gain strength? The answer is not in the repo or in
  PR descriptions.
- Is PEG's default opponent model pessimistic (src/impl/config.c:16977, README) or rational
  (src/impl/peg.h:67-68)? Confirm by running it.
- What is MAGPIE's actual speed on our machine (6 cores, Linux): movegen/s, rollouts/s at 2 and 5 plies with
  default PAT, and endgame nodes/s? To be measured in `docs/harness/builds.md`.
- Did #630's suggested end-to-end experiment (KLV3 top-15 candidates, KLV2 rollouts) ever run, and with what
  result?
- How strong is MAGPIE against Macondo/BestBot and Quackle at equal time? No head-to-head was found in the
  repo.
- What does Sheppard 2002 (Maven; *Artificial Intelligence* 134, doi:10.1016/S0004-3702(01)00166-7) say about
  simulation and pre-endgame design, to compare with MAGPIE's? Its content was not read for this dossier
  (paywalled; UNVERIFIED).
- For the Macondo dossier: code now flows from MAGPIE back to Macondo. Macondo's `leavemap` "mirrors MAGPIE's
  LeaveMap" (domino14/macondo `9c33baa` `leavemap/leavemap.go:6`), its cross-set cache is credited to MAGPIE
  (`cross_set/cache.go:28`), it has a `wmp/` package, and its config has a `magpie-data-path`
  (`config/config.go:37`). How much of Macondo's current movegen and sim is ported from MAGPIE?
