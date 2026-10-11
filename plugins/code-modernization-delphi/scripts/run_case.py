#!/usr/bin/env python3
"""Run one input case through the legacy and the new program and collect one CSV per output table and side.

    python3 run_case.py <RUN.json> --input <case input dir> --id C01 --cases <cases.json>
                        [--prefix fresh] [--build] [--skip-legacy] [--workspace DIR]

It knows nothing about databases or how either program stores its results: RUN.json says how to build, run and
capture each side, the way the domain knowledge describes. This script runs those commands, puts each side's
captured files into a canonical form, and lists the pairs for compare.py and proof_pack.py. It never judges.

RUN.json (written by the analyze stage from the domain knowledge, frozen once proven):

    {"tables": [{"name": "T_CUST_CLEAN", "key": ["CUST_ID"], "etl": "ETL-001"}],
     "csv": {"null": "\\\\N"},                      # how captured files write NULL (default \\N)
     "env": {"JAVA_HOME": "/path"},                 # optional, added to every command's environment
     "legacy": {"build": "...", "run": "...", "capture": "...", "recorded": false},
     "new":    {"build": "...", "run": "...", "capture": "...", "test": "...",
                "properties": {"path": "{work}/etl.properties", "values": {"k": "v with {work}"}}}}

Per side: the input dir is copied to a scratch dir {work}; `properties` (optional) is written; `build` (with
--build) and `run` run; then `capture` runs and must leave `{out}/<TABLE>.csv` for every table (a side whose run
already writes those files needs no capture). `recorded: true` means the legacy cannot run here: `run` may be
empty and `capture` produces the recorded output (for example copies it out of the case dir); the proof then
caps at PARTLY PROVEN. Placeholders: {work} the side's scratch copy, {out} the capture dir, {input} the original
case dir (read only), {ws} the workspace, {id} the case id. Commands run from the workspace through the shell.

Captured CSVs: a header row of column names, then rows; fields may be quoted with double quotes ("" inside);
the NULL token is RUN.json csv.null. Canonical form written for comparison: header, then rows sorted by the table's
key columns and then by every column, each field kept exactly as captured (quotes included, so "1" and 1 stay
different), NULL written as \\N, UTF-8, LF line ends.

For case <id> under the cases file's folder <root> and prefix <p> ("" or "fresh"):
  <root>/<p>/work/<id>/<side>/     scratch copies; the input dir itself is never written
  <root>/<p>/<side>/<id>/<T>.csv   canonical output of table T
  <root>/<p>/logs/<id>.<side>.log  the commands and their output
  <root>/<p>/diag/<id>/<T>.txt     row-by-row difference by key, for people and trace_diff.py (diagnostic only)

A case entry already in the cases file keeps every field a person or an earlier run set (mask, tolerance,
approvedDifference, note); only its paths are refreshed. Exit 0 when every command succeeded, 1 when one failed
(outputs and cases are still written, so the comparison shows what is missing), 2 for unusable input.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

NULL = "\\N"
DIAG_ROWS = 50
SIDES = ("legacy", "new")


class InputError(Exception):
    pass


def load_run(path):
    try:
        with open(path, encoding="utf-8") as fh:
            run = json.load(fh)
    except (OSError, ValueError) as err:
        raise InputError("cannot read %s: %s" % (path, err))
    tables = run.get("tables")
    if not isinstance(tables, list) or not tables:
        raise InputError("RUN.json needs a non-empty tables list")
    for t in tables:
        if not isinstance(t, dict) or not isinstance(t.get("name"), str) or not t["name"].replace("_", "").isalnum():
            raise InputError("bad table entry %r" % (t,))
        if not isinstance(t.get("key", []), list):
            raise InputError("table %s: key must be a list" % t["name"])
    for side in SIDES:
        spec = run.get(side)
        if not isinstance(spec, dict):
            raise InputError("RUN.json needs a %s object" % side)
        if not (spec.get("run") or spec.get("capture")):
            raise InputError("RUN.json %s needs run or capture" % side)
    run.setdefault("csv", {}).setdefault("null", NULL)
    return run


def split_records(text):
    """CSV text -> list of records, each a list of raw fields (quotes kept). Quoted fields may span lines."""
    records, rec, field, q, i, n = [], [], [], False, 0, len(text)
    while i < n:
        ch = text[i]
        if q:
            field.append(ch)
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    field.append('"')
                    i += 1
                else:
                    q = False
        elif ch == '"':
            q = True
            field.append(ch)
        elif ch == ",":
            rec.append("".join(field))
            field = []
        elif ch in "\r\n":
            if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
            rec.append("".join(field))
            field = []
            if rec != [""]:
                records.append(rec)
            rec = []
        else:
            field.append(ch)
        i += 1
    if field or rec:
        rec.append("".join(field))
        if rec != [""]:
            records.append(rec)
    return records


def unquote(cell):
    return cell[1:-1].replace('""', '"') if len(cell) >= 2 and cell[0] == cell[-1] == '"' else cell


def canonical(path, key, null):
    """A captured CSV -> (header cells, sorted rows of raw cells), or None when the file is missing."""
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            records = split_records(fh.read())
    except FileNotFoundError:
        return None
    except UnicodeDecodeError as err:
        raise InputError("%s is not UTF-8: %s" % (path, err))
    if not records:
        return [], []
    header = records[0]
    rows = [[NULL if c == null else c for c in r] for r in records[1:]]
    names = [unquote(h).upper() for h in header]
    idx = [names.index(k.upper()) for k in key if k.upper() in names]
    order = idx + [i for i in range(len(header)) if i not in idx]
    rows.sort(key=lambda r: [r[i] if i < len(r) else "" for i in order])
    return header, rows


def write_csv(path, table):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    header, rows = table
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join([",".join(header)] + [",".join(r) for r in rows]) + "\n")


def diag(path, name, key, old, new):
    """Row-by-row difference of two canonical tables, matched on the key (all columns when there is none)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = []
    if old is None or new is None:
        out.append("%s: %s table missing" % (name, "legacy" if old is None else "new"))
    else:
        (oc, orows), (nc, nrows) = old, new
        on, nn = [unquote(c).upper() for c in oc], [unquote(c).upper() for c in nc]
        if on != nn:
            out.append("columns differ: legacy %s, new %s" % (",".join(oc), ",".join(nc)))
        kidx = [on.index(k.upper()) for k in key if k.upper() in on] or list(range(len(oc)))
        nmap = [nn.index(c) if c in nn else None for c in on]

        def align(r):
            return [r[j] if j is not None and j < len(r) else NULL for j in nmap]

        def index(rows):
            m = {}
            for r in rows:
                m.setdefault(tuple(r[i] if i < len(r) else "" for i in kidx), []).append(r)
            return m
        om, nm = index(orows), index([align(r) for r in nrows])
        out.append("rows: legacy %d, new %d" % (len(orows), len(nrows)))
        shown = 0
        for kk in sorted(set(om) | set(nm)):
            a, b = om.get(kk, []), nm.get(kk, [])
            if a == b:
                continue
            shown += 1
            if shown > DIAG_ROWS:
                out.append("... more differing keys not shown")
                break
            label = ",".join(kk)
            if not a or not b:
                out.append("key %s: only in %s" % (label, "new" if not a else "legacy"))
                continue
            for ra, rb in zip(a, b):
                for i, c in enumerate(oc):
                    va, vb = (ra[i] if i < len(ra) else ""), (rb[i] if i < len(rb) else "")
                    if va != vb:
                        out.append("key %s: %s legacy=%s new=%s" % (label, c, va, vb))
            if len(a) != len(b):
                out.append("key %s: legacy has %d row(s), new %d" % (label, len(a), len(b)))
        if shown == 0:
            out.append("no differences")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")


def make_writable(root):
    for base, dirs, names in os.walk(root):
        for n in dirs + names:
            path = os.path.join(base, n)
            if not os.path.islink(path):
                os.chmod(path, os.stat(path).st_mode | 0o200)
    os.chmod(root, os.stat(root).st_mode | 0o200)


def subst(text, ctx):
    for k, v in ctx.items():
        text = text.replace("{%s}" % k, v)
    return text


def run_cmd(cmd, ctx, env, log, ws):
    with open(log, "a", encoding="utf-8", errors="replace") as fh:
        fh.write("$ %s\n" % subst(cmd, ctx))
        fh.flush()
        rc = subprocess.call(subst(cmd, ctx), shell=True, cwd=ws, env=env, stdout=fh, stderr=subprocess.STDOUT)
        fh.write("exit %d\n" % rc)
    return rc


def upsert_cases(cases_path, run, case_id, prefix):
    try:
        with open(cases_path, encoding="utf-8") as fh:
            spec = json.load(fh)
    except FileNotFoundError:
        spec = {"system": "", "legacy": {"label": "legacy"}, "new": {"label": "new"}, "cases": []}
    except ValueError as err:
        raise InputError("cases file %s is not JSON: %s" % (cases_path, err))
    by_id = {c.get("id"): c for c in spec.setdefault("cases", [])}
    for t in run["tables"]:
        cid = "%s-%s" % (case_id, t["name"])
        entry = by_id.get(cid)
        if entry is None:
            entry = {"id": cid, "input": case_id,
                     "title": "%s%s on input %s" % ((t.get("etl") + " ") if t.get("etl") else "", t["name"], case_id)}
            spec["cases"].append(entry)
            by_id[cid] = entry
        for side in SIDES:
            entry[side] = "/".join(filter(None, [prefix, side, case_id, t["name"] + ".csv"]))
        entry.setdefault("input", case_id)
    tmp = cases_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, cases_path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run")
    ap.add_argument("--input", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--prefix", default="")
    ap.add_argument("--build", action="store_true", help="run the build commands first")
    ap.add_argument("--skip-legacy", action="store_true", help="reuse this case's earlier legacy output")
    ap.add_argument("--workspace", default=".")
    a = ap.parse_args(argv)
    failed = []
    try:
        if not a.id.replace("-", "").replace("_", "").isalnum():
            raise InputError("case id must be letters, digits, - or _")
        if a.prefix not in ("", "fresh"):
            raise InputError('prefix must be "" or "fresh"')
        run = load_run(a.run)
        ws = os.path.abspath(a.workspace)
        root = os.path.dirname(os.path.abspath(a.cases))
        src = os.path.abspath(a.input)
        if not os.path.isdir(src):
            raise InputError("input dir %s does not exist" % src)
        base = os.path.join(root, a.prefix) if a.prefix else root
        logs = os.path.join(base, "logs")
        os.makedirs(logs, exist_ok=True)
        tables = {}
        for side in SIDES:
            final = os.path.join(base, side, a.id)
            log = os.path.join(logs, "%s.%s.log" % (a.id, side))
            if side == "legacy" and a.skip_legacy:
                missing = [t["name"] for t in run["tables"] if not os.path.isfile(os.path.join(final, t["name"] + ".csv"))]
                if missing:
                    raise InputError("--skip-legacy: no earlier legacy output of %s for case %s" % (", ".join(missing), a.id))
                tables[side] = {t["name"]: canonical(os.path.join(final, t["name"] + ".csv"), t.get("key", []), NULL)
                                for t in run["tables"]}
                continue
            work = os.path.join(base, "work", a.id, side)
            out = os.path.join(base, "work", a.id, side + "-out")
            for d in (work, out):
                if os.path.exists(d):
                    shutil.rmtree(d)
            shutil.copytree(src, work)
            make_writable(work)   # the input may be read-only on purpose; its scratch copy must not be
            os.makedirs(out)
            if os.path.exists(log):
                os.remove(log)
            ctx = {"work": work, "out": out, "input": src, "ws": ws, "id": a.id}
            env = dict(os.environ)
            env.update({k: subst(str(v), ctx) for k, v in (run.get("env") or {}).items()})
            spec = run[side]
            props = spec.get("properties")
            if props:
                with open(subst(props.get("path", "{work}/run.properties"), ctx), "w", encoding="utf-8") as fh:
                    for k, v in (props.get("values") or {}).items():
                        fh.write("%s=%s\n" % (k, subst(str(v), ctx)))
            ok = True
            for step in ("build", "run", "capture"):
                if step == "build" and not a.build:
                    continue
                if spec.get(step) and run_cmd(spec[step], ctx, env, log, ws):
                    failed.append("%s %s" % (side, step))
                    ok = False
                    break
            if os.path.exists(final):
                shutil.rmtree(final)
            tables[side] = {}
            for t in run["tables"]:
                got = canonical(os.path.join(out, t["name"] + ".csv"), t.get("key", []), run["csv"]["null"])
                tables[side][t["name"]] = got
                if got is not None:
                    write_csv(os.path.join(final, t["name"] + ".csv"), got)
        for t in run["tables"]:
            diag(os.path.join(base, "diag", a.id, t["name"] + ".txt"), t["name"], t.get("key", []),
                 tables["legacy"][t["name"]], tables["new"][t["name"]])
        upsert_cases(os.path.abspath(a.cases), run, a.id, a.prefix)
    except InputError as err:
        print("run_case: %s" % err, file=sys.stderr)
        return 2
    if failed:
        print("run_case %s: failed: %s (see %s)" % (a.id, ", ".join(failed), logs), file=sys.stderr)
        return 1
    print("run_case %s: ok, %d table(s) per side" % (a.id, len(run["tables"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
