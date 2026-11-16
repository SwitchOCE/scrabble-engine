# Research plan (stage 1)

Stage 1 ends when we can answer: **what do we fork or build on, what will make our engine
stronger than the rest, and how will we measure that?** The output is a plan for stage 2
(building), backed by the dossiers below.

## R1. Existing engines: how they work

One dossier per engine in `docs/engines/` (template: `_template.md`). For each:

- Move generation: data structure (GADDAG, DAWG, KWG), cross-checks, anchor handling,
  speed in moves/second on our machine.
- Static evaluation: score + leave value. How leaves are valued (tables, superleaves,
  how they were trained), board/positional terms, bag-state terms.
- Simulation (Monte Carlo rollouts): candidate selection, ply depth, inference of the
  opponent's rack, stopping rules, win% vs spread.
- Endgame (bag empty, perfect information): search algorithm, move ordering, pruning,
  transposition tables.
- Pre-endgame (1–7 tiles in bag): what is solved exactly vs approximated.
- Exchange and pass logic. Time management. Multi-threading.
- How the engine was tuned and tested; known weaknesses.
- Build status on our machine and how to drive it from a script (CLI, protocol, API).

Engines: Quackle, Macondo, MAGPIE, wolges, Elise, Maven. See `docs/engines/README.md`.

### R1b. Engine history: why things changed

How an engine got strong tells us more than its current code. For each open engine,
write `docs/engines/<engine>-history.md` from its commits, pull requests and issues
(exported by `scripts/fetch-history.sh` into `reference/history/<engine>/`):

- **Timeline of major changes**: when move generation, leaves, simulation, endgame and
  so on were added or rewritten, with PR/commit links.
- **Why each change was made**, in the authors' words where possible (PR body, review
  thread, issue).
- **Measured effect**: any win %, spread, speed or Elo numbers given for a change, and
  how they were measured.
- **Failed and abandoned experiments**: PRs closed without merging, reverts, ideas
  tried and dropped. Negative results save us repeating them. Record why they failed if
  anyone said.
- **Ideas from one engine that later spread to another** (e.g. Macondo → MAGPIE,
  wolges formats adopted by Woogles).
- **Open issues about strength or known weaknesses.**

Same treatment for Stockfish in R3: its commit messages carry the SPRT results of each
patch, and fishtest holds the record of tests that failed.

## R2. Test harness: playing engines against each other

Before we write an engine we need a way to measure one.

- A match runner that plays engine A vs engine B over thousands of games with shared
  tile sequences (duplicate-style seeding to cut variance).
- Statistics: win %, spread, confidence intervals, SPRT stopping (as fishtest does).
- Which engines can be driven headless? (Macondo and MAGPIE have CLIs; Quackle has
  `quackletest`; wolges is a library; Elise needs Wine and possibly GUI automation.)
- Check whether MAGPIE or Macondo already has an autoplay mode we can reuse.

## R3. Chess engines: what changed and what transfers

Write up in `docs/chess/`. For each technique: what it is, how much Elo it gave,
and whether and how it maps to Scrabble.

- NNUE: architecture, incremental (efficiently updatable) accumulator, quantisation,
  SIMD inference, how training data is generated (self-play + search labels), trainer
  (nnue-pytorch). Scrabble analogue: incremental board/rack features after each placed
  tile.
- Before NNUE: the hand-tuned eval and how it was tuned (Texel tuning, SPSA).
- AlphaZero / Leela: policy + value nets with MCTS. Compare with simulation in Scrabble.
- Search: alpha-beta, PVS, transposition tables, move ordering, null move, LMR,
  aspiration windows, lazy SMP. Most apply to the Scrabble endgame.
- Engineering: bitboards, magic tables, cache-friendly data, fishtest-scale distributed
  testing, SPRT.
- Imperfect information: what poker (CFR, ReBeL) and bridge engines do about hidden
  information and chance. Scrabble has both.

## R4. Scrabble AI literature

Collect in `docs/literature/` with a one-paragraph summary each. Start with:
Sheppard's Maven paper (2002), Quackle docs, Macondo "how it works", Woogles BestBot
and leave-value posts, the MAGPIE notes, academic papers on Scrabble endgames,
rack inference and RL for Scrabble.

## R5. Data

- Lexicons: which ones (NWL, CSW, others), how engines get them, licence terms.
- Game corpora: Woogles game exports, cross-tables, GCG files. Volume and licence.
- Self-play: how fast can we generate labelled positions with an existing engine?

## R6. Decision: what to fork

Inputs from R1–R5. Write the result as `docs/decisions/0001-fork-base-and-licence.md`.
Criteria: strength, speed, code quality, how easy to bolt a neural eval into, language,
licence, how active it is and whether its authors would welcome collaboration.

## Open decisions for the project owner

1. **GPU compute.** This machine has no NVIDIA GPU. Training nets at Stockfish scale
   needs rented or owned GPUs.

## Decided by the project owner

The approved stage-1 plan is [plans/stage1-plan.md](plans/stage1-plan.md).

- **Licence: GPL-3.0 is acceptable, MIT is preferred** (decided 2026-11-16). Owner:
  "GPL's fine. It'd be preferable to be MIT, but I'm okay with GPL as well." So forking
  Quackle, Macondo or MAGPIE is allowed. The fork base itself stays open until R6
  (stage-1 step 5).

  Set by the orchestrating session from the owner's words (relayed 2026-11-16), not the
  owner's own wording: in R6, MIT is preferred; it weighs in favour of wolges or our own
  code, decisively when the other criteria are close. Language stays its own R6
  criterion. Note, not a decision: network training is in Python either way.
- **"Eclipse" is Elise** (decided 2026-11-16). Elise (closed, Windows) stays deferred
  until the open engines are measured; see "Suggested order".
- **Lexicon: Collins Scrabble Words (CSW)** (decided 2026-11-16), the latest edition the
  engines support, for all matches and benchmarks. **Edition: CSW24**, confirmed from
  the pinned sources below (all four open engines reference it, none references a newer
  one); stage-1 step 2b checks the built data matches. Lexicon files and built
  KWG/DAWG/GADDAG files stay uncommitted under `data/`.

  Editions the reference clones use for the CSW24 finding (pins in `docs/engines/pins.tsv`):
  - Quackle `35e11bb21a3bf362c533541d0b5fe8ad92a0c08f`: ships `csw24.dawg`
    (`data/lexica/CMakeLists.txt:5`); `data/lexica/copyrights.txt:10` names "Collins
    Offical Scrabble™ Wordlist 2024"; regression suite for csw24
    (`test/regression/suites/csw24-english/suite.json:3`).
  - Macondo `9c33baa636258ce1a2add1e843f9c8ce1a939436`: Collins value net trained on
    CSW24 self-play games (`README.md:98`); tests use CSW24 (`wmp/wmp_test.go:13`) and
    older CSW19 (`endgame/negamax/solver_test.go:203`) and CSW21 (`:206`).
  - MAGPIE `b78101815898641c5f449a7d8b51101b58a2caf0`: `make prepare_data` validates or
    upgrades the CSW24 WIT and creates a missing RIT (`AGENTS.md:19`); README examples use `set -lex CSW24` (`README.md:249`); most
    unit tests use CSW21 (`test/test_constants.h:9`). `download_data.sh:66-68` fetches
    versioned tarballs and does not name editions.
  - wolges `be00002981690e22eada4df871da067bd88f7719`: quick start uses `CSW24.kwg`
    (`README.md:44`); its Initial Setup builds CSW19 (`README.md:31-33`).
  - No edition newer than CSW24 appears in these clones (grep for `CSW2[5-9]`/`CSW3x`).

## Process decisions (orchestrator)

- **Ruleset.** Matches use WESPA rules: CSW with a 5-point challenge. Decided by the
  orchestrator as a process choice; the owner named no rule. (UNVERIFIED: no WESPA rules
  link checked yet.) Macondo `9c33baa636258ce1a2add1e843f9c8ce1a939436` implements this
  rule (`game/challenge.go:166`, `ChallengeRule_FIVE_POINT`).

  Inference: bot-vs-bot games rarely involve phonies, so the challenge rule should
  seldom change results.

## Findings shaping stage 2

From the [MAGPIE dossier](engines/magpie.md):

- **(a) Leave tables look saturated.** Six retraining rounds of BestBot's leaves gave 50.0% → 50.4% head-to-head
  ([Woogles, 2025-06-02](https://blog.woogles.io/posts/2025-06-02-new-leaves)). MAGPIE's contextual,
  pool-aware leaves (jvc56/MAGPIE#630) gave about +1 Elo. Gains have to come from evaluation that sees the
  board and bag, most likely a value net at the playout leaf.
- **(b) The target will move.** The MAGPIE authors are already testing a GPU value net in rollouts
  (jvc56/MAGPIE#920, branch `vn-nnue-m5`). Our edge has to come from doing it better or faster: a
  CPU-efficient incremental net, or better training data. Update from the pushed branches
  (`claude/value-net-pat` `ad85baba`): they run Macondo's 3.7M-parameter transformer on Apple GPU/Neural Engine
  (16 ms per row on a CPU core). As a one-ply player it scores 56.83% ± 0.90 against static. Inside the sim the
  only test, at equal iterations, was flat (50.67% ± 1.85%), and the net leaf was never played. So the open
  ground is a µs-scale CPU leaf net shown at equal time.

Contacting the MAGPIE authors is the owner's call; nothing has been sent.

## Suggested order

Follows the approved [stage-1 plan](plans/stage1-plan.md): harness first. Step 2a (reuse
check) → 2b/2c (headless builds, adapters), with the MAGPIE dossier in parallel → 2d
(baseline matches, MAGPIE profile), with the other dossiers and the Stockfish study in
parallel → step 5 synthesis (R6).
Closed engines (Elise, Maven) after the open ones, since they are the costliest.
