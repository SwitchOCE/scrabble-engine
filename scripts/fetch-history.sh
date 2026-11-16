#!/usr/bin/env bash
# Export commit, pull-request and issue history for the reference engines into
# reference/history/<name>/. Re-runnable: per-PR comment files already present are skipped.
#
# Usage: scripts/fetch-history.sh [--no-comments] [name ...]
#   names default to every repo below. --no-comments skips the per-PR review threads
#   (one API call per PR; the slow part).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out_root="$root/reference/history"

declare -A repos=(
  [quackle]=quackle/quackle
  [macondo]=domino14/macondo
  [magpie]=jvc56/MAGPIE
  [wolges]=andy-k/wolges
  [stockfish]=official-stockfish/Stockfish
  [nnue-pytorch]=official-stockfish/nnue-pytorch
)

comments=1
names=()
for a in "$@"; do
  case "$a" in
    --no-comments) comments=0 ;;
    *) names+=("$a") ;;
  esac
done
[ ${#names[@]} -eq 0 ] && names=(quackle macondo magpie wolges)

# gh api with retries (GitHub returns occasional 502s on big repos).
api() {
  local i
  for i in 1 2 3 4 5; do
    gh api "$@" && return 0
    # Out of REST quota (5000/hour): wait for the reset instead of failing.
    local left reset
    read -r left reset < <(gh api rate_limit --jq '.resources.core | "\(.remaining) \(.reset)"')
    if [ "${left:-1}" -lt 5 ]; then
      echo "   rate limit hit; sleeping until $(date -d @"$reset" +%T)" >&2
      sleep $(( reset - $(date +%s) + 5 ))
    else
      echo "   retry $i: gh api $*" >&2; sleep $((i * 5))
    fi
  done
  return 1
}

for name in "${names[@]}"; do
  repo="${repos[$name]:?unknown name $name}"
  out="$out_root/$name"; mkdir -p "$out/pr-comments"
  echo "== $name ($repo)"

  # Commits, from the local clone if present.
  clone="$root/reference/$name"
  if [ -d "$clone/.git" ]; then
    git -C "$clone" log --format='%H%x09%cs%x09%an%x09%s' > "$out/commits.tsv"
    git -C "$clone" log --format='==== %H %cs %an%n%B' > "$out/commits-full.txt"
    echo "   commits: $(wc -l < "$out/commits.tsv")"
  fi

  # REST, paginated: robust on repos with thousands of PRs. --slurp joins pages.
  api --paginate --slurp "repos/$repo/pulls?state=all&per_page=100" \
    | jq '[.[][] | {number, title, body, state, author: .user.login, createdAt: .created_at,
                    mergedAt: .merged_at, closedAt: .closed_at, labels: [.labels[].name],
                    url: .html_url, head: .head.ref}]' > "$out/prs.json"
  api --paginate --slurp "repos/$repo/issues?state=all&per_page=100" \
    | jq '[.[][] | select(.pull_request | not) | {number, title, body, state,
                    author: .user.login, createdAt: .created_at, closedAt: .closed_at,
                    labels: [.labels[].name], comments, url: .html_url}]' > "$out/issues.json"

  # One line per PR, oldest first: number, created, outcome, author, title.
  # outcome: MERGED, CLOSED (closed without merge = abandoned/rejected), OPEN.
  jq -r 'sort_by(.number)[] | [.number, .createdAt[:10],
         (if .mergedAt then "MERGED" elif .state == "closed" then "CLOSED" else "OPEN" end),
         .author, .title] | @tsv' \
     "$out/prs.json" > "$out/prs-index.tsv"
  echo "   PRs: $(jq length "$out/prs.json")  (merged $(grep -c $'\tMERGED\t' "$out/prs-index.tsv" || true), closed unmerged $(grep -c $'\tCLOSED\t' "$out/prs-index.tsv" || true))"
  echo "   issues: $(jq length "$out/issues.json")"

  if [ "$comments" = 1 ]; then
    n=0
    for num in $(jq -r '.[].number' "$out/prs.json"); do
      f="$out/pr-comments/$num.json"
      [ -s "$f" ] && continue
      { api "repos/$repo/pulls/$num" | jq '{additions, deletions, changed_files, merge_commit_sha}'
        api --paginate --slurp "repos/$repo/issues/$num/comments" | jq '[.[][] | {author: .user.login, createdAt: .created_at, body}]'
        api --paginate --slurp "repos/$repo/pulls/$num/comments" | jq '[.[][] | {author: .user.login, createdAt: .created_at, path, line, body}]'
        api --paginate --slurp "repos/$repo/pulls/$num/reviews" | jq '[.[][] | {author: .user.login, state, body}]'
      } | jq -s '{number: '"$num"', stats: .[0], comments: .[1], review_comments: .[2], reviews: .[3]}' > "$f.tmp" \
        && mv "$f.tmp" "$f"
      n=$((n+1))
    done
    echo "   PR threads fetched this run: $n (total $(ls "$out/pr-comments" | wc -l))"
  fi
done
date -u +%FT%TZ > "$out_root/FETCHED_AT"
