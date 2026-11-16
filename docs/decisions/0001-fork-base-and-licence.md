# 0001: Fork base and licence

Status: licence **decided** (2026-11-16); fork base **open** (decided at the end of
research track R6, stage-1 step 5)

## Question

Do we fork an existing engine, and which? This also sets our licence.

## Options

| Option | Licence result |
| --- | --- |
| Fork Quackle / Macondo / MAGPIE | GPL-3.0 (must stay GPL) |
| Fork wolges | Any licence that keeps the MIT notice |
| Write from scratch, learning from all of them | Our choice |

## Evidence

Filled in from the engine dossiers.

## Decision

**Licence (owner, 2026-11-16):** "GPL's fine. It'd be preferable to be MIT, but I'm okay
with GPL as well." GPL-3.0 is acceptable; MIT is preferred.

How R6 applies it (from the approved stage-1 plan, `docs/plans/stage1-plan.md`, step 5;
not the owner's words): licence is a tiebreaker, not a blocker. Choose on strength,
speed and how easily a neural evaluation fits. Prefer the MIT option (wolges, or our own
code) only when the call is close. The language follows the fork; network training is in
Python either way.

**Fork base:** open until R6.

## Consequences
