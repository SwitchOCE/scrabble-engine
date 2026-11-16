# scrabble-engine

Goal: build a Scrabble (crossword game) engine that beats the strongest existing engines:
Quackle, Macondo, MAGPIE, wolges, Elise and Maven.

## Approach

1. **Understand the field.** Document exactly how each existing engine works (move
   generation, leave evaluation, simulation, endgame and pre-endgame search, time
   management) from its source, or by black-box testing and reverse engineering when
   closed. Get working builds of each so we can play matches against them.
2. **Borrow from chess.** Study how chess engines improved, above all Stockfish's move to
   NNUE, and its search, pruning, parallelism and testing methods (SPRT, fishtest). Keep
   what carries over to an imperfect-information game with a random bag.
3. **Train our own networks** for Scrabble evaluation and use them where Stockfish uses
   NNUE: cheap, incremental and fast enough to run inside search.
4. **Fork if we can.** If an existing open engine is a good base, start from it rather
   than from scratch. See [docs/decisions](docs/decisions/) for the licence implications.

## Current stage: research and planning

No engine code yet. The work now is in [docs/research-plan.md](docs/research-plan.md).

## Layout

| Path | What |
| --- | --- |
| `docs/research-plan.md` | Research tracks, questions and deliverables |
| `docs/engines/` | One dossier per existing engine, plus the catalogue |
| `docs/chess/` | Chess-engine techniques and whether they transfer |
| `docs/literature/` | Papers and articles on Scrabble AI |
| `docs/decisions/` | Decision records (fork base, licence, language, lexicon) |
| `docs/tooling.md` | Toolchains needed and how to install them |
| `scripts/` | Tool check and reference-engine fetch scripts |
| `reference/` | Clones of other engines (git-ignored, read-only) |

## Getting started

```bash
scripts/check-tools.sh        # what's installed, what's missing
scripts/fetch-references.sh   # clone the open-source engines (and Stockfish) into reference/
scripts/fetch-history.sh      # export commits, PRs, issues and review threads to reference/history/
```
