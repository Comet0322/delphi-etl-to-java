#!/usr/bin/env python3
"""Gate of the unattended fix loop: says, per ETL, whether to stop, keep fixing, or block. Never a model's opinion.

    python3 loop_gate.py <system> [--workspace DIR] [--record]

Reads analysis/<system>/RUN.json (which table belongs to which ETL), re-judges
analysis/<system>/equivalence/cases.json and fresh-cases.json with compare.py itself (it does not trust an earlier
EQUIVALENCE.json), reads analysis/<system>/VERIFICATION.json when it is newer than the built code, and keeps its
history in analysis/<system>/AUTO_STATUS.json under "gate".

Prints one line per ETL and one OVERALL line, and writes the same into AUTO_STATUS.json:

  ETL-001 EQUIVALENT diffs=0                every case of its tables is same (or a person approved it)
  ETL-002 CONTINUE diffs=3                  fix the Java and run the gate again
  ETL-003 BLOCKED:<code> diffs=2            stop working on it; a person decides (codes below)
  OVERALL VERIFY        every ETL is EQUIVALENT or BLOCKED, the proof pack is missing or older than the code
  OVERALL CONTINUE      some ETL is CONTINUE, or the proof pack is not PROVEN for reasons the loop can fix
  OVERALL DONE          every ETL EQUIVALENT and the proof pack PROVEN (PARTLY PROVEN when RUN.json says the
                        legacy cannot run here: recorded baselines cap the verdict)
  OVERALL BLOCKED       nothing left the loop may do

A case's diff counts for an ETL through its id "<input>-<TABLE>". --record counts this call as one attempt (call it
once per fix iteration); without it the gate only reports.

Block codes:
  same_diffs          the same differences (same cases, same first difference) N runs in a row
  no_progress         the number of differences did not go down in N runs
  max_attempts        the attempt limit was reached
  frozen_changed      RUN.json, or a legacy output, mask, tolerance or approval of a case seen before, changed
  mask_or_tolerance   a case carries a mask or a tolerance: only a person may decide one in unattended mode
  verify_stuck        the proof pack stayed not PROVEN for N verify runs with every ETL equivalent
Limits come from AUTO_STATUS.json "limits" (defaults: same_diffs 3, no_progress 4, max_attempts 8, verify 3).

Exit 0 for OVERALL DONE, 1 for VERIFY or CONTINUE, 3 for BLOCKED, 2 for unusable input.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LIMITS = {"same_diffs": 3, "no_progress": 4, "max_attempts": 8, "verify": 3}
SKIP_DIRS = {"target", "build", ".git", "node_modules", "__pycache__", ".idea"}


class InputError(Exception):
    pass


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        if default is not None:
            return default
        raise InputError("%s not found" % path)
    except ValueError as err:
        raise InputError("%s is not JSON: %s" % (path, err))


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def judge(cases_path):
    """compare.py's records for a cases file, or [] when the file does not exist."""
    if not os.path.isfile(cases_path):
        return [], {}
    spec = load_json(cases_path)
    fd, out = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "compare.py"), cases_path, "--out", out, "--quiet"],
                       capture_output=True, text=True)
        result = load_json(out, default={})
    finally:
        os.remove(out)
    if "cases" not in result:
        raise InputError("compare.py could not judge %s" % cases_path)
    return result["cases"], {c.get("id"): c for c in spec.get("cases", [])}


def newest_code(root):
    newest = 0.0
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for n in names:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(base, n)))
            except OSError:
                pass
    return newest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args(argv)
    ws = os.path.abspath(a.workspace)
    adir = os.path.join(ws, "analysis", a.system)
    try:
        run = load_json(os.path.join(adir, "RUN.json"))
        status_path = os.path.join(adir, "AUTO_STATUS.json")
        status = load_json(status_path, default={})
        limits = dict(DEFAULT_LIMITS, **(status.get("limits") or {}))
        gate = status.setdefault("gate", {})
        frozen = gate.setdefault("frozen", {})
        table_etl = {t["name"]: t.get("etl") or t["name"] for t in run.get("tables", [])}
        etls = sorted(set(table_etl.values()))
        eq = os.path.join(adir, "equivalence")

        problems = []
        run_hash = sha(json.dumps({k: run.get(k) for k in ("tables", "csv", "legacy", "new")}, sort_keys=True))
        if frozen.setdefault("RUN.json", run_hash) != run_hash:
            problems.append(("frozen_changed", "RUN.json changed since the loop started"))

        diffs = {e: [] for e in etls}
        unknown = []
        for name in ("cases.json", "fresh-cases.json"):
            path = os.path.join(eq, name)
            records, given = judge(path)
            for r in records:
                cid = r["id"]
                spec = given.get(cid, {})
                if spec.get("mask") or spec.get("tolerance") or load_json(path).get("tolerance"):
                    problems.append(("mask_or_tolerance", "case %s carries a mask or tolerance" % cid))
                seal = sha(json.dumps({"legacy": r.get("legacySha256"), "approved": spec.get("approvedDifference", ""),
                                       "mask": spec.get("mask"), "tolerance": spec.get("tolerance")}, sort_keys=True))
                key = "%s:%s" % (name, cid)
                if r.get("legacySha256"):
                    if frozen.setdefault(key, seal) != seal:
                        problems.append(("frozen_changed", "case %s: its legacy output, mask, tolerance or approval changed" % cid))
                table = cid.split("-", 1)[1] if "-" in cid else ""
                etl = table_etl.get(table)
                if etl is None:
                    unknown.append(cid)
                    continue
                if r["verdict"] in ("differs", "missing"):
                    first = r.get("firstDiff") or {}
                    diffs[etl].append("%s:%s:%s:%s" % (name, cid, r["verdict"], first.get("line", "")))

        code_root = os.path.join(ws, "modernized", a.system)
        ver_path = os.path.join(adir, "VERIFICATION.json")
        verification = None
        if os.path.isfile(ver_path) and os.path.getmtime(ver_path) >= newest_code(code_root):
            verification = load_json(ver_path)

        hist = gate.setdefault("etls", {})
        lines, states = [], {}
        for e in etls:
            h = hist.setdefault(e, {"runs": 0, "counts": [], "fingerprints": [], "state": ""})
            n = len(diffs[e])
            fp = sha("\n".join(sorted(diffs[e])))[:16]
            if h["state"].startswith("BLOCKED"):
                state = h["state"]
            elif problems:
                state = "BLOCKED:" + problems[0][0]
            elif n == 0:
                state = "EQUIVALENT"
            else:
                if a.record:
                    h["runs"] += 1
                    h["counts"].append(n)
                    h["fingerprints"].append(fp)
                c, f = h["counts"], h["fingerprints"]
                s, p = limits["same_diffs"], limits["no_progress"]
                if len(f) >= s and len(set(f[-s:])) == 1:
                    state = "BLOCKED:same_diffs"
                elif len(c) > p and min(c[-p:]) >= min(c[:-p]):
                    state = "BLOCKED:no_progress"
                elif h["runs"] >= limits["max_attempts"]:
                    state = "BLOCKED:max_attempts"
                else:
                    state = "CONTINUE"
            if a.record or state.startswith("BLOCKED") or state == "EQUIVALENT":
                h["state"] = state
            h["diffs"] = n
            h["sample"] = sorted(diffs[e])[:10]
            states[e] = state
            lines.append("%s %s diffs=%d" % (e, state, n))

        vg = gate.setdefault("verify", {"runs": 0, "verdicts": []})
        legacy_runs = run.get("legacy") is not None
        if all(s.startswith("BLOCKED") for s in states.values()) and states:
            overall = "BLOCKED"
        elif any(s == "CONTINUE" for s in states.values()):
            overall = "CONTINUE"
        elif verification is None:
            overall = "VERIFY"
        else:
            verdict = (verification.get("overall") or {}).get("verdict", "NOT PROVEN")
            ok = verdict == "PROVEN" or (verdict == "PARTLY PROVEN" and not legacy_runs)
            stamp = sha(json.dumps(verification.get("overall"), sort_keys=True) + str(os.path.getmtime(ver_path)))[:16]
            if a.record and stamp not in vg.get("seen", []):
                vg.setdefault("seen", []).append(stamp)
                vg["runs"] += 1
                vg["verdicts"].append(verdict)
            reasons = "; ".join(r[:200] for m in verification.get("modules", []) for r in m.get("reasons", [])[:5]) or verdict
            if ok and all(s == "EQUIVALENT" for s in states.values()):
                overall = "DONE"
            elif ok:
                overall = "BLOCKED"
            elif vg["runs"] >= limits["verify"]:
                overall = "BLOCKED"
                problems.append(("verify_stuck", "the proof pack stayed %s for %d verify runs: %s" % (verdict, vg["runs"], reasons)))
            else:
                overall = "CONTINUE"
                problems.append(("verification", reasons))
        gate["overall"] = overall
        gate["problems"] = [{"code": c, "detail": d} for c, d in problems]
        gate["unmappedCases"] = unknown
        tmp = status_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(status, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, status_path)
    except InputError as err:
        print("loop_gate: %s" % err, file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    for c, d in problems:
        print("  %s: %s" % (c, d))
    if unknown:
        print("  unmapped cases (no ETL for their table): %s" % ", ".join(unknown[:10]))
    print("OVERALL %s" % overall)
    return {"DONE": 0, "BLOCKED": 3}.get(overall, 1)


if __name__ == "__main__":
    sys.exit(main())
