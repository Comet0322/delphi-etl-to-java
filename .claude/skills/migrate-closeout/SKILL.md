---
name: migrate-closeout
description: Stage 5 of a legacy ETL to Java migration. Generates the per-ETL report from inventory and compare results, lists blocked items and assumptions for the user, and writes knowledge-proposals.md for merging back into the domain-knowledge skill. Use from the migrate skill when every ETL is done or blocked.
---

# migrate-closeout

## 1. Report (generated, never hand-written)

```
python3 scripts/report.py --etl-dir etl --results results/compare --out report
```

Produces one table per ETL: legacy operation (with file:line) ↔ data and
rule ↔ Java location ↔ verification status/evidence run. Top of the report
states `DRAFT` and lists every `source: assumed` decision when the charter is
a draft.

## 2. Knowledge proposals

Write `knowledge-proposals.md` — **never edit the domain-knowledge skill
directly**. Include only:

- decisions the user answered in clarify (`source: user`), and
- legacy behaviors proven by a comparison run (cite op_id and run number).

Format each as a proposed line for the domain knowledge's `SKILL.md`
(feature → handling table) or `rule.md`.
Exclude guesses and anything unverified.

## 3. Hand over

Print for the user, in this order:
1. ETLs `done` / `blocked` counts.
2. Each blocked ETL: code, what was tried, what you need from them.
3. Assumed decisions (if draft) and which ETLs they affect.
4. Path of the report and of `knowledge-proposals.md`.

Update `status.yaml` `stage: done`. Commit `[closeout] report`.
