#!/usr/bin/env python3
"""Agents, in survey (--probe), transform, verify and fix: run both programs on every case and compare.

    python3 dual_run.py <system> [--workspace DIR] [--probe] [--rerun-legacy]

Cases. C01 is the sample input named in STATUS.json (intent.inputs). When analysis/<system>/fresh_inputs.py exists
it is run as `python3 fresh_inputs.py <dir>` and must create one folder per fresh case in <dir> (F01, F02, ...,
same structure as C01) and <dir>/categories.json:

    {"cases": {"F01": ["thresholds", "rounding_ties"]}, "not_applicable": {"empty_input_file": "no ETL reads a file"}}

It must be deterministic and use the standard library only.

Output tables are the `outputs` ({name, key}) of every ETL in ANALYSIS.json. RUN.json says how each side is built,
run and captured, the way the domain knowledge describes; this script knows nothing about databases:

    {"csv": {"null": "\\\\N"}, "env": {"JAVA_HOME": "/path"},
     "legacy": {"build": "...", "run": "...", "capture": "...", "recorded": false},
     "new":    {"build": "...", "run": "...", "capture": "...", "test": "...",
                "properties": {"path": "{work}/etl.properties", "values": {"k": "v with {work}"}}}}

Per side and case the input folder is copied to {work} (made writable), `properties` is written, `run` runs, then
`capture` must leave {out}/<TABLE>.csv (a run that writes those files itself needs no capture). Placeholders:
{work}, {out}, {input} the original case folder (read only), {tmp} a scratch folder of this invocation (build
output), {ws} the workspace, {knowledge} the domain-knowledge folder, {id} the case id. Commands run from the
workspace through the shell. `recorded: true`: the legacy cannot run here, `capture` copies its recorded output;
fresh cases then have no legacy side.

While transform works through the tasks, STATUS.json "task" names the current one: only the tables of the ETLs of
the tasks up to it are compared, the others are `pending` (the Java does not run them yet). With no "task" every
table is compared.

One invocation builds each side once, runs `new.test` once, runs the new side on every case, and the legacy side
only for a case whose input changed since its stored output (or with --rerun-legacy). A table's canonical form:
the header, then the rows sorted by the key and then every column, fields kept as captured (quotes included), NULL
written as \\N.

RESULTS.json is written by this script only (a person's approval of a difference goes in STATUS.json "approved"):

    {"run_sha": "...", "tests": {"exit": 0, "tail": "..."}, "categories": {...},
     "cases": {"C01": {"input_sha": "...", "legacy": {"T": "csv"}, "new": {"T": "csv"}, "errors": {"new": "..."},
                       "tables": {"T": {"verdict": "same|differs|missing|no-legacy|pending", "diff": ["key 2: AMT legacy=2.25 new=2.26"]}}}}}

--probe runs C01 on both sides, prints the rows per table and side and writes nothing (exit 1 when the legacy
misses a table or the new side fails to build or run). Otherwise prints one line per table that is not the same.
Exit 0 when every compared table is the same, 1 otherwise, 2 for unusable input.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

NULL = "\\N"
DIFF_LINES = 30
TAIL = 30
SIDES = ("legacy", "new")


class InputError(Exception):
    pass


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        if default is not None:
            return default
        raise InputError("%s is missing" % path)
    except ValueError as err:
        raise InputError("%s is not valid JSON: %s" % (path, err))


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def dir_sha(root):
    h = hashlib.sha256()
    for base, dirs, names in os.walk(root):
        dirs.sort()
        for n in sorted(names):
            p = os.path.join(base, n)
            h.update(os.path.relpath(p, root).encode("utf-8") + b"\0")
            with open(p, "rb") as fh:
                h.update(fh.read() + b"\0")
    return h.hexdigest()


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
    """A captured CSV file -> canonical CSV text, or None when the file is missing."""
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            records = split_records(fh.read())
    except FileNotFoundError:
        return None
    except UnicodeDecodeError as err:
        raise InputError("%s is not UTF-8: %s" % (path, err))
    if not records:
        return ""
    header = records[0]
    rows = [[NULL if c == null else c for c in r] for r in records[1:]]
    names = [unquote(h).upper() for h in header]
    idx = [names.index(k.upper()) for k in key if k.upper() in names]
    order = idx + [i for i in range(len(header)) if i not in idx]
    rows.sort(key=lambda r: [r[i] if i < len(r) else "" for i in order])
    return "\n".join([",".join(header)] + [",".join(r) for r in rows]) + "\n"


def row_count(text):
    return max(0, len(split_records(text)) - 1) if text else 0


def diff(key, old, new):
    """Two canonical tables -> (verdict, lines), rows matched on the key (all columns when there is none)."""
    if old is None or new is None:
        return "missing", ["%s table missing" % ("legacy" if old is None else "new")]
    if old == new:
        return "same", []
    out = []
    orec, nrec = split_records(old) or [[]], split_records(new) or [[]]
    oc, nc = orec[0], nrec[0]
    on, nn = [unquote(c).upper() for c in oc], [unquote(c).upper() for c in nc]
    if on != nn:
        out.append("columns differ: legacy %s, new %s" % (",".join(oc), ",".join(nc)))
    kidx = [on.index(k.upper()) for k in key if k.upper() in on] or list(range(len(oc)))
    nmap = [nn.index(c) if c in nn else None for c in on]

    def index(rows, align):
        m = {}
        for r in rows:
            if align:
                r = [r[j] if j is not None and j < len(r) else NULL for j in nmap]
            m.setdefault(tuple(r[i] if i < len(r) else "" for i in kidx), []).append(r)
        return m
    om, nm = index(orec[1:], False), index(nrec[1:], True)
    out.append("rows: legacy %d, new %d" % (len(orec) - 1, len(nrec) - 1))
    for kk in sorted(set(om) | set(nm)):
        a, b = om.get(kk, []), nm.get(kk, [])
        if a == b:
            continue
        if len(out) > DIFF_LINES:
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
                    out.append("key %s: %s legacy=%s new=%s" % (label, unquote(c).upper(), va, vb))
        if len(a) != len(b):
            out.append("key %s: legacy has %d row(s), new %d" % (label, len(a), len(b)))
    return "differs", out


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


class Runner:
    def __init__(self, ws, run, tables, knowledge, tmp):
        self.ws, self.run, self.tables, self.tmp = ws, run, tables, tmp
        self.base = {"ws": ws, "tmp": tmp, "knowledge": knowledge}
        self.null = (run.get("csv") or {}).get("null", NULL)

    def env(self, ctx):
        env = dict(os.environ)
        env.update({k: subst(str(v), ctx) for k, v in (self.run.get("env") or {}).items()})
        return env

    def sh(self, cmd, ctx):
        """-> (exit code, output tail)."""
        p = subprocess.run(subst(cmd, ctx), shell=True, cwd=self.ws, env=self.env(ctx),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        text = re.sub(r"\x1b\[[0-9;]*m", "", p.stdout.decode("utf-8", "replace"))
        return p.returncode, "\n".join(text.splitlines()[-TAIL:])

    def build(self, side):
        cmd = self.run[side].get("build")
        if not cmd:
            return None
        rc, tail = self.sh(cmd, self.base)
        return None if rc == 0 else "build failed (exit %d):\n%s" % (rc, tail)

    def side(self, side, cid, src):
        """-> ({table: canonical text or None}, error or None)."""
        spec = self.run[side]
        work = os.path.join(self.tmp, cid, side)
        out = os.path.join(self.tmp, cid, side + "-out")
        shutil.copytree(src, work)
        make_writable(work)
        os.makedirs(out)
        ctx = dict(self.base, work=work, out=out, input=src, id=cid)
        props = spec.get("properties")
        if props:
            with open(subst(props.get("path", "{work}/run.properties"), ctx), "w", encoding="utf-8") as fh:
                for k, v in (props.get("values") or {}).items():
                    fh.write("%s=%s\n" % (k, subst(str(v), ctx)))
        error = None
        for step in ("run", "capture"):
            if spec.get(step):
                rc, tail = self.sh(spec[step], ctx)
                if rc:
                    error = "%s failed (exit %d):\n%s" % (step, rc, tail)
                    break
        got = {t["name"]: canonical(os.path.join(out, t["name"] + ".csv"), t.get("key") or [], self.null)
               for t in self.tables}
        return got, error


def output_tables(analysis):
    tables = []
    for e in analysis.get("etls") or []:
        for t in e.get("outputs") or []:
            if not isinstance(t, dict) or not str(t.get("name", "")).replace("_", "").isalnum():
                raise InputError("ETL %s: bad output entry %r" % (e.get("id"), t))
            tables.append({"name": t["name"], "key": t.get("key") or [], "etl": e.get("id")})
    if not tables:
        raise InputError("ANALYSIS.json names no output tables (etls[].outputs)")
    return tables


def in_scope(analysis, task):
    """ETL ids built by the tasks up to `task`, or None (every ETL) when no task is under way."""
    if not task:
        return None
    tasks = analysis.get("tasks") or []
    ids = [t.get("id") for t in tasks]
    if task not in ids:
        raise InputError("STATUS.json task %s is not in ANALYSIS.json tasks" % task)
    return {e for t in tasks[:ids.index(task) + 1] for e in t.get("etls") or []}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--rerun-legacy", action="store_true")
    a = ap.parse_args(argv)
    ws = os.path.abspath(a.workspace)
    adir = os.path.join(ws, "analysis", a.system)
    tmp = tempfile.mkdtemp(prefix="run-%s-" % a.system)
    try:
        status = load_json(os.path.join(adir, "STATUS.json"))
        intent = status.get("intent") or {}
        run = load_json(os.path.join(adir, "RUN.json"))
        for side in SIDES:
            if not isinstance(run.get(side), dict) or not (run[side].get("run") or run[side].get("capture")):
                raise InputError("RUN.json %s needs run or capture" % side)
        analysis = load_json(os.path.join(adir, "ANALYSIS.json"))
        tables = output_tables(analysis)
        scope = in_scope(analysis, status.get("task"))
        sample = intent.get("inputs", "")
        if not os.path.isdir(sample):
            raise InputError("STATUS.json intent.inputs %r is not a folder" % sample)
        r = Runner(ws, run, tables, intent.get("knowledge", ""), tmp)
        recorded = bool(run["legacy"].get("recorded"))

        if a.probe:
            bad = []
            for side in SIDES:
                err = r.build(side) if not (side == "legacy" and recorded) else None
                got, err = (None, err) if err else r.side(side, "C01", sample)
                for t in tables:
                    text = (got or {}).get(t["name"])
                    print("%s %s: %s" % (side, t["name"], "missing" if text is None else "%d rows" % row_count(text)))
                    if side == "legacy" and text is None:
                        bad.append("legacy did not produce %s" % t["name"])
                if err:
                    print("%s %s" % (side, err))
                    bad.append("%s %s" % (side, err.split("\n")[0]))
            print("PROBE " + ("ok" if not bad else "failed: " + "; ".join(bad)))
            return 1 if bad else 0

        res_path = os.path.join(adir, "RESULTS.json")
        old = load_json(res_path, default={"cases": {}})
        run_sha = sha(json.dumps(run, sort_keys=True) + json.dumps(tables, sort_keys=True))
        stale = a.rerun_legacy or old.get("run_sha") != run_sha
        cases = [("C01", sample)]
        categories = {}
        gen = os.path.join(adir, "fresh_inputs.py")
        if os.path.isfile(gen):
            fresh = os.path.join(tmp, "fresh")
            os.makedirs(fresh)
            p = subprocess.run([sys.executable, gen, fresh], cwd=ws, capture_output=True, text=True)
            if p.returncode:
                raise InputError("fresh_inputs.py failed (exit %d): %s" % (p.returncode, p.stderr[-2000:]))
            categories = load_json(os.path.join(fresh, "categories.json"), default={})
            cases += [(n, os.path.join(fresh, n)) for n in sorted(os.listdir(fresh))
                      if os.path.isdir(os.path.join(fresh, n))]

        built, results = {}, {"run_sha": run_sha, "categories": categories, "cases": {}}
        built["new"] = r.build("new")
        if run["new"].get("test") and not built["new"]:
            rc, tail = r.sh(run["new"]["test"], r.base)
            results["tests"] = {"exit": rc, "tail": tail}
        else:
            results["tests"] = {"exit": None, "tail": built["new"] or "RUN.json new.test is empty"}
        for cid, src in cases:
            prev = old.get("cases", {}).get(cid) or {}
            c = {"input_sha": dir_sha(src), "legacy": {}, "new": {}, "errors": {}, "tables": {}}
            legacy_runs = not (recorded and cid != "C01")
            if not legacy_runs:
                c["legacy"] = None
            elif not stale and prev.get("input_sha") == c["input_sha"] and prev.get("legacy") \
                    and not (prev.get("errors") or {}).get("legacy"):
                c["legacy"] = prev["legacy"]
            else:
                if "legacy" not in built:
                    built["legacy"] = None if recorded else r.build("legacy")
                if built["legacy"]:
                    c["errors"]["legacy"] = built["legacy"]
                else:
                    c["legacy"], err = r.side("legacy", cid, src)
                    if err:
                        c["errors"]["legacy"] = err
            if built["new"]:
                c["errors"]["new"] = built["new"]
            else:
                c["new"], err = r.side("new", cid, src)
                if err:
                    c["errors"]["new"] = err
            for t in tables:
                n = t["name"]
                if scope is not None and t["etl"] not in scope:
                    c["tables"][n] = {"verdict": "pending", "diff": []}
                    continue
                if c["legacy"] is None:
                    c["tables"][n] = {"verdict": "no-legacy", "diff": []}
                    continue
                v, lines = diff(t["key"], c["legacy"].get(n), c["new"].get(n))
                c["tables"][n] = {"verdict": v, "diff": lines}
            results["cases"][cid] = c
        tmp_path = res_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_path, res_path)
    except InputError as err:
        print("dual_run: %s" % err, file=sys.stderr)
        return 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = 0
    for cid, c in results["cases"].items():
        for side, err in c["errors"].items():
            print("%s %s %s" % (cid, side, err.split("\n")[0]))
        for n, t in c["tables"].items():
            if t["verdict"] not in ("same", "no-legacy", "pending"):
                bad += 1
                print("%s %s %s: %s" % (cid, n, t["verdict"], " | ".join(t["diff"][:3])))
    tests = results["tests"]
    print("tests: %s" % ("not run: " + tests["tail"].split("\n")[0] if tests["exit"] is None else "exit %d" % tests["exit"]))
    print("%d case(s), %d table result(s) not the same -> %s" % (len(results["cases"]), bad, res_path))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
