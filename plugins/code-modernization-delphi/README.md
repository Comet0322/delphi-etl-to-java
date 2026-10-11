# code-modernization-delphi

Unattended migration of small Delphi ETL systems (up to about 10,000 lines) to Java, with a script-computed proof
that the Java behaves like the legacy. Derived from Anthropic's
[code-modernization](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-modernization)
plugin 1.0.0 (Apache 2.0, see `LICENSE`): the dual run, the stop conditions and the proof checks follow its ideas;
the code is new.

## Run

```bash
chmod -R a-w <source dir> <sample input dir>       # nothing can then edit them
mkdir work && cd work
claude --plugin-dir <path>/plugins/code-modernization-delphi
/code-modernization-delphi:modernize-auto <name> --source <source dir> --inputs <sample input dir> --knowledge <skill dir>
```

Headless: `claude -p --plugin-dir … --settings '{"advisorModel":""}'
--permission-mode bypassPermissions "/code-modernization-delphi:modernize-auto …"` (turn the advisor off when your
user settings name one, or stage agents wait on it). Run it in a folder outside any repository whose own skills
should not load.

## What is where

| Plugin (process and proof) | Domain-knowledge skill (everything about the project) |
|---|---|
| `commands/modernize-auto.md` — the router | `SKILL.md` — the template, and how to build, run and capture the output of both programs |
| `AUTO_STAGES.md` — what each stage does, artifact formats, rules every stage follows | `rule.md` — mapping rules (structure, capabilities, tables, types, RTL, field access), structure checks, fresh-input categories |
| `agents/stage-*.md` — survey, analyze, audit, transform, verify, fix | `template-project/` — the Java project every migration starts from |
| `scripts/` — one per moment of the run (below) | `collect_sqlite.py` — the testbed's capture command (SQLite tables to CSV) |

## Flow and files

Every agent is dispatched by the router, one at a time; no agent starts another (subagents cannot nest in Claude
Code 2.0.x). Analysis is split per ETL, transform per task in legacy driver order, fix per ETL.

```
router ─ setup ─ survey ─ analyze ETL-001 … ETL-n ─ audit ─(amend once)─ transform T0 … Tn ─┐
         (stage_check after every agent)                                                    │
        ┌─ verify ─ loop_gate ─ DONE/BLOCKED ─ summary                                      │
        └── fix ETL-a … ETL-b ◄─ CONTINUE (TRACE lines; WAIT for an ETL whose upstream differs) ◄┘
```

The router commits `analysis/<system>` and `modernized/<system>` after every agent (setup makes the workspace a git
repository when it is not in one), so `git log` lists every step with its check result and `git show <id>` shows
what one agent changed; SUMMARY.md lists the commits.

After transform task Tn the Java runs the legacy driver up to the last ETL of Tn, and the dual run compares only
those ETLs' tables (the rest are `pending`), so each task is proven before the next one starts.

Every agent writes at most two files under `analysis/<system>/` (`A/`):

| Agent | Writes |
|---|---|
| router (`setup.py`, its own bookkeeping) | `A/STATUS.json` — intent, stage, analyzed ETLs, current task, tasks done, timing, checks, decisions, proposals, blocked, gate; a person's `approved` |
| survey | `A/ANALYSIS.json` (ETLs, tasks, driver and shared-unit mapping), `A/RUN.json` (how each side is built, run, captured) |
| analyze (one per ETL) | `A/ANALYSIS.json` (that ETL's unit mapping, inventory, rules) |
| audit | `A/AUDIT.json` |
| transform (one per task) | the Java project `modernized/<system>/java/`, `A/RESULTS.json` (by `dual_run.py`) |
| verify | `A/fresh_inputs.py`, `A/RESULTS.json` (by `dual_run.py`) |
| fix (one per ETL) | the Java project, `A/RESULTS.json` (by `dual_run.py`) |
| closeout | `A/SUMMARY.md` |

## Scripts

| Script | Who runs it, when | Does |
|---|---|---|
| `setup.py` | router, before survey | writes STATUS.json (paths, date, hash of the legacy source, limits) |
| `stage_check.py` | router, after every survey, analyze, transform and verify agent | checks coverage and structure (`--etl`, `--task` narrow it to one ETL or the tasks so far): task order, Pascal scanner against the mapping, one-to-one names, op comments, rule.md structure checks, fresh-input categories |
| `dual_run.py` | agents, in survey (`--probe`), transform, verify and fix | runs both sides on the sample and the fresh cases as RUN.json says, runs the tests, compares each output table in canonical CSV form, writes RESULTS.json |
| `loop_gate.py` | router, in the loop after verify and after each fix round | per-ETL stop conditions (CONTINUE, WAIT, EQUIVALENT, BLOCKED), the proof verdict (PROVEN / PARTLY PROVEN / NOT PROVEN), a trace of each difference to op, legacy lines and Java lines |
| `summary.py` | router, at closeout | writes SUMMARY.md from STATUS.json and AUDIT.json |

Tests: `python3 -m unittest discover -s scripts/tests`.

## What a person decides

The run is a draft. A person reviews the assumed decisions and the P0 rules, accepts or rejects each remaining
difference (STATUS.json `approved`), and merges the knowledge proposals into the skill (all listed in SUMMARY.md). The run never does any of these.
