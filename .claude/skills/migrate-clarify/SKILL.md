---
name: migrate-clarify
description: Stage 2 of a legacy ETL to Java migration. Matches the needs the project has against the domain-knowledge skill, asks the user only the high-level questions it does not cover (or applies defaults when unattended), then writes and freezes charter.yaml and compare.yaml. Use from the migrate skill.
---

# migrate-clarify (the only stage that may ask the user)

## 1. Find the gaps

Read `<domain_knowledge.path>/SKILL.md` and `rule.md`. For each need in
`needs.yaml`, decide:

| The domain knowledge… | Action |
|---|---|
| states how to handle it | use it; `source: skill` |
| says "preserve legacy" or only a semantic rule | keep legacy behavior; do not ask |
| says "not covered: ask", or is silent | high-level gap → question (if the need is high level) |

Judge by what is written, not by what you would guess the company does.
List in the charter which needs you matched to which document section, so the
coverage check is auditable.

A need is **high level** if it is about architecture, which library or tool
implements a function, project template, deployment/scheduling, output file
formats, or an intentional deviation from legacy. Anything about syntax or
data semantics is **not** a question: preserve legacy and let verification
prove it.

Also add for confirmation: the intended target shape (package/class layout)
unless the domain knowledge decided it.

## 2. Every question carries a default

```
Q: Which library should write the output CSV?
   default: java.io + java.nio only
   why asked: legacy writes a delimited file; domain knowledge is silent
```

Batch **all** questions into one message, deduplicated across ETLs.

## 3. Resolve

- `interactive`: ask once, wait, record answers with `source: user`.
- `unattended`: take each default with `source: assumed`; record `affects`
  (op_ids) so an overturned assumption can be re-verified selectively. Set
  `charter.status: draft`.

## 4. Write the frozen files

1. `charter.yaml` from the template: legacy/target/template/domain path,
   `decisions` list, thresholds from the template unless the user said
   otherwise, `frozen_extra` = glob of the domain-knowledge files.
2. `compare.yaml` from the template: one dataset per output table of each ETL.
   **Strict by default.** Set tolerances only if the user or the domain
   knowledge states them, per column. Use the baseline/candidate naming the
   domain knowledge defines.
3. `python3 scripts/freeze.py freeze`
4. Commit `[charter][clarify] frozen`, tag `charter-v1` (or
   `charter-draft-v1` when any decision is `assumed`).
5. `status.yaml`: `stage: implement`, `charter`, `assumed_count`.

After this point the hook refuses edits to the frozen files. Changing them
requires a human to run `scripts/freeze.py unfreeze "<reason>"`.
