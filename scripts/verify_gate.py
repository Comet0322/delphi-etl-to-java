#!/usr/bin/env python3
"""Decide whether the verify loop may continue for one ETL.

Prints exactly one line:  DONE | CONTINUE | BLOCKED:<code>
Rules and thresholds come from charter.yaml `blocked:`; nothing is judged by
the agent. Exit code: 0 DONE, 10 CONTINUE, 20 BLOCKED.
"""
import argparse
import json
import os
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from freeze import check_lock  # noqa: E402


def load_runs(out_dir, etl):
    runs = []
    for f in sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []:
        if re.match(r"run-\d+\.json$", f):
            with open(os.path.join(out_dir, f), encoding="utf-8") as fh:
                r = json.load(fh)
            if r.get("etl") == etl:
                runs.append(r)
    return runs


def decide(runs, rules):
    if not runs:
        return "CONTINUE"
    last = runs[-1]
    if last["diff_count"] == 0:
        return "DONE"
    max_attempts = rules.get("max_attempts", 8)
    same_n = rules.get("same_fingerprint_runs", 3)
    no_prog = rules.get("no_progress_runs", 4)

    if len(runs) >= max_attempts:
        return "BLOCKED:max_attempts"
    fps = [r["fingerprint"] for r in runs]
    if len(fps) >= same_n and len(set(fps[-same_n:])) == 1:
        return "BLOCKED:same_fingerprint"
    if len(fps) >= 3 and fps[-1] in fps[:-2] and fps[-1] != fps[-2]:
        return "BLOCKED:oscillation"
    counts = [r["diff_count"] for r in runs]
    if len(counts) > no_prog and min(counts[-no_prog:]) >= min(counts[:-no_prog]):
        return "BLOCKED:no_progress"
    return "CONTINUE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etl", required=True)
    ap.add_argument("--charter", default="charter.yaml")
    ap.add_argument("--out-dir", default="results/compare")
    ap.add_argument("--lock", default=".charter.lock")
    args = ap.parse_args()

    problems = check_lock(args.lock)
    if problems:
        print("BLOCKED:frozen_file_changed (%s)" % ", ".join(problems))
        return 20
    with open(args.charter, encoding="utf-8") as f:
        rules = (yaml.safe_load(f) or {}).get("blocked", {})
    verdict = decide(load_runs(args.out_dir, args.etl), rules)
    print(verdict)
    return {"DONE": 0, "CONTINUE": 10}.get(verdict, 20)


if __name__ == "__main__":
    sys.exit(main())
