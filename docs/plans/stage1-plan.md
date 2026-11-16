Approved by the owner 2026-11-16, along with: GPL acceptable, MIT preferred; include the Stockfish ranked table; include abandoned PRs in leave/sim/endgame in dossiers.
Later notes: the GPL question (step 1 of Order) is answered: GPL acceptable, MIT preferred.

# Stage 1 plan, steps 2–5 (revised after plan-interrogate)

Test for every step: does it feed one of three decisions — (a) what to fork, (b) where a neural eval pays off, (c) how we prove we are stronger?
Lexicon: Collins, latest edition all of Quackle, Macondo and MAGPIE have data for (likely CSW24; confirm, record). Files under `data/`, never committed.

## Step 2 — Match harness and baseline (top priority)
- **2a Reuse check.** Confirm what plan-interrogate found: Macondo autoplay can drive an outside engine (`ai/externalengine/config.go`: `--gcg --lexicon --rack` in, one JSON line out; `CUSTOM_BOT`, `automatic/config.go:79`). It has paired-bag mode (`game/pairedbag.go:40`) and paired stats (`stats/paired.go`). Checkpoint: does this replace a new harness?
- **2b Headless builds** of Quackle, Macondo and MAGPIE at the pinned SHAs. Commands and versions go in `docs/harness/builds.md`.
- **2c Adapters, not a new harness.** Thin Quackle and MAGPIE adapters to Macondo's external-engine contract. Macondo owns the bag, so both seat orders see the same tiles. Build only what 2a shows is missing.
- **2d Baseline.** Paired games with sequential (SPRT-style) stopping instead of a fixed 1,000 games. Static-eval matches for every pair. Simulation matches at equal time per move, only where the static results don't settle it. Report win rate and spread with confidence intervals.
- **2d add: one MAGPIE profile.** Sims/sec, and the split of time between move generation and evaluation. This feeds decision (b) with a measurement.
- Gates: runtime means adapter tests, plus a smoke match whose GCG logs replay legally in a second engine. Then the scope-reviewer.

## Step 3 — Engine dossiers
- **MAGPIE first.** Check its depth and format before running Quackle, Macondo and wolges in parallel. Budget about 300k tokens each, less for Quackle (31 PRs).
- **Depth** goes on leave valuation, simulation (including rack inference) and endgame/pre-endgame. Move generation, exchanges, time management, threading, build and UI get one paragraph each, never left blank.
- **PR/issue history** only where it explains a change to those three parts. That includes the CLOSED/abandoned PRs in those areas (what was tried and dropped).
- **Key literature** goes in as sources: the Maven paper, Macondo/Woogles posts on leaves and simulation.
- Each dossier ends with "Relevance to the three decisions". It must answer directly: **how hard it is to add a neural evaluation** (where evaluation happens in the code, and the per-position cost budget inside simulation).
- The wolges dossier must also answer: **what wolges lacks compared with MAGPIE** (simulation, endgame, pre-endgame, rack inference, autoplay), with a rough work estimate for each piece.
- Gates: citation spot-check (cited SHAs are in pins.tsv; path:line exists at that SHA), then the scope-reviewer.

## Step 4 — Stockfish, narrow
- **(i) The move to NNUE:** architecture, accumulator updates, quantisation, training data generation.
- **(ii) SPRT/fishtest method:** bounds, pentanomial statistics, STC/LTC ladder.
- **(iii) Ranked table, from the parser output:** the top Stockfish techniques by measured Elo, each marked "transfers to Scrabble" or "doesn't", with no new reading.
- Output goes to `docs/chess/nnue.md` and `docs/chess/testing-method.md`. Budget about 400k tokens.
- Gates: as step 3.

## Step 5 — Synthesis
- Write the answers to all three decisions:
  - **(a) Fork recommendation** in `docs/decisions/0001`, with MAGPIE as the hypothesis to test.
  - **(b) Where a neural eval pays off.**
  - **(c) How we prove we are stronger**, i.e. the test method and baseline.
- Evidence: steps 2–4.
- **Licence is a tiebreaker, not a blocker** (owner: GPL fine, MIT preferred). Choose on strength, speed and how easily a neural eval fits. Prefer the MIT option (wolges, or our own code) only when the call is close. The language follows the fork; network training is in Python either way.
- Gates: the scope-reviewer; the owner approves.

## Order
1. GPL question (owner).
2. Step 2a.
3. Steps 2b and 2c, with the MAGPIE dossier in parallel.
4. Step 2d and the profile, with the other three dossiers and step 4 in parallel.
5. Step 5.

Checkpoints: after 2a, after the MAGPIE dossier, after 2d, after step 5.

## Deferred, with triggers
- **Elise and Maven:** after the open engines are measured.
- **Full R1b history docs:** when a dossier finds a change to leave, sim or endgame it can't explain.
- **R5 corpora and self-play data:** when net training is planned.
- **Stockfish PR threads:** when a ranked technique needs its reasoning.
- **wolges in the harness:** a static-eval match only, if 2a shows its adapter is cheap, so the MIT tiebreaker has a measured strength behind it. Otherwise, add it only if step 5's call turns out close.
- **GPU compute:** later.
