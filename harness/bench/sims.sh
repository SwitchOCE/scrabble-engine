#!/usr/bin/env bash
# Sim speed for Macondo and MAGPIE at fixed settings on harness/bench/positions.
#
# Settings, both engines: top 15 static candidates, 2 plies after the candidate,
# no inference, no early stopping, no pruning (MAGPIE: -sr rr -threshold none,
# so every candidate gets the same number of rollouts, as in Macondo),
# T threads, a fixed wall time of S seconds.
# Each engine reports its own counts:
#   Macondo: "time taken: X, nps: Y, nodes: Z" and "iterationCt" (one iteration =
#            one rollout of *every* candidate).
#   MAGPIE:  "Iters" (total rollouts over all candidates), "Time", "Nps".
# A node, in both, is one move played in a rollout (the candidate or a ply move).
#
# Usage: harness/bench/sims.sh [SECONDS] [THREADS...]   (default 10, threads 1 6)
set -uo pipefail
S=${1:-10}; shift || true
THREADS=${*:-1 6}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=/home/alex/code/scrabble-engine
REF=$ROOT/reference
DATA=$ROOT/data

macondo() { # pos threads
  echo "### macondo $(basename "$1") threads=$2 plies=2 cands=15 secs=$S"
  { echo "set lexicon CSW24"; echo "load $1"; echo "last"; echo "gen 15"
    echo "sim -plies 2 -threads $2"; sleep "$S"; echo "sim stop"; sleep 2
    echo "exit"; } |
    (cd "$DATA/macondo" && MACONDO_DATA_PATH=$DATA/macondo "$REF/macondo/bin/shell" 2>&1) |
    grep -a -E 'time taken|iterationCt' | sed 's/\x1b\[[0-9;]*m//g'
}

magpie() { # pos threads
  echo "### magpie $(basename "$1") threads=$2 plies=2 cands=15 secs=$S"
  python3 -I "$HERE/magpie_api.py" run "$1" "generate -numplays 15" \
    "simulate -plies 2 -numplays 15 -tlim $S -iterations 2000000000 -sinfer false -scensus false -sr rr -threshold none -threads $2" 2>&1 |
    grep -a -o -E '(Iters|Time|Nps|Status|Census|Infer): +[^ ].*' | sed 's/  */ /g'
}

# wolges: the shell's `sim N` has fixed settings (its own candidate field of ~100
# moves, 4 plies, candidates pruned as they fall out, threads = CPUs available),
# so threads are set with taskset (Rust's available_parallelism follows the
# affinity mask) and N is chosen to take roughly S seconds. One wolges iteration
# = one rollout of every candidate still in. We sum the per-candidate
# `rollouts` column of `sim show 500` to get the total.
wolges() { # pos threads
  local cpus=0 n=$((S * 50))
  [ "$2" -gt 1 ] && cpus=0-$(($2 - 1)) && n=$((S * 50 * $2))
  echo "### wolges $(basename "$1") threads=$2 plies=4 cands=wolges-field iterations=$n"
  printf 'lexicon CSW24.kwg\nleaves CSW24.klv2\ngcg load %s\nsim %d\nsim show 500\nexit\n' "$1" "$n" |
    (cd "$DATA/wolges" && taskset -c "$cpus" "$REF/wolges/target/release/shell" 2>/dev/null) |
    awk '/^sim: .* more iterations, .* ms/ {print}
         / rollouts / {for(i=1;i<=NF;i++) if($i=="rollouts"){r+=$(i+1); c++}}
         END {print "candidates_listed=" c, "rollouts_total=" r}'
}

for p in "$HERE"/positions/pos-*.gcg; do
  for t in $THREADS; do
    for e in ${ENGINES:-macondo magpie wolges}; do
      $e "$p" "$t"
    done
  done
done
