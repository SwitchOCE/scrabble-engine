# Engine catalogue

Pinned commits: `pins.tsv` (written by `scripts/fetch-references.sh`).

| Engine | Source | Language | Licence | Status | Dossier |
| --- | --- | --- | --- | --- | --- |
| Quackle | [quackle/quackle](https://github.com/quackle/quackle) | C++ (Qt GUI) | GPL-3.0 | Open, maintained. Championship Player still a reference strength. | [quackle.md](quackle.md) |
| Macondo | [domino14/macondo](https://github.com/domino14/macondo) | Go | GPL-3.0 | Open, active. Powers Woogles BestBot. | [macondo.md](macondo.md) |
| MAGPIE | [jvc56/MAGPIE](https://github.com/jvc56/MAGPIE) | C | GPL-3.0 | Open, very active (pin `b781018`, 2026-11-15). Started as a C rewrite of Macondo, now ahead of it: BAI simulation with rack inference, ABDADA endgame, 1–4-in-bag PEG, census leavegen. Evaluation is still tables (KLV leaves, linear PAT, win% table at sim leaves); a sim-leaf model (#527) and a GPU value net (branch `vn-nnue-m5`) are experiments, not in main. | [magpie.md](magpie.md) |
| wolges | [andy-k/wolges](https://github.com/andy-k/wolges) | Rust | MIT | Open, active. Fast movegen, KWG/KLV formats used by Woogles. | [wolges.md](wolges.md) |
| Elise | Closed (Windows) | ? | Proprietary | The owner's "Eclipse" (decided). Deferred until the open engines are measured. Need a working build. | [elise.md](elise.md) |
| Maven | Closed (Brian Sheppard; shipped in Hasbro products) | ? | Proprietary | Need a working build. 2002 paper is public. | [maven.md](maven.md) |

Also relevant: [woogles-io/liwords](https://github.com/woogles-io/liwords) (AGPL-3.0),
the Woogles server; useful for game formats and bot integration, not an engine.

Lexicon for all matches and benchmarks: Collins, edition CSW24 (see "Decided by the project owner" in `../research-plan.md`).

Dossiers are created as research starts; missing links are expected.

Headless play and match-harness reuse for Quackle, Macondo, MAGPIE and wolges:
[../harness/reuse-check.md](../harness/reuse-check.md).
