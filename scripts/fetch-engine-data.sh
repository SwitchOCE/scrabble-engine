#!/usr/bin/env bash
# Fetch CSW24 data for Quackle, Macondo and MAGPIE into $ROOT/data (git-ignored).
# Records URLs and SHA-256 sums in $ROOT/data/MANIFEST.tsv. Never commit the files.
#
# Usage: scripts/fetch-engine-data.sh [ROOT]   (default ROOT: the main checkout)
#
# Sources (all from each engine's own documented location):
#   MAGPIE  : download_data.sh at the pinned SHA -> MAGPIE-DATA versioned tarballs
#   Macondo : lexicon/download.go -> liwords-ui/public/wasm/2024/<LEX>.{kwg,klv2}
#             (we copy from the pinned liwords clone, and also fetch the live URL
#             to compare checksums)
#   Quackle : ships data/lexica/csw24.dawg and data/strategy/csw/superleaves in-tree
set -euo pipefail

ROOT=${1:-/home/alex/code/scrabble-engine}
REF=$ROOT/reference
DATA=$ROOT/data
DL=$DATA/downloads
MAN=$DATA/MANIFEST.tsv
mkdir -p "$DL/magpie" "$DL/macondo-live"
[ -f "$MAN" ] || printf 'file\tsha256\tbytes\tsource\n' > "$MAN"

record() { # file source
  local f=$1 src=$2
  printf '%s\t%s\t%s\t%s\n' "${f#$DATA/}" "$(sha256sum "$f" | cut -d' ' -f1)" \
    "$(stat -c %s "$f")" "$src" >> "$MAN"
}

# ---- MAGPIE ---------------------------------------------------------------
# Versions are read from the pinned clone's download_data.sh.
DATA_VERSION=$(sed -n 's/^DATA_VERSION="\(.*\)"/\1/p' "$REF/magpie/download_data.sh")
TESTDATA_VERSION=$(sed -n 's/^TESTDATA_VERSION="\(.*\)"/\1/p' "$REF/magpie/download_data.sh")
BASE="https://github.com/jvc56/MAGPIE-DATA/raw/main/versioned-tarballs"
fetch_tgz() { # name version
  local name=$1 ver=$2 out="$DL/magpie/$1-$2.tgz"
  [ -s "$out" ] && { echo "have $out"; return; }
  if curl -sfI "$BASE/$name-$ver.tgz.aa" >/dev/null 2>&1; then
    local s=aa parts=()
    while curl -sfL "$BASE/$name-$ver.tgz.$s" -o "$out.$s"; do
      record "$out.$s" "$BASE/$name-$ver.tgz.$s"; parts+=("$out.$s")
      s=$(python3 -I -c "import sys;a,b=sys.argv[1];print(a+chr(ord(b)+1) if b!='z' else chr(ord(a)+1)+'a')" "$s")
    done
    rm -f "$out.$s"
    cat "${parts[@]}" > "$out"
  else
    curl -sfL "$BASE/$name-$ver.tgz" -o "$out"
  fi
  record "$out" "$BASE/$name-$ver.tgz (reassembled if chunked)"
}
fetch_tgz data "$DATA_VERSION"
fetch_tgz testdata "$TESTDATA_VERSION"
mkdir -p "$DATA/magpie"
tar -xzf "$DL/magpie/data-$DATA_VERSION.tgz" -C "$DATA/magpie"
tar -xzf "$DL/magpie/testdata-$TESTDATA_VERSION.tgz" -C "$DATA/magpie"

# ---- Macondo --------------------------------------------------------------
LW=$REF/liwords/liwords-ui/public/wasm/2024
LIVE="https://github.com/woogles-io/liwords/raw/refs/heads/master/liwords-ui/public/wasm/2024"
LWSHA=$(sed -n 's/^liwords\t[^\t]*\t\([0-9a-f]*\).*/\1/p' "$REF/PINS.tsv")
MD=$DATA/macondo
mkdir -p "$MD/lexica/gaddag"
# Macondo's own non-lexicon data (letter distributions, winpct, preendgame) from the clone.
cp -r "$REF/macondo/data/letterdistributions" "$REF/macondo/data/strategy" "$MD/"
for f in CSW24.kwg CSW24.klv2 super-CSW24.klv2; do
  cp "$LW/$f" "$MD/lexica/gaddag/$f"
  record "$MD/lexica/gaddag/$f" "liwords@$LWSHA:liwords-ui/public/wasm/2024/$f"
  curl -sfL "$LIVE/$f" -o "$DL/macondo-live/$f" && record "$DL/macondo-live/$f" "$LIVE/$f (fetched $(date -u +%F))"
done

# ---- Quackle (in-tree; recorded only) --------------------------------------
QSHA=$(sed -n 's/^quackle\t[^\t]*\t\([0-9a-f]*\).*/\1/p' "$REF/PINS.tsv")
for f in data/lexica/csw24.dawg data/strategy/csw/superleaves data/strategy/default_english/superleaves; do
  printf '%s\t%s\t%s\t%s\n' "quackle-in-tree/$f" "$(sha256sum "$REF/quackle/$f" | cut -d' ' -f1)" \
    "$(stat -c %s "$REF/quackle/$f")" "quackle@$QSHA:$f" >> "$MAN"
done
echo "done; manifest: $MAN"
