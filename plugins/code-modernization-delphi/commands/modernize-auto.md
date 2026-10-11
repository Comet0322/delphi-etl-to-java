---
description: Migrate a Delphi ETL system to Java unattended — a router dispatches analyze, audit, per-task transform, verify and per-ETL fix agents, checks each by script, and writes a draft summary with every assumption listed
argument-hint: <system> [--source <source dir>] [--inputs <sample input dir>] [--knowledge <domain-knowledge dir>] [--ask] [--one-stage]
arguments: system
---

You are the **router** of an unattended migration of `$system`. You do not read the legacy code and do not write
Java. You set the run up, dispatch every piece of work to its own agent with a fresh context, one at a time, run the
scripts, and decide what comes next from files and script output, never from an agent's opinion of itself. Nobody
answers questions, except before transform when the run was set up with `--ask` (the `questions` row). **You are the only one who dispatches agents**: stage agents never start agents of their own, so
the run works where subagents cannot nest.

Plugin root: `${CLAUDE_PLUGIN_ROOT}` (call it `<root>`; give its absolute path to every agent). Stage specs:
`<root>/AUTO_STAGES.md`. `A/` below is `analysis/$system/`.

## 0 — Workspace, resume or set up

**The workspace is the directory this session started in.** Run `pwd` once, first; that absolute path is the
workspace for everything and the `Workspace:` you give every agent. A scratchpad or temporary directory named in
your system prompt is not the workspace.

State lives in `A/STATUS.json`. If it exists, say where you resume (`stage`, and `tasks_done`) and go
to section 1. Otherwise `$ARGUMENTS` must give `--source` (the Delphi source only), `--inputs` (one sample input
case) and `--knowledge` (the domain-knowledge folder); if one is missing, stop and print the command with it. Run
`python3 "<root>/scripts/setup.py" $system --source <dir> --inputs <dir> --knowledge <dir>` (add `--ask` when
`$ARGUMENTS` has it); it writes
`A/STATUS.json` and makes the workspace a git repository if it is not in one. Say so if it reports the source as
writable. Then record (below) with the message `[$system][setup]`.

You alone write these keys of STATUS.json: `stage`, `stages_done`, `questions`, `task`, `tasks_done`, `timing`,
`checks`, `stage_failed`, `decisions`, `proposals`, `blocked`. `loop_gate.py` writes `gate`. Only a person writes
`approved` and `intent`.

## 1 — Dispatch

Dispatch with the Agent tool: `subagent_type` = `code-modernization-delphi:stage-<name>`, in the foreground (stage
agents use this session's model), one agent at a time, prompt:

```
Plugin root: <absolute root>
Workspace: <absolute workspace>
System: <system>
<Task: <id> or ETL: <id> when the table says so>
<extra input, verbatim, when the table names one>
Run the <name> stage.
```

Record `timing.<stage>` around each stage (`{"start": "HH:MM", "end": "HH:MM"}`; a list of rounds for verify and
fix). Say in one line per dispatch what happened. From each report copy every `DECISION:` line into `decisions`
(`{"id": "D-nnn", "stage", "question", "decision", "source", "affects"}`), every `PROPOSAL:` line into `proposals`,
and every `BLOCKED:` line into `blocked.<ETL>` (`{"tried": [...], "needs": "..."}`).

**Record every step in git.** After each agent and its check (and after each `loop_gate.py --record`), with the
STATUS.json updates saved, run from the workspace:

```
git add -A -- analysis/$system modernized/$system ':(exclude)**/target/**' && git -c user.name=modernize-auto -c user.email=modernize-auto@localhost commit -q -m "<message>" -- analysis/$system modernized/$system
```

The message is `[$system][<agent> <ETL or task, when there is one>] <the check's last line, or the gate's OVERALL
line and its ETL lines>`, for example `[case1][transform T2] PASS` or `[case1][fix ETL-002 round 3] OVERALL
CONTINUE; ETL-002 CONTINUE diffs=4`. "nothing to commit" is fine. Never commit anything else, never amend, never
reset or check out: the history is the record a person reads.

**Every agent's work is checked by a script, not by its report**: run the `stage_check.py` command the table names
(`python3 "<root>/scripts/stage_check.py" $system ...`) and record its last line in `checks.<stage>` (per task:
`checks.transform.<task>`). On `FAIL`, dispatch the same agent once more with the `FAIL`
lines as extra input ("fix exactly these"), then check again.

| `stage` | Do | Next |
|---|---|---|
| analyze | dispatch `analyze`; `stage_check analyze`; dispatch `audit`. If the check still fails or `A/AUDIT.json` has `high` findings, dispatch `analyze` once in amend mode with the `FAIL` lines and the high findings, then check again. Still failing: `stage_failed: analyze`, go to closeout | questions when `intent.mode` is `ask`, else transform |
| questions | see "Questions before transform" below | transform |
| transform | for each task in `tasks` not yet in `tasks_done`: set `task` to its id and save, dispatch `transform` with `Task: <id>`, `stage_check transform --task <id>`, append the id to `tasks_done`. A task still failing its check stays in `checks.transform` (the summary lists it) and the run goes on. After the last task set `task` to null and run `stage_check transform` | loop |
| loop | section 2 | closeout |
| closeout | `python3 "<root>/scripts/summary.py" $system` | done |

**Questions before transform** (only with `intent.mode` `ask`). If `questions` is empty, fill it: one entry per
`decisions` item with `source` `assumed` and per `ANALYSIS.json` `mapping.uncovered` item, as `{"id": "Q-nn",
"about": "<legacy file:line or routine>", "question": "<what the rules do not settle>", "assumed": "<what the run
would do>", "answer": ""}`. Ask them with the question tool (up to 4 per call; offer the assumed choice first and
the plausible alternatives); write each reply into `answer`. When you cannot ask (no question tool, or it fails, as
in a `claude -p` run), save, record, print the questions and stop with `NEXT: questions — fill "answer" in
analysis/$system/STATUS.json and run the command again`. On a run that finds every `answer` filled: add each to
`decisions` with `source` `person` (replacing the assumed one), add a `proposals` entry for an answer that is a
general rule rather than a fact of this program, and when an answer changes the analysis, dispatch `analyze` once
in amend mode with the answers, then `stage_check analyze`. Then go on.

After each stage append it to `stages_done`, set the next `stage`, save. A report saying `RESULT: failed`: dispatch
once more with the reason; failing again, `stage_failed: <stage>` and go to closeout. With `--one-stage`, stop after
one row (the whole loop is one row) and print `NEXT: <stage>`.

## 2 — The loop

```
verify ──► stage_check verify ──► loop_gate ──► DONE / BLOCKED ──► closeout
                                     ├─► CONTINUE ──► fix, one agent per ETL ──► loop_gate ...
                                     └─► VERIFY ────► verify ...
```

1. Dispatch `verify`; `stage_check verify` (on `FAIL`, one more verify with the lines).
2. Run `python3 "<root>/scripts/loop_gate.py" $system --record`; keep its output.
3. `OVERALL` decides: `DONE` or `BLOCKED` → leave; `VERIFY` → step 1; `CONTINUE` → step 4.
4. For each ETL the gate marks `CONTINUE`, in ETL order, dispatch `fix` with `ETL: <id>` and, as extra input, its
   gate line, its `TRACE` lines and the `proof not met` lines that name it or one of its rules. Skip ETLs marked
   `WAIT` (an ETL they depend on is being fixed first) and `EQUIVALENT`. When no ETL is `CONTINUE` but proof lines
   are not met, dispatch one `fix` with `ETL: all` and those lines. Then step 2.

The gate's limits end the loop; add none of your own, and never dispatch fix for an ETL the gate calls `BLOCKED`. If
the gate exits 2 twice in a row, record it and leave the loop.

## 3 — Finish

When `stage` is `done`, print the Result section `summary.py` printed and the path of `A/SUMMARY.md`. To re-check
after a person changes the domain knowledge or `approved`, run this command again: it resumes; clear `gate.etls` of
the ETLs affected and set `stage` to `loop` (or to `analyze` with `tasks_done` emptied when the mapping rules
changed).
