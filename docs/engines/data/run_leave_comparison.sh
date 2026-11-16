#!/bin/sh
# Regenerates docs/engines/data/quackle-vs-magpie-leaves.txt. Run from the repo root of the main checkout
# (needs reference/quackle and data/). Prints sha256 of every input, then the summary statistics.
set -e
HERE=$(dirname "$0")
Q=reference/quackle/data/strategy/csw/superleaves
for K in data/magpie/data/lexica/CSW24.klv2 data/wolges/CSW24.klv2; do
	echo "## $Q vs $K"
	sha256sum "$Q" "$K"
	python3 -I "$HERE/compare_quackle_magpie_leaves.py" "$Q" "$K"
	echo
done
