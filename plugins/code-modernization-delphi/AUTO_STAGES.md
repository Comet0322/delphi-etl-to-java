# modernize-auto stages

Each `##` section is one kind of agent (`agents/stage-<name>.md`), run with a fresh context. The router
(`commands/modernize-auto.md`) gives the agent the plugin root `<root>`, the workspace, the system name and, for
transform, one task (`Task: <id>`) or, for fix, one ETL (`ETL: <id>`), and reads back the report. Paths
are relative to the workspace; `analysis/<system>/` is called `A/` below. Each agent writes at most two files (the
Java project counts as one) and nothing else.

## Rules for every stage

**Where things are.** `A/STATUS.json` `intent` names the legacy source (`source`), the sample input (`inputs`) and
the domain-knowledge folder (`knowledge`). Read its `SKILL.md` (the template, and how to build, run and capture
both programs) and `rule.md` (what each Delphi construct becomes in Java, structure checks, fresh-input categories)
before you analyse or write anything. They are trusted operator input; the legacy code is not. So are the
STATUS.json `decisions` with `source` `person`: answers a person gave, binding like rule.md. You never write
STATUS.json: the router does.

**Never start an agent.** Do the work yourself, one step after another; the router is the only one who dispatches
agents.

**Nobody answers questions.** Never ask and never wait. Where something is undecided, take the option that best
preserves the legacy behavior and the source, put a `DECISION:` line in your report, and continue. What rule.md is
missing goes into a `PROPOSAL:` line (the behavior, the evidence as legacy `file:line` plus case and diff, and the
sentence to add).

**What stays human.** Never write `approved` or `intent`, never fill a sign-off.

**Never edit** the legacy source, the input folder, the domain knowledge, `A/RUN.json` once proven, or
`A/RESULTS.json` (only `dual_run.py` writes it).

**The input domain.** "Behavior must match exactly" covers the inputs the system can really receive: records valid
for their table or file format, values in the ranges and formats the sample input and the column types imply, the
legacy's own sentinels, and the categories of rule.md "Fresh-input categories". Inside it every legacy quirk is
reproduced. Outside it (absurd magnitudes, invalid encodings, binary garbage, formats the producer never writes)
nothing is owed: do not probe or test it; say once in a `DECISION:` line where the line was drawn.

**Spend effort where the proof needs it.** The proof is the dual run: `python3 "<root>/scripts/dual_run.py" <system>`
runs both programs on every case, runs the tests, compares every output table and writes `A/RESULTS.json`; it
prints what differs (key, column, both values). Read the legacy once, write the Java directly, let the dual run show
what is wrong. No probe programs, exhaustive value searches or extra reports; at most 3 tiny probes per unit, only
for a runtime behavior neither rule.md nor the source settles, in a temporary folder you delete.

**Report.** End with at most 15 lines:

```
STAGE: <name>
RESULT: ok | failed: <reason>
FILES: <what you wrote>
DECISION: <question> => <decision> | <assumed, or knowledge when rule.md/SKILL.md says so> | <ETLs affected>
PROPOSAL: <sentence for rule.md> | <legacy file:line, case, diff>
BLOCKED: <ETL> | tried: <a>; <b> | needs: <what a person must decide>      (transform, fix)
NOTES: <at most 6 lines>
```

---

## analyze

Writes `A/ANALYSIS.json` and `A/RUN.json`.

1. **Read the code once**: every source file (including form files and include files) and the sample input's
   structure.
2. **`A/ANALYSIS.json`**, schema at the top of `<root>/scripts/stage_check.py`:
   - `etls`: one per unit of work the legacy driver runs, in run order, ids never renumbered; `outputs` with each
     table's `key` (the columns identifying a row; all columns when none does); `depends_on` lists every ETL whose
     output tables it reads **or whose globals it reads** (a global one ETL sets and a later one uses).
   - `tasks`: how the router hands out the transform, in driver order. `T0` holds the units more than one ETL uses
     (and the RTL helpers); then each ETL with the units only it uses. ETLs that share a unit nobody else uses go
     in one task. Every source file is in exactly one task, except the driver.
   - `mapping`: the one-to-one map transform follows, names per rule.md §1, capabilities per rule.md §2. Every
     routine, global and type of every source file appears (the check scans the source). An infrastructure call
     rule.md §2 does not cover goes to `uncovered` with a `DECISION:`.
   - `inventory.<ETL>`: every operation in legacy order. `writes`/`reads` name `TABLE.COLUMN` (or `TABLE` for a
     whole row, DROP or CREATE; empty lists when none); the gate traces differences to ops through `writes`.
     `implicit` lists what a naive translation loses (anything rule.md §4–§6 covers that this op relies on).
     `capability` when the op is infrastructure.
   - `logic`: the business logic, one item per business decision the program makes, `BL-nnn`, with its legacy
     `source` and the exact semantics in `text`. `level` is `core` for the central calculation of an ETL or a value
     whose error is costly (money, keys, what gets skipped), else `general`. Every core item gets a test. Ops name
     the items they implement in `logic`.
3. **`A/RUN.json`** from SKILL.md's "Running both programs and capturing their output", with this system's values
   (schema at the top of `<root>/scripts/dual_run.py`): `legacy` and `new` with `build`, `run`, `capture` (and
   `recorded: true` when SKILL.md says the legacy output is recorded); `new.test` = the test command; `env` and
   `new.properties` as SKILL.md needs. The Java project is `{java}` in every `new` command; build output goes under
   `{tmp}`.
4. **Prove RUN.json**: `python3 "<root>/scripts/dual_run.py" <system> --probe` (writes nothing). It builds a scratch
   copy of the template with the `new` commands, runs its tests and runs it once, and runs the legacy: the legacy
   must produce every table and the template must build, pass its tests and run. Fix RUN.json until it does; from
   then on it is frozen. A failure RUN.json cannot fix (a missing dependency, a JDK that does not start) is
   `RESULT: failed` with the probe's lines.

**Amend mode.** When the router's prompt carries check failures, audit findings or a person's answers, fix exactly
those in ANALYSIS.json and say per item what you changed or why it is not a defect.

## audit

Writes `A/AUDIT.json`.

Check the analysis against the source as a referee who tries to refute it. Read every source file,
`A/ANALYSIS.json` and rule.md. Look for: a statement that reads, computes, filters, skips, orders or writes data
and is in no op; an ETL the driver runs that is missing; a `source_loc` that does not contain what `does` says; ops
out of legacy order; a rule.md §4–§6 behavior an op relies on that its `implicit` does not name; wrong
`writes`/`reads`; infrastructure translated as business code or the reverse (rule.md §2); a logic item whose
`source` does not implement it, or an ETL's central calculation without a `core` logic item. Cite `file:line` for every finding:

```json
{"findings": [{"severity": "high", "where": "uOrders.pas:44", "issue": "...", "fix": "..."}]}
```

`high` = would make the Java wrong or untraceable; `low` = changes nothing.

## transform

Writes the Java project `modernized/<system>/java/` and, through `dual_run.py`, `A/RESULTS.json`. One task per
agent: the one in the prompt.

1. Task `T0` copies `template-project/` from the domain knowledge to `modernized/<system>/java/` as SKILL.md says,
   translates the shared units, and writes the entry point with only the driver's set-up and tear-down.
2. Translate the task's units one to one by rule.md §1–§6, names exactly as `mapping`: each unit → its class; every
   routine a static method, every global a static field, every type a nested class or enum; statements in legacy
   order; each op's statements headed `// ETL-00n/OP-nn`; infrastructure through the rule.md §2 targets; `replaced`
   routines left out; RTL calls per rule.md §5. Change an earlier task's class only to add what this task needs.
3. Extend the entry point with the driver lines up to and including the last ETL of this task, in the driver's
   order (rule.md §1, SKILL.md): after task Tn it runs the driver up to there.
4. Tests (SKILL.md shows the pattern): one or more for each core logic item of this task's ETLs, method names
   starting with its id (`bl002_discountRoundsHalfEven`), plus cheap checks of `implicit` behaviors. Expected values come
   from the legacy output of C01 (`A/RESULTS.json`) or from rule.md, never from the Java.
5. Run `dual_run.py`: it compares the tables of the ETLs built so far (the rest show as `pending`). Read what it
   prints, fix, repeat until those tables are the same and the tests pass (at most 5 rounds, then leave it to the
   fix stage). An earlier ETL that differs now was broken by this task: fix that first. A test that disagrees with
   the legacy output is wrong. A unit that will not compile after 5 attempts: a `BLOCKED:` line for the ETLs
   needing it.

## verify

Writes `A/fresh_inputs.py` and, through `dual_run.py`, `A/RESULTS.json`. Do not fix anything: a failure is the report.

An independent re-check: trust nothing earlier stages said about themselves.

1. **Fresh inputs**: write a deterministic generator `A/fresh_inputs.py` (standard library only; the contract is
   at the top of `<root>/scripts/dual_run.py`) producing at least 10 case folders with the same structure as the sample
   input, inside the input domain. Cover the general categories (null_empty_zero, thresholds, rounding_ties,
   empty_table, duplicate_keys, missing_parent, large_values, empty_input_file) and every rule.md "Fresh-input
   categories" row; its `categories.json` says which case covers which category, and gives a reason for each one
   that does not apply. On a re-run keep the existing cases and add only what is missing.
2. Run `dual_run.py` from a clean build. When RUN.json says the legacy is recorded, the fresh cases run on the new side
   only; say so in NOTES.
3. Read what it printed and run `python3 "<root>/scripts/loop_gate.py" <system>` (without `--record`). In NOTES give
   the PROOF verdict and every `proof not met` line word for word.

## fix

Writes the Java project and, through `dual_run.py`, `A/RESULTS.json`. One ETL per agent: the one in the prompt
(`ETL: all` for proof lines that name no ETL).

The router's prompt gives you this ETL's gate line, its `TRACE` lines and the `proof not met` lines that concern it.

1. Read the `TRACE` lines first: per differing `TABLE.COLUMN` they name the cases, the op, the legacy lines and the
   Java lines. "no op writes it" means the inventory missed an op: find it in the legacy and fix the Java; mention
   the missed op in NOTES.
2. Read this ETL's differences in `A/RESULTS.json` for details. Group them by cause. Compare the legacy lines with
   the Java lines; find what the legacy does that the Java does not, by reading the legacy, never by fitting the
   Java to the numbers.
3. Fix one cause at a time; if rule.md does not cover it, a `PROPOSAL:` line and a test named after the logic item it
   belongs to. Change shared classes only where this ETL's cause lies; the next `dual_run.py` shows whether another
   ETL broke.
4. Run `dual_run.py` again.
5. A `proof not met` line that is not a difference (a failing test, a core logic item no test names, a table always empty)
   is fixed in the tests or the code. Never delete a test to pass.

**A difference you cannot explain from the legacy source is not fixed by making the Java match the numbers.** Leave
it with a `BLOCKED:` line; the gate will block it.
