#!/usr/bin/env bash
# Static move generation speed, single thread, on harness/bench/positions/pos-*.gcg.
#
# For each engine and position: load the position once, then generate the full
# move list and rank it by static equity R times through the engine's own
# command loop (only the top move is printed). Wall time of an R-run minus an
# R=1 run, divided by R-1, is the marginal time per generation. (An R=0 baseline
# is wrong for wolges: its first `gen` costs ~0.27 s, found by the scope review.)
# Quackle's harness cannot repeat gen without reloading, so for Quackle each
# repetition also re-reads the GCG and prints the board (flagged in builds.md).
#
# Usage: harness/bench/movegen.sh [R]   (default 2000)
# Prints TSV: engine position reps seconds_total seconds_base us_per_gen gens_per_s
set -euo pipefail
R=${1:-2000}
HERE=$(cd "$(dirname "$0")" && pwd)
POS=$HERE/positions
ROOT=/home/alex/code/scrabble-engine
REF=$ROOT/reference
DATA=$ROOT/data
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

now() { date +%s.%N; }
timeit() { # cmdfile engine-runner...  -> seconds
  local t0 t1; t0=$(now); "$@" > /dev/null 2>&1; t1=$(now)
  python3 -I -c "import sys;print(f'{float(sys.argv[2])-float(sys.argv[1]):.4f}')" "$t0" "$t1"
}

run_macondo() { # cmdfile
  (cd "$DATA/macondo" && MACONDO_DATA_PATH=$DATA/macondo "$REF/macondo/bin/shell" < "$1"); }
run_magpie() { (cd "$REF/magpie" && ./bin/magpie < "$1"); }
run_wolges() { (cd "$DATA/wolges" && "$REF/wolges/target/release/shell" < "$1"); }
run_quackle() { # argsfile
  (cd "$DATA/quackle/run" && xargs -a "$1" -d '\n' "$REF/quackle/build-headless/test/libquackle_test"); }

mk() { # engine pos reps -> file
  local e=$1 p=$2 r=$3 f=$TMP/$1-$(basename "$2")-$3
  case $e in
    macondo) { echo "set lexicon CSW24"; echo "load $p"; echo "last"
               for ((i=0;i<r;i++)); do echo "gen 1"; done; echo exit; } > "$f" ;;
    magpie)  { echo "set -lex CSW24 -threads 1 -savesettings false -autosavegcg false"; echo "load $p"; echo "goto end"
               for ((i=0;i<r;i++)); do echo "gen"; done; } > "$f" ;;
    wolges)  { echo "lexicon CSW24.kwg"; echo "leaves CSW24.klv2"; echo "gcg load $p"
               for ((i=0;i<r;i++)); do echo "gen 1"; done; echo exit; } > "$f" ;;
    quackle) { echo "--mode=positions"; echo "--lexicon=csw24"; echo "--computer=Speedy Player"
               # one position is always loaded; r extra loads+gens on top of it
               for ((i=0;i<=r;i++)); do echo "--position=$p"; done; } > "$f" ;;
  esac
  echo "$f"
}

printf 'engine\tposition\treps\ts_total\ts_base\tus_per_gen\tgens_per_s\n'
for e in ${ENGINES:-quackle macondo wolges}; do
  for p in "$POS"/pos-*.gcg; do
    base=$(timeit run_$e "$(mk $e "$p" 1)")
    tot=$(timeit run_$e "$(mk $e "$p" "$R")")
    python3 -I -c "
import sys
e,p,r,t,b=sys.argv[1],sys.argv[2],int(sys.argv[3]),float(sys.argv[4]),float(sys.argv[5])
us=(t-b)/(r-1)*1e6
print(f'{e}\t{p}\t{r}\t{t:.3f}\t{b:.3f}\t{us:.1f}\t{1e6/us:.0f}')" "$e" "$(basename "$p")" "$R" "$tot" "$base"
  done
done
