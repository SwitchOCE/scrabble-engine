# Guide for agents working in this repo

Read [README.md](README.md) for the goal and [docs/research-plan.md](docs/research-plan.md)
for the current work.

## Rules for research notes

- **Cite everything.** For a claim about an engine's code, give the repo, the commit SHA
  from `reference/PINS.tsv`, and `path:line`. For a claim from a paper, blog or forum,
  give the link. A claim with no source is marked `UNVERIFIED`.
- **Separate fact from inference.** Write what the code does, then, in its own
  paragraph headed "Inference", what you think it means or why it was done.
- **Measure, don't guess.** Speed or strength claims need the command, the hardware, and
  the numbers. Put raw run output under `docs/<area>/data/` if it is small; otherwise
  say where it lives.
- **One dossier per engine** in `docs/engines/<engine>.md`, following
  `docs/engines/_template.md`. Update the catalogue table in `docs/engines/README.md`
  when you learn something.
- **Open questions go in the doc's "Open questions" section**, not lost in chat.

## Reference engines

- `reference/` holds clones made by `scripts/fetch-references.sh`. It is git-ignored.
  Treat it as read-only: build there if you need to, but don't edit sources. If you need
  a patched build (instrumentation, logging), copy it out or make a branch inside the
  clone and record the patch in the dossier.
- Pinned SHAs are recorded in `reference/PINS.tsv` and copied to
  `docs/engines/pins.tsv` so notes stay reproducible.
- `reference/history/<name>/` (from `scripts/fetch-history.sh`) holds each repo's
  history: `commits.tsv`, `commits-full.txt`, `prs.json`, `prs-index.tsv` (one line per
  PR: number, date, MERGED/CLOSED/OPEN, author, title), `issues.json`, and
  `pr-comments/<n>.json` (review threads and diff size). Start from `prs-index.tsv`;
  CLOSED means closed without a GitHub merge, usually an abandoned experiment.
  Exception: Stockfish maintainers commit patches directly and close the PR, so most
  accepted Stockfish PRs show CLOSED. Check its commit messages ("closes #n") to tell
  accepted from rejected. wolges PRs are all self-merged by its author.
- History write-ups cite PRs as `owner/repo#n` and commits by short SHA.

## Licences and data

- Quackle, Macondo and MAGPIE are GPL-3.0. wolges is MIT. Copying code from a GPL engine
  makes our engine GPL. Reading it to learn is fine. Don't paste GPL code into this repo
  until the fork base in `docs/decisions/0001-fork-base-and-licence.md` is decided (the
  licence part is settled: GPL acceptable, MIT preferred). Test tools that link a GPL
  engine (e.g. `harness/adapters/quackle/`) stay in their own directory with a GPL note.
- Word lists (NWL, CSW, etc.) are copyrighted. Never commit lexicon files or built
  GADDAG/KWG files. Keep them under `data/` (git-ignored).
- Closed engines (Elise, Maven): black-box testing is fine. Before decompiling or
  disassembling, check the licence/EULA and note it in the dossier.

## Long-running commands

Builds, full test suites, simulations, matches and training runs: run in the background
with a hard timeout (about twice the expected runtime). Report only the summary.

## Machine

Linux, 6 cores, 14 GB RAM, no NVIDIA GPU. Neural-network training beyond small
experiments will need external GPU compute (see the open decision in the research plan).
