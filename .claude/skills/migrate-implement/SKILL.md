---
name: migrate-implement
description: Stage 3 of a legacy ETL to Java migration. Initializes the target project from the charter's template and converts one ETL at a time, in dependency order, into Java that mirrors inventory.yaml operation by operation. Use from the migrate skill.
---

# migrate-implement (no human involved)

## Setup (once)

- If `target.template` is set: copy it to `target.dir`, rename
  artifact/package as the domain knowledge says. Otherwise create a minimal
  Maven project for `target.java_version`.
- Do not modify template infrastructure (`etl.core` etc.) unless an ETL
  cannot be written without it; if you must, note it in the commit message.

## Per ETL (dependency order from `depends_on`, one at a time)

1. `git checkout -b etl/<ETL-ID>`.
2. Read `etl/<ID>/inventory.yaml`. For each operation write the Java that
   does exactly that, preserving the `implicit` behaviors listed. Put the
   `op_id` in a comment on the code that implements it.
3. You are free on syntax and idiom (loops, naming, helper methods, types).
   Where the domain knowledge's `rule.md` covers a Delphi semantic, use
   its Java equivalent. Where a legacy quirk looks like a bug, keep it and add a
   `// legacy quirk: ...` comment; report it, do not fix it.
4. Fill each operation's `target_loc` in the inventory (Class#method).
5. Make it compile and pass any unit tests that exist
   (`mvn -q -o package` if offline is possible).
6. Commit `[ETL-xxx][implement] n operations`; `status.yaml`: ETL
   `stage: implemented`.

## Not allowed

- Inventing behavior not in the inventory. If the inventory is missing
  something you discover, **add it to the inventory first** (append a new
  op_id; never renumber), then implement it.
- Editing frozen files.
- Running the migrated job against anything but the configured candidate
  output (plain-named tables are baselines).
