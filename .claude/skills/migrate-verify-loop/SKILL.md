---
name: migrate-verify-loop
description: Stage 4 of a legacy ETL to Java migration. Runs the migrated job, compares its output to the legacy baseline, fixes the Java according to the differences and repeats until zero diffs or a machine-judged blocker. Use from the migrate skill.
---

# migrate-verify-loop (no human involved)

Per ETL, in dependency order. Repeat:

1. **Run** the migrated job (writes to the candidate/new tables).
2. **Compare**:
   `python3 scripts/compare.py --config compare.yaml --etl <ID>`
   Each call appends `results/compare/run-NNN.json`; never edit or delete.
3. **Gate**:
   `python3 scripts/verify_gate.py --etl <ID>`

   | Output | Do |
   |---|---|
   | `DONE` | set ETL `done`, store evidence run in each op, commit `[ETL][verify] run NNN: 0 diffs`, next ETL |
   | `CONTINUE` | step 4 |
   | `BLOCKED:<code>` | step 5 |
4. **Fix**: read the diffs, trace each to an operation via `target_loc` /
   `source_loc`, find what the legacy code does that the Java does not, and
   fix the Java (and add the missed behavior to the op's `implicit` in the
   inventory). Fix root causes, group diffs by cause, change one cause at a
   time. Commit `[ETL][verify] run NNN: K diffs remaining`. Go to 1.
5. **Block**: set ETL `stage: blocked` with in `status.yaml`
   `code`, `tried` (what you did), `needs` (the exact decision or input
   required). Continue with ETLs that do not depend on it.

## Hard rules

- A diff you cannot explain from the legacy source is **not** fixed by
  adjusting the Java to match the numbers. Treat unexplained as blocked.
- Never change `compare.yaml`, tolerances, or the baseline data. If the
  remaining diff looks like pure noise (e.g. floating point), block with
  `needs: "tolerance decision"` and put the suggested setting and evidence in
  `tried`.
- If the gate says `BLOCKED:frozen_file_changed`, stop everything and report.
- Baseline tables are never written.
