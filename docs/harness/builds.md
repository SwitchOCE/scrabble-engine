# Engine builds and raw speed (plan step 2b)

Goal (owner): know which existing engine is strongest, and have working builds to test
against. This step builds Quackle, Macondo, MAGPIE and (added by the orchestrator)
wolges headless at the pinned SHAs with **CSW24** data, smoke-tests each, and measures
raw speed. No match harness here (that is step 2a, `docs/harness/reuse-check.md`).

Hardware for every number below: `Intel(R) Core(TM) i5-9500T CPU @ 2.20GHz` (6 cores,
1 thread per core, max 3.7 GHz), 14 GB RAM, Linux 7.0.0-42-generic. The machine was
otherwise idle except for an unrelated download; one benchmark ran at a time.

## Status

| Engine | SHA (PINS.tsv) | Build | CSW24 data | Smoke test |
| --- | --- | --- | --- | --- |
| Quackle | `35e11bb` | OK: `libquackle_test`, `quackletest`, `iotest`, `makegaddag` (no GUI) | `csw24.dawg` in tree; `csw24.gaddag` built by us; leaves `strategy/csw/superleaves` | OK |
| Macondo | `9c33baa` | OK: `bin/shell` | `CSW24.kwg`, `CSW24.klv2` (liwords); word map built by Macondo | OK |
| MAGPIE | `b781018` | OK: `bin/magpie` (clang-21 PGO release), `bin/libmagpie.so` (gcc, no PGO) | MAGPIE-DATA `data-20260925` + CSW24 word map built by us | OK |
| wolges | `be00002` | OK: `shell`, `auto`, `simmer`, `json`, `movegen-test`, `buildlex` | `CSW24.kwg`, `CSW24.klv2` (liwords) | OK |

### Speed in brief (details and caveats under Speed)

| Measure (CSW24, this machine) | Quackle | Macondo | MAGPIE | wolges |
| --- | --- | --- | --- | --- |
| Best static move, 5 fixed positions, µs per call (1 thread), range | 975–14,059 | 171–6,420 | not measurable (~70 ms per command) | 292–311 |
| Static self-play, games/s (1 thread) | 3.8 | 111 | 169 | 319 |
| Sim, 2-ply rollouts/s, 15 candidates, 1 thread | not drivable headless | 5,851–10,934 | 6,817–10,682 | (4-ply, own field) 4,664–6,665 |
| Same, 6 threads | – | 28,685–47,653 | 33,145–57,189 | (4-ply) 14,467–24,597 |
| Sim moves played/s, 1 thread | – | 17.6k–32.8k | 20.4k–32.0k | ≤23.3k–33.3k |

Clone HEADs were checked against `reference/PINS.tsv` by reading each clone's
`refs/heads/*` file (the worktree sandbox blocks `git` aimed at `reference/`).

## Where things live (nothing here is committed)

| What | Path |
| --- | --- |
| Quackle binaries | `reference/quackle/build-headless/{test/libquackle_test,test/quackletest,test/iotest,makegaddag/makegaddag}` |
| Quackle data overlay | `data/quackle/data/` (symlinks to the clone's `data/*` plus our `lexica/csw24.gaddag`); run from `data/quackle/run/` because the harness hard-codes `../data` (quackle@35e11bb `test/testharness.cpp:250`) |
| Macondo binary | `reference/macondo/bin/shell` |
| Macondo data | `data/macondo/` (set `MACONDO_DATA_PATH`) |
| MAGPIE binaries | `reference/magpie/bin/{magpie,magpie_convert,libmagpie.so}` |
| MAGPIE data | `data/magpie/data/`, `data/magpie/testdata/`; symlinked as `reference/magpie/data` and `reference/magpie/testdata` (both git-ignored by MAGPIE) |
| wolges binaries | `reference/wolges/target/release/{shell,auto,simmer,json,movegen-test,buildlex}` |
| wolges data | `data/wolges/CSW24.{kwg,klv2}` |
| Downloads + manifest | `data/downloads/`, `data/MANIFEST.tsv` |
| Build logs | `build/logs/*.log` (main checkout, git-ignored) |

Paths are relative to the main checkout `/home/alex/code/scrabble-engine`.

## Toolchains

go1.27.4 (`~/.local/go`, already installed), rustc/cargo 1.100.0 (`~/.cargo/bin`, not
on PATH by default), Ubuntu clang 21.1.8 + `llvm-profdata-21`, gcc 15.2.0, cmake 4.2.3,
Qt 6.10.2 (`qt6-base-dev`).

## Build commands

All run from the main checkout, in the background with a hard timeout.

```sh
# Quackle: configure from quacker/ (the only top-level CMake that pulls in test/),
# build only the headless targets. ~1 min.
cd reference/quackle
cmake -S quacker -B build-headless -DCMAKE_BUILD_TYPE=Release -DQT_VERSION=6
cmake --build build-headless -j6 --target quackletest libquackle_test iotest makegaddag

# Macondo. ~1 min (module download included).
cd reference/macondo && PATH=$HOME/.local/go/bin:$PATH make macondo_shell

# MAGPIE. `make release` trains a PGO profile; it needs the data and the CSW24
# word map first (see Data). Without PGO_CC/LLVM_PROFDATA it stops with
# "*** PGO needs llvm-profdata (llvm-profdata, llvm-profdata-20 .. -15 ...)":
# the Makefile does not look for -21. ~5 min.
cd reference/magpie
make magpie BUILD=no_pgo_release
bin/magpie convert dawg2text CSW24
bin/magpie convert text2wordmap CSW24 -threads 6
make release PGO_CC=clang-21 LLVM_PROFDATA=llvm-profdata-21
make libmagpie            # for harness/bench/magpie_api.py (gcc -O3, no PGO)

# wolges. The shell binary needs the `shell` feature. ~2 min.
cd reference/wolges && PATH=$HOME/.cargo/bin:$PATH \
  cargo build --release --features shell \
  --bin shell --bin auto --bin simmer --bin json --bin movegen-test --bin buildlex
```

No source in any clone was edited, and no branch was made.

## Data

`scripts/fetch-engine-data.sh` fetches everything below into `data/` and writes
`data/MANIFEST.tsv` (URL, size, sha256 for each download). The table lists the sha256 of
every data file each engine actually loads in the runs below (checked after the runs).

| Engine | File (under the engine's data dir) | sha256 | Source |
| --- | --- | --- | --- |
| Quackle | `lexica/csw24.dawg` | `8736cd4dfb88a664188940778239d3be6251853d3a962effbb636b1446eb8fed` | in tree, quackle@35e11bb `data/lexica/csw24.dawg` |
| Quackle | `lexica/csw24.gaddag` | `1c68e5896dbca258d55c81c46b830d7030cc6a90d0fc76939ac6aadde0054758` | built by us, see below |
| Quackle | `strategy/csw/superleaves` | `cf20c38578cfd6263d494e2748cf96b4028e3e9ff77812a5e4efc082c4ab3797` | in tree; `csw*` lexica fall back to `strategy/csw/` (quackle@35e11bb `datamanager.cpp:150-151`) |
| Quackle | `alphabets/english.quackle_alphabet` | `83997ef8c837cbdab42f0065999ccf274f0bd7b9c0195dffd76d05513c410c6f` | in tree |
| Macondo | `lexica/gaddag/CSW24.kwg` | `62ca7a84f07429a9976f77a4f74b94911aca5d49cce050dce72dd0e032c0566f` | liwords `liwords-ui/public/wasm/2024/CSW24.kwg` (macondo@9c33baa `lexicon/download.go:20`) |
| Macondo | `lexica/gaddag/CSW24.klv2` | `b0ef5f6637cca0cd8e0962d6fb7d35b2d22f9bf648015f48fa8f80e24a60610b` | same place |
| Macondo | `lexica/gaddag/super-CSW24.klv2` | `c69835cd98e08aac15c4ea7b773c1694e9622566c378ec97d621a8afd3cd613a` | same place (loaded, unused on a 15x15 board) |
| Macondo | `lexica/CSW24.wmp` | `183096e751f5464b43205658c7bcd092575fda1ea13e605ce56198b338292f91` | built by Macondo on first use ("wmp-policy build_if_missing:true"); byte-identical to MAGPIE's |
| Macondo | `strategy/default/winpct.csv` | `18c79601f57f10b4e0a1b49ab59ce7946ad462751636d148f1c850183f491e42` | macondo@9c33baa `data/strategy/default/` |
| Macondo | `strategy/default/preendgame.json` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | same |
| Macondo | `letterdistributions/english` | `6ee0fae2f06b3d9a67a97265384d82b058f6ba007aaf27b53389775892e27929` | macondo@9c33baa `data/letterdistributions/` |
| MAGPIE | `lexica/CSW24.kwg` | `62ca7a84f07429a9976f77a4f74b94911aca5d49cce050dce72dd0e032c0566f` | MAGPIE-DATA `data-20260925` |
| MAGPIE | `lexica/CSW24.klv2` | `1937df3fd5dc1882e6c283bdc0c8870ecf25b38645cb214fd4802d302ad34dea` | same |
| MAGPIE | `lexica/CSW24.wmp` | `183096e751f5464b43205658c7bcd092575fda1ea13e605ce56198b338292f91` | built by us (`text2wordmap`) |
| MAGPIE | `lexica/CSW24.wit` | `bdbf3d1dab93715ca0f63166cfbb60584aed808cdebd9f376b2d47763995c1c4` | built by `make release` (`kwg2witifneeded`) |
| MAGPIE | `lexica/CSW24.rit` | `6dac004c198cef6a6429614c042e2a0b7dc3b60efb2a263aeafadef5f8e0b3cb` | built by `make release` (`klvwmp2rit`) |
| MAGPIE | `strategy/CSW24.pat` | `222d37ae5057fa0a091992c1a0a1a9f46d2086a5d772369cc316529ed6630e03` | MAGPIE-DATA |
| MAGPIE | `strategy/CSW24_pegadjust.csv` | `114f1f0a5978a9afcc4db64ced77ebdb99c88082f3e77b9069f747f1fd7b2c30` | MAGPIE-DATA |
| MAGPIE | `strategy/winpct_english.csv` | `34c072d285e64973cfa0bd044f4d70f128677578c30993a35d85a5c607bc0417` | MAGPIE-DATA |
| MAGPIE | `letterdistributions/english.csv` | `e698ce0b93e025daccd3390107a914d74581c4603de38df65131768b1c6f9102` | MAGPIE-DATA |
| wolges | `CSW24.kwg` | `62ca7a84…0566f` (same as Macondo) | copied from liwords |
| wolges | `CSW24.klv2` | `b0ef5f66…0610b` (same as Macondo) | copied from liwords |

MAGPIE-DATA tarball: `https://github.com/jvc56/MAGPIE-DATA/raw/main/versioned-tarballs/data-20260925.tgz.{aa..ae}`
(versions read from magpie@b781018 `download_data.sh`), reassembled sha256
`625e253bbbbbc7488aea2a8c581b67f7698b0a21c140dac513ae1c0e0abde0b4` (192,232,563 bytes);
`testdata-20260101.tgz` sha256 `fde407febee789df23711bd203272fc4e23b3daf715ff13f376b1150a4cdf045`.
Per-chunk sums are in `data/MANIFEST.tsv`. The orchestrator reports that this tarball
was rebuilt in place on 2 Nov (jvc56/MAGPIE#982) and CSW24.klv2 changed from
`b0ef5f66…` to `1937df3f…`, so a version name alone does not pin MAGPIE's data.

liwords files: the pinned liwords clone (`ceccdb6`) and the live `refs/heads/master` URL
Macondo downloads from served identical bytes on 2026-11-16 (both recorded in the
manifest). Macondo itself downloaded them into `data/macondo/lexica/gaddag/` on its first
run, because `lexicon/download.go:53-56` looks there and the copy step had used a
`default_english/` subfolder; the script now copies to the right place.

**Same word list everywhere.** The four engines read the same CSW24 words:
MAGPIE's and liwords' `CSW24.kwg` are byte-identical, and Quackle's `csw24.dawg`
dumps to 280,887 words whose list is byte-identical to MAGPIE's `dawg2text CSW24`
(sha256 `4200a40a…63893` for both).

**Leaves differ by engine (each engine's own CSW24 leaves, as shipped):**

- Macondo and wolges: liwords `CSW24.klv2` (`b0ef5f66…`), which is the *old* MAGPIE-DATA CSW24 leaves.
- MAGPIE: the rebuilt `CSW24.klv2` (`1937df3f…`), plus PAT weights `CSW24.pat` (on by default since jvc56/MAGPIE#987, per the orchestrator) and `CSW24_pegadjust.csv`.
- Quackle: `strategy/csw/superleaves`, a different format. It is the only Collins leave file Quackle ships, so we use it; **it is not CSW24-specific (flagged)**. History: quackle `1462523` (2014-11-30, "Fix Collins superleaves") and `e29118f` (2019-07-21), whose message says "There's only two distinct superleaves files … the Collins superleaves is in strategy/csw" (`reference/history/quackle/commits-full.txt:1146-1158`).

  Inference: the file predates CSW15, CSW19 and CSW24 and was fitted on an older Collins edition (which one is UNVERIFIED). Quackle plays CSW24 words with older Collins leaves.

**Quackle gaddag.** Quackle ships no gaddag; without one it warns "Performance without
gaddag won't be quite so awesome" and generates from the dawg. Built with Quackle's own
tools:

```sh
cd data/quackle/run
reference/quackle/build-headless/test/libquackle_test --mode=worddump --lexicon=csw24 \
  | sed -n 's/^wordDump: //p' > csw24-words.raw        # 280,887 words
reference/quackle/build-headless/makegaddag/makegaddag --input=csw24-words.raw \
  --output=../data/lexica/csw24.gaddag                 # "Wrote 280887 words over 6692047 nodes", 3 s
```

**Side effect outside the repo.** Macondo's first run wrote
`~/.config/macondo/config.yaml` (data path, `default-lexicon: CSW24`). Later runs read it.

## Smoke tests

Positions: `harness/bench/positions/pos-{04,07,10,14,16}.gcg`, cut by
`harness/bench/make_positions.py` from one static wolges self-play game
(`game-20261116.gcg`, `shell`: `new 20261116`, then `bot` until the game ended). Each
file is the first NN moves plus a `#rackK` line for the side to move. GCG is the only
format all four read: Quackle and wolges have no CGP reader.

All four loaded CSW24, generated moves and agreed on the top moves of `pos-14`
(rack `?ALNORU`): `O8 (C)ONsULAR`, `O8 (C)OURLANs`, `O8 (C)RUNOdAL` at 80 points. Each
also played a static move:

- Quackle: `libquackle_test --mode=positions --lexicon=csw24 --computer="Speedy Player" --position=pos-14.gcg`; `--mode=selfplay` plays full games (log: `GAME OVER Speedy Player A : 482 Speedy Player B : 387`).
- Macondo: `set lexicon CSW24`, `load pos-14.gcg`, `last`, `gen 10`; autoplay games with `HASTY_BOT`.
- MAGPIE: `set -lex CSW24 …`, `load pos-14.gcg`, `goto end`, `gen`, `shmoves 10`, `tcommit` (played `O8 (C)ONsULAR`).
- wolges: `lexicon CSW24.kwg`, `leaves CSW24.klv2`, `gcg load pos-14.gcg`, `gen 3`; `bot` plays the best static move.

Static equities differ by engine (leaves, and MAGPIE's PAT term: it ranks `O8 (C)ONsULAR`
at 76.97 for 80 points with an empty leave).

**MAGPIE overwrites the GCG it loads.** With autosave on (the default), `tcommit` wrote
the move into `pos-14.gcg`. All MAGPIE commands here now pass `-autosavegcg false`, and
the position files are read-only.

## Speed

Scripts: `harness/bench/movegen.sh`, `harness/bench/selfplay.sh`, `harness/bench/sims.sh`,
`harness/bench/magpie_api.py`. Raw output: `docs/harness/data/`.

### 1. Best static move per position, single thread

Command: `harness/bench/movegen.sh 1000`, three passes. For each position: load once,
then ask for the best static move 1000 times through the engine's own command loop;
time = (wall time of that run − wall time of a run with 0 repetitions) / 1000. Median
of 3 passes, µs per call (raw: `data/movegen-console.tsv`).

| Position (rack) | Quackle | Macondo | wolges | MAGPIE |
| --- | --- | --- | --- | --- |
| pos-04 (HERDOOO) | 975 | 216 | 292 | not measured |
| pos-07 (AELSTIV) | 2473 | 938 | 311 | not measured |
| pos-10 (FCSMMIO) | 1930 | 577 | 307 | not measured |
| pos-14 (?ALNORU, a blank) | 14059 | 6420 | 304 | not measured |
| pos-16 (RWKIGIQ) | 1918 | 171 | 309 | not measured |

What each call does:

- **Quackle:** `--mode=positions` with the position listed 1001 times, so each repetition also re-reads the GCG and prints the board and top 10 (to `/dev/null`). Speedy Player generates every move and ranks it by static equity. An upper bound on its movegen time.
- **Macondo:** `gen 1`: all moves, ranked by equity (leaves), top 1 printed.
- **wolges:** `gen 1`: `gen_moves_unfiltered` with `max_gen: 1` (wolges@be00002 `src/shell_session.rs:1923-1945`). Asking for one move lets wolges cut generation short, so this is "find the best move", not "list every move". The flat ~300 µs, blank or not, suggests the shell's own per-command cost dominates (`help` costs ~50 µs per call); wolges' true movegen time is at most this.
- **MAGPIE:** every console or C-API command costs ~70 ms of CPU, even `shmoves 1` (41 `generate` calls: 3.0 s user CPU; `generate` and `shmoves 1` both ~73 ms via the C API, with a GCG or a CGP position). That swamps movegen, so no per-position MAGPIE number is reported. Its self-play speed is below.

Not directly comparable: the engines differ in what "best static move" includes (MAGPIE
adds PAT; Quackle's harness reloads the position).

### 2. Static self-play, single thread

Command: `harness/bench/selfplay.sh 500` (Quackle: 100 games). Full CSW24 games of the
engine's static player against itself, wall time including start-up (raw:
`data/selfplay-static.txt`, `data/selfplay-static-quackle.txt`).

| Engine | Player | Games | Wall s | Games/s |
| --- | --- | --- | --- | --- |
| Quackle | Speedy Player, `--seed=1` | 100 | 26.04 | 3.8 (2272 moves: 87 moves/s) |
| Macondo | `HASTY_BOT` ×2, `-threads 1 -seed 1` | 500 | 4.49 | 111 |
| MAGPIE | `-s1/-s2 equity -r1/-r2 best -numplays 1 -threads 1 -seed 1`; word map, WIT, RIT and PAT on (defaults) | 500 | 2.95 | 169 |
| wolges | `auto --games 500` (its own timer: 1.13 s) | 500 | 1.57 | 319 (442 by its own timer) |

Facts:

- Quackle's "Speedy Player" is the `EndgamePlayer` class (quackle@35e11bb `endgameplayer.cpp:29`).
- Per move, Quackle is ~10× slower in self-play than in table 1 (11.5 ms per move against 1–2 ms per position, outside the blank position).
- Quackle's `--quiet` skips the games: `haveComputerPlay()` is inside `if (!m_quiet)` (quackle@35e11bb `test/testharness.cpp:771-798`), so 500 "games" took 0.4 s (that run is the Quackle block in `data/selfplay-static.txt`; the real one is `data/selfplay-static-quackle.txt`). The script now reads the move log instead.
- The games are not the same games across engines.

Inference: `EndgamePlayer` probably searches the endgame instead of playing it
statically, which would explain the slower moves (UNVERIFIED: its endgame code was not
read). The other three may also handle endgames differently (UNVERIFIED).

### 3. Sims

Command: `harness/bench/sims.sh 10 1 6`, then `harness/bench/summarize_sims.py
docs/harness/data/sims.txt` (raw: `data/sims.txt`). Each run is one position, one
thread count, one engine, about 10 s.

Settings:

- **Macondo and MAGPIE, same settings:** the top 15 static candidates, 2 plies after the candidate, no inference, no early stop, no pruning, fixed 10 s.
  - Macondo: `gen 15`, `sim -plies 2 -threads T`, `sim stop` after 10 s (no `-stop`, so `StopNone`, macondo@9c33baa `shell/sim.go:31`). Inference is off unless asked for (`sim.go:49`).
  - MAGPIE: `generate -numplays 15`, `simulate -plies 2 -numplays 15 -tlim 10 -iterations 2000000000 -sinfer false -scensus false -sr rr -threshold none -threads T` through the C API. `-sr rr` gives every candidate the same number of rollouts; `-threshold none` turns off the statistical stop. PAT, word map, WIT and RIT were left at their defaults (on). Census is on by default; we turned it off.
- **wolges, its own fixed settings:** the shell's `sim N` cannot be told how many candidates or plies to use. It sims its own field (110 candidates listed here), 4 plies (`move_picker::DEFAULT_NUM_SIM_PLIES`, wolges@be00002 `src/move_picker.rs:22`) and drops candidates as they fall behind. Threads are all CPUs the process may use (`src/parallelism.rs:10-16`), so we limit them with `taskset -c 0` / `-c 0-5`. N = 500 (1 thread) or 3000 (6 threads); the 6-thread runs lasted only 1.4–2.2 s.

What one "iteration" means:

| Engine | One iteration | Leaf evaluation | Node |
| --- | --- | --- | --- |
| Macondo | one opponent rack draw, then a rollout of **every** candidate (macondo@9c33baa `montecarlo/montecarlo.go:1034-1141`) | spread + leave value of the tiles left (`leftover`), win% from `winpct.csv` | one move played: the candidate or a ply move (`montecarlo.go:1113, 1141`) |
| MAGPIE | `Iters` counts rollouts of **one** candidate, summed over candidates ("maximum total iterations across all simulated plays", `help simulate`) | spread + leftover leave values of the last two plies (magpie@b781018 `src/impl/random_variable.c:616-672`); win% table | one move played (`sim_results_increment_node_count`, same file) |
| wolges | one rollout of every candidate still in (the shell's own counter); we report the sum of each candidate's `rollouts` instead | UNVERIFIED (not read) | not counted by wolges; we use rollouts × 5, an upper bound |

So the comparable columns are **rollouts/s** (one candidate played to the horizon) for
Macondo against MAGPIE, and **nodes/s** (moves played inside the sim, roughly one static
movegen each) for all three. wolges rollouts are 4-ply, so its rollouts/s is not
comparable with the 2-ply engines.

| Position | Threads | Macondo rollouts/s | MAGPIE rollouts/s | wolges rollouts/s | Macondo nodes/s | MAGPIE nodes/s | wolges nodes/s (≤) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pos-04 | 1 | 10,934 | 10,682 | 6,665 | 32,802 | 32,044 | 33,324 |
| pos-04 | 6 | 47,653 | 57,189 | 24,597 | 142,959 | 171,529 | 122,985 |
| pos-07 | 1 | 8,887 | 9,509 | 5,961 | 26,661 | 28,527 | 29,807 |
| pos-07 | 6 | 43,503 | 46,156 | 21,961 | 130,509 | 138,581 | 109,804 |
| pos-10 | 1 | 5,851 | 6,817 | 4,931 | 17,554 | 20,448 | 24,653 |
| pos-10 | 6 | 28,685 | 33,145 | 14,467 | 86,056 | 99,446 | 72,333 |
| pos-14 | 1 | 9,356 | 7,955 | 4,725 | 28,068 | 23,864 | 23,625 |
| pos-14 | 6 | 41,844 | 38,748 | 20,583 | 125,533 | 116,265 | 102,916 |
| pos-16 | 1 | 6,973 | 7,837 | 4,664 | 20,919 | 23,509 | 23,322 |
| pos-16 | 6 | 34,363 | 38,508 | 20,658 | 103,088 | 115,554 | 103,289 |

Speed-up from 1 to 6 threads (rollouts/s): Macondo 4.4–4.9×, MAGPIE 4.9–5.4×,
wolges 2.9–4.4× (its 6-thread runs lasted only 1.4–2.2 s, so its figure includes more
start-up per rollout).

Facts: at one thread, Macondo and MAGPIE do about the same number of 2-ply rollouts
per second at these settings (within 18% of each other; Macondo is ahead on two positions, MAGPIE on three). At six threads MAGPIE
is ahead on four of five positions (by 6–20%). wolges plays about as many moves per
second inside its sim as the other two at one thread, and fewer at six.

Inference: raw sim speed is similar enough that strength will be decided by what each
engine does with its rollouts (candidate choice, pruning, inference, leaves, PAT,
endgame handling), not by speed alone.

## Open questions

- **MAGPIE's ~70 ms per command.** Every console or C-API command costs ~70 ms of CPU (14 ms of it system time), with a GCG or CGP position, sync mode or not. Why? Until it is known, a per-move MAGPIE adapter pays 70 ms per command, and per-position movegen cannot be timed through the API.
- **Quackle superleaves:** which Collins edition was `strategy/csw/superleaves` fitted on (it dates from 2014 or earlier)? Would fresh CSW24 superleaves (Quackle ships `encodeleaves`) change its strength?
- **Quackle sims cannot be timed headless.** `libquackle_test` has no sim-speed mode (`--mode=sim` only runs self-checks, quackle@35e11bb `test/testharness.cpp:1263-1296`) and prints no iteration count. Measuring it needs a small patch (a branch in the clone) or the SWIG bindings.
- **Macondo's per-move time limit:** built-in sim bots have a hard-coded 30 s per turn (from step 2a); table 3 does not depend on it.
- **wolges sim settings:** the shell's `sim N` has a fixed field of ~110 candidates and 4 plies; a same-settings comparison with Macondo and MAGPIE (15 candidates, 2 plies) needs wolges' `simmer` options or a patch.
- **Leaves:** a controlled strength run should also give Macondo, MAGPIE and wolges the same `.klv2` to separate search from leaves.
- **Macondo writes `~/.config/macondo/config.yaml`.** Harness runs should set the config path or environment explicitly so results don't depend on that file.
