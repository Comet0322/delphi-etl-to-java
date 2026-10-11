#!/usr/bin/env python3
"""Router, in the loop after each verify or fix: decide what comes next. From files, never a model's opinion.

    python3 loop_gate.py <system> [--workspace DIR] [--record]

The gate reads RESULTS.json (dual_run.py), ANALYSIS.json, RUN.json and STATUS.json, keeps its history in STATUS.json
"gate", and prints one line per ETL, the proof checks, a trace of every difference when there is something to fix,
and an OVERALL line:

  ETL-001 EQUIVALENT diffs=0        every table of the ETL is the same in every case (or a person approved it)
  ETL-002 CONTINUE diffs=3          fix the Java and run the gate again
  ETL-003 WAIT diffs=4              differs, but an ETL it depends on differs too: fix that one first (not counted
                                    as an attempt; its differences may disappear)
  ETL-003 BLOCKED:<code> diffs=2    stop working on it; a person decides
  OVERALL VERIFY     no fresh cases yet, or RESULTS.json is older than the Java: run the verify stage
  OVERALL CONTINUE   some ETL is CONTINUE, or a proof check fails that the code or tests can fix
  OVERALL DONE       every ETL EQUIVALENT and the proof PROVEN (PARTLY PROVEN when the legacy output is recorded)
  OVERALL BLOCKED    nothing left the loop may do

Proof checks: the tests passed (RUN.json new.test, run by dual_run.py); every core business-logic item is named in a test
source (BL-002 as bl002 or BL-002); every table is the same in every case; at least 10 fresh cases covering the edge
categories (stage_check.py verify); every output table has rows in at least one case (an empty comparison proves
nothing); the legacy source is unchanged since init. Verdict PROVEN when all hold, PARTLY PROVEN when all hold but
the legacy output is recorded, else NOT PROVEN.

The trace joins each differing TABLE.COLUMN to its ETL, the inventory ops that write it (source_loc = legacy lines)
and their `// ETL-xxx/OP-nn` comments in the Java, with a cascade note when an ETL it depends on also differs.

--record counts this call as one attempt (once per fix round). Block codes: same_diffs (the same differences N
rounds in a row), no_progress (the count did not go down in N rounds), max_attempts, frozen_changed (RUN.json
changed), source_changed, verify_stuck (the proof stayed not PROVEN for N verify rounds). Limits: STATUS.json
"limits". Exit 0 DONE, 1 VERIFY or CONTINUE, 3 BLOCKED, 2 unusable input.
"""
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import stage_check as check  # noqa: E402

SKIP_DIRS = {"target", "build", ".git", "node_modules", "__pycache__", ".idea"}
DIFF = re.compile(r"^key (.*?): (\S+) legacy=(.*) new=(.*)$")
ONLY = re.compile(r"^key (.*?): only in (legacy|new)$")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def newest(root):
    t = 0.0
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for n in names:
            t = max(t, os.path.getmtime(os.path.join(base, n)))
    return t


def table_etl(analysis):
    return {str(t.get("name", "")).upper(): e.get("id") for e in analysis.get("etls") or [] for t in e.get("outputs") or []}


def differences(results, approved, owner):
    """-> {etl: ["case:table:verdict:first line"]} of every table result not the same and not approved."""
    out = {}
    for cid, c in (results.get("cases") or {}).items():
        for t, r in (c.get("tables") or {}).items():
            if r.get("verdict") in ("same", "no-legacy", "pending") or approved.get("%s-%s" % (cid, t)):
                continue
            lines = r.get("diff") or [""]
            first = next((l for l in lines if not l.startswith("rows:")), lines[0])
            out.setdefault(owner.get(t.upper(), "?"), []).append("%s:%s:%s:%s" % (cid, t, r.get("verdict"), first))
    return out


def trace(p, analysis, results, approved, owner):
    """Lines joining each differing TABLE.COLUMN to ops, legacy lines and Java lines."""
    found = {}
    for cid, c in (results.get("cases") or {}).items():
        for t, r in (c.get("tables") or {}).items():
            if r.get("verdict") in ("same", "no-legacy", "pending") or approved.get("%s-%s" % (cid, t)):
                continue
            cols = set()
            for line in r.get("diff") or []:
                m = DIFF.match(line)
                if m:
                    cols.add(m.group(2).upper())
                elif ONLY.match(line) or "table missing" in line or line.startswith("columns differ"):
                    cols.add("(row)")
            for col in cols or {"(row)"}:
                found.setdefault((owner.get(t.upper(), "?"), t.upper(), col), set()).add(cid)
    differing = {k[0] for k in found}
    deps = {e.get("id"): e.get("depends_on") or [] for e in analysis.get("etls") or []}
    comments = check.op_comments(p["java"])
    lines = []
    for (etl, table, col), cases in sorted(found.items()):
        column_ops, table_ops = [], []
        for op in (analysis.get("inventory") or {}).get(etl) or []:
            for w in op.get("writes") or []:
                wt, _, wc = str(w).upper().replace('"', "").partition(".")
                if wt == table and (wc == col or (col == "(row)" and wc not in ("", "*"))):
                    column_ops.append(op)
                    break
                if wt == table and wc in ("", "*"):
                    table_ops.append(op)
                    break
        ops = column_ops or table_ops     # a whole-table op (CREATE, DROP) only when nothing writes the column
        where = "; ".join("%s legacy %s java %s" % (
            o.get("op_id"), o.get("source_loc"),
            ",".join("%s:%d" % loc for loc in comments.get("%s/%s" % (etl, o.get("op_id")), [])[:2]) or "no comment")
            for o in ops) or "no op writes it (missing from the inventory?)"
        cascade = [d for d in deps.get(etl, []) if d in differing]
        lines.append("TRACE %s %s.%s in %d case(s) (%s) -> %s%s" % (
            etl, table, col, len(cases), ",".join(sorted(cases)[:4]), where,
            " [possible cascade from %s: fix it first]" % ",".join(cascade) if cascade else ""))
    return lines


def proof(p, analysis, results, run, status, states):
    passed, failed = [], []

    def check_(ok, text, why):
        (passed if ok else failed).append(text if ok else "%s: %s" % (text, why))
    tests = results.get("tests") or {}
    tail = (tests.get("tail") or "").splitlines()
    shown = [l.strip() for l in tail if re.search(r"Failures: [1-9]|Errors: [1-9]|FAIL|expected|Exception|error:", l)][:4] or tail[-2:]
    check_(tests.get("exit") == 0, "tests pass", "exit %s; %s" % (tests.get("exit"), " / ".join(shown)[:400]))
    test_text = "\n".join(check.read(f) for f in check.java_sources(p["java"], "test"))
    untested = []
    for r in analysis.get("logic") or []:
        if r.get("level") != "core":
            continue
        num = str(r.get("id", "")).split("-")[-1]
        if not re.search(r"(?i)\bbl[-_]?%s(?!\d)" % re.escape(num), test_text):
            untested.append(r.get("id"))
    check_(not untested, "every core logic item has a test", "no test names %s" % ", ".join(map(str, untested)))
    differing = [e for e, s in states.items() if s != "EQUIVALENT"]
    check_(not differing, "every table is the same in every case", "%s not equivalent" % ", ".join(differing))
    fails = []
    check.check_verify(p, fails)
    check_(not fails, "at least %d fresh cases cover the edge categories" % check.MIN_FRESH,
           "; ".join(d for _, d in fails[:5]))
    empty = []
    for t in table_etl(analysis):
        rows = 0
        for c in (results.get("cases") or {}).values():
            side = {k.upper(): v for k, v in (c.get("legacy") or c.get("new") or {}).items()}
            rows = max(rows, len([l for l in (side.get(t) or "").split("\n")[1:] if l]))
        if not rows:
            empty.append(t)
    check_(not empty, "every output table has rows in some case", "always empty: %s" % ", ".join(empty))
    src = (status.get("intent") or {}).get("source", "")
    same_src = os.path.isdir(src) and check.source_sha(src) == (status.get("intent") or {}).get("source_sha")
    check_(same_src, "legacy source unchanged", "its hash differs from the one taken at init")
    recorded = bool((run.get("legacy") or {}).get("recorded"))
    verdict = "NOT PROVEN" if failed else ("PARTLY PROVEN" if recorded else "PROVEN")
    if recorded:
        passed.append("legacy output is recorded: fresh cases ran on the new side only")
    return {"verdict": verdict, "passed": passed, "failed": failed, "source_changed": not same_src,
            "needs_verify": bool(fails)}


def run_gate(p, record):
    a = p["analysis"]
    status = check.load_json(p["status"])
    analysis = check.load_json(os.path.join(a, "ANALYSIS.json"))
    run = check.load_json(os.path.join(a, "RUN.json"))
    res_path = os.path.join(a, "RESULTS.json")
    results = check.load_json(res_path, default={})
    limits = dict(check.LIMITS, **(status.get("limits") or {}))
    approved = status.get("approved") or {}
    gate = status.setdefault("gate", {})
    owner = table_etl(analysis)
    problems = []
    run_hash = sha(json.dumps(run, sort_keys=True))
    if gate.setdefault("frozen_run", run_hash) != run_hash:
        problems.append(("frozen_changed", "RUN.json changed since the loop started"))
    stale = not results or os.path.getmtime(res_path) < newest(os.path.dirname(p["java"]))
    diffs = differences(results, approved, owner)
    hist = gate.setdefault("etls", {})
    deps = {e.get("id"): e.get("depends_on") or [] for e in analysis.get("etls") or []}
    open_ = {e for e in set(owner.values()) if diffs.get(e)
             and not (hist.get(e) or {}).get("state", "").startswith("BLOCKED")}
    wait = {e for e in open_ if any(d in open_ for d in deps.get(e, []))}
    states, lines = {}, []
    for e in sorted(set(owner.values())):
        h = hist.setdefault(e, {"runs": 0, "counts": [], "fingerprints": [], "state": ""})
        d = sorted(diffs.get(e, []))
        if h["state"].startswith("BLOCKED"):
            state = h["state"]
        elif problems:
            state = "BLOCKED:" + problems[0][0]
        elif not d:
            state = "EQUIVALENT"
        elif e in wait:
            state = "WAIT"
        else:
            if record and not stale:
                h["runs"] += 1
                h["counts"].append(len(d))
                h["fingerprints"].append(sha("\n".join(d))[:16])
            c, f = h["counts"], h["fingerprints"]
            s, n = limits["same_diffs"], limits["no_progress"]
            if len(f) >= s and len(set(f[-s:])) == 1:
                state = "BLOCKED:same_diffs"
            elif len(c) > n and min(c[-n:]) >= min(c[:-n]):
                state = "BLOCKED:no_progress"
            elif h["runs"] >= limits["max_attempts"]:
                state = "BLOCKED:max_attempts"
            else:
                state = "CONTINUE"
        if record or state.startswith("BLOCKED") or state == "EQUIVALENT":
            h["state"] = state
        h["diffs"], h["sample"] = len(d), d[:10]
        states[e] = state
        lines.append("%s %s diffs=%d" % (e, state, len(d)))
    pf = proof(p, analysis, results, run, status, states) if results else None
    vg = gate.setdefault("verify", {"runs": 0, "seen": []})
    if stale:
        overall = "VERIFY"
        problems.append(("stale", "RESULTS.json is missing or older than the Java: run dual_run.py"))
    elif pf["source_changed"]:
        overall = "BLOCKED"
        problems.append(("source_changed", "the legacy source changed since init"))
    elif states and all(s.startswith("BLOCKED") for s in states.values()):
        overall = "BLOCKED"
    elif any(s in ("CONTINUE", "WAIT") for s in states.values()):
        overall = "CONTINUE"
    elif pf["needs_verify"]:
        overall = "VERIFY"
    elif pf["verdict"] != "NOT PROVEN":
        overall = "DONE" if all(s == "EQUIVALENT" for s in states.values()) else "BLOCKED"
    else:
        stamp = sha(json.dumps(results.get("tests"), sort_keys=True) + str(os.path.getmtime(res_path)))[:16]
        if record and stamp not in vg["seen"]:
            vg["seen"].append(stamp)
            vg["runs"] += 1
        if vg["runs"] >= limits["verify"]:
            overall = "BLOCKED"
            problems.append(("verify_stuck", "the proof stayed NOT PROVEN for %d rounds" % vg["runs"]))
        else:
            overall = "CONTINUE"
    traced = trace(p, analysis, results, approved, owner) if overall == "CONTINUE" else []
    gate.update({"overall": overall, "proof": pf, "problems": [{"code": c, "detail": d} for c, d in problems]})
    check.save_json(p["status"], status)
    for line in lines:
        print(line)
    for x in (pf or {}).get("failed", []):
        print("  proof not met: %s" % x)
    for c, d in problems:
        print("  %s: %s" % (c, d))
    for t in traced:
        print(t)
    print("PROOF %s" % (pf or {}).get("verdict", "not run"))
    print("OVERALL %s" % overall)
    return {"DONE": 0, "BLOCKED": 3}.get(overall, 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args(argv)
    p = check.paths(a.workspace, a.system)
    try:
        return run_gate(p, a.record)
    except check.InputError as err:
        print("loop_gate: %s" % err, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
