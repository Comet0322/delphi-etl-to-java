#!/usr/bin/env python3
"""Generate the per-ETL migration report from inventory + compare results.

Nothing here is hand-written: legacy op (file:line) <-> data & rule <-> Java
location <-> verification status. Output: report/<ETL>.md and report/index.md
"""
import argparse
import glob
import json
import os
import re
import sys

import yaml


def load_yaml(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or default


def latest_run(results_dir, etl):
    best = None
    for p in sorted(glob.glob(os.path.join(results_dir, "run-*.json"))):
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
        if r.get("etl") == etl:
            best = r
    return best


def cell(s):
    return str(s if s not in (None, "") else "-").replace("|", "\\|").replace("\n", " ")


def implicit_summary(imp):
    hits = [k for k, v in (imp or {}).items() if isinstance(v, dict) and v.get("applies")]
    return ", ".join(hits) if hits else "-"


def etl_report(inv, run, st):
    rows = ["# %s %s" % (inv.get("etl_id"), inv.get("name") or ""), ""]
    if inv.get("depends_on"):
        rows += ["Depends on: " + ", ".join(inv["depends_on"]), ""]
    if st.get("stage") == "blocked":
        b = st.get("blocked", {})
        rows += ["> **BLOCKED** `%s` — needs: %s" % (b.get("code"), b.get("needs")), ""]
    if run:
        rows += ["Latest comparison: run %03d, **%d diff(s)**" % (run["run"], run["diff_count"]), ""]
    rows += ["| Op | Type | Legacy loc | Data & rule | Implicit | Java | Verification |",
             "|---|---|---|---|---|---|---|"]
    for op in inv.get("operations", []):
        data = "%s → %s: %s" % (", ".join(op.get("inputs") or []) or "-",
                                ", ".join(op.get("outputs") or []) or "-", op.get("rule") or "")
        if st.get("stage") == "done" and run and run["diff_count"] == 0:
            ver = "verified (run %03d)" % run["run"]
        elif st.get("stage") == "blocked":
            ver = "blocked"
        elif op.get("confidence") == "needs_human":
            ver = "needs human"
        else:
            ver = "unverified"
        rows.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            cell(op.get("op_id")), cell(op.get("type")), cell(op.get("source_loc")), cell(data),
            cell(implicit_summary(op.get("implicit"))), cell(op.get("target_loc")), ver))
    return "\n".join(rows) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etl-dir", default="etl")
    ap.add_argument("--results", default="results/compare")
    ap.add_argument("--out", default="report")
    ap.add_argument("--charter", default="charter.yaml")
    ap.add_argument("--status", default="status.yaml")
    a = ap.parse_args()

    charter = load_yaml(a.charter, {})
    status = load_yaml(a.status, {}).get("etls", {}) if load_yaml(a.status) else {}
    os.makedirs(a.out, exist_ok=True)

    index = ["# Migration report", ""]
    if charter.get("status") == "draft":
        index += ["> **DRAFT** — contains assumed decisions:", ""]
        for d in charter.get("decisions", []):
            if d.get("source") == "assumed":
                index.append("> - `%s` = %s (affects: %s)" % (d.get("key"), d.get("value"), d.get("affects") or "-"))
        index.append("")
    index += ["| ETL | Operations | Stage | Diffs |", "|---|---|---|---|"]

    for inv_path in sorted(glob.glob(os.path.join(a.etl_dir, "*", "inventory.yaml"))):
        inv = load_yaml(inv_path, {})
        etl = inv.get("etl_id")
        run = latest_run(a.results, etl)
        st = status.get(etl, {})
        with open(os.path.join(a.out, "%s.md" % re.sub(r"[^\w.-]", "_", etl)), "w", encoding="utf-8") as f:
            f.write(etl_report(inv, run, st))
        index.append("| %s | %d | %s | %s |" % (etl, len(inv.get("operations", [])), st.get("stage", "-"),
                                                run["diff_count"] if run else "-"))
    with open(os.path.join(a.out, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    print("report written to %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
