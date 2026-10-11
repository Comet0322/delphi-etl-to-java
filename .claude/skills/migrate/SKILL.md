---
name: migrate
description: Orchestrates a legacy ETL (VB6/Delphi) to Java migration end to end — analyze, clarify, implement, verify-loop, closeout. Use when the user asks to migrate legacy ETL programs to Java, or to resume such a migration.
---

# migrate

Runs the five stage skills in order. State lives in `status.yaml`; read it
first, resume from `stage`. Never rely on conversation memory.

## Inputs (ask only if missing)

- `legacy.source_dir` — where the legacy source is
- `domain_knowledge.path` — directory of the domain-knowledge skill, itself a
  skill under `.claude/skills/` (e.g. `delphi-to-java-etl`); may be empty
- `mode` — `interactive` (default) or `unattended`

## Stages

| # | Skill | Human involved? | Produces |
|---|---|---|---|
| 1 | `migrate-analyze` | no | `etl/*/inventory.yaml` (draft), `needs.yaml` |
| 2 | `migrate-clarify` | once, `interactive` only | `charter.yaml` (frozen), `compare.yaml` |
| 3 | `migrate-implement` | no | Java code, `target_loc` filled |
| 4 | `migrate-verify-loop` | no | `results/compare/run-*.json`, `status.yaml` |
| 5 | `migrate-closeout` | once, at the end | `report/`, `knowledge-proposals.md` |

## Rules that apply to every stage

1. **Legacy behavior is the spec.** Preserve it, including quirks. Deviations
   only if the user explicitly asked.
2. **Ask only high-level questions** (architecture, which library for what,
   template, intentional deviations). Never ask about syntax or about
   semantics the legacy code already answers.
3. **Single writer per file.** Frozen files (`charter.yaml`, `compare.yaml`,
   domain-knowledge files) are never edited by the agent.
4. **Never make diffs vanish by loosening the comparison.** A residual diff you
   cannot explain is a blocker, not something to massage.
5. **Commit at the end of each stage per ETL** with message
   `[ETL-001][stage] detail`, branch `etl/ETL-001`. Data files and baseline
   samples are never committed.
6. **No human available?** (`mode: unattended`) Do not stop to ask. Use each
   question's default, record `source: assumed`, keep going, list assumptions
   in the report. Truly unresolvable items become `blocked`.

## Draft vs confirmed

A run with any `source: assumed` decision is a **draft**: `charter.status:
draft`, tag `charter-draft-vN`, never merged to the main line. After a human
answers the open items, tag `charter-vN`, re-verify only the ETLs whose
`affects` list was touched.

## Resuming

`status.yaml` → find first ETL not `done` and not `blocked`, continue its
stage. If everything is `done` or `blocked`, go to `migrate-closeout`.
