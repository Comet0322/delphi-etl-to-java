#!/usr/bin/env python3
"""Compare baseline vs candidate datasets as configured in compare.yaml.

Writes results/compare/run-NNN.json (append-only; never overwrites) and prints
a one-line summary. Exit code 0 = zero diffs, 1 = diffs, 2 = error.

Tolerances live only in the config file. This script has no knowledge of any
particular database, table suffix or company convention: sources are read
through small adapters selected by `source.adapter`.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
from decimal import Decimal, InvalidOperation

import yaml


# ---------------------------------------------------------------- adapters
def load_sqlite(source, ref):
    conn = sqlite3.connect(source["path"])
    try:
        cur = conn.execute("SELECT * FROM %s" % ref)
        cols = [d[0].upper() for d in cur.description]
        return cols, [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def load_csv(source, ref):
    path = os.path.join(source.get("dir", "."), ref)
    with open(path, newline="", encoding=source.get("encoding", "utf-8")) as f:
        rd = csv.DictReader(f)
        rows = [{k.upper(): (v if v != "" else None) for k, v in r.items()} for r in rd]
        return [c.upper() for c in rd.fieldnames], rows


ADAPTERS = {"sqlite": load_sqlite, "csv": load_csv}


# ------------------------------------------------------------ normalization
def norm(value, rule, defaults):
    """Return a comparable form of one cell under its rule."""
    kind = rule.get("type", "string")
    null_eq_empty = rule.get("null_equals_empty", defaults.get("null_equals_empty", False))
    if value is None or (isinstance(value, str) and value == "" and null_eq_empty):
        return None if not null_eq_empty else ""
    if kind in ("decimal", "int", "float"):
        try:
            return Decimal(str(value).strip())
        except InvalidOperation:
            return str(value)
    s = str(value)
    mode = rule.get("strip", defaults.get("strip", "none"))
    if mode == "right":
        s = s.rstrip(" ")
    elif mode == "both":
        s = s.strip(" ")
    if rule.get("case_insensitive", False):
        s = s.upper()
    return s


def same(a, b, rule, defaults):
    if isinstance(a, Decimal) and isinstance(b, Decimal):
        tol = Decimal(str(rule.get("abs_tol", defaults.get("abs_tol", 0))))
        return abs(a - b) <= tol
    return a == b


# ------------------------------------------------------------------ compare
def keyed(rows, key, rules, defaults):
    out, seen = {}, {}
    for r in rows:
        k = tuple(norm(r.get(c), rules.get(c, {}), defaults) for c in key)
        n = seen.get(k, 0)
        seen[k] = n + 1
        out[k + (n,)] = r
    return out


def compare_dataset(ds, source, defaults):
    load = ADAPTERS[source["adapter"]]
    bcols, brows = load(source, ds["baseline"])
    ccols, crows = load(source, ds["candidate"])
    key = [c.upper() for c in ds["key"]]
    rules = {k.upper(): v for k, v in ds.get("columns", {}).items()}
    ignore = {c.upper() for c in ds.get("ignore", [])}
    cols = [c for c in bcols if c in ccols and c not in ignore and c not in key]
    schema_diff = sorted((set(bcols) ^ set(ccols)) - ignore)

    b = keyed(brows, key, rules, defaults)
    c = keyed(crows, key, rules, defaults)
    diffs = []
    for k in sorted(set(b) - set(c), key=str):
        diffs.append({"dataset": ds["name"], "kind": "missing", "key": list(map(str, k[:-1])), "columns": []})
    for k in sorted(set(c) - set(b), key=str):
        diffs.append({"dataset": ds["name"], "kind": "extra", "key": list(map(str, k[:-1])), "columns": []})
    for k in sorted(set(b) & set(c), key=str):
        bad = []
        for col in cols:
            rule = rules.get(col, {})
            if not same(norm(b[k].get(col), rule, defaults), norm(c[k].get(col), rule, defaults), rule, defaults):
                bad.append(col)
        if bad:
            diffs.append({"dataset": ds["name"], "kind": "changed", "key": list(map(str, k[:-1])), "columns": bad,
                          "baseline": {x: str(b[k].get(x)) for x in bad},
                          "candidate": {x: str(c[k].get(x)) for x in bad}})
    for col in schema_diff:
        diffs.append({"dataset": ds["name"], "kind": "schema", "key": [], "columns": [col]})
    return {"rows_baseline": len(brows), "rows_candidate": len(crows)}, diffs


def fingerprint(diffs):
    items = sorted(json.dumps([d["dataset"], d["kind"], d["key"], d["columns"]]) for d in diffs)
    return hashlib.sha256("\n".join(items).encode()).hexdigest()[:16]


def next_run_number(out_dir):
    nums = [int(m.group(1)) for f in os.listdir(out_dir) for m in [re.match(r"run-(\d+)\.json$", f)] if m]
    return max(nums, default=0) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--etl", default=None, help="only datasets tagged with this ETL id")
    ap.add_argument("--out-dir", default="results/compare")
    args = ap.parse_args()

    with open(args.config, "rb") as f:
        raw = f.read()
    cfg = yaml.safe_load(raw)
    defaults = cfg.get("defaults", {})
    datasets = [d for d in cfg["datasets"] if args.etl is None or d.get("etl") == args.etl]
    if not datasets:
        print("ERROR: no datasets selected", file=sys.stderr)
        return 2

    os.makedirs(args.out_dir, exist_ok=True)
    stats, all_diffs = {}, []
    try:
        for ds in datasets:
            s, d = compare_dataset(ds, cfg["source"], defaults)
            stats[ds["name"]] = s
            all_diffs.extend(d)
    except Exception as e:  # missing table, bad config, ...
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    run = next_run_number(args.out_dir)
    result = {
        "run": run,
        "etl": args.etl,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "datasets": stats,
        "diff_count": len(all_diffs),
        "fingerprint": fingerprint(all_diffs),
        "diffs": all_diffs,
    }
    path = os.path.join(args.out_dir, "run-%03d.json" % run)
    with open(path, "x", encoding="utf-8") as f:  # 'x': refuse to overwrite
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("run %03d etl=%s diffs=%d fingerprint=%s -> %s" %
          (run, args.etl, len(all_diffs), result["fingerprint"], path))
    return 0 if not all_diffs else 1


if __name__ == "__main__":
    sys.exit(main())
