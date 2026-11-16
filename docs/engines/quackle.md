# Quackle

- Source: https://github.com/quackle/quackle, commit `35e11bb21a3bf362c533541d0b5fe8ad92a0c08f` (from `pins.tsv`, 2026-10-12)
- Licence: GPL-3.0 (`LICENSE`; file headers, e.g. `encodeleaves/encodeleaves.cpp:1-17`)
- Language / build: C++ core (`libquackle`), Qt for `quackleio` and the GUI (`quacker/`), CMake. One line: building the
  headless harness needs Qt Core (docs/harness/reuse-check.md §3).
- How to drive it headless: `test/testharness.cpp` (`--mode=positions|selfplay|…`, `--computer=`, `--threads=`),
  or a small adapter over `libquackle` + `libquackleio`; see docs/harness/reuse-check.md §3. GUI: Qt app, not covered.

**Citation convention.** Every `path:line` without a repo prefix is quackle/quackle at `35e11bb` (full SHA above),
read from the clone in `reference/quackle` (working tree at the pin). Issues are `quackle/quackle#n` from
`reference/history/quackle/issues.json`. MAGPIE values are quoted from `docs/engines/magpie.md` (jvc56/MAGPIE at
`b781018`); they are not re-checked here. This dossier is written as a diff from that one.

## Summary

- **What it is:** the 2006-era Championship Player, unchanged in algorithm. Static equity = score + superleave
  + small heuristics; a 2-ply sim of 14 candidates with a fixed iteration count; a 1–2-in-bag pre-endgame that
  enumerates opponent racks; and a heuristic endgame (greedy playouts plus a one-reply minimum), not a search.
- **Does well:** simple, readable, small (core ≈11k lines of C++). Its superleaves cover the full 1–6-tile lattice
  and agree closely with MAGPIE's CSW24 leaves (Pearson 0.977, measured below). The pre-endgame is exhaustive over
  opponent racks.
- **Does badly:** no rack inference, no common random numbers, a crude screening rule for sim stopping, a
  win-table leaf keyed only by spread and unseen count, and an endgame that is not exact. Its budget is iteration
  counts, so on current hardware it uses a small fraction of its 66 s.
- **Active work** (2026, John Fultz) is threading, CI and packaging, not playing strength.
- **What we would take:** nothing in code. It is a fixed, well-known opponent for strength tests, and a source of
  ideas whose value MAGPIE has already measured (pre-endgame bag adjustment, opening placement table).

## Pipeline (Championship Player)

1. `TorontoPlayer` ("Championship Player") is a `Resolvent` with `secondsPerTurn = 66` (resolvent.cpp:91-96;
   resolvent.h:55-61). It is registered with Speedy, Static, Five Minute and Twenty Second players
   (computerplayercollection.cpp:42-52).
2. `Resolvent::moves` picks a delegate by bag size: empty → `EndgamePlayer`; 1–2 tiles → `Preendgame`; otherwise
   `SmartBogowin`. It passes on its parameters (so 66 s) and thread count (resolvent.cpp:42-74;
   preendgame.cpp:43-47).
3. `SmartBogowin` generates the top 14 static moves, prunes to those within 33 points of the best, sims each in
   turn, and returns the highest mean win (bogowinplayer.cpp:137-231).

## Defaults (Championship Player vs MAGPIE)

MAGPIE column from magpie.md (CLI default / PlayChooser where they differ).

| Setting | Quackle CP | Where | MAGPIE |
| --- | --- | --- | --- |
| Time per turn | 66 s cap, checked between candidates | resolvent.cpp:95; bogowinplayer.cpp:213-217 | sim `-tlim` 60 s; PlayChooser splits the clock |
| Candidates | top 14 static, within 33 equity of best | bogowinplayer.cpp:46, 137-148; sim.cpp:209-224 | 100 / 15 |
| Plies after candidate | 2; to game end if bag ≤ 14 | bogowinplayer.cpp:138-141; sim.cpp:418-422 | 5 / 2 |
| Samples per candidate | 132 (2×66); 330 (5×66) if within 1.96·35/√132 bogopoints of best | bogowinplayer.cpp:38-39, 194-196; bogowinplayer.h:67-81 | ≥500 / ≥30, then BAI |
| Stopping rule | after the last candidate or past 66 s | bogowinplayer.cpp:177-218 | GK16 GLR, δ = 0.01 |
| Opponent rack | uniform from unseen; no inference | sim.cpp:788-819; bogowinplayer.cpp:114-132 | inferred, 5-point margin |
| Common random numbers | no | sim.cpp:604-607 | yes, plus bag cycling |
| Sim leaf | `bogowin(spread + leaves, bag + 7)` | sim.cpp:716-735 | win% table + 0.5·sigmoid(spread) |
| Pre-endgame trigger | 1–2 in bag | preendgame.cpp:43-47; resolvent.cpp:54-58 | 1–4 (to 7 if candidates leave ≤4) |
| Pre-endgame candidates / time | 30 (from a 66-iteration nested sim) / 396 s | preendgame.cpp:32-33, 57-62, 96 | all, cascade; unlimited |
| Endgame trigger | bag empty | resolvent.cpp:49-53 | bag empty |
| Endgame search | 320 own × 160 replies, greedy playout leaf | endgame.cpp:41-45, 172-400 | alpha-beta ID, 6 plies, TT, ABDADA |
| Threads | sim: CPU-topology pool; endgame: 1 | sim.cpp:324-344, 484-503 | core count |

## Move generation

GADDAG (Gordon) generation, or anagramming on an empty board. Every generated move is evaluated with the full
static equity, and the best is kept in a running comparison (generator.cpp:1896-1925, 1378-1381). There is no
shadow bound and no leave map; each leave is a `std::map` lookup (strategyparameters.h:145-150). Exchanges are
enumerated by subset when the bag has ≥7 tiles (generator.cpp:1861-1893; game.cpp:432-435;
gameparameters.cpp:32).

## Static evaluation and leaves

`DataManager` installs `CatchallEvaluator` (datamanager.cpp:59). Its `equity` (catchall.cpp:27-74) is:

- **empty board:** score + leave + `vcPlace(start, length, vowel bitmask)` for a placement, or +3.5 for an
  exchange (catchall.cpp:30-58);
- **bag not empty:** score + leave + a timing term indexed by `bag − tiles used + 7`,
  `{0, −8, 0, −0.5, −2, −3.5, −2, 2, 10, 7, 4, −1, −2}` for indexes 0–12, else 0 (catchall.cpp:61-69);
- **bag empty:** score + 2×opponent's rack if going out, else score − 8 − 2.61×own rack (catchall.cpp:70-95).

**Leave value** (`ScorePlusLeaveEvaluator::leaveValue`, evaluator.cpp:73-168): the superleave if the table has a
non-zero entry. Otherwise a formula: tile worths + duplicate penalties (`syn2`) + pair synergy (boosted 1.5× above
3 if no tile worth < −5.5) + a vowel/consonant table, floored at −40. A superleave of exactly 0 falls through to the
formula (evaluator.cpp:77-78).

**Strategy files** (`StrategyParameters::initialize`, strategyparameters.cpp:35-42): `syn2`, `worths`, `vcplace`,
`bogowin`, `superleaves`. Lookup order: lexicon directory, then `csw` for lexica starting with "csw", then the backup
lexicon, then `default` (datamanager.cpp:145-160). The backup is `default_english` for 26-letter A–Z alphabets
(quacker/settings.cpp:391; test/testharness.cpp:273). So a CSW24 game loads:

| File | From | Content |
| --- | --- | --- |
| `superleaves` | `data/strategy/csw/` | binary: length, tiles, 2-byte value in 1/256 points, offset −128 (strategyparameters.cpp:205-241) |
| `syn2`, `vcplace`, `worths` | `data/strategy/default_english/` | text tables; used only for leaves not in the superleave table and for opening placement |
| `bogowin` | `data/strategy/default/` | win probability by lead (−300…300) and unseen tiles; 55,893 lines, unseen 1–93 (counted by us) (strategyparameters.cpp:87-115; strategyparameters.h:60-62, 122-143) |

**How they were made.** The code does not say. Two tools ship that look like leave makers: `leavecalc.c`
("old, unused reference code") builds random boards from static self-play and then plays 3 static plies from a
given leave (leavecalc.c:1, 20-157); `ruby-leavestuff.tgz` holds scripts that merge files called `openers`,
`static` and `eight-work` (`realshit.rb`, `useboth.rb`). History: "Remove obsolete or useless strategy files" and
"Fix Collins superleaves" (2014, `2cf9747`, `1462523`); TWL06 superleaves copied to `default_english` (2015,
`150e9f7`, fixing quackle/quackle#10); "There's only two distinct superleaves files" (2019, `e29118f`). Which Collins
edition the CSW superleaves were made for, and by what method: UNVERIFIED. quackle/quackle#136 (open, 2025) asks to
adopt Macondo's leaves; quackle/quackle#67 (open, 2017) asks for a better static evaluator.

**Comparison with MAGPIE's CSW24 leaves** (measured; table in Measurements):

- Both tables have exactly 914,624 entries with the same keys, i.e. the full lattice of 1–6-tile leaves with
  blanks.
- Pearson correlation 0.977.
- Quackle is lower by 2.7 points on average (mean −5.35 vs −2.68). The gap grows with leave length: −1.1 for 1 tile,
  −1.8 for 2, −2.3 for 3, −2.6 to −2.7 for 4–6. The RMS difference grows from 1.9 to 4.6 points.
- Single tiles: blank 27.95 vs 27.97; S 8.56 vs 9.37; Z 3.89 vs 9.54; Q −8.85 vs −6.57.

**Inference.** The two tables rank leaves almost the same way, so at equal search the leave table is unlikely to be
where most of a strength gap lies. Z is the largest single disagreement. Z is worth more in Collins than in older
lists, which fits Quackle's table being made for an older lexicon (UNVERIFIED). Because the gap grows with leave
length, Quackle penalises keeping tiles more than MAGPIE does, so its static player favours playing more tiles.
MAGPIE's `-pegadjust` table is "laid out as Quackle's was" (magpie.md), i.e. it descends from the timing term
above.

## Simulation (`SmartBogowin` + `Simulator`)

- **Candidates:** `kibitz(13 + nmoves)` static moves, so 14 for one move, then `pruneTo(33, 14)`: keep those within
  33 equity of the best (bogowinplayer.cpp:46, 137-148; sim.cpp:209-224). Moves the user flagged are always kept
  (bogowinplayer.cpp:149-153).
- **Plies:** 2 after the candidate (candidate, reply, own move). With ≤14 tiles in the bag, `plies = −1`, which
  means 1000, i.e. to game end (bogowinplayer.cpp:138-141; sim.cpp:418-422).
- **Order and budget:** candidates are simmed one at a time, best static first. Each gets `minIterations` =
  2×`secondsPerTurn`. The candidate gets `maxIterations − minIterations` more if
  `bogopoints(move) + 1.96·35/√minIterations > bogopoints(best)`, and becomes the best if its win then beats it
  (bogowinplayer.cpp:158-211; bogowinplayer.h:67-81). For the Championship Player that is 132 iterations, or 330
  for close ones. The first candidate is never extended past 132.
- **Stopping:** the clock is checked only after each candidate. Past 66 s the remaining candidates are skipped
  (bogowinplayer.cpp:213-217). There is no other stopping rule; a fast machine finishes all candidates early.
- **Bogopoints** maps a win probability back to a spread equivalent through the `bogowin` table at the current
  unseen count, minus the current spread. The constant 35 is an assumed standard deviation in points
  (bogowinplayer.cpp:53-81, 194).
- **One iteration** (`simulateOnePosition`, sim.cpp:600-736):
  1. Fresh random opponent rack from the unseen tiles and a fresh draw order for every playahead
     (sim.cpp:604-607, 788-834). No common random numbers between candidates.
  2. Moves after the candidate are each side's static best (`staticBestMove`, i.e. `kibitz(1)`; sim.cpp:639-644;
     game.cpp:284-288).
  3. The leave of each side's last move is added (+ own, − opponent) as `residual` (sim.cpp:665-699). That is the
     evaluator's `playerConsideration`, the leave value only (evaluator.cpp:61-64). `sharedConsideration` is 0
     (evaluator.cpp:66-71).
  4. **Leaf:** game over → 1 / 0.5 / 0. Otherwise `bogowin(spread + residual, bag + 7)`, flipped if the opponent is
     on turn (sim.cpp:716-735).
- **Selection:** sort by mean win (sim.cpp:836-864; bogowinplayer.cpp:222-231). The reported equity is mean spread
  over the plies + mean residual (sim.cpp:963-986).
- **Opponent rack modelling:** uniform from the unseen pool. `m_partialOppoRack` is set only by the GUI
  (quacker/quacker.cpp:1334). The `inferring` flag only prints the previous position (bogowinplayer.cpp:114-132),
  and `InferringPlayer` is commented out of the player list (computerplayercollection.cpp:50). Code comment: "TODO
  -- some kind of inference engine can be inserted here" (sim.cpp:803).
- **Threads:** iterations of the candidate being simmed are spread over a pool, about 3 playaheads queued per thread
  (sim.cpp:484-503). The pool size defaults to the CPU topology's performance pool (sim.cpp:324-344; `42c5d25`,
  2026-08-08). quackle/quackle#93 (open, 2019) asked for exactly this per-iteration threading.

**Differences from MAGPIE, with Inference on strength:**

| Aspect | Quackle CP | MAGPIE | Inference: which way, and how much |
| --- | --- | --- | --- |
| Allocation | sequential screen with fixed min/max counts | BAI top-two, GLR stop | MAGPIE spends samples where the decision is close. Quackle's leader keeps only 132 samples, so a lucky early leader can survive. Edge to MAGPIE. |
| Noise | independent draws per playahead | CRN + bag cycling + paired variance | At equal samples MAGPIE's comparisons are far less noisy. Edge to MAGPIE. |
| Opponent rack | uniform | inferred (5-point margin) | BestBot saw no measurable gain from Macondo's inference (magpie.md). Probably small. |
| Depth | 2 plies, to end at ≤14 in bag | 5 (CLI) / 2 (PlayChooser) | At 2 plies they are equal. The to-end rollouts at 3–14 in bag are greedy, so they may add bias as well as depth. Unclear. |
| Leaf | `bogowin(spread+leave, unseen)` | win% by spread, bag and both racks, blended with sigmoid(spread) | Similar in kind. MAGPIE's spread term separates moves in decided games. Small edge to MAGPIE. |
| Total samples | ≤14×330 = 4,620 rollouts | about 26,000 2-ply rollouts/s on one thread (magpie.md, #894) | The CP's full search is about 0.2 s of one MAGPIE thread. At equal wall time MAGPIE searches orders of magnitude more. This is likely the largest edge. |

## Pre-endgame (`Preendgame`)

- **Trigger:** 1–2 tiles in the bag (preendgame.cpp:43-47, 107-114; "TODO fix up 2-in-bag").
- **Candidates:** a nested `SmartBogowin` asked for 30 moves: it kibitzes 43, prunes to 33 points, and sims each
  for 66 iterations (nested min = max = 1×`secondsPerTurn`) to game end (preendgame.cpp:32-39, 49-55, 69-100;
  bogowinplayer.cpp:41-42, 140-141). Deeper nestings take ⌈30/2ⁿ⌉ static moves (preendgame.cpp:49-55, 71-79).
- **Scenarios:** every 7-tile opponent rack from the unseen pool, weighted by its probability of being drawn
  (preendgame.cpp:120-128; enumerator.cpp:50-108). The bag is whatever remains, so the scenario has full
  information.
- **Reply and value:** for each candidate and rack, the opponent's reply comes from a fresh `Resolvent` (endgame
  if the bag is now empty, nested pre-endgame otherwise). Candidate win = 1 − Σ p(rack)·win(reply)
  (preendgame.cpp:147-195). The opponent therefore plays the endgame knowing both racks.
- **Time:** 6×`secondsPerTurn` = 396 s for the CP, checked after each candidate (preendgame.cpp:57-62, 206-207).
- **Known bug report:** a 1-in-bag position where Quackle gave 25% and 75% for two plays that Elise rated 75% and
  25% (quackle/quackle#100, open, 2019).

**Versus MAGPIE.** MAGPIE covers 1–4 tiles in the bag (up to 7 if every candidate leaves ≤4). It is pessimistic by
default, solves bag-emptying scenarios with its endgame solver, and runs without a time limit by default
(magpie.md). Quackle's scenario values rest on its heuristic endgame (below) and on only 30 sim-chosen
candidates.

**Inference.** At 3–4 in the bag Quackle falls back to the plain sim, where MAGPIE solves. MAGPIE should gain most
there. At 1–2 in the bag both enumerate, so the difference comes down to endgame accuracy and candidate breadth.
Quackle's opponent reply is a full-information endgame, which is in effect also pessimistic.

## Endgame (`Endgame`)

`EndgamePlayer::moves` → `Endgame::solve` (endgameplayer.cpp:40-73; endgame.cpp:263-400):

1. Take the top 320 static moves (14 when nested once, 1 when nested twice) (endgame.cpp:33-46, 273-283).
2. Play each out greedily to game end (static best for both sides). The result is the move's "optimistic" value.
   It is also "pessimistic" only if the move goes out at once (endgame.cpp:291-362).
3. In descending optimistic order, until optimistic < best pessimistic: **disappoint** the move. Try the
   opponent's top 160 replies (7 nested, 1 sub-nested), each followed by a greedy playout, and keep the minimum.
   Each reply loop stops once the minimum drops below the best pessimistic (endgame.cpp:172-261, 364-395).
4. Play the chosen move out with a nested solve at every later ply to set its win and spread
   (endgame.cpp:402-463).

There is no alpha-beta, transposition table, iterative deepening or time limit, and no threading. Abort works only
through the dispatch (endgame.cpp:294-297). Static eval with an empty bag is the going-out term above
(catchall.cpp:70-95). Related issues: quackle/quackle#39 (option to maximise total score, open).

**Inference.** In effect this is a 2-ply max–min over ≤320×160 moves with a greedy leaf. It misses setups that need
three or more of one's own moves, and stuck-tile lines where the greedy playout is wrong. MAGPIE's 6-ply
alpha-beta with greedy leaves is strictly deeper. Most endgames are simple, so the strength cost is concentrated in
the close, complex ones. Size UNVERIFIED; we would have to measure it.

## Exchange / pass

Exchanges are generated as subsets with equity = leave value (+3.5 on an empty board) and compete in the candidate
list (generator.cpp:1861-1893; catchall.cpp:54-55). A pass is the fallback best move (generator.cpp:1898). A user
report says the CP rarely exchanges on the opening turn compared with another program (quackle/quackle#111, German).

## Time management and threading

Fixed per-turn budget in iterations; `secondsPerTurn` is only a cap (above). No clock awareness, no banking.
Twenty Second Player: 20 s → 40/100 iterations; Five Minute: 300 s → 600/1500 (resolvent.cpp:100-114). Sim threads
as above; endgame single-threaded.

## Build and GUI

One line each: CMake builds `quacker`, `quackle` and `quackleio` (README.md:15-20); Qt is needed for `quackleio` and the GUI. GUI (`quacker/`): not covered.

## Tuning and testing

Regression goldens for sim structure, abort and chunking, run by `test/testharness.cpp --mode sim` in CI
(commits `abf30f5`, `467eaf8`, `4196b39`; quackle/quackle#140). No strength-testing harness, SPRT or match tooling in
the repo. Only user reports exist. quackle/quackle#67 says that in ~50,000 games the Speedy Player, moving first,
won ~50% against the 20-second CP, while Speedy-vs-Speedy first players win ~56%. No method or lexicon is given;
UNVERIFIED.

## Measurements

| What | Number | Settings | Hardware | Source | Measured by |
| --- | --- | --- | --- | --- | --- |
| Leave tables, Quackle CSW vs MAGPIE CSW24 | 914,624 = 914,624 keys; Pearson 0.977; mean −5.35 vs −2.68; RMS diff 1.9 (1 tile) to 4.6 (6 tiles) | `python3 -I docs/engines/data/compare_quackle_magpie_leaves.py reference/quackle/data/strategy/csw/superleaves data/magpie/data/lexica/CSW24.klv2` (MAGPIE-DATA `data-20260925`) | i5-9500T, 6 cores, Linux | `docs/engines/data/quackle-vs-magpie-leaves.txt` | us |
| CP search size | ≤14 candidates × ≤330 iterations, 3 moves each | read from code (above) | n/a | bogowinplayer.cpp:38-46, 137-211 | us (code reading) |

Not measured yet: moves/s, rollouts/s and endgame times on our machine (needs the Qt build; docs/harness).

## History

Public git starts in 2013 with "Initial git commit." (`9306cb6`, Jason Katz-Brown). Authors in file headers: Jason
Katz-Brown, John O'Laughlin, John Fultz (2005–2019). Commits per year: 2013–16 about 20–50, 2019: 67 (threaded sims
`f2e4233`, strategy dedupe), 2026: 90 (threading rework, QoS, CI, macOS packaging). Of 31 PRs, none touch the
algorithms (`reference/history/quackle/prs-index.tsv`). The sim, pre-endgame and endgame logic predate the public
history. That the CP's settings date from a 2006 Toronto match is suggested by the class name `TorontoPlayer` only;
UNVERIFIED.

## Inference

- The Championship Player is a strength reference by reputation, not by recent measurement. Its algorithm is
  frozen, and its budget is a fixed sample count that modern hardware finishes well inside 66 s. "Beat the CP at
  66 s" is therefore a much weaker bar than its name suggests. A fair test should also run it at a fixed, matched
  iteration count.
- Of the differences from MAGPIE, sample efficiency (BAI + CRN) and raw throughput should dominate. After them come
  the 3–4-in-bag pre-endgame and the deeper endgame. The leave table and the lack of inference should matter
  least.
- Its evaluation is the same shape as MAGPIE's (score + leave + timing + opening table, and a win table at the
  leaf). MAGPIE is in effect Quackle's design with better statistics and faster code.

## Evaluation call sites

Same numbering as magpie.md:

| # | Site | Quackle | Calls per… |
| --- | --- | --- | --- |
| E1 | Leave value | `ScorePlusLeaveEvaluator::leaveValue`: superleave map lookup, formula fallback (evaluator.cpp:73-168) | every generated move (no per-rack cache) |
| E2 | Static move equity | `CatchallEvaluator::equity`: score + leave + timing/opening/endgame terms (catchall.cpp:27-95), from `Generator::equity` (generator.cpp:1378-1381) | every generated move |
| E3 | Rollout policy | `GamePosition::staticBestMove` = `kibitz(1)` (game.cpp:284-288; sim.cpp:644) | every rollout ply |
| E4 | Sim leaf | `bogowin(spread + residual, bag + 7)`, residual = leaves of each side's last move (sim.cpp:665-699, 716-735) | once per playahead |
| E5 | Inference | none (bogowinplayer.cpp:114-132; sim.cpp:803) | n/a |
| E6 | Endgame / PEG leaf | greedy static playout to game end (endgame.cpp:224-247, 310-332); PEG: win of the `Resolvent` reply (preendgame.cpp:178-188) | per endgame candidate × reply; per PEG candidate × rack |

**Inference.** Every site goes through one global evaluator (`QUACKLE_EVALUATOR`, game.cpp:498-516), so a learned
evaluator could be dropped in with little code (a day or two). But Quackle's slow movegen and simple search would
cap what it could show. It is not a useful testbed for a neural eval.

## Relevance to the three decisions

1. **What to fork.** Not Quackle. It is GPL-3.0 like MAGPIE, much slower (no shadow pruning, map-based leaves),
   and weaker in every search component, and its algorithms are frozen. Nothing in it is missing from MAGPIE.
2. **Where a neural eval pays off.** The CP reaches championship level with a 2-ply sim, a 3-key win table and
   board-blind leaves. That suggests most of the remaining gains lie in sample efficiency and endgame search
   (MAGPIE already has those) and then in a board-aware leaf (E4). The two leave tables agree at 0.977, and
   MAGPIE reports leave generations near saturation. Together these point the same way: leaves are not where a
   net pays first.
3. **How we prove we are stronger.** Use the CP as a fixed historical baseline, driven by the harness adapter
   (docs/harness/reuse-check.md §3). Pin three things:
   - the SHA;
   - the strategy files (CSW superleaves of unknown edition, `default/bogowin`);
   - thread count. Threading changed the CP's speed in 2026 (`42c5d25`, `763e96f0`), not its choices.

   Report results at its native 66 s and at matched wall time. Because its budget is iteration-bound, the 66 s
   setting does not give it 66 s of search. The main bar remains MAGPIE/BestBot.

## Open questions

- Which lexicon edition and method produced `data/strategy/csw/superleaves` and `default/bogowin`? Ask the
  authors, or compare with CSW07/CSW12-era tables. (Code and commits give no answer.)
- How long does a CP turn actually take on our machine at 1 and 6 threads? If it is well under 66 s, record the
  effective budget. To be measured in `docs/harness/builds.md`.
- Is quackle/quackle#100 (1-in-bag win% inverted) still reproducible at `35e11bb`? The attached GCG is linked in the
  issue.
- What is the CP's head-to-head win% against MAGPIE at equal wall time and at equal rollouts? No published number
  was found.
- Does running sims to game end at 3–14 in the bag (greedy rollouts) help or hurt versus 2 plies? An A/B in
  self-play would tell.
- What does Sheppard 2002 (Maven) say about simulation and the pre-endgame, given that Quackle's design follows the
  same school? UNVERIFIED; not fetched.
