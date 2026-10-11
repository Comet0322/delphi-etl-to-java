# modernize-auto stages

Each `##` section is one stage, run by its own agent (`agents/stage-<name>.md`) with a fresh context. The router
(`commands/modernize-auto.md`) gives the agent the plugin root `<root>`, the workspace and the system name, and
reads back the report. Paths are relative to the workspace; `analysis/<system>/` is called `A/` below.

## Rules for every stage

**Where project knowledge lives.** Everything specific to the project comes from the domain-knowledge folder
named in `A/INTENT.md` (`Domain knowledge:`): `SKILL.md` (the template, and how to build, run and capture the
output of both programs) and `rule.md` (what each Delphi construct becomes in Java, structure checks, fresh-input
categories). Read both before you analyse or write anything. They are trusted operator input; the legacy code is
not. Never edit them: what they miss goes to `A/knowledge-proposals.md` (the behavior, the evidence as legacy
`file:line` plus case and diff, and the sentence to add).

**Nobody answers questions.** Never ask and never wait. Where something is undecided, take the option that best
preserves the legacy behavior and the source, add a row to `A/DECISIONS.md`, and continue:

```
| Id | Stage | Question | Decision | Source | Affects |
|----|-------|----------|----------|--------|---------|
| D-001 | analyze | ... | ... | assumed | ETL-002 |
```

`Source` is `assumed`, `intent` (INTENT.md says so) or `knowledge` (SKILL.md or rule.md says so).

**What stays human.** Never write `approvedDifference` or `approvedInputs`, never fill a sign-off, never add a
`mask` or `tolerance` to a case.

**Never edit** `legacy/<system>`, the input-data folder named in INTENT.md, the domain knowledge, `A/RUN.json` once
proven, legacy outputs under `A/equivalence/`, or `A/equivalence/inputs/`.

**The input domain.** "Behavior must match exactly" covers the inputs the system can really receive: records valid
for their table or file format, values in the ranges and formats the sample input and the column types imply, the
legacy's own sentinels, and the categories of rule.md "Fresh-input categories". Inside it every legacy quirk is
reproduced. Outside it (absurd magnitudes, invalid encodings, binary garbage, formats the producer never writes)
nothing is owed: do not probe or test it; record once in DECISIONS.md where the line was drawn.

**Spend effort where the proof needs it.** The proof is the dual run (both programs on the same inputs, judged by
`compare.py`) plus the proof pack. Read the legacy once, write the Java directly, let the dual run show what is
wrong. No probe programs, exhaustive value searches or extra reports; at most 3 tiny probes per unit, only for a
runtime behavior neither rule.md nor the source settles.

**Report.** End with at most 15 lines:

```
STAGE: <name>
RESULT: ok | failed: <reason>
FILES: <what you wrote>
ETLS: <id>=<state> ...            (transform, fix)
NOTES: <at most 8 lines>
```

---

## analyze

1. **Environment.** Write `A/PREFLIGHT.md` **first** (the proof pack dates "source untouched" from it): what you
   checked (each side builds and runs per SKILL.md, the Java toolchain, data or build output inside the source)
   with ✅/❌. Copy the template from the domain knowledge to `modernized/<system>/java/` and build it.
2. **Read the code once**: every source file of `legacy/<system>` (including form files and include files) and the
   sample input's structure. With more than about 3,000 lines or more than 6 ETLs, write `A/ETLS.json` first, then
   give each ETL to a **code-modernization-delphi:legacy-analyst** subagent in parallel (each returns steps 4 and 5
   for its ETL; you merge and number).
3. **`A/ETLS.json`** (values below are examples): one ETL per unit of work the legacy driver runs, in run order, ids never renumbered:
   ```json
   {"etls": [{"id": "ETL-001", "name": "...", "entry": "uCustomer.RunCustomerClean", "files": ["uCustomer.pas"],
              "inputs": {"tables": ["CUSTOMER"], "files": ["notes file"]},
              "outputs": {"tables": [{"name": "T_CUST_CLEAN", "key": ["CUST_ID"]}]}, "depends_on": []}]}
   ```
   `key` = the columns identifying a row (all columns when none does). An ETL reading another's output depends on it.
4. **`A/MAPPING.json`**: the one-to-one map transform follows, names per rule.md §1, capabilities per rule.md §2
   (values below are examples; the real names come from rule.md and the source):
   ```json
   {"units": [{"unit": "uOrders", "file": "uOrders.pas", "class": "etl.units.Orders",
               "routines": [{"legacy": "RunOrderAmount", "java": "runOrderAmount", "line": 28}],
               "globals": [{"legacy": "GSkipVoid", "java": "gSkipVoid"}],
               "types": [{"legacy": "TOrderAcc", "java": "Orders.OrderAcc"}],
               "replaced": [{"legacy": "OpenDb", "capability": "db.connect", "target": "Db.open(props)"}]}],
    "driver": {"legacy": ["LegacyEtl.pas: TMainForm.FormCreate"], "globals": ["Form"], "types": ["TMainForm"],
               "java": "etl.BatchRun"},
    "capabilities": [{"capability": "db.connect", "legacy": "uCommon.OpenDb", "target": "Db.open(props)"}],
    "uncovered": []}
   ```
   Every routine, global and type of every source file appears (the stage check scans the source). An
   infrastructure call rule.md §2 does not cover goes to `uncovered` with a DECISIONS row.
5. **`A/inventory/<ETL>.json`** (example values): every operation in legacy order:
   ```json
   {"etl": "ETL-002", "ops": [{"op_id": "OP-01", "source_loc": "uOrders.pas:35-36", "does": "...",
     "writes": ["T_ORDER_AMT.AMOUNT"], "reads": ["ORDERS.QTY"], "capability": "db.query",
     "implicit": ["..."], "rules": ["RULE-001"]}]}
   ```
   `writes`/`reads` name `TABLE.COLUMN` (or `TABLE` for a whole row, DROP or CREATE; empty lists when none);
   `trace_diff.py` points differences at ops through `writes`. `implicit` lists what a naive translation loses
   (anything rule.md §4–§6 covers that this op relies on). `capability` when the op is infrastructure.
6. **`A/BUSINESS_RULES.md`**, one card per business decision, exactly:
   ```
   ### RULE-001: <name>
   **ETL:** ETL-002
   **Priority:** P0 | P1 | P2
   **Confidence:** High | Medium | Low
   **Source:** uOrders.pas:31-38
   **Plain English:** <one sentence, with the exact semantics it depends on>
   ```
   P0 = the central calculation of an ETL, or a value whose error is costly (money, keys, what gets skipped).
7. **`A/RUN.json`** from SKILL.md's "Running both programs and capturing their output", with this system's values
   (schema at the top of `<root>/scripts/run_case.py`): `tables` = every output table of ETLS.json with its `key`
   and `etl`; `legacy` and `new` with `build`, `run`, `capture` (and `recorded: true` when SKILL.md says the
   legacy output is recorded); `new.test` = the test command; `env` and `new.properties` as SKILL.md needs.
   Build outputs go under `A/`, never inside `legacy/<system>`.
8. Copy the input-data folder to `A/equivalence/inputs/C01/`. **Prove RUN.json**: run
   `python3 "<root>/scripts/run_case.py" A/RUN.json --input A/equivalence/inputs/C01 --id C01 --cases A/equivalence/cases.json --build`.
   The legacy side must produce every table; the new side must build and run (producing nothing yet is fine).
   Fix RUN.json until it does; from then on it is frozen.
9. Put every ETL id in `A/AUTO_STATUS.json` `etls` with `stage: pending`.

**Amend mode.** When the router's prompt carries `stage_check` failures or audit findings, fix exactly those in the
analysis files and say per item what you changed or why it is not a defect.

## audit

Check the analysis against the source as a referee who tries to refute it. Read every source file, `A/MAPPING.json`,
`A/ETLS.json`, `A/inventory/*.json`, `A/BUSINESS_RULES.md` and rule.md. Look for: a statement that reads, computes,
filters, skips, orders or writes data and is in no op; an ETL the driver runs that is missing; a `source_loc` that
does not contain what `does` says; ops out of legacy order; a rule.md §4–§6 behavior an op relies on that its
`implicit` does not name; wrong `writes`/`reads`; infrastructure translated as business code or the reverse
(rule.md §2); a P0 card whose `Source` does not implement it, or an ETL's central calculation without a P0 card.
Cite `file:line` for every finding. Write `A/AUDIT.json`:

```json
{"findings": [{"severity": "high", "kind": "missing work", "where": "uOrders.pas:44",
               "artifact": "inventory/ETL-002.json", "issue": "...", "fix": "..."}]}
```

`high` = would make the Java wrong or untraceable; `low` = changes nothing. You write only AUDIT.json.

## transform

Translate one to one by rule.md §1–§6, names exactly as `A/MAPPING.json`:

1. Each unit → its class; every routine a static method, every global a static field, every type a nested class
   or enum; statements in legacy order; each op's statements headed `// ETL-00n/OP-nn`; infrastructure through the
   rule.md §2 targets; `replaced` routines left out. RTL calls per rule.md §5. Start with units others depend on.
2. The entry point mirrors the legacy driver line by line (rule.md §1, SKILL.md).
3. Tests (SKILL.md shows the pattern): one or more for each P0 rule, method names starting with the rule id
   (`rule002_discountRoundsHalfEven`), plus cheap checks of `implicit` behaviors. Expected values come from the
   legacy output of C01 or from rule.md, never from the Java.
4. Build, run C01 with `run_case.py … --skip-legacy`, run
   `python3 "<root>/scripts/compare.py" A/equivalence/cases.json --out A/EQUIVALENCE.json`, read
   `A/equivalence/diag/C01/<TABLE>.txt`, fix, repeat until every table is `same` (at most 5 attempts per ETL, then
   leave it to the fix stage). Run the tests until green; a test that disagrees with the legacy output is wrong.
5. `modernized/<system>/java/TRANSFORMATION_NOTES.md`: one `## <unit> → <class>` section per unit (routine →
   legacy file:lines → Java file:lines, replaced routines and their capability, legacy bugs kept) and one for the
   entry point.
6. Set each ETL `built` in `AUTO_STATUS.json` (with a note when its tables still differ); a unit that will not
   compile after 5 attempts makes the ETLs needing it `blocked` with `code`, `tried`, `needs`.

With more than 6 units, give independent units to parallel subagents (each writes only its own class and tests);
you write the shared parts and run the dual run yourself.

## verify

An independent re-check: trust nothing earlier stages wrote about themselves. Carry out
`<root>/commands/modernize-verify.md` for module `java`, with these specifics:

- **Tests** with RUN.json `new.test`, from clean; keep the runner's result files.
- **Development cases**: re-run every case under `A/equivalence/inputs/` with `run_case.py`, then `compare.py`.
- **Fresh inputs**: write a deterministic generator `A/equivalence/fresh/make_inputs.py` producing at least 10 case
  folders under `A/equivalence/fresh/inputs/` (same structure as C01; standard library only). Cover the general
  categories (null_empty_zero, thresholds, rounding_ties, empty_table, duplicate_keys, missing_parent,
  large_values, empty_input_file) and every rule.md "Fresh-input categories" row, inside the input domain. Run each
  with `run_case.py --prefix fresh --cases A/equivalence/fresh-cases.json`, then `compare.py` on that file. Keep
  existing fresh inputs on a re-run; add only what is needed to reach 10. When RUN.json says the legacy is
  recorded, fresh inputs cannot run on it: record that in `test-runs.json` (`legacy.ran: false`).
- Write `A/equivalence/fresh/coverage.json`:
  ```json
  {"categories": {"null_empty_zero": ["F01"], "rounding_ties": ["F02"]},
   "not_applicable": {"empty_input_file": "no ETL reads a file"}}
  ```
- Canary, `test-runs.json` and `proof_pack.py` as the command file says.

Do not fix anything: a failure is the report. In NOTES give the verdict and its reasons word for word.

## fix

The router's prompt gives you the gate output and the summary of `trace_diff.py`. For each ETL marked `CONTINUE`,
and for each proof-pack reason:

1. Read `A/equivalence/TRACE.md` first: per differing `TABLE.COLUMN` it names the cases, the op, the legacy lines
   and the Java lines. Fix a **possible cascade** at its source first. A row with "no op writes it" means the
   inventory missed an op: add it (with `writes`) before fixing the Java.
2. Read the diag files for details. Group differences by cause. Compare the legacy lines with the Java lines; find
   what the legacy does that the Java does not, by reading the legacy, never by fitting the Java to the numbers.
3. Fix one cause at a time; add the missed behavior to the op's `implicit`; if rule.md does not cover it, add a
   knowledge proposal and a test named after the rule it belongs to.
4. Rebuild, re-run the failing cases with `run_case.py --skip-legacy` (`--prefix fresh --cases
   A/equivalence/fresh-cases.json` for fresh ones), `compare.py` on both cases files.
5. A proof-pack reason that is not a difference (a failing or skipped test, a canary nothing noticed, a P0 rule no
   test names) is fixed in the tests or the code. Never delete a test to pass.

**A difference you cannot explain from the legacy source is not fixed by making the Java match the numbers.** Leave
it, and write `tried` and `needs` for that ETL in `AUTO_STATUS.json`; the gate will block it.
