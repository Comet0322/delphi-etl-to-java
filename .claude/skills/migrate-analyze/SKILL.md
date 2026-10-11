---
name: migrate-analyze
description: Stage 1 of a legacy ETL to Java migration. Reads the legacy source without asking the user and produces draft inventory.yaml files (every operation, with implicit behavior) plus needs.yaml (which knowledge topics the project touches). Use from the migrate skill or when asked to analyze legacy ETL code.
---

# migrate-analyze (no human involved)

Template files: `.claude/skills/migrate/templates/`.

## Steps

1. **Make a UTF-8 working copy** of the legacy source into
   `legacy.utf8_copy_dir`. Detect Big5/CP950 vs UTF-8 by trial decoding; never
   modify the originals. Include form definition files (`.dfm`, `.frm`) —
   calculated fields, filters and master/detail links live there.
2. **Split into ETLs.** One ETL = one unit of work that reads inputs and writes
   outputs. Assign ids `ETL-001…` in a stable order; record `depends_on` when
   one ETL reads another's output.
3. **For each ETL write `etl/<ID>/inventory.yaml`** from
   `inventory.template.yaml`:
   - List operations in execution order. One op = one thing done to one dataset.
   - `source_loc` is mandatory (file:line).
   - For **every** operation answer all `implicit` checklist items, with
     `loc`. Do not leave them out. `applies: false` still needs a look at the
     code, not a guess.
   - Read event handlers, unit-level globals, initialization sections,
     dataset properties (Filter, IndexFieldNames, MasterSource), `.dfm`
     calculated fields, and swallowed exceptions.
   - Mark `confidence: needs_human` only when the code cannot tell you (e.g. a
     business rule hidden behind a magic constant, behavior depending on data
     you cannot see).
4. **Write `needs.yaml`**: the list of features/capabilities the project
   touches (database access, file output, encodings, money, dates,
   scheduling, logging...), each with evidence.
   ```yaml
   needs:
     - need: writes a fixed-width text file
       evidence: [ETL-002/OP-04]
     - need: Currency arithmetic with rounding
       evidence: [ETL-003/OP-02]
   ```
5. **Preflight**: list the input tables/files each ETL needs and whether the
   baseline outputs exist and are reachable. Missing ones go in `needs.yaml`
   under `missing_inputs:`.
6. Update `status.yaml` (`stage: clarify`), commit
   `[ETL-xxx][analyze] n operations`.

## Boundaries

- Do not translate anything yet.
- Do not ask the user. Unknowns become `needs_human` entries or `needs.yaml` items.
- Do not decide architecture; that is the next stage.
