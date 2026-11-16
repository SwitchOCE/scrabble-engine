#!/usr/bin/env bash
# Static self-play speed, single thread, CSW24: N games of the engine's
# best-static-move player against itself, wall time from outside the process
# (includes start-up and data loading, ~0.1-0.5 s, small next to the run).
#
# Usage: harness/bench/selfplay.sh [N]   (default 500)
# Output: one block per engine with the command, its tail, and the wall time.
set -uo pipefail
N=${1:-500}
ROOT=/home/alex/code/scrabble-engine
REF=$ROOT/reference
DATA=$ROOT/data

go_() { # name dir cmd...
  local name=$1 dir=$2; shift 2
  echo "### $name"
  echo "\$ (cd $dir && $*)"
  local t0 t1; t0=$(date +%s%N)
  (cd "$dir" && "$@") 2>&1 | tail -${TAILN:-6}
  t1=$(date +%s%N)
  echo "wall_s=$(( (t1 - t0) / 1000000 ))e-3 games=$N"
}

ENGINES=${ENGINES:-quackle macondo magpie wolges}
for e in $ENGINES; do
  case $e in
    # --quiet makes the harness skip the games (measured: 500 "games" in 0.4 s), so the
    # move log goes to a file instead and is counted.
    quackle) log=$(mktemp)
             go_ quackle "$DATA/quackle/run" sh -c "'$REF/quackle/build-headless/test/libquackle_test' \
               --mode=selfplay --lexicon=csw24 '--computer=Speedy Player' --seed=1 --repetitions=$N > $log; \
               echo games=\$(grep -c 'GAME OVER' $log) moves=\$(grep -c commits $log)"
             rm -f "$log" ;;
    macondo) out=$(mktemp -d)
             go_ macondo "$DATA/macondo" env MACONDO_DATA_PATH=$DATA/macondo "$REF/macondo/bin/shell" \
               autoplay -lexicon CSW24 -botcode1 HASTY_BOT -botcode2 HASTY_BOT -numgames $N \
               -threads 1 -seed 1 -outputdir "$out" -block
             echo "games_file_lines=$(cat "$out"/games-*.txt 2>/dev/null | wc -l)"; rm -rf "$out" ;;
    magpie)  go_ magpie "$REF/magpie" ./bin/magpie autoplay games $N -lex CSW24 -threads 1 -seed 1 \
               -s1 equity -s2 equity -r1 best -r2 best -numplays 1 -gp false -savesettings false -hr true ;;
    wolges)  go_ wolges "$DATA/wolges" "$REF/wolges/target/release/auto" --games $N CSW24.kwg CSW24.klv2 ;;
  esac
done
