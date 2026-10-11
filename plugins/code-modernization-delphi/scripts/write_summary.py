#!/usr/bin/env python3
"""Write analysis/<system>/AUTO_SUMMARY.md from the run's files. The closeout of modernize-auto.

    python3 write_summary.py <system> [--workspace DIR]

Everything in the summary is read from files, so it cannot misstate the result: the gate's OVERALL and per-ETL
state (AUTO_STATUS.json), the proof pack's verdict, reasons and limits (VERIFICATION.json), the stage checks and
times, the assumed decisions (DECISIONS.md), the audit findings (AUDIT.json), blocked ETLs with what they need,
and the knowledge proposals. Prints the Result section.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import etl_artifacts as ea  # noqa: E402

TODO = [
    "Review the assumed decisions below, above all the input domain; change INTENT.md or the domain knowledge where "
    "one is wrong and run modernize-auto again.",
    "Review the P0 rules in BUSINESS_RULES.md.",
    "Accept or reject each remaining difference (`approvedDifference` in the cases files). This run never does.",
    "Sign VERIFICATION.md.",
    "Merge knowledge-proposals.md into the domain knowledge (rule.md).",
]


def summary(p):
    a = p["analysis"]
    status = ea.load_json(os.path.join(a, "AUTO_STATUS.json"), required=False) or {}
    ver = ea.load_json(os.path.join(a, "VERIFICATION.json"), required=False) or {}
    audit = ea.load_json(os.path.join(a, "AUDIT.json"), required=False) or {}
    gate = status.get("gate") or {}
    verdict = (ver.get("overall") or {}).get("verdict") or "not run"
    out = ["# Auto summary — %s" % status.get("system", ""), "", "This is a **draft**: decisions below were assumed, "
           "nothing was approved by a person.", "", "## Result", ""]
    out.append("- Gate OVERALL: **%s**" % (gate.get("overall") or "not run"))
    out.append("- Proof pack verdict: **%s**" % verdict)
    if status.get("stage_failed"):
        out.append("- Stage failed: **%s** — %s" % (status.get("stage_failed"), status.get("stage_failed_reason", "")))
    for m in ver.get("modules", []):
        for r in m.get("reasons", []):
            out.append("  - not met (%s): %s" % (m.get("name"), r))
        for r in m.get("passed", []):
            out.append("  - passed (%s): %s" % (m.get("name"), r))
    out += ["", "| ETL | Gate state | Diffs | Fix rounds | Stage |", "|---|---|---|---|---|"]
    for e in sorted(set(status.get("etls", {})) | set(gate.get("etls", {}))):
        g, s = gate.get("etls", {}).get(e, {}), status.get("etls", {}).get(e, {})
        out.append("| %s | %s | %s | %s | %s |" % (e, g.get("state", ""), g.get("diffs", ""), g.get("runs", 0), s.get("stage", "")))
    out += ["", "| Stage | Start | End | Check |", "|---|---|---|---|"]
    checks = status.get("checks") or {}
    for stage, t in (status.get("timing") or {}).items():
        for r in (t if isinstance(t, list) else [t]):
            out.append("| %s | %s | %s | %s |" % (stage, r.get("start", ""), r.get("end", ""), checks.get(stage, "")))
    blocked = [(e, s.get("blocked") or {}) for e, s in sorted((status.get("etls") or {}).items())
               if (s.get("blocked") or {}).get("code")]
    out += ["", "## Blocked", ""]
    out += ["- %s: %s. Tried: %s. Needs: %s" % (e, b.get("code"), "; ".join(b.get("tried") or []) or "—", b.get("needs") or "—")
            for e, b in blocked] or ["None."]
    try:
        rows = [l for l in ea.read(os.path.join(a, "DECISIONS.md")).splitlines() if re.match(r"^\|\s*D-\d+", l)]
    except OSError:
        rows = []
    assumed = [l for l in rows if re.search(r"\|\s*assumed\s*\|", l)]
    out += ["", "## Assumed decisions (%d of %d)" % (len(assumed), len(rows)), ""]
    if assumed:
        out += ["| Id | Stage | Question | Decision | Source | Affects |", "|---|---|---|---|---|---|"] + assumed
    else:
        out.append("None.")
    findings = audit.get("findings") or []
    out += ["", "## Audit findings (%d)" % len(findings), ""]
    out += ["- **%s** %s at %s: %s" % (f.get("severity", "?"), f.get("kind", ""), f.get("where", ""), f.get("issue", ""))
            for f in findings] or ["None."]
    out += ["", "## For a person to do", ""] + ["%d. %s" % (i + 1, t) for i, t in enumerate(TODO)]
    limits = [x for m in ver.get("modules", []) for x in (m.get("notProven") or [])]
    out += ["", "## What this does not prove", ""] + ["- " + x for x in dict.fromkeys(limits)] or []
    kp = os.path.join(a, "knowledge-proposals.md")
    if os.path.isfile(kp):
        n = len([l for l in ea.read(kp).splitlines() if l.startswith("## ")])
        out += ["", "## Knowledge proposals", "", "%d proposal(s) in `knowledge-proposals.md`." % n]
    out += ["", "Report: `REPORT.html`. Proof: `VERIFICATION.md`. Traces of differences: `equivalence/TRACE.md`."]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system")
    ap.add_argument("--workspace", default=".")
    a = ap.parse_args(argv)
    p = ea.paths(a.workspace, a.system)
    try:
        text = summary(p)
    except ea.ArtifactError as err:
        print("write_summary: %s" % err, file=sys.stderr)
        return 2
    with open(os.path.join(p["analysis"], "AUTO_SUMMARY.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text.split("## Blocked")[0].rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
