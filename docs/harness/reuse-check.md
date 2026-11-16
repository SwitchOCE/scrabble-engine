# Harness reuse check (plan step 2a)

Goal (owner): "finding working builds for those engines that we can test against".
Step 2a asks what autoplay / bot-vs-bot modes Quackle, Macondo and MAGPIE already have,
what formats they read and write, and whether any can already play a *different* engine.
wolges was added to the scope by the orchestrator.

Pins (from `reference/PINS.tsv`; the clone HEADs were not re-checked with git, because the
worktree sandbox blocks git commands aimed at `reference/`):

| Engine | Short SHA | Licence |
| --- | --- | --- |
| Macondo | `9c33baa` | GPL-3.0 |
| MAGPIE | `b781018` | GPL-3.0 |
| Quackle | `35e11bb` | GPL-3.0 |
| wolges | `be00002` | MIT |

Citations below are `engine@sha path:line`. Nothing was built: this machine has no Go or
Rust toolchain (`go`, `cargo` not on PATH; `gcc`, `clang`, `cmake`, Qt6 are present).

## Verdict on the plan review's claims

All four claims hold.

- The external-engine player exists. It runs `<binary> <extra args> --gcg=<file> --lexicon=<name> --rack=<tiles>` and reads one JSON line back (macondo@9c33baa `ai/externalengine/player.go:62-155`, `ai/externalengine/config.go:3-11`).
- It is wired in as `CUSTOM_BOT` at macondo@9c33baa `automatic/config.go:79-84`, and the runner uses it at `automatic/game_runner.go:209-219`.
- `SetPairedBagMode` is at macondo@9c33baa `game/pairedbag.go:40`.
- Paired statistics are in macondo@9c33baa `stats/paired.go:48` (`SignFlipPValue`) and `:114` (`PairedTTestPValue`). They are used by `automatic/logfile_analysis.go:146-211` (`PairedResult`).

The feature came in through domino14/macondo#504 (merged 2026-10-19). Its description
reports smoke matches of SIMMING_BOT against Quackle Speedy Player (48 games) and Twenty
Second Championship Player (16 games), driven by a tool called `quackle-evaluator` through
wrapper scripts. **That tool is not in the Quackle repo at `35e11bb`** (grep finds no
match), and the PR does not link to its source. Its location is UNVERIFIED.

## 1. Macondo's external-engine contract

### Facts

**Invocation.** Each turn, `BestPlay` writes the game so far to a temp file
(`os.CreateTemp("", "macondo-ext-*.gcg")`) and runs the binary once, with `ExtraArgs`
first and then `--gcg=`, `--lexicon=`, `--rack=` (macondo@9c33baa
`ai/externalengine/player.go:69-94`). The process is new every turn. `SetLastMoves` and
`AddLastMove` do nothing, because "the engine is stateless and reads full GCG each turn"
(`player.go:50-54`). `extargs` is split on spaces, so a value that contains a space
needs a wrapper script (`shell/helptext/autoplay.txt:173-182`, `shell/shell.go:1788-1791`).

**What the engine gets:**

| Input | Passed? | Where |
| --- | --- | --- |
| Full game history as GCG | Yes, the whole game every turn. Written with `addlHeaderInfo=false`, so there is no `#lexicon`, `#title` or `#id` line, only `#character-encoding UTF-8`, two `#player` lines and the events | `player.go:69`; `gcgio/gcg.go:735-774, 845-848, 858-879` |
| Rack on turn | `--rack=` (`?` = blank, from `RackLettersFor`) | `player.go:63-66, 92` |
| Lexicon | Its name only, e.g. `--lexicon=CSW24`. The adapter must map the name to its own files | `player.go:91` |
| Challenge rule | **Not passed.** Autoplay never sets it, so it is the proto zero value `VOID`, and `ValidateMove` rejects plays that contain invalid words | `api/proto/macondo/macondo.proto:52-58`; `game/game.go:522-529` |
| Bag / unseen tiles | Not passed explicitly. The engine works them out from the board, its rack and the tile distribution. English is assumed: `#tile-distribution` is written only when `addlHeaderInfo` is true | `gcg.go:756-771` |
| Opponent's known tiles | Not passed as such. **But every event line carries the mover's full rack before the move** (`>p2: AEINRST 8D RAT +5 5`), so the GCG shows the opponent's earlier racks and, by subtracting what they played, the tiles they kept | `gcg.go:776-814` |
| Time remaining / per-move budget | **Not passed.** The context has no deadline for `CUSTOM_BOT` ("The external engine process manages its own time") | `automatic/game_runner.go:369-372`; `autoplay.txt:173-174` |

**Output.** Macondo reads the last non-empty line of stdout as JSON (`player.go:121-135`).
Anything printed before that line is ignored. The schema is
(`ai/externalengine/response.go:5-15`):

```json
{"player":"…","rack":"…","cumulative_score":0,
 "action":"place|exchange|pass","position":"8D","tiles":"CRAAlED",
 "score":0,"equity":0.0,"win":0.0}
```

Only `action`, `position` and `tiles` are used (`player.go:137-155`).

- **Place:** `{"action":"place","position":"8D","tiles":"CRAAlED"}`.
  - Position uses GCG coordinates: row then column for across (`8D`), column then row for down (`D8`) (`move/move.go:485-510`).
  - Uppercase letters are tiles and lowercase letters are blanks (`player.go:149-151`).
  - Played-through letters can be written out in full: `modifyForPlaythrough` checks that each one matches the board and turns it into a played-through marker (`game/turn.go:94-124`). Writing `.` for a played-through square probably works too (Macondo's own wolges bridge writes `ASCIIPlayedThrough`, `bot/wolges_interface.go:237`), but that is decided in the `word-golib` dependency, which is not in this checkout. UNVERIFIED. Adapters should write full letters.
- **Exchange:** `{"action":"exchange","tiles":"QV"}`. The tiles are upper-cased before parsing (`player.go:142-143`).
- **Pass:** `{"action":"pass"}`.
- Anything else is rejected, e.g. `"resign"` gives "unknown action" (`player_test.go:90`).

Macondo scores the move itself and ignores the engine's `score` (`player_test.go:70`).

**Failure handling.** A non-zero exit, JSON it cannot parse, an illegal move or an invalid
word returns an error. For `CUSTOM_BOT` that error stops the run. Only built-in bots fall
back to a static move (`game_runner.go:385-396`).

**Macondo still needs its own data for the external seat.** `NewFromGame` loads
Macondo's leave file for the lexicon (`player.go:35`, `equity/loaders.go:18`
`leaves.klv2`). The seat also keeps a static move generator, which random openings use
(`game_runner.go:402-410`).

### Running autoplay with CUSTOM_BOT

The shell runs one command passed on the command line and then exits
(macondo@9c33baa `cmd/shell/main.go:109-119`). Use `-block` so it waits for the games.

```sh
bin/shell autoplay -lexicon CSW24 \
  -botcode1 SIMMING_BOT -simthreads1 1 \
  -botcode2 CUSTOM_BOT -extbinary2 /abs/path/quackle-adapter.sh \
  -gamepairs -seed 42 -numgames 500 -threads 5 \
  -outputdir runs/quackle-vs-macondo -block
```

- The same fields can go in a protojson config file (`autoplay cfg.json`): `externalEngineBinary` and `externalEngineArgs` per player (`autoplay.txt:107-109, 155-158`; proto `macondo.proto:513-518`).
- Both seats can be `CUSTOM_BOT`, because each player's config is read separately (`automatic/config.go:50-84`). So Macondo can referee Quackle against MAGPIE without playing itself.
- `CUSTOM_BOT` forces `addToHistory`, which is what makes the GCG available (`automatic/automatic_utils.go:452-454`).

**Paired bags.** `-gamepairs` plays each seed twice with the seats swapped
(`automatic_utils.go:104-130`). The bag is fixed-order, and each seat draws from its own
end (`game/pairedbag.go:8-34`). Pairing only takes effect with a non-zero seed
(`game_runner.go:306-308`). If no seed is given, one is generated and logged
(`automatic_utils.go:325-335`).

The pairs-mode guard refuses a built-in simming bot unless `simthreads` is 1
(`automatic_utils.go:363-374`). In paired mode the runner also drops the 30-second
per-turn deadline for built-in bots, so a Macondo sim stops on its own `Stop99`
condition (`game_runner.go:373-380`; `ai/bot/elite.go:312`).

**Where results land** (`autoplay.txt:13-19`; `automatic_utils.go:258-273, 425-436`). All
three files go in `outputDir`:

- `{experimentId}.txt`: the per-turn log.
- `games-{experimentId}.txt`: one CSV row per game, `gameID,p1_score,p2_score,…,first`, plus `pair,divergent` in pairs mode (`automatic_utils.go:549-552`, `:139-150`).
- `{experimentId}.config.json`: the resolved config.

No per-game GCG is written. The engine's stdout and its decoded move go to Macondo's zerolog
on stderr (`player.go:99-115`). `autoanalyze games-<id>.txt` in the shell runs
`AnalyzeLogFile`, which gives pair-level margin and win p-values (sign-flip and paired t)
(`shell/api.go:1833-1914`; `automatic/logfile_analysis.go:57-211`). There is no SPRT
(grep for `sprt` finds nothing in Macondo or MAGPIE).

### Inference

The contract is small and fits a one-shot CLI. Its weak points for a fair match:

- **No clock.** Every engine has to be given a fixed per-move budget through its own flags.
- **The GCG leaks the opponent's earlier racks.** Quackle and MAGPIE do not use that leak by default (see below), but our own engine could use it without anyone noticing.
- **A new process every turn.** Each engine reloads its lexicon and leaves every turn. That adds wall-clock time but not think time, as long as the engine's timer starts after loading.

## 2. MAGPIE

### Facts

- **CLI.** The program has a `magpie>` prompt. A command passed on the command line runs and then the program exits ("script mode"), except `set` and `cgp` (magpie@b781018 `README.md:892-900`). `-mode sync` makes the prompt finish each command before reading the next, which is meant for driving MAGPIE from another program (`README.md:902-915`).
- **C API.** There is a string-in, string-out C API (`make libmagpie`; `src/impl/cmd_api.h:73-142`). Its output is "machine readable by default" (`README.md:934`).
- **Commands** (`src/impl/config.c:16690-16800`):
  - `load` reads a local GCG, a URL, a cross-tables game or a woogles game. It uses `#lexicon` if the file has one; otherwise `-lex` must be set (`README.md:350-353`).
  - `cgp` loads a CGP.
  - `rack` sets the rack of the player on turn.
  - `generate` lists moves by static equity.
  - `gsimulate` / `rgsimulate` generate and then simulate.
  - `peg` solves the pre-endgame and `endgame` solves the endgame.
  - `tcommit` commits the top move.
  - `shmoves` prints the move list.
  - There is no `bestmove` / PlayChooser command for a single position.
- **Sim limits.** `-plies`, `-tlim` seconds (default 60), `-iterations`, `-scondition` and `-threads` (`README.md:445-452`; `src/impl/help_table.c` `sim_rows`). `-sinfer true` (the default) infers the opponent's leave from their last play.
- **Opponent rack handling.** If no rack is given, `simulate` sims against "the opponent's currently known rack" (`config.c:4268-4274`). When a GCG is replayed, the off-turn rack is filled only from tiles exposed by phonies, or from all unseen tiles once the bag is empty (`src/impl/gameplay.c:1287-1297`). So the rack fields in Macondo's GCG do not leak into MAGPIE's sim.
- **Move notation.** MAGPIE prints moves as `8D JE(E)P`, with played-through letters in parentheses, blanks lowercase, `(exch QV)` for an exchange and `pass` for a pass (`src/str/move_string.c:58-120`).
- **Autoplay** is self-play only. `autoplay games N -gp true -seed S` gives game pairs (`README.md:645-660`). `-pc1` / `-pc2` give each side a PlayChooser clock (total ms per game). PlayChooser then picks static, sim, pre-endgame or endgame play from the position (`README.md:662-720`; `config.c:5485-5493`).
  - `play_chooser_choose_move` exists as a C function that takes a `fixed_seconds_per_move` and passes on only tiles "known … via … phonies" (`src/impl/play_chooser.h:54-77, 209-214`).
  - MAGPIE cannot drive another engine: the only `popen` is in `get_gcg.c`, which downloads games.
- **Data.** Data comes from a ~195 MB download (`download_data.sh`; `README.md:227-240`). Nothing is downloaded in the clone yet (`data/` is absent).

**Can MAGPIE take a position and rack and return one move headlessly?** Yes, through
either sync mode on stdin or the C API, for example:

```
set -lex CSW24 -savesettings false -threads 1
load /tmp/x.gcg
rack ?AACDER
gsimulate -tlim 5
shmoves 1
```

Static play is `generate` then `shmoves 1`. With the bag empty use `endgame`; with 1–4
tiles in the bag use `peg`. Whether `load` leaves the game at its last event or at the
start is not checked; an adapter should send `goto end` to be safe.

### Inference

A script adapter can only reach MAGPIE's console commands, so it has to repeat
PlayChooser's phase choice itself (sim, pre-endgame or endgame). A C adapter calling
`play_chooser_choose_move` with `fixed_seconds_per_move` gets exactly how MAGPIE plays in
its own timed autoplay. That is the fairer comparison.

## 3. Quackle

### Facts

- **Headless harness.** `test/testharness.cpp` builds `quackletest` (`test/CMakeLists.txt:35`).
  - It has `--mode=positions|report|selfplay|…`, `--position=game.gcg` (can be repeated), `--computer=`, `--computer2=`, `--lexicon=`, `--seed=`, `--repetitions=` and `--threads=` (quackle@35e11bb `test/testharness.cpp:105-134, 136-237`).
  - `positions` mode loads each GCG, takes its current position and prints the top 10 moves as text (`:282-292, 622-647`).
  - `selfplay` plays a computer against `--computer2` (`:714-745`).
  - The data directory is hard-coded to `../data` (`:250`).
  - It cannot set the rack on turn. The GCG reader's `#rack` pragma is ignored until a move has been read (`quackleio/gcgio.cpp:113-129`), so it cannot give the opening rack.
  - Its output is not JSON.
- **Bindings.** There are SWIG bindings (Python 2/3, Ruby, Lua, Go, PHP) over `game.h`, `computerplayer.h`, `sim.h` and `quackleio/gcgio.h` (`bindings/quackle.i:45-115`). `bindings/python3/test1_position.py:44-78` does exactly what we need: load a GCG, `setPosition`, `moves(10)`. But `bindings/Makefile` links `../lib/release/libquackle.a` and Qt5 by pkg-config, which does not match the current CMake/Qt6 build. Whether the bindings still build is UNVERIFIED. `swig` is not installed.
- **Players** (`computerplayercollection.cpp:45-49`):
  - "Speedy Player" (`EndgamePlayer`, `endgameplayer.cpp:29`) plays static moves until the endgame.
  - "Championship Player": `Resolvent`, `secondsPerTurn = 66` (`resolvent.cpp:91-96`).
  - "Twenty Second Championship Player" (20 s, `:109-114`).
  - "Five Minute Championship Player" (`:100-105`).
  - `Resolvent` hands off to `EndgamePlayer` when the bag is empty, `Preendgame` when the bag is low, and `SmartBogowin` otherwise (`resolvent.cpp:42-74`).
  - `SmartBogowin` sims 2 plies with `minIterations = 2·secondsPerTurn` and `maxIterations = 5·secondsPerTurn`, and stops when `secondsPerTurn` is exceeded (`bogowinplayer.cpp:38-44, 138-215`; `bogowinplayer.h:67-80`).
  - The time budget is `ComputerParameters.secondsPerTurn`, set with `setParameters`. Threads are set with `setThreadCount` (`computerplayer.h:31-38, 79, 134-152`).
- **Opponent racks in the sim** are drawn from the unseen bag, starting from `m_partialOppoRack`, which is only set when a caller sets it (`sim.cpp:785-811`). So the rack fields in Macondo's GCG do not leak.
- **Lexicon.** `data/lexica/csw24.dawg` ships with Quackle. No `.gaddag` ships; it is built with `makegaddag`. CSW strategy falls back to `data/strategy/csw/superleaves` (`datamanager.cpp:150-151`).
- **GCG compatibility.** Quackle's GCG reader takes `#player`, `#character-encoding`, `#note` and move lines. It ignores `#lexicon` (the lexicon is set on `DataManager`), and Macondo does not write one anyway (`quackleio/gcgio.cpp:76-140`). After reading, `setCurrentPlayerRack` sets the rack on turn (`game.h:330`, used at `gcgio.cpp:279`).

**Smallest adapter.** A ~150–250-line C++ program that:

- links `libquackle` and `libquackleio` (Qt6 Core);
- parses `--gcg --lexicon --rack` plus `--player=… --seconds=N --threads=T --datadir=…`;
- reads the GCG with `GCGIO`, then calls `currentPosition().setCurrentPlayerRack(rack)`;
- picks the computer player by name, sets `secondsPerTurn`, then calls `setPosition` and `move()`;
- prints the JSON line, with `positionString()` and `prettyTiles()` written out in full letters, lowercase for blanks.

This is presumably what `quackle-evaluator` is (UNVERIFIED). Building it means building
`libquackleio`, which needs Qt.

## 4. wolges (added scope)

### Facts

The binaries are `auto`, `shell`, `json`, `simmer`, `endgame` and others
(wolges@be00002 `Cargo.toml:45-80`).

- **`json`** generates moves for a built-in board/rack question. It does not read a GCG (`src/main_json.rs:11-25`).
- **`auto`** is self-play only (`src/main_auto.rs`).
- **`shell`** is a command shell built on rustyline (`src/main_shell.rs:15-40`). Its commands include:
  - `lexicon FILE` (kwg) and `leaves FILE` (klv2);
  - `rules NAME` and `challenges RULE`;
  - `gcg load FILE`, `rack TILES` and `source FILE`;
  - `bot`, which plays the best move by static equity;
  - `bot sim MS`, which plays the best move of an MS-millisecond sim, or of a solved endgame when the bag is empty;
  - `infer mover|public`.

  These are listed at `src/shell_session.rs:272-420`.
- **How `gcg load` sets racks.** It replays the file's moves and then sets "the racks it gives as they stand" (`shell_session.rs:2437-2443`). It is not checked whether that treats the opponent's kept tiles from Macondo's rack fields as known.

So wolges can be driven headlessly, either by piping `lexicon …`, `leaves …`,
`gcg load …`, `rack …`, `bot sim 5000`, `show` into `shell` (whether it accepts piped
stdin is UNVERIFIED), or by a small Rust binary on the library.

### Inference

The adapter is cheap: about 80–120 lines of script around `shell`, or about 150 lines of
Rust. The Rust version is MIT, so it can live in our repo. A **static-eval** wolges match
(`bot`) needs only the KWG and KLV2 and no time setting, so it is the cheapest first real
match once a Rust toolchain is installed. Before any sim match, check how `gcg load`
handles the opponent's rack.

## 5. Fair-match settings

### Facts

| Setting | Macondo | MAGPIE | Quackle | wolges |
| --- | --- | --- | --- | --- |
| Lexicon CSW24 | `-lexicon CSW24`; KWG under its `data/lexica` | `-lex CSW24` (data tarball) | `csw24.dawg` ships; build `csw24.gaddag` | `CSW24.kwg` via `buildlex` (`README.md:30-33`) |
| Leaves | `data/strategy/CSW24/leaves.klv2` (`equity/loaders.go:18`) | its CSW24 `.klv2` (file name UNVERIFIED) | `strategy/csw/superleaves`, its own format | `CSW24.klv2` (genblend) |
| Per-move time | Built-in sim: `MaxTimePerTurn` = 30 s, a package var with no autoplay flag (`game_runner.go:32`; only `cmd/inferdiag` sets it). In pairs mode there is no deadline at all | `-tlim S` (or PlayChooser `fixed_seconds_per_move`) | `secondsPerTurn` (adapter flag) | `bot sim MS` |
| Threads | `-simthreads1/2`; game threads `-threads` | `-threads` | `setThreadCount` / `--threads` | UNVERIFIED |
| Remaining clock | not given to engine | PlayChooser can use one, but Macondo doesn't pass it | no clock concept | none |

### Inference

**Recommended match settings**

- **Same word list.** All engines build CSW24 from the same source text. Compare word counts or dumps once before the first match, because Quackle's shipped `csw24.dawg` was built separately.
- **Leaves.** Each engine uses its own shipped leaves for CSW24, because we are testing the engines as their authors tune them. A second, controlled run can give Macondo, MAGPIE and wolges the same `.klv2` to isolate search from leaves. Quackle cannot share one, because superleaves is a different format.
- **Equal time.** Give every sim engine the same fixed seconds per move, set through its own flag. Quackle's iteration cap (5 × seconds) can stop it early, and Macondo's `Stop99` can too, so log wall time per move in each adapter and report the time actually used, not just the budget.
- **Threads.** Use one thread per engine and no more concurrent games than cores. On this 6-core machine, use `-threads 5`, which leaves a core for Macondo and the OS. Alternatively, run one game at a time with N threads each. Never oversubscribe.
- **Pairs.** Use `-gamepairs` with a seed. With timed sims the two halves of a pair will diverge, but both seats still start from the same tiles. Report the `divergent` fraction.
- **Challenge rule.** Use VOID, which is what autoplay does. Every engine should play only valid words; a phony stops the run.
- **Endgames.** Macondo puts no deadline on external engines, so each adapter must cap its own endgame solve.

## 6. Gaps

| Item | Size (estimate) | Notes |
| --- | --- | --- |
| Quackle adapter (C++, links libquackle + libquackleio + Qt6) | 150–250 lines + CMake target | GPL, because it links Quackle. Keep it in a separate GPL directory, not in engine code. Also build `csw24.gaddag` |
| MAGPIE adapter v1 (Python driving `bin/magpie` in sync mode) | 100–150 lines | Does not link MAGPIE, so the licence question doesn't arise. Must repeat the phase choice: sim / `peg` (bag 1–4) / `endgame` (bag 0). Parses `shmoves` and strips the `( )` |
| MAGPIE adapter v2 (C, `play_chooser_choose_move`) | ~200 lines | GPL; same play as MAGPIE's own timed autoplay |
| wolges adapter | 80–120 lines script, or ~150 lines Rust | MIT. Needs `cargo` |
| Macondo per-move time flag for built-in sim bots | ~20 lines Go (proto field, `config.go`, `shell.go`) | Needed for an equal-time Macondo vs X match. Would be a local patch, recorded in the dossier |
| Redact opponent racks in the GCG passed to engines | ~30 lines (in each adapter, or one Macondo patch) | Stops a dishonest engine, e.g. ours, from reading the opponent's earlier racks |
| SPRT stopping | ~100 lines on top of `games-*.txt` | Neither Macondo nor MAGPIE has it |
| Toolchains | install Go ≥ 1.24 (`go.mod`), Rust/cargo | Macondo and wolges cannot be built here today |

**What cannot be done with the current contract:**

- Tell an engine its remaining game time. Matches are fixed seconds per move.
- Keep an engine's state between turns (hash tables, inference). Every turn is a new process.
- Learn what the engine thought: `equity` and `win` are parsed but not logged as the engine's own values.

## Recommendation

- **Reuse Macondo autoplay** as the referee. That gives `CUSTOM_BOT`, `-gamepairs` with a seed, `games-*.txt` and `autoanalyze` for paired statistics. Install Go first.
- **Write three thin adapters to the `--gcg --lexicon --rack` → JSON contract:**
  - **MAGPIE:** first a Python sync-mode driver, later a C PlayChooser adapter.
  - **Quackle:** a C++ program on `libquackle`/`libquackleio`, with `--player` and `--seconds`.
  - **wolges:** a script around `shell`, or a Rust binary. A static-eval wolges match is the cheapest first match.
- **Patch Macondo minimally** (local branch, recorded in the dossier): a per-move time field for built-in sim bots, plus GCG rack redaction for engines we don't trust.

## Open questions

1. Where is the `quackle-evaluator` source used in domino14/macondo#504? Is it public and reusable? It would save writing the Quackle adapter.
2. Does `word-golib` `ToMachineWord` accept `.` for played-through squares? (Adapters will write full letters until this is checked.)
3. In autoplay, is GCG `#player1` always the player who moves first? The adapter needs this to know who is on turn at move 1. (`FlipPlayers` swaps `g.players`, `game/game.go:337-339`; check that history follows.)
4. Does MAGPIE's `load` leave the game at its last event? Does MAGPIE accept Macondo's GCG exactly as written (no `#lexicon` line)?
5. Does the wolges `shell` read piped stdin? Does `gcg load` treat the opponent's kept tiles as known?
6. Are Quackle's `csw24.dawg`, MAGPIE's CSW24 KWG and Macondo's CSW24 KWG the same word list?
7. Do the Quackle SWIG bindings still build against the CMake/Qt6 build? (This only matters if we prefer Python for the Quackle adapter.)
