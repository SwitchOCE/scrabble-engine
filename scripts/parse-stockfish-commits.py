#!/usr/bin/env python3
"""Parse Stockfish commit messages into a table of changes and their test results.

No LLM needed: Stockfish commit messages report fishtest SPRT results in a near-fixed
format (label / URL / LLR / Total W L D / Ptnml). This script extracts them, tags each
commit by code area, technique and kind, and writes:

  docs/chess/data/stockfish-commits.tsv   one row per commit (committed)
  docs/chess/data/stockfish-tests.tsv     one row per parsed test result (git-ignored)
  build/stockfish-commits-parsed.jsonl    everything, incl. file lists (git-ignored)
  docs/chess/stockfish-commit-stats.md    aggregate summary; text below the
                                          HAND_MARKER line is kept across reruns

Usage: python3 -I scripts/parse-stockfish-commits.py [path/to/stockfish/clone]
Standard library only. Runs in about 2 s on the full history.
"""
import json
import math
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLONE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reference" / "stockfish"
DATA = ROOT / "docs" / "chess" / "data"
JSONL = ROOT / "build" / "stockfish-commits-parsed.jsonl"
DOC = ROOT / "docs" / "chess" / "stockfish-commit-stats.md"
PR_INDEX = ROOT / "reference" / "history" / "stockfish" / "prs-index.tsv"
HAND_MARKER = "<!-- Hand-written sections below. The script keeps everything after this line. -->"

NORMALIZED_DATE = "2021-04-25"  # first <> (normalized-Elo) bounds in a message
NNUE_DATE = "2020-08-06"  # 84f3e867 "Add NNUE evaluation"; NNUE-only tags start here

# ---------- git log ----------

RS, US = "\x1e", "\x1f"


def git_log():
    """Yield (sha, date, author, body, files) for every non-merge commit.

    The reference clone is blobless (`git clone --filter=blob:none`), so anything that
    reads file contents (--numstat, --stat, rename detection) makes git fetch blobs over
    the network one commit at a time and the run hangs. --name-status with --no-renames
    needs only trees, which a blobless clone has. GIT_NO_LAZY_FETCH makes git fail fast
    instead of fetching if that ever changes. Line counts are therefore not reported.
    Date is the committer date (when the patch landed on master).
    """
    fmt = f"{RS}%H{US}%cs{US}%an{US}%B{US}"
    raw = subprocess.run(
        ["git", "-C", str(CLONE), "log", "--no-merges", "--no-renames", "--name-status",
         f"--format={fmt}"],
        capture_output=True, text=True, errors="replace", check=True,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
    ).stdout
    for rec in raw.split(RS)[1:]:
        sha, date, author, body, status = rec.split(US)
        files = [line.split("\t", 1)[1] for line in status.strip().splitlines() if "\t" in line]
        yield sha, date, author, body.strip(), files


# ---------- test-result parsing ----------

# "LLR: 2.94 (-2.94,2.94) <0.50,2.50>". Parenthesised stopping bounds and the SPRT Elo
# bounds are both optional (early 2013 messages give neither). Requires "LLR:" with a
# colon so prose such as "stopped at LLR=1.2" is not read as a result.
LLR_RE = re.compile(
    r"LLR:\s*(-?\d+(?:\.\d+)?)"
    r"(?:\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\))?"
    r"(?:\s*([\[<{])\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*[\]>}])?")
# fishtest util.format_bounds: [] BayesElo, {} logistic Elo, <> normalized Elo.
ELO_MODEL = {"[": "BayesElo", "{": "logistic", "<": "normalized"}
TOTAL_RE = re.compile(r"Total:\s*(\d+)\s+W:\s*(\d+)\s+L:\s*(\d+)\s+D:\s*(\d+)")
PTNML_RE = re.compile(r"Ptnml\(0-2\):\s*(\d+)\s*,?\s*(\d+)\s*,?\s*(\d+)\s*,?\s*(\d+)\s*,?\s*(\d+)")
URL_RE = re.compile(
    r"https?://tests\.stockfishchess\.org/(?:tests/(?:view|live_elo)/|html/live_elo\.html\?)[0-9a-f]+")
ELO_LINE_RE = re.compile(r"\bELO:\s*(-?[\d.]+)\s*(?:\+-|±)\s*([\d.]+)", re.I)
STAT_RE = re.compile(r"\bLLR\b|Total:\s*\d|Ptnml\(|\bn?ELO:|\bLOS:", re.I)

NAMED_TC = ("VVLTC", "VLTC", "LTC", "STC")
NUM_TC_RE = re.compile(r"(?<![\d.])(\d{1,3})(?:\"|''|s)?\s*\+\s*(\d*\.\d+)")
SECONDS_TC_RE = re.compile(r"(?<![\d.+])(\d{1,3})\"")
THREADS_RES = (re.compile(r"\b(?:th|threads?)\s*[=:]?\s*(\d+)\b", re.I),
               re.compile(r"(?<![\d.])(\d+)\s*-?\s*(?:threads?|th)\b", re.I))
NONREG_WORDS = re.compile(r"non[- ]?reg|no[- ]regression|simplification bounds", re.I)
# "master vs patch" / "reverse test": master plays as the candidate, so a failed SPRT
# means the patch is not weaker.
# Tests run in a non-default configuration measure something other than normal play
# (a MultiPV fix "gains" 25-75 Elo in MultiPV mode). Excluded from elo_stc/elo_ltc.
SPECIAL_RE = re.compile(r"multi ?pv|\bskill\b|chess ?960|\bd?frc\b|contempt|ponder|max_ply", re.I)
# Subject-level version: contempt patches were tested in normal play, so not listed.
SPECIAL_SUBJ_RE = re.compile(r"multi ?pv|\bskill\b|chess ?960|\bd?frc\b|ponder", re.I)
REVERSE_RE = re.compile(r"\breverse|master vs\.? (this |the )?patch", re.I)


def tc_of(text):
    """Return (tc, source, threads) from a test's label text."""
    threads = None
    for rx in THREADS_RES:
        if m := rx.search(text):
            threads = int(m.group(1))
            break
    for name in NAMED_TC:
        if re.search(rf"\b{name}\b", text, re.I):
            return name, "name", threads
    base = None
    if m := NUM_TC_RE.search(text):
        base = int(m.group(1))
    elif m := SECONDS_TC_RE.search(text):
        base = int(m.group(1))
    if base is not None:
        if threads and threads > 1:  # fishtest SMP tests: 5+0.05 th N (STC), 20+0.2 th N (LTC)
            return ("LTC" if base >= 20 else "STC"), "numeric", threads
        return ("STC" if base <= 20 else "LTC" if base < 120 else "VLTC"), "numeric", threads
    low = text.lower()
    if re.search(r"\bvery long\b", low):
        return "VLTC", "words", threads
    if re.search(r"\blong\b", low):
        return "LTC", "words", threads
    if re.search(r"\bshort\b", low):
        return "STC", "words", threads
    return "", "", threads


def elo_from_results(w, l, d, ptnml=None):
    """Logistic Elo and 95% half-width from game results.

    The point estimate is the same from W/L/D or from pentanomial pairs (both give the
    mean score). The error bar uses pentanomial (game-pair) variance when Ptnml is
    given, as fishtest does for paired openings, else trinomial per-game variance.
    """
    if ptnml and sum(ptnml) > 0:
        n = sum(ptnml)
        xs = [0, 0.25, 0.5, 0.75, 1.0]
        s = sum(x * c for x, c in zip(xs, ptnml)) / n
        var = sum(c * (x - s) ** 2 for x, c in zip(xs, ptnml)) / n
        model = "pentanomial"
    else:
        n = w + l + d
        if n == 0:
            return None, None, None
        s = (w + d / 2) / n
        var = (w * (1 - s) ** 2 + d * (0.5 - s) ** 2 + l * s ** 2) / n
        model = "trinomial"
    if s <= 0 or s >= 1:
        return None, None, None
    se = math.sqrt(var / n)
    f = lambda x: -400 * math.log10(1 / x - 1)
    lo, hi = max(s - 1.96 * se, 1e-9), min(s + 1.96 * se, 1 - 1e-9)
    return round(f(s), 2), round((f(hi) - f(lo)) / 2, 2), model


def is_url_only(t):
    return bool(URL_RE.search(t)) and len(URL_RE.sub("", t).strip(" :-()[]<>")) == 0


def test_context(lines, i):
    """Collect label text, URL and stat lines around the result anchored at line i."""
    label_parts, url_up, url_down, stats, last = [], None, None, [lines[i]], i
    # upward: an optional URL line, then the first text line (the label)
    for j in range(i - 1, max(i - 5, -1), -1):
        t = lines[j].strip()
        if not t and j == i - 1 and j > 0 and lines[j - 1].strip().endswith(":"):
            continue  # "STC, 11 threads:" / blank line / results
        if not t or STAT_RE.search(t):
            break
        if t.startswith("```"):
            continue
        if is_url_only(t):
            if label_parts:   # URL above the label belongs to the previous test
                break
            url_up = url_up or URL_RE.search(t).group(0)
            continue
        if URL_RE.search(t) and not url_up:
            url_up = URL_RE.search(t).group(0)
        label_parts.append(t)
        break
    # downward: stat lines and a trailing URL, until blank / next test / prose
    for k in range(i + 1, min(i + 7, len(lines))):
        t = lines[k].strip()
        if not t or LLR_RE.search(t):
            break
        if t.startswith("```"):
            continue
        if is_url_only(t):
            url_down = url_down or URL_RE.search(t).group(0)
            last = k
            continue
        if STAT_RE.search(t) and not (k > i + 1 and TOTAL_RE.search(t) and TOTAL_RE.search("\n".join(stats))):
            stats.append(t)
            last = k
            continue
        break
    return " ".join(label_parts), url_down or url_up, "\n".join(stats), last


def make_test(label, llr_line_extra, stats, url, m=None):
    tc, tc_src, threads = tc_of(label + " " + llr_line_extra)
    smp = bool((threads and threads > 1) or re.search(r"\bsmp\b", label, re.I))
    test = {"label": label[:100], "tc": tc, "tc_source": tc_src, "threads": threads, "smp": smp,
            "special": bool(SPECIAL_RE.search(label))}
    if m:
        llr = float(m.group(1))
        lo = float(m.group(2)) if m.group(2) else -2.94
        hi = float(m.group(3)) if m.group(3) else 2.94
        test.update(llr=llr, llr_bounds=[lo, hi] if m.group(2) else None,
                    passed=llr >= hi - 0.03, failed=llr <= lo + 0.03)
        if m.group(4):
            b0, b1 = float(m.group(5)), float(m.group(6))
            test.update(elo_model=ELO_MODEL[m.group(4)], sprt=[b0, b1],
                        nonreg=(b0 + b1) / 2 < 0)
        else:
            test.update(elo_model=None, sprt=None,
                        nonreg=True if NONREG_WORDS.search(label) else None)
    else:  # fixed-games test: Total line with no SPRT
        test.update(llr=None, passed=None, failed=None, elo_model=None, sprt=None,
                    nonreg=None)
    test["reverse"] = bool(m and REVERSE_RE.search(label))
    if test["reverse"]:
        test.update(passed=test["failed"], failed=test["passed"], nonreg=True)
    if tm := TOTAL_RE.search(stats):
        n, w, l, d = map(int, tm.groups())
        test.update(games=n, w=w, l=l, d=d)
        pm = PTNML_RE.search(stats)
        test["ptnml"] = [int(x) for x in pm.groups()] if pm else None
        test["elo"], test["elo_95"], test["elo_err_model"] = elo_from_results(w, l, d, test["ptnml"])
    if em := ELO_LINE_RE.search(stats):
        test["reported_elo"] = float(em.group(1))
    if url:
        test["url"] = url
    return test


def parse_tests(body):
    lines = body.splitlines()
    tests, used = [], set()
    for i, line in enumerate(lines):
        m = LLR_RE.search(line)
        if not m:
            continue
        label, url, stats, last = test_context(lines, i)
        before, after = line[:m.start()], line[m.end():]
        if before.strip():  # "STC: LLR: ..." on one line
            label = (label + " " + before.strip()).strip()
        stats = after + "\n" + stats
        used.update(range(i, last + 1))  # only the lines this test consumed
        tests.append(make_test(label, after, stats, url, m))
    # fixed-games results ("ELO: x +- y ... Total: ...") not attached to any LLR line
    for i, line in enumerate(lines):
        if i in used or not TOTAL_RE.search(line):
            continue
        start = i
        while start > 0 and STAT_RE.search(lines[start - 1]) and start - 1 not in used:
            start -= 1
        label, url, _, _ = test_context(lines, start)
        end = i
        while end + 1 < len(lines) and end + 1 < i + 3 and STAT_RE.search(lines[end + 1]) \
                and not TOTAL_RE.search(lines[end + 1]) and not LLR_RE.search(lines[end + 1]):
            end += 1
        stats = "\n".join(lines[start:end + 1])
        used.update(range(start, end + 1))
        t = make_test(label, "", stats, url)
        t["context"] = " ".join(x.strip() for x in lines[max(0, start - 3):start])[:300]
        tests.append(t)
    # Two unlabelled SPRTs and nothing else (common in 2014): Stockfish's practice is STC
    # first, then LTC. Marked tc_source="order" so it can be filtered out.
    sprts = [t for t in tests if t["llr"] is not None]
    if len(sprts) == 2 and all(not t["tc"] and not t["label"] for t in sprts):
        sprts[0].update(tc="STC", tc_source="order")
        sprts[1].update(tc="LTC", tc_source="order")
    return tests


# ---------- PR numbers ----------

CLOSES_RE = re.compile(
    r"\b(?:closes?|resolves?)\b:?\s*(?:https?://github\.com/official-stockfish/Stockfish/pull/|#)(\d+)",
    re.I)
SF_PR_URL_RE = re.compile(r"github\.com/official-stockfish/Stockfish/pull/(\d+)")
SUBJ_PR_RE = re.compile(r"\(#(\d+)\)\s*$")


def load_pr_numbers():
    try:
        with open(PR_INDEX) as f:
            return {int(line.split("\t", 1)[0]) for line in f if line[:1].isdigit()}
    except OSError:
        return None


SF_PR_MENTION_RE = re.compile(r"github\.com/official-stockfish/Stockfish/pull/(\d+)(?![\d#])")


def pr_of(subject, body, known):
    """The PR a commit closes. Only 'closes/resolves' forms and a trailing '(#n)' in the
    subject count; other PR links in a message usually point at related work (and
    nnue-pytorch/nettest PRs). 'fixes #n' is skipped: it usually names an issue.
    Returns (number, source).
    If the PR index is available, numbers that are not PRs (issues) are dropped."""
    cands = [int(x) for x in CLOSES_RE.findall(body)]
    if m := SUBJ_PR_RE.search(subject):
        cands.append(int(m.group(1)))
    if known is not None:
        cands = [c for c in cands if c in known]
    if cands:
        return cands[-1], "closes"
    # Fallback: exactly one Stockfish PR link and no 'closes' line ("see the pull request
    # discussion: .../pull/n"). 85% of these match the PR title vs 91% for 'closes'.
    mentions = {int(x) for x in SF_PR_MENTION_RE.findall(body)}
    if len(mentions) == 1 and (known is None or next(iter(mentions)) in known):
        return mentions.pop(), "mention"
    return None, None


# ---------- tagging ----------

AREA_BY_FILE = [
    ("nnue", r"src/nnue/|\.nnue$|nnue"),
    ("search", r"src/(search|movepick|history)\.(cpp|h)$"),
    ("evaluate", r"src/evaluate\.(cpp|h)$"),
    ("eval-classical", r"src/(pawns|material|psqt|psqtab|endgame|bitbase)\.(cpp|h)$"),
    ("tt", r"src/tt\.(cpp|h)$"),
    ("time", r"src/timeman\.(cpp|h)$"),
    ("threads", r"src/(thread\w*|numa)\.(cpp|h)$"),
    ("movegen-position", r"src/(movegen|position|bitboard|types|move)\.(cpp|h)$"),
    ("tablebases", r"src/syzygy/|tbprobe"),
    ("uci-io", r"src/(uci\w*|engine|misc|benchmark|tune|score|memory|book)\.(cpp|h)$"),
    ("build-ci", r"Makefile|\.github/|^tests/|CMake|\.travis|appveyor|scripts/|net\.sh"),
    ("docs", r"README|\.md$|\.txt$|AUTHORS|Copying|CONTRIBUTING"),
]
AREA_RX = [(a, re.compile(rx)) for a, rx in AREA_BY_FILE]

# technique -> (regex, case_sensitive, gate). Matched on subject + message text before
# the first test result. Gates cut prose false positives ("the reduction in training
# time" in a net-update message): "search" tags need a file in the search or
# movegen-position areas; "nnue" tags need date >= NNUE_DATE and a file in nnue/evaluate.
TECHNIQUES = {
    "reductions-lmr": (r"\blmr\b|late move reduction|\breductions?\b", False, "search"),
    "null-move": (r"null[- ]?move|\bnmp\b", False, "search"),
    "futility": (r"futility", False, "search"),
    "razoring": (r"razor", False, "search"),
    "probcut": (r"probcut", False, "search"),
    "singular-ext": (r"singular", False, "search"),
    "extensions": (r"extension|\bextend", False, "search"),
    "lmp-movecount": (r"\blmp\b|late move pruning|move ?count", False, "search"),
    "see": (r"\bSEE\b|static exchange|\bsee_ge\b", True, "search"),
    "history": (r"history|\bhist\b", False, "search"),
    "correction-history": (r"corr(ection)?[ _-]?hist|correction value|\bcorrhist", False, "search"),
    "killers-countermoves": (r"killer|counter ?moves?|refutation", False, "search"),
    "move-ordering": (r"move ?order|movepick|move ?picker", False, "search"),
    "aspiration": (r"aspiration", False, "search"),
    "iir": (r"\biir\b|internal iterative", False, "search"),
    "qsearch": (r"qsearch|quiescen", False, "search"),
    "transposition-table": (r"\btte?s?\b|transposition|hashfull", False, None),
    "time-management": (r"time ?manage|timeman|optimum ?time|\btm\b", False, None),
    "smp-threads": (r"lazy ?smp|\bsmp\b|\bthreads?\b|\bnuma\b", False, None),
    "nnue-arch": (r"architecture|\blayers?\b|accumulator|feature ?set|halfka|halfkp|"
                  r"\bbuckets?\b|sfnnv\d|threat input|\bpsqt\b", False, "nnue"),
    "nnue-net": (r"nn-[0-9a-f]{12}|new net|\bnet\b|network|trained|training|retrain", False, "nnue"),
    "nnue-inference": (r"simd|avx|sse\d|neon|vnni|quantiz|incremental|refresh|finny", False, "nnue"),
    "tablebases": (r"syzygy|tablebase", False, None),
    "eval-scaling": (r"scale ?factor|scal(e|es|ed|ing) (down )?(the )?eval|eval\w* scal|optimism|"
                     r"complexity|50[- ]move|rule50", False, None),
    "speedup": (r"speed ?up|faster|\bnps\b|optimi[sz](e|es|ed|ing|ation)\b", False, None),
    "tuning-spsa": (r"\bspsa\b|\btuned?\b|retune|\btuning (run|session|of|was|with)", False, None),
}
TECH_RE = {k: (re.compile(rx) if cs else re.compile(rx, re.I), gate)
           for k, (rx, cs, gate) in TECHNIQUES.items()}
GATES = {
    None: lambda date, areas: True,
    "search": lambda date, areas: bool(areas & {"search", "movegen-position"}),
    "nnue": lambda date, areas: date >= NNUE_DATE and bool(areas & {"nnue", "evaluate"}),
}

# "No functional change" at line start; not when qualified ("in single thread", "for one
# thread", "apart from ..."): those patches change multi-thread or edge-case behaviour.
CODE_BLOCK_RE = re.compile(r"```.*?(```|$)", re.S)  # training commands etc.; not prose
RELEASE_RE = re.compile(r"^(Stockfish \d+(\.\d+)?\s*$|Stockfish (DD|\d{6})\b|Restore development)", re.I)
NONFUNC_RE = re.compile(r"^\W*(no|non)[- ]functional changes?\b"
                        r"(?![^\n]*\b(single|one thread|common case|apart from|multipv|smp)\b)",
                        re.I | re.M)
NET_UPDATE_RE = re.compile(
    r"nn-[0-9a-f]{12}|^(update|new|switch to)\b.{0,40}\b(net|nets|network|networks)\b|"
    r"\bupdate (the )?(default|main|small|big|large) net|^(update\b.{0,40})?(sfnnv\d|nnue[- ]architecture)", re.I)
TUNING_RE = re.compile(r"\bspsa\b|\btun(e|ed|ing)\b|retune|\bparam(eter)?s? (tweak|update)", re.I)
SPEEDUP_RE = re.compile(r"speed ?up|faster|\bnps\b|optimi[sz](e|es|ed|ing|ation)\b", re.I)
SPEEDUP_SUBJ_RE = re.compile(r"\b(prefetch\w*|unroll\w*|hoist\w*|vectori[sz]\w*|branchless)\b", re.I)
SIMPLIFY_RE = re.compile(r"simplif|\bremove|clean ?up|refactor", re.I)
BUGFIX_RE = re.compile(r"\bfix|\bbug", re.I)
NONFUNC_SUBJ_RE = re.compile(
    r"\b(rename[sd]?|renaming|naming|comments?|typos?|whitespace|formatting|indentation|"
    r"copyright|readme)\b", re.I)


TC_RANK = {"VVLTC": 4, "VLTC": 3, "LTC": 2, "STC": 1, "": 0}


def result_of(tests, subject):
    """gain / mixed / nonreg / tested-not-passed / untested, from SPRT results.

    gain needs a passed gainer SPRT at the longest time control at which a
    single-thread gainer SPRT was decided; "mixed" = passed at a shorter TC but only
    failed at the longest one tried (e.g. passed STC, failed LTC)."""
    passed = [t for t in tests if t.get("passed")]
    gainer = [t for t in tests if t["nonreg"] is False and (t.get("passed") or t.get("failed"))
              and not t["smp"]]
    if any(t["nonreg"] is False for t in passed):
        top = max((TC_RANK[t["tc"]] for t in gainer), default=0)
        if top and not any(t["passed"] for t in gainer if TC_RANK[t["tc"]] == top):
            if any(t["nonreg"] is True for t in passed):
                return "nonreg"
            return "mixed"
        return "gain"
    if any(t["nonreg"] is True for t in passed):
        return "nonreg"
    if passed:  # bounds not printed (early 2013): fall back on the subject
        return "nonreg" if SIMPLIFY_RE.search(subject) else "gain"
    return "tested-not-passed" if tests else "untested"


def kind_of(subject, body, files, date, result, areas):
    """One primary kind per commit, first rule that fires wins."""
    if RELEASE_RE.search(subject):
        return "release"
    if files and all(re.search(r"Makefile|\.github/|^tests/|CMake|\.travis|appveyor|scripts/|"
                               r"net\.sh|README|\.md$|\.txt$|AUTHORS|Copying|CONTRIBUTING|"
                               r"^\.|\.yml$|\.cfg$", f) for f in files):
        return "build-ci-docs"
    if date >= NNUE_DATE and NET_UPDATE_RE.search(subject):
        return "net-update"
    if TUNING_RE.search(subject):
        return "tuning"
    if SPEEDUP_RE.search(subject):
        return "speedup"
    # Bench-neutral gain: "No functional change" means the bench node count is unchanged,
    # so a passed gainer SPRT points to speed. Time management and multi-thread changes
    # are bench-neutral too; the time area is excluded (e.g. ad5d86c7). Low-level
    # optimisation words in the subject count too.
    if NONFUNC_RE.search(body) and (
            (result in ("gain", "mixed") and "time" not in areas)
            or SPEEDUP_SUBJ_RE.search(subject)):
        return "speedup"
    if NONFUNC_RE.search(body) or (result == "untested" and NONFUNC_SUBJ_RE.search(subject)):
        return "non-functional"
    if SIMPLIFY_RE.search(subject):
        return "simplification"
    if BUGFIX_RE.search(subject):
        return "bugfix"
    return "other-functional"


def pick_elo(tests, tc):
    """Elo of the first passed gainer test at `tc`, single-thread runs only (SMP runs
    measure something else and are sometimes run with MultiPV or Skill settings)."""
    c = [t for t in tests if t["tc"] == tc and t.get("passed") and t["nonreg"] is not True
         and not t["smp"] and not t["special"] and t.get("elo") is not None]
    return c[0]["elo"] if c else None


# Fixed-games runs against an older engine or before/after pairs ("Test contempt 21
# against SF 7", "With patch applied", "Before") do not measure patch vs master.
REF_RUN_RE = re.compile(r"\bagainst\b|\bvs\.?\b|\bbefore\b|\bafter\b|with(out)? (this |the )?patch|"
                        r"\bSF ?\d|\b\d+\.\d+\.\d+\b|revert", re.I)


def pick_fixed(tests):
    """(Elo, TC) of the first single-thread, default-config fixed-games run that is not a
    comparison against another reference."""
    def ok(t):
        text = t["label"] + " " + t.get("context", "")
        _, _, th = tc_of(text)
        return not (REF_RUN_RE.search(text) or SPECIAL_RE.search(text) or (th and th > 1)
                    or re.search(r"\bsmp\b", text, re.I))
    c = [t for t in tests if t["llr"] is None and not t["smp"] and not t["special"]
         and t.get("elo") is not None and ok(t)]
    return (c[0]["elo"], c[0]["tc"] or "?") if c else (None, None)


def pick_smp(tests):
    """Elo of the first passed gainer SMP SPRT, else the first SMP fixed-games run."""
    c = [t for t in tests if t["smp"] and not t["special"] and t.get("elo") is not None
         and ((t.get("passed") and t["nonreg"] is not True) or t["llr"] is None)]
    c.sort(key=lambda t: t["llr"] is None)  # SPRTs first
    return c[0]["elo"] if c else None


def elo_fields(tests, result, special):
    """LTC Elo plus flagged fallbacks. elo_best = LTC, else VLTC/VVLTC, else STC (all
    passed single-thread gainer SPRTs), else fixed-games Elo when the commit passed no
    gainer SPRT. elo_best_src says which one was used."""
    if special:
        return dict(elo_stc=None, elo_ltc=None, elo_vltc=None, elo_fixed=None,
                    elo_fixed_tc=None, elo_smp=None, elo_best=None, elo_best_src=None)
    f = dict(elo_stc=pick_elo(tests, "STC"), elo_ltc=pick_elo(tests, "LTC"),
             elo_vltc=pick_elo(tests, "VLTC"), elo_vvltc=pick_elo(tests, "VVLTC"),
             elo_smp=pick_smp(tests))
    f["elo_fixed"], f["elo_fixed_tc"] = (pick_fixed(tests) if result not in ("gain", "mixed")
                                         else (None, None))
    f["elo_best"], f["elo_best_src"] = None, None
    for key, src in (("elo_ltc", "LTC"), ("elo_vltc", "VLTC"), ("elo_vvltc", "VVLTC"),
                     ("elo_stc", "STC"), ("elo_fixed", "fixed")):
        if f[key] is not None:
            f["elo_best"], f["elo_best_src"] = f[key], src
            break
    f["elo_vltc"] = f["elo_vltc"] if f["elo_vltc"] is not None else f.pop("elo_vvltc")
    f.pop("elo_vvltc", None)
    return f


def main():
    known_prs = load_pr_numbers()
    rows = []
    for sha, date, author, body, files in git_log():
        subject = body.splitlines()[0] if body else ""
        tests = parse_tests(body)
        for t in tests:  # 6da1590de0 (2024) writes normalized bounds in [] brackets
            if t["elo_model"] == "BayesElo" and date >= NORMALIZED_DATE:
                t["elo_model"] = "normalized (from date)"
        areas = {a for a, rx in AREA_RX for f in files if rx.search(f)}
        result = result_of(tests, subject)
        pre = re.split(r"LLR:|Total:", CODE_BLOCK_RE.sub(" ", body), maxsplit=1)[0][:800]
        kind = kind_of(subject, body, files, date, result, areas)
        if kind == "net-update":
            areas.add("nnue")
        if files and not areas:
            areas.add("other")
        text = subject + "\n" + pre
        techs = sorted(k for k, (rx, gate) in TECH_RE.items()
                       if GATES[gate](date, areas) and rx.search(text))
        pr, pr_src = pr_of(subject, body, known_prs)
        rows.append({
            "sha": sha, "date": date, "author": author, "subject": subject,
            "pr": pr, "pr_source": pr_src,
            "files": files, "areas": sorted(areas), "techniques": techs,
            "result": result, "kind": kind,
            "nonfunctional_marker": bool(NONFUNC_RE.search(body)),
            "tests": tests,
            "special_config": bool(SPECIAL_SUBJ_RE.search(subject)),
            **elo_fields(tests, result, bool(SPECIAL_SUBJ_RE.search(subject))),
        })

    DATA.mkdir(parents=True, exist_ok=True)
    JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(JSONL, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    fmt = lambda x: "" if x is None else str(x)
    with open(DATA / "stockfish-commits.tsv", "w") as f:
        f.write("date\tsha\tpr\tpr_source\tresult\tkind\tareas\ttechniques\tn_tests\telo_stc\telo_ltc"
                "\telo_vltc\telo_fixed\telo_fixed_tc\telo_best\telo_best_src\telo_smp\tn_files\tsubject\n")
        for r in rows:
            f.write("\t".join(fmt(x) for x in [
                r["date"], r["sha"][:10], r["pr"], r["pr_source"], r["result"], r["kind"],
                ",".join(r["areas"]), ",".join(r["techniques"]), len(r["tests"]),
                r["elo_stc"], r["elo_ltc"], r["elo_vltc"], r["elo_fixed"], r["elo_fixed_tc"],
                r["elo_best"], r["elo_best_src"], r["elo_smp"], len(r["files"]),
                r["subject"].replace("\t", " ")]) + "\n")
    with open(DATA / "stockfish-tests.tsv", "w") as f:
        f.write("date\tsha\ttc\ttc_source\tthreads\tllr\tpassed\telo_model\tsprt_elo0"
                "\tsprt_elo1\tnonreg\tgames\tw\tl\td\tptnml\telo\telo_95\turl\tlabel\n")
        for r in rows:
            for t in r["tests"]:
                sp = t["sprt"] or [None, None]
                f.write("\t".join(fmt(x) for x in [
                    r["date"], r["sha"][:10], t["tc"], t["tc_source"], t["threads"],
                    t["llr"], t["passed"], t["elo_model"], sp[0], sp[1], t["nonreg"],
                    t.get("games"), t.get("w"), t.get("l"), t.get("d"),
                    ",".join(map(str, t["ptnml"])) if t.get("ptnml") else "",
                    t.get("elo"), t.get("elo_95"), t.get("url"),
                    t["label"].replace("\t", " ")]) + "\n")
    write_summary(rows, known_prs)
    print(f"parsed {len(rows)} commits, {sum(len(r['tests']) for r in rows)} tests -> "
          f"{DATA}/stockfish-{{commits,tests}}.tsv, {JSONL}, {DOC}")


# ---------- summary ----------

def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "-"


def med(xs):
    return f"{statistics.median(xs):.2f}" if xs else "-"


def write_summary(rows, known_prs):
    head = subprocess.run(["git", "-C", str(CLONE), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    tests = [t for r in rows for t in r["tests"]]
    sprt = [t for t in tests if t["llr"] is not None]
    tested = [r for r in rows if r["tests"]]
    since2014 = [r for r in rows if r["date"] >= "2014"]
    L = []
    w = L.append
    w("# Stockfish commit history: parsed statistics\n")
    w(f"Generated by `scripts/parse-stockfish-commits.py` from official-stockfish/Stockfish "
      f"`{head}` (the pin in `reference/PINS.tsv`). The sections above the hand-written "
      "marker are regenerated on every run; do not edit them by hand.\n")
    w("Per-commit table: [`data/stockfish-commits.tsv`](data/stockfish-commits.tsv). "
      "Per-test table: `data/stockfish-tests.tsv` (not committed; the script regenerates it). "
      "Full JSON with file lists: `build/stockfish-commits-parsed.jsonl` (git-ignored; "
      "rerun the script).\n")

    w("## Definitions\n")
    w("- **result** (from SPRT lines in the message): *gain* = passed an SPRT with gainer "
      "bounds (midpoint of the Elo bounds > 0) at the longest single-thread TC tried; "
      "*mixed* = passed a gainer SPRT at a shorter TC but failed at the longest; "
      "*nonreg* = passed only "
      "non-regression bounds (midpoint <= 0, e.g. `<-1.75,0.25>`); *tested-not-passed* = "
      "results present but none passed (fixed-game runs, failed or stopped tests quoted "
      "for context); *untested* = no results in the message.")
    w("- **kind** (from subject, body and files; first rule wins): release (\"Stockfish 15\", "
      "\"Restore development version\") > build-ci-docs (only "
      "non-source files) > net-update (subject names a net `nn-xxxx`, \"update ... net\", "
      "or an SFNNv architecture bump; from 2020-08 only) > tuning (spsa/tune) > speedup > "
      "non-functional (\"No functional change\" line) > simplification (simplify/remove/"
      "cleanup/refactor subject) > bugfix > other-functional. speedup also covers a \"No "
      "functional change\" commit that passed a gainer SPRT (a bench-neutral gain, usually "
      "speed; commits touching time management are left out because they are "
      "bench-neutral without being faster) or whose subject says "
      "prefetch/unroll/hoist/vectorize/branchless.")
    w("- **areas**: from files touched (one commit can have several). `evaluate` is "
      "src/evaluate.*: classical eval before 2020-08, NNUE glue after 2023-07, both in "
      "between. Net-update commits also get `nnue`.")
    w("- **techniques**: keyword tags on the subject and the text before the first test "
      "result. NNUE tags only from 2020-08-06. Heuristic; see Accuracy below.")
    w("- **LTC Elo**: logistic Elo recomputed from W/L/D of the first passed gainer LTC "
      "test (single-thread only, default configuration: tests labelled MultiPV, Skill, "
      "Chess960/FRC, contempt, ponder or MAX_PLY, and commits whose subject names MultiPV, "
      "Skill, Chess960/FRC or ponder, are left out). Not the SPRT bound and not fishtest's normalized Elo.")
    w("- **Fallback Elo** (separate columns, never mixed into LTC Elo): *best Elo* = LTC Elo, "
      "else VLTC, else VVLTC, else STC (passed single-thread gainer SPRTs), else the "
      "first single-thread default-config fixed-games run when the commit passed no "
      "gainer SPRT. `elo_best_src` in the TSV says which. *SMP Elo* (TSV only) = first "
      "passed multi-thread gainer SPRT, else first multi-thread fixed-games run.\n")

    kinds = Counter(r["kind"] for r in rows)
    results = Counter(r["result"] for r in rows)
    w("## Totals\n")
    w(f"- Non-merge commits: {len(rows)}; with at least one parsed test: {len(tested)}; "
      f"tests parsed: {len(tests)} ({len(sprt)} SPRT, {len(tests) - len(sprt)} fixed-games).")
    w("- By result: " + ", ".join(f"{k} {v}" for k, v in results.most_common()))
    w("- By kind: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()) + "\n")

    w("## Field coverage\n")
    w("| field | covered | of | rate |")
    w("|---|---|---|---|")
    cov = [
        ("commits with >=1 test (all years)", len(tested), len(rows)),
        ("commits with >=1 test (2014 on)", sum(1 for r in since2014 if r["tests"]), len(since2014)),
        ("SPRT tests with time control identified", sum(1 for t in sprt if t["tc"]), len(sprt)),
        ("SPRT tests with Elo bounds (model known)", sum(1 for t in sprt if t["sprt"]), len(sprt)),
        ("SPRT tests with gain/nonreg decided", sum(1 for t in sprt if t["nonreg"] is not None), len(sprt)),
        ("tests with W/L/D (Elo computed)", sum(1 for t in tests if t.get("elo") is not None), len(tests)),
        ("tests with pentanomial counts", sum(1 for t in tests if t.get("ptnml")), len(tests)),
        ("tests with fishtest URL", sum(1 for t in tests if t.get("url")), len(tests)),
        ("gain commits with LTC Elo", sum(1 for r in rows if r["result"] == "gain" and r["elo_ltc"] is not None),
         results["gain"]),
        ("gain commits with any Elo (best Elo)", sum(1 for r in rows if r["result"] == "gain" and r["elo_best"] is not None),
         results["gain"]),
        ("commits with PR number (2014-06 on)", sum(1 for r in rows if r["date"] >= "2014-06" and r["pr"]),
         sum(1 for r in rows if r["date"] >= "2014-06")),
    ]
    for name, a, b in cov:
        w(f"| {name} | {a} | {b} | {pct(a, b)} |")
    w("")
    w("SPRT bounds by Elo model: " + ", ".join(
        f"{k or 'none printed'} {v}" for k, v in Counter(t["elo_model"] for t in sprt).most_common()) + ".\n")

    w("## By year\n")
    w("| year | commits | tested | gain | nonreg | net-update | tuning | non-functional | "
      "gain with LTC Elo | median LTC Elo |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["date"][:4]].append(r)
    for y in sorted(by_year):
        rs = by_year[y]
        res, kd = Counter(r["result"] for r in rs), Counter(r["kind"] for r in rs)
        ltc = [r["elo_ltc"] for r in rs if r["result"] == "gain" and r["elo_ltc"] is not None]
        w(f"| {y} | {len(rs)} | {sum(1 for r in rs if r['tests'])} | {res['gain']} | "
          f"{res['nonreg']} | {kd['net-update']} | {kd['tuning']} | {kd['non-functional']} | "
          f"{len(ltc)} | {med(ltc)} |")
    w("")

    w("## Kind by result (gainers vs simplifications)\n")
    res_cols = ["gain", "mixed", "nonreg", "tested-not-passed", "untested"]
    w("| kind | " + " | ".join(res_cols) + " | total |")
    w("|---|" + "---|" * (len(res_cols) + 1))
    kr = defaultdict(Counter)
    for r in rows:
        kr[r["kind"]][r["result"]] += 1
    for k, _ in kinds.most_common():
        w(f"| {k} | " + " | ".join(str(kr[k][c]) for c in res_cols) + f" | {kinds[k]} |")
    w("")

    def tag_table(key, title, note):
        agg = defaultdict(lambda: {"n": 0, "gain": 0, "nonreg": 0, "elo": [], "best": [], "stc": [],
                                   "first": "9999", "last": ""})
        for r in rows:
            for t in r[key]:
                a = agg[t]
                a["n"] += 1
                a["first"], a["last"] = min(a["first"], r["date"]), max(a["last"], r["date"])
                if r["result"] == "gain":
                    a["gain"] += 1
                    if r["elo_ltc"] is not None:
                        a["elo"].append(r["elo_ltc"])
                    if r["elo_stc"] is not None:
                        a["stc"].append(r["elo_stc"])
                elif r["result"] == "nonreg":
                    a["nonreg"] += 1
                if r["elo_best"] is not None and (r["result"] == "gain" or r["elo_best_src"] == "fixed"):
                    a["best"].append(r["elo_best"])
        w(f"## {title}\n")
        w(note + "\n")
        w("| tag | commits | gain | nonreg | gain with LTC Elo | median LTC Elo | summed LTC Elo | "
          "with STC Elo | summed STC Elo | with best Elo | summed best Elo | first | last |")
        w("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for t, a in sorted(agg.items(), key=lambda kv: -sum(kv[1]["elo"])):
            w(f"| {t} | {a['n']} | {a['gain']} | {a['nonreg']} | {len(a['elo'])} | {med(a['elo'])} | "
              f"{sum(a['elo']):.1f} | {len(a['stc'])} | {sum(a['stc']):.1f} | {len(a['best'])} | "
              f"{sum(a['best']):.1f} | {a['first'][:7]} | {a['last'][:7]} |")
        w("")

    tag_table("areas", "Elo reported per code area (files touched)",
              "Sorted by summed LTC Elo of gain commits. STC columns: gain commits with a passed "
              "STC gainer SPRT. *Best Elo* adds the fallbacks (VLTC/VVLTC/STC-only gains and "
              "fixed-games Elo of commits with no gainer SPRT; see Definitions); it mixes time "
              "controls, so use it to see what the LTC column misses, not to rank. A commit "
              "touching several areas counts in each, so no column adds up to anything.")
    tag_table("techniques", "Elo reported per technique (keyword tags)",
              "Same columns. Tags overlap heavily (one commit often gets 3-5).")

    w("## Elo reported per kind\n")
    w("| kind | gain commits | with LTC Elo | median LTC Elo | summed LTC Elo | with STC Elo | "
      "median STC Elo | summed STC Elo |")
    w("|---|---|---|---|---|---|---|---|")
    for k, _ in kinds.most_common():
        g = [r for r in rows if r["kind"] == k and r["result"] == "gain"]
        e = [r["elo_ltc"] for r in g if r["elo_ltc"] is not None]
        st = [r["elo_stc"] for r in g if r["elo_stc"] is not None]
        w(f"| {k} | {kr[k]['gain']} | {len(e)} | {med(e)} | {sum(e):.1f} | {len(st)} | {med(st)} | "
          f"{sum(st):.1f} |")
    w("")

    def commit_table(title, note, sel, key, label, n, extra=None):
        w(f"## {title}\n")
        w(note + "\n")
        src_h, src_sep = (" source |", "---|") if extra else ("", "")
        w(f"| date | commit | PR | kind | {label} |{src_h} areas | subject |")
        w("|---|---|---|---|---|" + src_sep + "---|---|")
        for r in sorted(sel, key=lambda r: -r[key])[:n]:
            pr = f"#{r['pr']}" if r["pr"] else ""
            subj = r["subject"][:70].replace("|", "/")
            src = f" {extra(r)} |" if extra else ""
            w(f"| {r['date']} | {r['sha'][:8]} | {pr} | {r['kind']} | {r[key]:.2f} |{src} "
              f"{','.join(r['areas'])} | {subj} |")
        w("")

    nolt = [r for r in rows if r["elo_ltc"] is None and r["elo_best"] is not None
            and (r["result"] == "gain" or r["elo_best_src"] == "fixed")]
    src_counts = Counter(r["elo_best_src"] for r in nolt)
    commit_table(
        "Largest gains without an LTC Elo",
        "Commits the LTC tables miss: gains measured only at VLTC/VVLTC or STC, and commits "
        "with no gainer SPRT whose fixed-games run shows the effect (e.g. adding NNUE, which "
        "was SPRT-tested only for non-regression). Counts by source: "
        + ", ".join(f"{k} {v}" for k, v in src_counts.most_common())
        + ". Top 30 by best Elo; the source column gives the TC. Fixed-games Elo is "
        "not selected by an SPRT, so it has no SPRT stopping bias, but the run may compare "
        "something other than the final patch.",
        nolt, "elo_best", "best Elo", 30,
        lambda r: r["elo_best_src"] + (f" @ {r['elo_fixed_tc']}" if r["elo_best_src"] == "fixed" else ""))
    commit_table(
        "Largest speedups (STC Elo)",
        "Gain commits of kind speedup, by Elo of the passed STC SPRT. Speedups are usually "
        "tested at STC only. Top 20.",
        [r for r in rows if r["kind"] == "speedup" and r["result"] == "gain" and r["elo_stc"] is not None],
        "elo_stc", "STC Elo", 20)
    commit_table(
        "Largest multi-thread gains (SMP Elo)",
        "Commits by SMP Elo: the first passed multi-thread gainer SPRT, else the first "
        "multi-thread fixed-games run. These are left out of every other Elo column. "
        "Thread counts and TCs differ between rows, so compare within the table only "
        "loosely. Top 10.",
        [r for r in rows if r["elo_smp"] is not None], "elo_smp", "SMP Elo", 10)

    w("## Largest measured single gains (LTC)\n")
    w("Top 40 gain commits by recomputed LTC Elo. Verify each before citing it.\n")
    w("| date | commit | PR | kind | LTC Elo | areas | subject |")
    w("|---|---|---|---|---|---|---|")
    top = sorted((r for r in rows if r["result"] == "gain" and r["elo_ltc"] is not None),
                 key=lambda r: -r["elo_ltc"])[:40]
    for r in top:
        pr = f"#{r['pr']}" if r["pr"] else ""
        subj = r["subject"][:70].replace("|", "/")
        w(f"| {r['date']} | {r['sha'][:8]} | {pr} | {r['kind']} | {r['elo_ltc']:.2f} | "
          f"{','.join(r['areas'])} | {subj} |")
    w("")

    hand = ""
    if DOC.exists():
        old = DOC.read_text()
        if HAND_MARKER in old:
            hand = old.split(HAND_MARKER, 1)[1]
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(L) + "\n" + HAND_MARKER + (hand or "\n"))


if __name__ == "__main__":
    main()
