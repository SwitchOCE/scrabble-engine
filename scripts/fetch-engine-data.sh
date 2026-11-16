#!/usr/bin/env bash
# Fetch and check the CSW24 data for Quackle, Macondo, MAGPIE and wolges under
# $ROOT/data (git-ignored; never commit these files).
#
# Usage: scripts/fetch-engine-data.sh [ROOT]   (default ROOT: the main checkout)
#
# What it does:
#   MAGPIE  : downloads the MAGPIE-DATA tarballs named in the pinned clone's
#             download_data.sh (skipped if already downloaded) and unpacks them
#             into data/magpie/ (skipped if already unpacked).
#   Macondo : copies CSW24.kwg, CSW24.klv2, super-CSW24.klv2 from the pinned
#             liwords clone (the place macondo lexicon/download.go:20 downloads
#             from) plus Macondo's own letterdistributions/ and strategy/, and
#             fetches the live URL copy to compare.
#   wolges  : copies CSW24.kwg and CSW24.klv2 from the same liwords files.
#   Quackle : makes the data/quackle overlay (symlinks to the clone's data/) and,
#             if libquackle_test and makegaddag are built, builds csw24.gaddag.
# What it does NOT do (done by the build steps or by the engines; see
# docs/harness/builds.md): MAGPIE's CSW24.wmp (`convert text2wordmap`), .wit and
# .rit (`make release`), and Macondo's CSW24.wmp (built by Macondo on first use).
# If those files exist, their sha256 is checked too.
#
# Every file is checked against the sha256 below; any mismatch or missing
# required file makes the script exit 1. data/MANIFEST.tsv is rewritten from
# scratch on every run (one row per file).
set -euo pipefail

ROOT=${1:-/home/alex/code/scrabble-engine}
REF=$ROOT/reference
DATA=$ROOT/data
DL=$DATA/downloads
MAN=$DATA/MANIFEST.tsv
mkdir -p "$DL/magpie" "$DL/macondo-live"

# path under data/ <TAB> expected sha256 <TAB> required (1) or optional (0)
EXPECTED='downloads/magpie/data-20260925.tgz	625e253bbbbbc7488aea2a8c581b67f7698b0a21c140dac513ae1c0e0abde0b4	1
downloads/magpie/testdata-20260101.tgz	fde407febee789df23711bd203272fc4e23b3daf715ff13f376b1150a4cdf045	1
magpie/data/lexica/CSW24.kwg	62ca7a84f07429a9976f77a4f74b94911aca5d49cce050dce72dd0e032c0566f	1
magpie/data/lexica/CSW24.klv2	1937df3fd5dc1882e6c283bdc0c8870ecf25b38645cb214fd4802d302ad34dea	1
magpie/data/strategy/CSW24.pat	222d37ae5057fa0a091992c1a0a1a9f46d2086a5d772369cc316529ed6630e03	1
magpie/data/strategy/CSW24_pegadjust.csv	114f1f0a5978a9afcc4db64ced77ebdb99c88082f3e77b9069f747f1fd7b2c30	1
magpie/data/strategy/winpct_english.csv	34c072d285e64973cfa0bd044f4d70f128677578c30993a35d85a5c607bc0417	1
magpie/data/letterdistributions/english.csv	e698ce0b93e025daccd3390107a914d74581c4603de38df65131768b1c6f9102	1
magpie/data/lexica/CSW24.wmp	183096e751f5464b43205658c7bcd092575fda1ea13e605ce56198b338292f91	0
magpie/data/lexica/CSW24.wit	bdbf3d1dab93715ca0f63166cfbb60584aed808cdebd9f376b2d47763995c1c4	0
magpie/data/lexica/CSW24.rit	6dac004c198cef6a6429614c042e2a0b7dc3b60efb2a263aeafadef5f8e0b3cb	0
macondo/lexica/gaddag/CSW24.kwg	62ca7a84f07429a9976f77a4f74b94911aca5d49cce050dce72dd0e032c0566f	1
macondo/lexica/gaddag/CSW24.klv2	b0ef5f6637cca0cd8e0962d6fb7d35b2d22f9bf648015f48fa8f80e24a60610b	1
macondo/lexica/gaddag/super-CSW24.klv2	c69835cd98e08aac15c4ea7b773c1694e9622566c378ec97d621a8afd3cd613a	1
macondo/strategy/default/winpct.csv	18c79601f57f10b4e0a1b49ab59ce7946ad462751636d148f1c850183f491e42	1
macondo/strategy/default/preendgame.json	4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945	1
macondo/letterdistributions/english	6ee0fae2f06b3d9a67a97265384d82b058f6ba007aaf27b53389775892e27929	1
macondo/lexica/CSW24.wmp	183096e751f5464b43205658c7bcd092575fda1ea13e605ce56198b338292f91	0
downloads/macondo-live/CSW24.kwg	62ca7a84f07429a9976f77a4f74b94911aca5d49cce050dce72dd0e032c0566f	0
downloads/macondo-live/CSW24.klv2	b0ef5f6637cca0cd8e0962d6fb7d35b2d22f9bf648015f48fa8f80e24a60610b	0
downloads/macondo-live/super-CSW24.klv2	c69835cd98e08aac15c4ea7b773c1694e9622566c378ec97d621a8afd3cd613a	0
wolges/CSW24.kwg	62ca7a84f07429a9976f77a4f74b94911aca5d49cce050dce72dd0e032c0566f	1
wolges/CSW24.klv2	b0ef5f6637cca0cd8e0962d6fb7d35b2d22f9bf648015f48fa8f80e24a60610b	1
quackle/data/lexica/csw24.dawg	8736cd4dfb88a664188940778239d3be6251853d3a962effbb636b1446eb8fed	1
quackle/data/strategy/csw/superleaves	cf20c38578cfd6263d494e2748cf96b4028e3e9ff77812a5e4efc082c4ab3797	1
quackle/data/alphabets/english.quackle_alphabet	83997ef8c837cbdab42f0065999ccf274f0bd7b9c0195dffd76d05513c410c6f	1
quackle/data/lexica/csw24.gaddag	1c68e5896dbca258d55c81c46b830d7030cc6a90d0fc76939ac6aadde0054758	0'

# ---- MAGPIE ---------------------------------------------------------------
DATA_VERSION=$(sed -n 's/^DATA_VERSION="\(.*\)"/\1/p' "$REF/magpie/download_data.sh")
TESTDATA_VERSION=$(sed -n 's/^TESTDATA_VERSION="\(.*\)"/\1/p' "$REF/magpie/download_data.sh")
BASE="https://github.com/jvc56/MAGPIE-DATA/raw/main/versioned-tarballs"
declare -A SOURCE
fetch_tgz() { # name version
  local name=$1 ver=$2 out="$DL/magpie/$1-$2.tgz"
  SOURCE["downloads/magpie/$1-$2.tgz"]="$BASE/$name-$ver.tgz (chunks .aa.. reassembled if chunked)"
  [ -s "$out" ] && return
  if curl -sfI "$BASE/$name-$ver.tgz.aa" >/dev/null 2>&1; then
    local s=aa parts=()
    while curl -sfL "$BASE/$name-$ver.tgz.$s" -o "$out.$s"; do
      parts+=("$out.$s")
      s=$(python3 -I -c "import sys;a,b=sys.argv[1];print(a+chr(ord(b)+1) if b!='z' else chr(ord(a)+1)+'a')" "$s")
    done
    rm -f "$out.$s"
    cat "${parts[@]}" > "$out"
  else
    curl -sfL "$BASE/$name-$ver.tgz" -o "$out"
  fi
}
fetch_tgz data "$DATA_VERSION"
fetch_tgz testdata "$TESTDATA_VERSION"
mkdir -p "$DATA/magpie"
[ -f "$DATA/magpie/data/lexica/CSW24.kwg" ] || tar -xzf "$DL/magpie/data-$DATA_VERSION.tgz" -C "$DATA/magpie"
[ -d "$DATA/magpie/testdata" ] || tar -xzf "$DL/magpie/testdata-$TESTDATA_VERSION.tgz" -C "$DATA/magpie"
for f in lexica/CSW24.kwg lexica/CSW24.klv2 strategy/CSW24.pat strategy/CSW24_pegadjust.csv \
         strategy/winpct_english.csv letterdistributions/english.csv; do
  SOURCE["magpie/data/$f"]="MAGPIE-DATA data-$DATA_VERSION"
done
for f in wmp wit rit; do SOURCE["magpie/data/lexica/CSW24.$f"]="built by MAGPIE build steps (builds.md)"; done

# ---- Macondo and wolges (liwords files) -------------------------------------
LW=$REF/liwords/liwords-ui/public/wasm/2024
LIVE="https://github.com/woogles-io/liwords/raw/refs/heads/master/liwords-ui/public/wasm/2024"
LWSHA=$(sed -n 's/^liwords\t[^\t]*\t\([0-9a-f]*\).*/\1/p' "$REF/PINS.tsv")
MSHA=$(sed -n 's/^macondo\t[^\t]*\t\([0-9a-f]*\).*/\1/p' "$REF/PINS.tsv")
MD=$DATA/macondo
mkdir -p "$MD/lexica/gaddag" "$DATA/wolges"
cp -r "$REF/macondo/data/letterdistributions" "$REF/macondo/data/strategy" "$MD/"
for f in letterdistributions/english strategy/default/winpct.csv strategy/default/preendgame.json; do
  SOURCE["macondo/$f"]="macondo@$MSHA:data/$f"
done
SOURCE["macondo/lexica/CSW24.wmp"]="built by Macondo on first use"
for f in CSW24.kwg CSW24.klv2 super-CSW24.klv2; do
  cp "$LW/$f" "$MD/lexica/gaddag/$f"
  SOURCE["macondo/lexica/gaddag/$f"]="liwords@$LWSHA:liwords-ui/public/wasm/2024/$f"
  if curl -sfL "$LIVE/$f" -o "$DL/macondo-live/$f"; then
    SOURCE["downloads/macondo-live/$f"]="$LIVE/$f (fetched $(date -u +%F))"
  fi
done
for f in CSW24.kwg CSW24.klv2; do
  cp "$LW/$f" "$DATA/wolges/$f"
  SOURCE["wolges/$f"]="liwords@$LWSHA:liwords-ui/public/wasm/2024/$f"
done

# ---- Quackle ---------------------------------------------------------------
Q=$REF/quackle
QSHA=$(sed -n 's/^quackle\t[^\t]*\t\([0-9a-f]*\).*/\1/p' "$REF/PINS.tsv")
QD=$DATA/quackle
mkdir -p "$QD/data/lexica" "$QD/run"
for d in alphabets strategy themes raw_lexica; do ln -sfn "$Q/data/$d" "$QD/data/$d"; done
for f in "$Q"/data/lexica/*; do ln -sfn "$f" "$QD/data/lexica/$(basename "$f")"; done
for f in lexica/csw24.dawg strategy/csw/superleaves alphabets/english.quackle_alphabet; do
  SOURCE["quackle/data/$f"]="quackle@$QSHA:data/$f (symlink)"
done
QT=$Q/build-headless/test/libquackle_test MG=$Q/build-headless/makegaddag/makegaddag
if [ ! -f "$QD/data/lexica/csw24.gaddag" ] && [ -x "$QT" ] && [ -x "$MG" ]; then
  (cd "$QD/run" && "$QT" --mode=worddump --lexicon=csw24 | sed -n 's/^wordDump: //p' > csw24-words.raw &&
   "$MG" --input=csw24-words.raw --output=../data/lexica/csw24.gaddag > /dev/null)
fi
SOURCE["quackle/data/lexica/csw24.gaddag"]="built: libquackle_test --mode=worddump | makegaddag"

# ---- Verify and write the manifest ------------------------------------------
fail=0
{
  printf 'file\tsha256\tbytes\tsource\n'
  while IFS=$'\t' read -r path want req; do
    f=$DATA/$path
    if [ ! -e "$f" ]; then
      [ "$req" = 1 ] && { echo "MISSING $path" >&2; fail=1; }
      continue
    fi
    got=$(sha256sum "$f" | cut -d' ' -f1)   # follows symlinks
    if [ "$got" != "$want" ]; then echo "MISMATCH $path: got $got, want $want" >&2; fail=1; fi
    printf '%s\t%s\t%s\t%s\n' "$path" "$got" "$(stat -L -c %s "$f")" "${SOURCE[$path]:-}"
  done <<< "$EXPECTED"
} > "$MAN.tmp"
mv "$MAN.tmp" "$MAN"
if [ "$fail" != 0 ]; then echo "checksum check FAILED; manifest: $MAN" >&2; exit 1; fi
echo "all checksums match; manifest: $MAN"
