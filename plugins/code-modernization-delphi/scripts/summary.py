#!/usr/bin/env python3
"""Router, at closeout: write analysis/<system>/SUMMARY.md and print its Result section.

    python3 summary.py <system> [--workspace DIR]

Everything in it is read from files, so it cannot misstate the result: the gate's verdict, proof checks and per-ETL
state, stage times and checks, blocked ETLs, assumed decisions and knowledge proposals (STATUS.json), and the audit
findings (AUDIT.json), and the commits the router made, one per agent (git log). Exit 0, or 2 for unusable input.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import stage_check as sc  # noqa: E402

NOT_PROVEN = [
    "Behavior on inputs outside the cases run (the sample and the fresh cases).",
    "Speed, memory, concurrency and behavior on the production database.",
    "Anything the domain knowledge or the assumed decisions get wrong.",
]


def check_cell(check):
    """A check line, or per-task checks ({"T0": "PASS", ...}) as "T0 PASS, T1 PASS"."""
    if isinstance(check, dict):
        return ", ".join("%s %s" % kv for kv in check.items())
    return str(check)


def summary(p):
    a = p["analysis"]
    status = sc.load_json(p["status"])
    audit = sc.load_json(os.path.join(a, "AUDIT.json"), default={})
    gate = status.get("gate") or {}
    pf = gate.get("proof") or {}
    out = ["# Summary — %s" % status.get("system", ""), "",
           "A **draft**: the decisions below were assumed, nothing was approved by a person.", "", "## Result", "",
           "- Gate: **%s**" % (gate.get("overall") or "not run"), "- Proof: **%s**" % (pf.get("verdict") or "not run")]
    if status.get("stage_failed"):
        out.append("- Stage failed: **%s** — %s" % (status["stage_failed"], status.get("stage_failed_reason", "")))
    out += ["  - not met: %s" % x for x in pf.get("failed", [])] + ["  - met: %s" % x for x in pf.get("passed", [])]
    out += ["", "| ETL | Gate | Diffs | Fix rounds |", "|---|---|---|---|"]
    out += ["| %s | %s | %s | %s |" % (e, g.get("state", ""), g.get("diffs", ""), g.get("runs", 0))
            for e, g in sorted((gate.get("etls") or {}).items())]
    out += ["", "| Stage | Start | End | Check |", "|---|---|---|---|"]
    for stage, t in (status.get("timing") or {}).items():
        for r in (t if isinstance(t, list) else [t]):
            out.append("| %s | %s | %s | %s |" % (stage, r.get("start", ""), r.get("end", ""),
                                                  check_cell((status.get("checks") or {}).get(stage, ""))))
    out += ["", "## Blocked", ""]
    out += ["- %s: tried %s; needs %s" % (e, "; ".join(b.get("tried") or []) or "—", b.get("needs") or "—")
            for e, b in sorted((status.get("blocked") or {}).items())] or ["None."]
    dec = status.get("decisions") or []
    assumed = [d for d in dec if d.get("source") == "assumed"]
    out += ["", "## Assumed decisions (%d of %d)" % (len(assumed), len(dec)), ""]
    out += ["- %s (%s): %s → %s [%s]" % (d.get("id", ""), d.get("stage", ""), d.get("question", ""), d.get("decision", ""),
                                         d.get("affects", "")) for d in assumed] or ["None."]
    findings = audit.get("findings") or []
    out += ["", "## Audit findings (%d)" % len(findings), ""]
    out += ["- **%s** %s: %s" % (f.get("severity", "?"), f.get("where", ""), f.get("issue", "")) for f in findings] or ["None."]
    out += ["", "## Knowledge proposals", ""]
    out += ["- %s" % (x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)) for x in status.get("proposals") or []] or ["None."]
    out += ["", "## For a person to do", "",
            "1. Review the assumed decisions, above all where the input domain was drawn; correct the domain "
            "knowledge where one is wrong and run modernize-auto again.",
            "2. Review the core business logic (ANALYSIS.json `logic`, level `core`).",
            "3. Accept or reject each remaining difference (STATUS.json `approved`: {\"C01-<TABLE>\": \"why\"}). "
            "This run never does.",
            "4. Merge the knowledge proposals into rule.md.",
            "", "## What this does not prove", ""] + ["- " + x for x in NOT_PROVEN]
    log = subprocess.run(["git", "-C", p["ws"], "log", "--reverse", "--format=%h %s", "--",
                          os.path.relpath(a, p["ws"]), os.path.relpath(os.path.dirname(p["java"]), p["ws"])],
                         capture_output=True, text=True)
    commits = log.stdout.strip().splitlines() if log.returncode == 0 else []
    out += ["", "## Commits (`git show <id>` for what an agent changed)", ""] + (["- " + c for c in commits] or ["None."])
    text = "\n".join(out) + "\n"
    with open(os.path.join(a, "SUMMARY.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text.split("\n| ETL |")[0].rstrip())
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system")
    ap.add_argument("--workspace", default=".")
    a = ap.parse_args(argv)
    try:
        return summary(sc.paths(a.workspace, a.system))
    except sc.InputError as err:
        print("summary: %s" % err, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
