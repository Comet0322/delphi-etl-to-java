# code-modernization-delphi

Unattended migration of small Delphi ETL systems (up to about 10,000 lines) to Java, with a script-computed proof
that the Java behaves like the legacy. Derived from Anthropic's
[code-modernization](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-modernization)
plugin 1.0.0 (Apache 2.0, see `LICENSE`): its comparison, proof pack, report and verify procedure are kept
unchanged; everything else is new or removed.

## Run

```bash
chmod -R a-w <source dir> <sample input dir>       # nothing can then edit them
mkdir work && cd work
claude --plugin-dir <path>/plugins/code-modernization-delphi
/code-modernization-delphi:modernize-auto <name> --source <source dir> --inputs <sample input dir> --knowledge <skill dir>
```

Headless: `claude -p --plugin-dir … --model sonnet --effort low --settings '{"advisorModel":""}'
--permission-mode bypassPermissions "/code-modernization-delphi:modernize-auto …"` (turn the advisor off when your
user settings name one, or stage agents wait on it). Run it in a folder outside any repository whose own skills
should not load.

## What is where

| Plugin (process and proof) | Domain-knowledge skill (everything about the project) |
|---|---|
| `commands/modernize-auto.md` — the router | `SKILL.md` — the template, and how to build, run and capture the output of both programs |
| `AUTO_STAGES.md` — what each stage does, artifact formats, rules every stage follows | `rule.md` — mapping rules (structure, capabilities, tables, types, RTL, field access), structure checks, fresh-input categories |
| `agents/stage-*.md` — analyze, audit, transform, verify, fix | `template-project/` — the Java project every migration starts from |
| `commands/modernize-verify.md`, `agents/legacy-analyst.md` — upstream | |
| `MODELS.json` — model per role | |

## Flow

```
router ── analyze ─ stage_check ─ audit ─(amend once)─ transform ─ stage_check ─┐
                                                                                │
        ┌─ verify ─ stage_check ─ loop_gate ─ DONE/BLOCKED ─ build_report + write_summary
        └──────────────── fix ◄─ trace_diff ◄─ CONTINUE
```

## Scripts

| Script | Does | Origin |
|---|---|---|
| `run_case.py` | one input case: build, run and capture each side as RUN.json says, canonical CSV per table, row diagnostics | new |
| `collect_sqlite.py` | example capture command: dump SQLite tables to CSV | new |
| `compare.py` | byte comparison, the judge of same or different | upstream |
| `proof_pack.py` (+ `trace_rules.py`, `baseline_diff.py`, `uplift_checks.py`) | the verdict: PROVEN, PARTLY PROVEN, NOT PROVEN | upstream |
| `build_report.py` | `REPORT.html` | upstream |
| `stage_check.py` | coverage and structure checks after each stage; project rules read from rule.md | new |
| `loop_gate.py` | stop conditions and frozen-file checks of the fix loop | new |
| `trace_diff.py` | each difference → TABLE.COLUMN → operation → legacy lines → Java lines, cascade notes | new |
| `write_summary.py` | `AUTO_SUMMARY.md`, from files only | new |
| `etl_artifacts.py` | Pascal scanner and shared readers | new |

Tests: `python3 -m unittest discover -s scripts/tests`.

## What a person decides

The run is a draft. A person reviews the assumed decisions (`DECISIONS.md`), the P0 rules, accepts or rejects each
remaining difference (`approvedDifference`), signs `VERIFICATION.md`, and merges `knowledge-proposals.md` into the
skill. The run never does any of these.
