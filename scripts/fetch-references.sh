#!/usr/bin/env bash
# Clone (or update) the open-source reference engines into reference/ and record pinned SHAs.
# Partial clones: full history, file contents fetched on demand.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
ref="$root/reference"
mkdir -p "$ref"

repos=(
  "quackle  https://github.com/quackle/quackle.git"
  "macondo  https://github.com/domino14/macondo.git"
  "magpie   https://github.com/jvc56/MAGPIE.git"
  "wolges   https://github.com/andy-k/wolges.git"
  "liwords  https://github.com/woogles-io/liwords.git"
  "stockfish     https://github.com/official-stockfish/Stockfish.git"
  "nnue-pytorch  https://github.com/official-stockfish/nnue-pytorch.git"
)

printf "name\turl\tcommit\tdate\n" > "$ref/PINS.tsv"
for entry in "${repos[@]}"; do
  read -r name url <<<"$entry"
  if [ -d "$ref/$name/.git" ]; then
    echo "== updating $name"; git -C "$ref/$name" pull --ff-only -q
  else
    echo "== cloning $name"; git clone -q --filter=blob:none "$url" "$ref/$name"
  fi
  sha=$(git -C "$ref/$name" rev-parse HEAD)
  date=$(git -C "$ref/$name" log -1 --format=%cs)
  printf "%s\t%s\t%s\t%s\n" "$name" "$url" "$sha" "$date" >> "$ref/PINS.tsv"
done
cp "$ref/PINS.tsv" "$root/docs/engines/pins.tsv"
column -t -s $'\t' "$ref/PINS.tsv"
