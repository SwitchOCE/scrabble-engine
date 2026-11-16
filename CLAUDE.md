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

## Licences and data

- Quackle, Macondo and MAGPIE are GPL-3.0. wolges is MIT. Copying code from a GPL engine
  makes our engine GPL. Reading it to learn is fine. Don't paste GPL code into this repo
  until `docs/decisions/0001-fork-base-and-licence.md` is decided.
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
