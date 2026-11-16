# Engine catalogue

Pinned commits: `pins.tsv` (written by `scripts/fetch-references.sh`).

| Engine | Source | Language | Licence | Status | Dossier |
| --- | --- | --- | --- | --- | --- |
| Quackle | [quackle/quackle](https://github.com/quackle/quackle) | C++ (Qt GUI) | GPL-3.0 | Open; 2026 work (threading, per-playahead randomisation, tests, CI, packaging) left search rules and tables unchanged. Championship Player: 2-ply sim of ≤14 candidates at ≤330 samples each (66 s cap on the sim only), no inference, 1–2-in-bag pre-endgame (≤396 s), heuristic non-exact endgame (no time limit). Historical strength reference; likely a weak bar today (inference, unmeasured). CSW leaves correlate 0.977–0.979 with CSW24 tables. | [quackle.md](quackle.md) |
| Macondo | [domino14/macondo](https://github.com/domino14/macondo) | Go | GPL-3.0 | Open, active. Powers Woogles BestBot. Ships a CSW24 transformer value net (1-ply ranker, level with a 2-ply sim in NWL23); Bayesian rack inference (+0.8 win pts); PEG only at 1 in bag. Moving onto MAGPIE's core (#538, open). | [macondo.md](macondo.md) |
| MAGPIE | [jvc56/MAGPIE](https://github.com/jvc56/MAGPIE) | C | GPL-3.0 | Open, very active (pin `b781018`, 2026-11-15). Started as a C rewrite of Macondo, now ahead of it: BAI simulation with rack inference, ABDADA endgame, 1–4-in-bag PEG, census leavegen. Evaluation is still tables (KLV leaves, linear PAT, win% table at sim leaves); a sim-leaf model (#527) and Macondo's transformer value net on Apple GPUs (branch `claude/value-net-pat`) and a GPU value net (`vn-nnue-m5`, unpublished; architecture UNVERIFIED) are experiments, not in main, with no equal-time sim result. | [magpie.md](magpie.md) |
| wolges | [andy-k/wolges](https://github.com/andy-k/wolges) | Rust | MIT | Open, very active. Full engine: sim with inference, exact endgame, PEG; leave lab behind the `.klv2` format. Gaps vs MAGPIE: parallel endgame, PEG in play, clocked autoplay. | [wolges.md](wolges.md) |
| Elise | Closed (Windows) | ? | Proprietary | The owner's "Eclipse" (decided). Deferred until the open engines are measured. Need a working build. | [elise.md](elise.md) |
| Maven | Closed (Brian Sheppard; shipped in Hasbro products) | ? | Proprietary | Need a working build. 2002 paper is public. | [maven.md](maven.md) |

Also relevant: [woogles-io/liwords](https://github.com/woogles-io/liwords) (AGPL-3.0),
the Woogles server; useful for game formats and bot integration, not an engine.

Lexicon for all matches and benchmarks: Collins, edition CSW24 (see "Decided by the project owner" in `../research-plan.md`).

Dossiers are created as research starts; missing links are expected.

Headless play and match-harness reuse for Quackle, Macondo, MAGPIE and wolges:
[../harness/reuse-check.md](../harness/reuse-check.md).
