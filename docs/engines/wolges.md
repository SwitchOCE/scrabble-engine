# wolges

- Source: https://github.com/andy-k/wolges, commit `be00002981690e22eada4df871da067bd88f7719` (from `pins.tsv`, 2026-11-14)
- Licence: MIT (`LICENSE.txt`; `README.md:13-18`)
- Language / build: Rust, Cargo. One library and several binaries (`auto`, `buildlex`, `endgame`, `json`, `leave`,
  `lex`, `read`, `shell`, `simmer`, `movegen-test`, `reply-cv`; `Cargo.toml:45-90`). PGO scripts
  `build-pgo*.sh`. Not built by us yet (no Rust toolchain installed; see `docs/harness/reuse-check.md` §4).
- How to drive it headless: the `shell` binary (`lexicon`, `leaves`, `gcg load`, `rack`, `bot`, `bot sim MS`,
  `infer`; `src/shell_session.rs:272-420`) or a small Rust binary on the library. Details in
  `docs/harness/reuse-check.md` §4.

**Scope.** This dossier answers one question for the fork decision: which parts of MAGPIE's stack does wolges
lack, and how much work is each? The checklist is the Pipeline and History sections of `magpie.md`. Other
topics get one line.

**Citation convention.** Every `path:line` without a repo prefix is andy-k/wolges at `be00002` (full SHA above),
read from the working tree of `reference/wolges`, which is at the pin (`reference/history/wolges/commits.tsv`
tops out at `be00002`). PRs are `andy-k/wolges#n` with the merge commit's short SHA. All PRs are self-merged
by the author (Andy Kurnia). MAGPIE refs are jvc56/MAGPIE at `b781018`, mostly via `docs/engines/magpie.md`.
The `lab/*.txt` notes are the author's write-ups of measured results; they are treated as primary
literature, but their numbers were not reproduced by us.

## Summary

- **Does well:** wolges is a full engine, not just a move generator. It has a shadow-playing movegen (MAGPIE's
  is derived from it), a rollout simmer with common random numbers and paired-difference pruning, soft
  (likelihood-weighted) rack inference with a fitted temperature, an exact empty-bag endgame solver, an exact
  1-in-bag pre-endgame, a threaded N-in-bag pre-endgame, and the best-documented leave-generation lab
  (census, self-play, blend, pool-aware "dynamic" leaves).
- **Does badly / missing vs MAGPIE:** no adaptive (top-two) sampling or GLR stopping; the empty-bag endgame
  runs on one thread; the multi-tile pre-endgame is only in the `endgame` CLI and is not used by any playing
  seat; no timed play (clocks, overtime) in match runs; no positional term like MAGPIE's PAT; no
  distributed-compute client.
- **What we would take:** almost everything. It is MIT, so a fork can stay MIT.
- **Size:** about 84k lines of Rust in `src/` (`src/endgame.rs` 16k, `src/movegen.rs` 16k,
  `src/main_leave.rs` 11k). Development is fast: 569 PRs from 2026-03 to the pin, and 1,019 lines in the
  commit log mention Claude as co-author (`reference/history/wolges/commits-full.txt`).
- **Relation to MAGPIE:** the source of the formats and ideas that MAGPIE builds on (KWG, KLV2, shadow
  playing, leave census; MAGPIE README.md:957-963 as cited in `magpie.md`).

## Pipeline

From position to move in the `shell`'s `bot sim MS` and in a `leave compare` simmer seat:

1. **Candidates:** up to 100 placements plus 5 non-placing moves (exchanges/pass) by static equity
   (`src/move_picker.rs:38-46`, `gen_simmer_candidates` `src/move_picker.rs:57`).
2. **Inference** of the opponent's kept leave from their last move, if the caller gives it
   (`pick_a_move_after`, `src/move_picker.rs:1943-1999`; `src/infer.rs:852`).
3. **Rollouts:** each iteration deals one shared draw (CRN), then rolls out every surviving candidate for
   `num_sim_plies` (default 4, `src/move_picker.rs:22`) with greedy best-move replies
   (`src/simmer.rs:600-680`). Once the bag empties, the rollout plays on to the end of the game
   (`src/simmer.rs:570-575`; `andy-k/wolges#279` `982602bb`).
4. **Leaf value:** `sim_objective` = spread in points + win probability × weight
   (`src/simmer.rs:26-28`). The win probability is a hand-tuned sigmoid or an empirical table
   (`src/simmer.rs:940-975`).
5. **Pruning and stopping:** every 16 iterations, candidates whose paired difference to the leader is below 0
   at a Bonferroni-split one-sided z are retired, and the field is capped as the budget runs out
   (`src/move_picker.rs:142`, `223-226`, `285-330`, `1594-1606`). The budget is a fixed iteration count
   (default 1000, `src/move_picker.rs:21`), or from a time budget via `plan_rollouts`
   (`src/move_picker.rs:640-674`).
6. **Empty bag:** the `shell` hands over to the exact endgame solver (`src/shell_session.rs:3101-3143`).
   A 1-in-bag or N-in-bag pre-endgame is not called by the `shell` or by `leave compare` (no `peg` reference
   in `src/shell_session.rs`, `src/move_picker.rs` or `src/main_auto.rs`).

## Move generation

`KurniaMoveGenerator` (`src/movegen.rs:6794`) on a KWG (GADDAWG). Shadow playing (per-anchor upper bounds,
best-first) is documented in `details.txt:404-470`. Further pieces: anagram "arm tables" for placements
(`src/anagrams.rs`; `andy-k/wolges#168`, `#224`), a per-full-rack leave table read in place of the KLV walk
(`src/racks.rs:5-11`; `src/movegen.rs:1217-1229`), and a census-steered generator for rollouts
(`gen_moves_unfiltered_lanes_steered`, `src/movegen.rs:8490`; taken after 1,024 rollouts of a decision,
`src/simmer.rs:133-137`). These match MAGPIE's WMP, RIT and census steering. A test corpus and baselines live in
`src/movegen-*-baseline.txt`.

## Static evaluation and leaves

Equity is in millipoints (`src/equity.rs:6`). Bag not empty: score + KLV2 leave (+0.7 opening hotspot
penalty, `src/equity.rs:8`; `src/infer.rs:66-90`). Bag empty: +2× opponent's tiles if going out, else
−10 − 2× own tiles (`src/movegen.rs:1169-1180`, `3627-3637`). A **bag term** (MAGPIE's pre-endgame adjustment)
exists as a mechanism with "none by default" and is only set in a test (`src/movegen.rs:526-545`, `6828-6841`).
**Dynamic leaves** reweight full-length leave values against the unseen pool (`dynamic_leaves`,
`src/movegen.rs:1045`, `1269`). No positional term like PAT.

### Leave-generation pipeline (`lab/leavegen.txt`)

This is where the `.klv2` tables come from. Four methods, all in the `leave` binary (`src/main_leave.rs`):

1. **Self-play** (the original): `leave autoplay` logs (full rack, best-move equity); `summarize` tallies per
   rack; `generate` spreads each rack's mean to its sub-leaves, weighted by frequency and draw count, centred
   on the empty leave, and smooths thin leaves; `buildlex klv` compiles the CSV to `.klv2`. Repeat per
   generation; `genleaves.sh` automates it (`lab/leavegen.txt:70-142`). Rare racks are forced by default
   (`lab/leavegen.txt:236-245`).
2. **Board sampling ("gilles")**: snapshots midgame boards to manufacture racks. At one million game pairs it
   beat the self-play table, which reads 47.88% against it (`lab/leavegen.txt:292-314`).
3. **Census**: on each board, exact best one-move value of every rack in the 5,379,616-entry sub-rack lattice,
   averaged over boards, iterated over generations. Recommended recipe `3x256,2048` (`lab/leavegen.txt:20-59`,
   `367-395`). Only late-midgame boards, because the play sheet enumerates every play from the unseen pool
   (`lab/leavegen.txt:508-551`). The author says its "clear, immediate win is runtime, not a proven jump in
   play strength" (`lab/leavegen.txt:553-563`).
4. **Blend**: 50/50 census + two self-play generations of ten million games, `genblend.sh`. It beats each
   parent by about 0.1 percentage points over five million pairs (`lab/leavegen.txt:964-1020`). This is the
   strongest table measured.

Pool-aware (dynamic) leaves beat the same static table 50.66% over 50k pairs at a smallest-keep floor of 2
(`lab/leavegen.txt:946-962`). Strength is always measured by `leave compare`, with mirrored game pairs
(`lab/leavegen.txt:144-200`; `andy-k/wolges#27` `7a19dc25`). The empirical win% table is keyed by
(bag, my rack size, opponent rack size) and margin, from self-play (`lab/leavegen.txt:800-846`;
`src/win_pct.rs:1-5`).

## Gap against MAGPIE, component by component

Facts only here; effort estimates are under Inference.

### Simulation

- **Has:** the rollout simmer (`src/simmer.rs`, 2.1k lines; `src/move_picker.rs`, 3.8k lines). CRN, with each
  candidate rolling out from a private snapshot of the shared draw (`lab/simmer.txt:113-117`). Retirement by
  paired difference to the leader every 16 iterations, z split over the looks, and a time-uniform
  confidence-sequence z (Howard et al. 2021) for budgets with no end (`src/move_picker.rs:215-311`).
  Deterministic: per-iteration seeds, fixed-order reduction, same result at any thread count
  (`lab/simmer.txt:192-220`). Rollouts reach the end of the game once the bag empties (`#279`). The whole bag is
  shuffled each iteration (`#280` `997ddd23`). Win weight 10, rising to 10,000 when the plies can reach the
  end (`src/simmer.rs:406-418`). Ply-1 reply from the start-board lane bests (`src/simmer.rs:757`).
- **Missing vs MAGPIE:** sampling is round-robin over the survivors (successive elimination), not top-two
  IDS with a GLR/GK16 stopping rule (`magpie.md` "Allocation and stopping"); no bag cycling of the opponent's
  rack (MAGPIE #764); no best-move carry across rollouts (MAGPIE #824; wolges has lane bests at ply 1 only);
  utility is spread + weighted win%, not MAGPIE's win% + 0.5·sigmoid(spread); the win% table has no
  full-state key (MAGPIE #703); no PAT inside rollouts.
- **Measured:** simmer vs hasty, 20 pairs at 200 rollouts a move: 58.75% (`lab/simmer.txt:73-75`).

### Endgame

- **Has:** `EndgameSolver` (`src/endgame.rs`): negamax, iterative deepening to the game's end (exact),
  aspiration windows, Zobrist TT that grows within a memory limit, word-pruned graph, limits on time, states
  and memory, answering from the deepest finished pass (`lab/endgame.txt:1-47`, `69-113`;
  `src/endgame.rs:33-55`, `1530-1544`; `andy-k/wolges#88` `9613007c`, `#294` `37e92432`). A depth-limited
  leaf is valued as if both players passed (`lab/endgame.txt:29-47`). The file's header still says "this
  module is very slow ... and it still has many bugs" (`src/endgame.rs:3-4`); it may be stale.
- **Missing vs MAGPIE:** the empty-bag search runs on one thread: threads appear only in the bag search
  (`src/main_endgame.rs:508` "worker threads with two or more tiles in the bag"). MAGPIE has ABDADA on all
  threads with a lockless TT, a greedy-playout leaf at a 6-ply default horizon, and multi-PV
  (`magpie.md` "Endgame").

### Pre-endgame

- **Has:** exact PEG-1 with a committed move (no peeking) and exchanges (`src/endgame.rs:4919-4970`;
  `andy-k/wolges#91` `f3e09d68`, `#101` `2267824a`; `lab/endgame.txt:116-263`). The N-in-bag `solve_peg`
  (`andy-k/wolges#436` `f726d827`, 2026-11-04) has two opponent models: `InfoSets`, where each player chooses
  blind until the bag empties, and `RandomDraws`, a faster approximation. It values moves on threads
  (`#437`, `#440`; `src/endgame.rs:4969-4985`, `6160-6177`). `lab/endgame.txt:176-184` still says PEG-2 and
  above are "not attempted"; the code is newer than the note.
- **Missing vs MAGPIE:** no playing seat calls it: N-in-bag runs only from the `endgame` binary
  (`src/main_endgame.rs:1606-1618`). There is no time-limited cascade or top-k staging like MAGPIE's
  32→16→8→4→2 (`magpie.md` "Pre-endgame"); this is UNVERIFIED for wolges beyond the `Limits` struct. There is
  no fitted pre-endgame adjustment table (the `BagTerm` mechanism has no values). No speed numbers are
  published.

### Rack inference

- **Has:** every rack the unseen tiles could have dealt, weighted by its draw probability ×
  `exp(−(gap − g0)/fuzz)`, where the gap is how far the actual move falls short of that rack's best
  (`src/infer.rs:1-12`, `636-706`). The fuzz is 3.105 points (`src/infer.rs:12`), fitted by maximum likelihood
  over self-play moves (`infer-fit`, `src/main_leave.rs:7586-7600`, `7623`; `andy-k/wolges#311` `0b36fd98`).
  Exchanges and passes are their own move kinds in the fit (`src/main_leave.rs:7580-7584`). Fed into sims,
  self-play included (`#312` `0c6d59f4`), on every core (`#323` `d544afb9`).
- **Missing vs MAGPIE:** nothing found. MAGPIE's merged inference is a hard 5-point cutoff with uniform
  weights; its softmax version is an open PR (MAGPIE #938; `magpie.md`). No strength measurement of wolges
  inference was found.

### Autoplay / self-play

- **Has:** `leave compare` plays mirrored game pairs with per-seat pickers `hasty`, `dynamic`, `deft` (a
  bingo-lane-aware greedy with endgame look-ahead) or `simmer`, per-seat win% tables, plies and rollouts, and
  `--sim-threads`. Runs are deterministic from the seed (`src/main_leave.rs:340-430`, `6632-6645`;
  `lab/simmer.txt:47-94`; `andy-k/wolges#30` `fb5977cf`). `auto` plays hasty against simmer and can harvest
  endgame positions (`src/main_auto.rs:139-167`; `lab/endgame.txt:50-66`).
- **Missing vs MAGPIE:** no seat can use the exact endgame or PEG (end pickers are only `hasty` or `deft`,
  `src/main_leave.rs:6640-6645`); no clocked games with overtime (MAGPIE PlayChooser); no game-per-thread
  vs all-threads-per-game modes; no distributed client (MAGPIE `contribute`/birdtest); no GCG export of
  self-play games (UNVERIFIED; not searched).

### Other (one line each)

- Exchange / pass: non-placing moves have their own candidate quota of 5 (`src/move_picker.rs:43-46`).
- Time management: fixed iteration budget by default; `plan_rollouts` turns a time budget into looks
  (`src/move_picker.rs:640-674`); no game-clock allocation.
- Threading: sim (deterministic slices), census boards, inference and PEG on threads; endgame single-threaded.
- Interfaces: `shell`, `json`, wasm-friendly library (`Cargo.toml:36-43`, feature `shell`); KWG/KLV2 formats are wolges'.

## Evaluation call sites

| # | Site | wolges location |
| --- | --- | --- |
| E1 | Leave | `leave_value_of` / `Klv::leave_value_from_tally` (`src/movegen.rs:3621-3644`; `src/klv.rs:330`), full-rack table `src/racks.rs` |
| E2 | Static move | score + E1 + opening penalty + optional bag term, inside `KurniaMoveGenerator` (`src/movegen.rs:1167-1229`) |
| E3 | Rollout policy | `gen_moves_unfiltered` / `_lanes_steered` with `max_gen: 1`, i.e. greedy E2 (`src/simmer.rs:628-668`) |
| E4 | Sim leaf | `compute_win_prob` (sigmoid or win% table) + `sim_objective` (`src/simmer.rs:16-28`, `940-975`) |
| E5 | Inference | best static equity per hypothesised rack, `weigh_racks_by_generation` (`src/infer.rs:446`) and the census sheet |
| E6 | Endgame leaf | both-pass leftover margin at the depth limit (`lab/endgame.txt:29-47`); search is otherwise exact |

## Measurements

None by us. Movegen and sim speed of wolges vs MAGPIE: **to be measured in `docs/harness/builds.md`** (a
separate agent is measuring).

| What | Number | Settings | Hardware | Source | Measured by |
| --- | --- | --- | --- | --- | --- |
| Simmer vs hasty | 58.75% for simmer | 20 game pairs, 200 rollouts a move, same leaves | not stated | `lab/simmer.txt:73-75` | wolges author |
| Blend vs census parent | 50.1162%, 50.0950% | 5M pairs, two seeds, CSW24 | not stated | `lab/leavegen.txt:976-980` | wolges author |
| Pool-aware vs static leaves | 50.66% | 50k pairs, floor 2 | not stated | `lab/leavegen.txt:946-956` | wolges author |
| Board sampling vs self-play table | 47.88% for self-play | 1M pairs | not stated | `lab/leavegen.txt:296-300` | wolges author |
| Census run time | 4x256 about 44 s, 3x256,2048 about 142 s | CSW24 | not stated | commit `4d2ea87d` (2026-07-17) | wolges author |
| Movegen moves/s, sim rollouts/s, endgame nodes/s | none published | — | — | searched `lab/*.txt`, `details.txt`, PR bodies, commit log | — |

**Comparability.** wolges publishes no movegen or sim throughput. MAGPIE's numbers are sim iterations/s and
rollout moves/s from PR descriptions, with hardware mostly unstated (`magpie.md` "Measurements"). MAGPIE has
no movegen-only figure either. So no like-for-like speed comparison exists in either project's docs; the
BestBot "5 to 10 times faster" claim is MAGPIE vs Macondo, not vs wolges.

## History

- 2020-12: first commits (`commits.tsv`). From 2026-03, PR-driven work: game-pair compare (`#27`, 2026-04),
  the leave lab (census, board sampling, blend, 2026-04 to 10), the win% table (`#69`, `#83`), the iteration
  budget replacing the 8 s timer (`#75` `7461837e`), the endgame and PEG-1 (`#85`–`#101`, 2026-07), soft
  inference (`#244` `f04cb3df`, 2026-10), endgame-to-the-end rollouts (`#279`), N-in-bag PEG (`#436`–`#453`,
  2026-11). Two open issues, neither on the engine (`issues.json`: #1 build formats, #33 non-English letters).

## Inference

**Gap table.** Estimates are for us adding the missing part to a wolges fork in Rust, to MAGPIE's level. The
rule of thumb is that one person-week gives about 300–600 lines of tested engine code. That figure is
UNVERIFIED, an assumption. Each estimate also budgets the matches needed to show a gain, which on 6 cores is
often the larger cost.

| Part | wolges has | Missing vs MAGPIE | Estimate | Reasoning |
| --- | --- | --- | --- | --- |
| Simulation | Full simmer: CRN, paired elimination, deterministic threads, inference, win% table, census steering | Top-two IDS + GLR stopping; bag cycling; best-move carry; spread-sigmoid utility; PAT | 2–4 pw | BAI core is ~1k lines in MAGPIE (`src/impl/bai.h` 2,040 lines incl. comments). Bag cycling and the utility change are ~100–200 lines each. Best-move carry is ~350 lines in MAGPIE (`best_move_carry.h`). Whether top-two beats wolges' successive elimination is unmeasured, so do a match first (~1 pw) before porting. |
| Endgame | Exact single-thread ID negamax + TT | Parallel search (ABDADA/Lazy SMP); greedy-playout leaf for a capped horizon | 2–4 pw | ABDADA on an existing TT is a few hundred lines, but MAGPIE tried and closed four parallel designs before one stuck (MAGPIE #444–#470), so tuning dominates. The leaf heuristic is ~200 lines. |
| Pre-endgame | PEG-1 exact; N-in-bag with InfoSets/RandomDraws, threaded, CLI only | Wiring into the bot and autoplay; time-limited staging; fitted bag-term table | 1–3 pw | Wiring is ~200–400 lines (the call exists in `src/main_endgame.rs:1606-1618`). Staging under a clock is ~500 lines. The bag-term table is a fit plus a match. The unknown is speed at 3–4 in the bag, which is measurement, not code. |
| Rack inference | Soft likelihood, ML-fitted fuzz, in sims | Nothing found; wolges is ahead of merged MAGPIE | 0 pw (+1 pw to measure its value) | MAGPIE's own softmax is still an open PR. |
| Autoplay / self-play | Seeded mirrored game pairs, per-seat pickers, threads | Endgame/PEG as end picker; clocked games; distributed client | 2–4 pw (no distributed); +2–4 pw for distributed | The end picker is ~300 lines. Clocks plus time allocation are ~500–1,000 lines (MAGPIE `play_chooser.c` 1,429). A fishtest-like client is ~1.8k lines in MAGPIE (`contribute.c`) plus a server we do not have. |

**Total:** roughly 7–15 person-weeks to reach MAGPIE's feature set on top of wolges, before any neural
work. About half of that is matches to confirm each change, not code.

- The gaps are mostly integration and parallelism, not missing algorithms. wolges already has the hard parts:
  movegen, exact endgame, exact and N-in-bag PEG, and the leave lab. It is ahead on inference, on endgame
  exactness, and on the PEG opponent model (InfoSets vs MAGPIE's pessimistic default).
- wolges values determinism and measured claims (game pairs, stated confidence). That suits our step 5 testing,
  but it means its defaults are tuned for reproducibility (fixed iteration budgets), not clock play.
- Speed is the real unknown. MAGPIE's sim numbers include optimisations (best-move carry, bag cycling, BAI)
  that wolges lacks, so MAGPIE may be faster per decision even if the movegens are close. Only the
  measurement in `docs/harness/builds.md` can settle this.
- For a learned evaluator, E4 (sim leaf) is one function in `src/simmer.rs:940-975`, as narrow as MAGPIE's.
  E2/E3 run inside the shadow-bounded generator, so they carry the same bound constraint as MAGPIE.

## Relevance to the three decisions

**1. What to fork.** If the call is close, wolges should be the fork base:
- it is MIT;
- it has a complete engine whose missing parts are about 7–15 person-weeks;
- it is better than MAGPIE at inference and at exact solving;
- it is the source of the formats and leave tables everyone uses.

Against it:
- no published speed numbers;
- single-threaded endgame;
- PEG not wired into play;
- one author with a high PR rate, so tracking upstream is costly, as with MAGPIE.

The deciding facts still to get are the speed head-to-head (`docs/harness/builds.md`) and a wolges `bot sim`
vs MAGPIE match at equal time.

**2. Where a neural evaluation pays off.** The same as for MAGPIE: the sim leaf (E4) first. In wolges it is a
sigmoid or a 3-key table, even simpler than MAGPIE's. The 50.66% from pool-aware leaves is evidence that
context-aware leave values (E1) still have something to gain.

**3. How we prove we are stronger.** `leave compare` already gives seeded mirrored game pairs with per-seat
pickers and stated confidence. It lacks clocks, which must be added (see the gap table) before timed matches.

## Open questions

- Speed: wolges movegen moves/s and simmer rollouts/s vs MAGPIE on our machine. To be measured in
  `docs/harness/builds.md`.
- Does MAGPIE's top-two BAI beat wolges' paired successive elimination at equal time? No comparison found.
- How fast is wolges' N-in-bag PEG (`InfoSets` vs `RandomDraws`) at 2–4 in the bag, and is it fast enough for
  tournament clocks? No numbers published.
- How much strength does wolges' soft inference add? No match result was found.
- Is the `src/endgame.rs:3-4` warning ("very slow", "many bugs") current?
- Does `gcg load` treat the opponent's rack as known? Carried over from `docs/harness/reuse-check.md` §4.
- Which wolges recipe made the `.klv2` in MAGPIE-DATA? Carried over from `magpie.md`.
