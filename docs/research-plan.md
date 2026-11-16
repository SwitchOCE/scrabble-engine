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

1. **Licence.** Forking Quackle, Macondo or MAGPIE means our engine is GPL-3.0.
   Forking wolges (MIT) or writing from scratch leaves the choice open.
2. **GPU compute.** This machine has no NVIDIA GPU. Training nets at Stockfish scale
   needs rented or owned GPUs.
3. **Which "missing" engine you meant.** Candidates: Elise and Maven (closed),
   MAGPIE and wolges (open). "Eclipse" may be Elise.
4. **Target lexicon / ruleset** for the first matches (e.g. CSW24 or NWL23, TWL rules).

## Suggested order

R1 (open engines) and R4 in parallel → R2 harness → R3 → R5 → R6.
Closed engines (Elise, Maven) after the open ones, since they are the costliest.
