#!/usr/bin/env python3
"""Router, after each analyze, transform and verify agent: check its output deterministically.

    python3 stage_check.py <system> analyze [--workspace DIR]
    python3 stage_check.py <system> transform [--task T2] [--workspace DIR]
    python3 stage_check.py <system> verify [--workspace DIR]

It prints one line per failed check (`FAIL <check>: <detail>`) and a last line `PASS` or `FAIL <n>`;
exit 0 on pass, 1 on failure, 2 for unusable input. It checks coverage and structure, never behavior (dual_run.py
and loop_gate.py do that). Project rules come from the domain knowledge's rule.md, nothing project-specific is written here.

analyze    ANALYSIS.json and RUN.json parse; RUN.json has a way to run or capture each side; every ETL has outputs
           with names; `tasks` puts every ETL in exactly one task, after the tasks of every ETL it depends on, and
           every Pascal file in exactly one task's units unless it is a driver file (named in mapping.driver.legacy);
           every routine, unit-level global and type the Pascal source declares
           is named in mapping; every ETL has outputs with names; every inventory op has op_id, does, a source_loc
           pointing at real lines, writes/reads lists naming only output tables for writes; there is a P0 rule
           whose source points at real lines.
transform  (--task: only the units and ETLs of the tasks up to that one) every mapped routine is a static method, every global a static field, every type a nested class or enum
           of its mapped class; replaced routines have no method; every op has its `// ETL-xxx/OP-nn` comment; each
           row of rule.md "Structure checks" (only-in, never, same-as-template, exists) holds.
verify     fresh_inputs.py exists; RESULTS.json has at least 10 fresh cases; its categories cover every general
           edge category below and every row of rule.md "Fresh-input categories" with fresh cases that exist, or
           give a reason one does not apply.

ANALYSIS.json (written by the analyze agent; values are examples):

    {"etls": [{"id": "ETL-001", "name": "...", "entry": "uCustomer.RunCustomerClean", "files": ["uCustomer.pas"],
               "outputs": [{"name": "T_CUST_CLEAN", "key": ["CUST_ID"]}], "depends_on": []}],
     "mapping": {"units": [{"unit": "uOrders", "file": "uOrders.pas", "class": "etl.units.Orders",
                            "routines": [{"legacy": "RunOrderAmount", "java": "runOrderAmount"}],
                            "globals": [{"legacy": "GSkipVoid", "java": "gSkipVoid"}],
                            "types": [{"legacy": "TOrderAcc", "java": "Orders.OrderAcc"}],
                            "replaced": [{"legacy": "OpenDb", "capability": "db.connect", "target": "Db.open(props)"}]}],
                 "driver": {"legacy": ["LegacyEtl.pas: TMainForm.FormCreate"], "globals": ["Form"],
                            "types": ["TMainForm"], "java": "etl.BatchRun"},
                 "uncovered": []},
     "inventory": {"ETL-001": [{"op_id": "OP-01", "source_loc": "uOrders.pas:35-36", "does": "...",
                                "writes": ["T_ORDER_AMT.AMOUNT"], "reads": ["ORDERS.QTY"], "capability": "db.query",
                                "implicit": ["..."], "rules": ["RULE-001"]}]},
     "rules": [{"id": "RULE-001", "name": "...", "etl": "ETL-001", "priority": "P0", "confidence": "High",
                "source": "uOrders.pas:31-38", "text": "<one sentence with the exact semantics>"}],
     "tasks": [{"id": "T0", "units": ["uCommon"], "etls": []},
               {"id": "T1", "units": ["uCustomer"], "etls": ["ETL-001"]}]}

`tasks` are the transform tasks in legacy driver order: T0 the units every ETL shares, then each ETL (or ETLs that
share a unit) with its own units. After task Tn the Java runs the driver up to the last ETL of Tn.
"""
import argparse
import hashlib
import json
import os
import re
import sys

GENERAL_CATEGORIES = ["null_empty_zero", "thresholds", "rounding_ties", "empty_table", "duplicate_keys",
                      "missing_parent", "large_values", "empty_input_file"]
LIMITS = {"same_diffs": 3, "no_progress": 4, "max_attempts": 8, "verify": 3}
MIN_FRESH = 10
PASCAL_EXT = (".pas", ".dpr", ".lpr", ".inc")
COMMENT = re.compile(r"\{[^}]*\}|\(\*.*?\*\)|//[^\n]*", re.S)
STRING = re.compile(r"'(?:[^']|'')*'")
ROUTINE = re.compile(r"^\s*(?:class\s+)?(procedure|function|constructor|destructor)\s+([A-Za-z_][\w.]*)", re.I)
OPENERS = re.compile(r"\b(begin|case|try|asm|record)\b", re.I)
CLASS_OPEN = re.compile(r"=\s*(?:packed\s+)?(class|object|interface)\b(?!\s*(?:;|of\b))", re.I)
END = re.compile(r"\bend\b", re.I)
SECTION = re.compile(r"^\s*(var|threadvar|const|type|resourcestring|implementation|interface|initialization|"
                     r"finalization|begin|uses|procedure|function|constructor|destructor|class|end\.)\b", re.I)
OP_ID = re.compile(r"//\s*(ETL-\d+/OP-\d+)")
LOC = re.compile(r"\s*([\w.]+):(\d+)(?:-(\d+))?\s*$")


class InputError(Exception):
    pass


# ---------------------------------------------------------------- shared readers (setup.py, loop_gate.py and summary.py use them too)

def paths(workspace, system):
    ws = os.path.abspath(workspace)
    a = os.path.join(ws, "analysis", system)
    return {"ws": ws, "analysis": a, "java": os.path.join(ws, "modernized", system, "java"),
            "status": os.path.join(a, "STATUS.json")}


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


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def read(path, cap=4 << 20):
    with open(path, "rb") as fh:
        data = fh.read(cap)
    for enc in ("utf-8", "cp950"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def intent(p):
    return load_json(p["status"]).get("intent") or {}


def source_sha(root):
    h = hashlib.sha256()
    for base, dirs, names in os.walk(root, followlinks=True):
        dirs.sort()
        for n in sorted(names):
            path = os.path.join(base, n)
            h.update(os.path.relpath(path, root).encode("utf-8") + b"\0")
            with open(path, "rb") as fh:
                h.update(fh.read() + b"\0")
    return h.hexdigest()


def java_sources(java, part="main"):
    root = os.path.join(java, "src", part, "java")
    out = []
    for base, dirs, names in os.walk(root):
        dirs.sort()
        out += [os.path.join(base, n) for n in sorted(names) if n.endswith(".java")]
    return out


def op_comments(java):
    """{"ETL-001/OP-03": [(path relative to the project, line)]} from the main sources."""
    out = {}
    for f in java_sources(java):
        rel = os.path.relpath(f, java)
        for no, line in enumerate(read(f).split("\n"), 1):
            for op in OP_ID.findall(line):
                out.setdefault(op, []).append((rel, no))
    return out


def rule_table(knowledge, heading):
    """Rows of the first Markdown table under the rule.md section whose heading contains `heading`, as dicts keyed by
    the lower-case header cells. Cells lose surrounding backticks; `\\|` is a literal |. No such section: []."""
    try:
        lines = read(os.path.join(knowledge, "rule.md")).splitlines()
    except OSError:
        raise InputError("rule.md not found in %s" % knowledge)
    start = next((i for i, l in enumerate(lines) if l.startswith("#") and heading.lower() in l.lower()), None)
    if start is None:
        return []
    header, rows = None, []
    for line in lines[start + 1:]:
        if line.startswith("#"):
            break
        if not line.strip().startswith("|"):
            if header is not None and rows:
                break
            continue
        cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        cells = [c[1:-1] if len(c) >= 2 and c[0] == c[-1] == "`" else c for c in cells]
        if header is None:
            header = [c.lower() for c in cells]
        elif not all(set(c) <= set("-: ") for c in cells):
            rows.append(dict(zip(header, cells)))
    return rows


# ---------------------------------------------------------------- Pascal scanner

def pascal_files(legacy):
    out = []
    for base, dirs, names in os.walk(legacy, followlinks=True):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        out += [os.path.join(base, n) for n in sorted(names) if n.lower().endswith(PASCAL_EXT)]
    return out


def strip_pascal(text):
    """Comments and string literals blanked, line structure kept."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    return STRING.sub(blank, COMMENT.sub(blank, text))


def scan_unit(path):
    """-> {"routines", "globals", "types": [(name, line)]} declared at unit or program level of one Pascal file.
    Methods are listed with their qualified name (TMainForm.FormCreate); forward and external headers are skipped."""
    lines = strip_pascal(read(path)).split("\n")
    routines, globals_, types, seen = [], [], [], set()
    in_type = in_header = in_var = False
    depth = 0
    for no, raw in enumerate(lines, 1):
        line = raw.strip()
        low = line.lower()
        if not line:
            continue
        m = ROUTINE.match(raw)
        if m and depth == 0:
            bodyless = re.search(r"\b(forward|external)\s*;", low)
            if not bodyless and m.group(2).lower() not in seen:
                seen.add(m.group(2).lower())
                routines.append((m.group(2), no))
            in_header, in_var, in_type = not bodyless, False, False
            continue
        if depth == 0 and SECTION.match(raw):
            word = SECTION.match(raw).group(1).lower()
            in_var = word in ("var", "threadvar") and not in_header
            in_type = word == "type" and not in_header
            if word in ("implementation", "interface", "initialization", "finalization"):
                in_header = False
            rest = line[len(word):].strip()
            if in_var and rest:
                line, low = rest, rest.lower()
            elif word != "begin":
                if word == "end.":
                    break
                if not CLASS_OPEN.search(raw):
                    continue
        if in_type and depth == 0:
            t = re.match(r"^\s*([A-Za-z_]\w*)\s*=", raw)
            if t:
                types.append((t.group(1), no))
        if in_var and depth == 0 and ":" in line and not CLASS_OPEN.search(raw):
            for n in line.split(":", 1)[0].split(","):
                if re.match(r"^[A-Za-z_]\w*$", n.strip()):
                    globals_.append((n.strip(), no))
        opened = len(OPENERS.findall(low)) + len(CLASS_OPEN.findall(raw))
        if opened and in_header and depth == 0 and re.search(r"\bbegin\b", low):
            in_header = False
        depth = max(0, depth + opened - len(END.findall(low)))
    return {"routines": routines, "globals": globals_, "types": types}


# ---------------------------------------------------------------- stage checks

def word_in(name, text):
    return re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(name), text, re.I) is not None


def check_loc(loc, line_counts, what, fails):
    """`file:12-20, 30-34, other.pas:5`: a range without a file belongs to the file before it."""
    last = None
    for part in str(loc or "").split(","):
        if last and re.match(r"^\s*\d+(-\d+)?\s*$", part):
            part = "%s:%s" % (last, part.strip())
        m = LOC.match(part)
        if m:
            last = m.group(1)
        if not m:
            fails.append(("locations", "%s: %r is not file:line[-line]" % (what, part.strip())))
            continue
        n, hi = line_counts.get(m.group(1).lower()), int(m.group(3) or m.group(2))
        if n is None:
            fails.append(("locations", "%s cites %s, not a source file" % (what, m.group(1))))
        elif hi > n:
            fails.append(("locations", "%s cites %s:%d, the file has %d lines" % (what, m.group(1), hi, n)))


def unit_of(path):
    return os.path.splitext(os.path.basename(path))[0].lower()


def driver_files(analysis):
    legacy = ((analysis.get("mapping") or {}).get("driver") or {}).get("legacy") or []
    return {unit_of(str(x).split(":")[0].strip()) for x in legacy}


def task_scope(analysis, upto=None):
    """-> (set of unit names, set of ETL ids) built by the tasks up to `upto`; (None, None): all."""
    if upto is None:
        return None, None
    tasks = analysis.get("tasks") or []
    ids = [t.get("id") for t in tasks]
    if upto not in ids:
        raise InputError("task %s is not in ANALYSIS.json tasks" % upto)
    chosen = tasks[:ids.index(upto) + 1]
    units = {str(u).lower() for t in chosen for u in t.get("units") or []} | driver_files(analysis)
    return units, {e for t in chosen for e in t.get("etls") or []}


def check_run_and_etls(analysis, run, fails):
    for side in ("legacy", "new"):
        spec = run.get(side)
        if not isinstance(spec, dict) or not (spec.get("run") or spec.get("capture")):
            fails.append(("run-json", "RUN.json %s needs run or capture" % side))
    etls = analysis.get("etls") or []
    if not etls:
        fails.append(("etls", "ANALYSIS.json has no etls"))
    outs = set()
    for e in etls:
        names = [t.get("name") for t in e.get("outputs") or [] if isinstance(t, dict)]
        if not names or not all(names):
            fails.append(("etls", "%s needs outputs with a name each" % e.get("id")))
        outs |= {str(n).upper() for n in names if n}
    return etls, outs


def check_tasks(p, analysis, etls, fails):
    tasks = analysis.get("tasks") or []
    if not tasks:
        fails.append(("tasks", "ANALYSIS.json has no tasks"))
        return
    if not driver_files(analysis):
        fails.append(("tasks", "mapping.driver.legacy names no driver file"))
    seen_etl, seen_unit, done = {}, {}, set()
    deps = {e.get("id"): e.get("depends_on") or [] for e in etls}
    for t in tasks:
        tid = t.get("id")
        for e in t.get("etls") or []:
            if e in seen_etl:
                fails.append(("tasks", "%s is in %s and %s" % (e, seen_etl[e], tid)))
            seen_etl[e] = tid
            if e not in deps:
                fails.append(("tasks", "%s names %s, not an ETL" % (tid, e)))
        for e in t.get("etls") or []:
            for d in deps.get(e, []):
                if d not in done and d not in (t.get("etls") or []):
                    fails.append(("tasks", "%s (%s) depends on %s, which no earlier task builds" % (e, tid, d)))
        done |= set(t.get("etls") or [])
        for u in t.get("units") or []:
            if str(u).lower() in seen_unit:
                fails.append(("tasks", "unit %s is in %s and %s" % (u, seen_unit[str(u).lower()], tid)))
            seen_unit[str(u).lower()] = tid
    for e in deps:
        if e not in seen_etl:
            fails.append(("tasks", "%s is in no task" % e))
    drivers = driver_files(analysis)
    for f in pascal_files(intent(p).get("source", "")):
        if unit_of(f) not in seen_unit and unit_of(f) not in drivers:
            fails.append(("tasks", "%s is in no task's units and is not the driver" % os.path.basename(f)))


def check_analyze(p, fails):
    a = p["analysis"]
    analysis = load_json(os.path.join(a, "ANALYSIS.json"))
    etls, outs = check_run_and_etls(analysis, load_json(os.path.join(a, "RUN.json")), fails)
    check_tasks(p, analysis, etls, fails)
    mapping_text = json.dumps(analysis.get("mapping") or {})
    line_counts = {}
    for f in pascal_files(intent(p).get("source", "")):
        line_counts[os.path.basename(f).lower()] = read(f).count("\n") + 1
        unit, rel = scan_unit(f), os.path.basename(f)
        for name, line in unit["routines"]:
            if not (word_in(name, mapping_text) or word_in(name.split(".")[-1], mapping_text)):
                fails.append(("mapping-coverage", "routine %s (%s:%d) is not in mapping" % (name, rel, line)))
        for kind in ("globals", "types"):
            for name, line in unit[kind]:
                if not word_in(name, mapping_text):
                    fails.append(("mapping-coverage", "%s %s (%s:%d) is not in mapping" % (kind[:-1], name, rel, line)))
    if not line_counts:
        fails.append(("source", "no Pascal files under intent.source"))
    inventory = analysis.get("inventory") or {}
    for e in etls:
        ops = inventory.get(e.get("id"))
        if not isinstance(ops, list) or not ops:
            fails.append(("inventory", "%s has no ops in inventory" % e.get("id")))
            continue
        for op in ops:
            oid = "%s %s" % (e.get("id"), op.get("op_id", "?"))
            for key in ("op_id", "source_loc", "does"):
                if not op.get(key):
                    fails.append(("inventory", "%s has no %s" % (oid, key)))
            for key in ("writes", "reads"):
                if not isinstance(op.get(key), list):
                    fails.append(("inventory", "%s needs a %s list (may be empty)" % (oid, key)))
            check_loc(op.get("source_loc"), line_counts, oid, fails)
            for w in op.get("writes") or []:
                if str(w).split(".")[0].upper() not in outs:
                    fails.append(("inventory", "%s writes %s, not an output table" % (oid, w)))
    rules = analysis.get("rules") or []
    if not any(r.get("priority") == "P0" for r in rules):
        fails.append(("rules", "no P0 rule"))
    for r in rules:
        if not re.match(r"^RULE-\d+$", str(r.get("id", ""))):
            fails.append(("rules", "rule id %r is not RULE-nnn" % r.get("id")))
        check_loc(r.get("source"), line_counts, str(r.get("id")), fails)


def class_file(java, cls):
    return os.path.join(java, "src", "main", "java", *cls.split(".")) + ".java"


def under(rel, prefixes):
    return any(rel == q or (q.endswith("/") and rel.startswith(q)) for q in prefixes)


def lower_camel(name):
    return name[:1].lower() + name[1:]


def check_transform(p, fails, task=None):
    a, java = p["analysis"], p["java"]
    main_root = os.path.join(java, "src", "main", "java")
    analysis = load_json(os.path.join(a, "ANALYSIS.json"))
    units, in_scope = task_scope(analysis, task)
    for u in (analysis.get("mapping") or {}).get("units", []):
        if units is not None and str(u.get("unit", "")).lower() not in units:
            continue
        f = class_file(java, u.get("class", ""))
        if not os.path.isfile(f):
            fails.append(("one-to-one", "%s (unit %s) does not exist" % (u.get("class"), u.get("unit"))))
            continue
        text = read(f)
        for r in u.get("routines", []):
            if not re.search(r"\bstatic\b[^;{=]*\b%s\s*\(" % re.escape(r["java"]), text):
                fails.append(("one-to-one", "%s has no static method %s (legacy %s)" % (u["class"], r["java"], r["legacy"])))
        for g in u.get("globals", []):
            if not re.search(r"\bstatic\b[^;(]*\b%s\b\s*[;=]" % re.escape(g["java"]), text):
                fails.append(("one-to-one", "%s has no static field %s (legacy %s)" % (u["class"], g["java"], g["legacy"])))
        for t in u.get("types", []):
            short = str(t.get("java", "")).split(".")[-1]
            if short and not re.search(r"\b(class|enum)\s+%s\b" % re.escape(short), text):
                fails.append(("one-to-one", "%s has no nested class or enum %s (legacy %s)" % (u["class"], short, t.get("legacy"))))
        for r in u.get("replaced", []):
            name = lower_camel(r["legacy"])
            if re.search(r"\bstatic\b[^;{=]*\b%s\s*\(" % re.escape(name), text):
                fails.append(("one-to-one", "%s still defines %s, replaced by %s" % (u["class"], name, r.get("capability"))))
    comments = op_comments(java)
    for etl, ops in (analysis.get("inventory") or {}).items():
        if in_scope is not None and etl not in in_scope:
            continue
        for op in ops or []:
            if op.get("op_id") and "%s/%s" % (etl, op["op_id"]) not in comments:
                fails.append(("op-comments", "no // %s/%s comment in the Java" % (etl, op["op_id"])))
    knowledge = intent(p).get("knowledge", "")
    sources = [(os.path.relpath(f, main_root).replace(os.sep, "/"), read(f)) for f in java_sources(java)]
    tables = [t.get("name") for e in analysis.get("etls") or [] for t in e.get("outputs") or [] if t.get("name")]
    for row in rule_table(knowledge, "Structure checks"):
        name, kind, pattern = row.get("check", "?"), row.get("kind", ""), row.get("pattern", "")
        where = [q.strip().strip("`") for q in row.get("paths", "").split(",") if q.strip()]
        try:
            if kind == "only-in":
                rx = re.compile(pattern)
                for rel, text in sources:
                    if not under(rel, where) and rx.search(text):
                        fails.append(("rule: " + name, "%s matches %s outside %s" % (rel, pattern, ", ".join(where))))
            elif kind == "never":
                for t in (tables if "{TABLE}" in pattern else [None]):
                    rx = re.compile(pattern.replace("{TABLE}", re.escape(t)) if t else pattern, re.I)
                    for rel, text in sources:
                        if rx.search(text):
                            fails.append(("rule: " + name, "%s matches %s" % (rel, rx.pattern)))
            elif kind == "same-as-template":
                troot = os.path.join(knowledge, "template-project", "src", "main", "java")
                for q in where:
                    tq, jq = os.path.join(troot, q), os.path.join(main_root, q)
                    if os.path.isfile(tq) or os.path.isfile(jq):
                        pairs = [(q, tq, jq)]
                    else:
                        names = set()
                        for d in (tq, jq):
                            for b, _, ns in os.walk(d):
                                names |= {os.path.relpath(os.path.join(b, n), d) for n in ns}
                        pairs = [(os.path.join(q, n), os.path.join(tq, n), os.path.join(jq, n)) for n in sorted(names)]
                        if not names:
                            fails.append(("rule: " + name, "%s exists neither in the template nor in the Java" % q))
                    for label, x, y in pairs:
                        if not (os.path.isfile(x) and os.path.isfile(y) and read(x) == read(y)):
                            fails.append(("rule: " + name, "%s differs from the template" % label))
            elif kind == "exists":
                for q in where:
                    if not os.path.exists(os.path.join(main_root, q)):
                        fails.append(("rule: " + name, "%s is missing" % q))
            else:
                fails.append(("rule: " + name, "unknown kind %r in rule.md Structure checks" % kind))
        except re.error as err:
            fails.append(("rule: " + name, "pattern %r is not a valid regex: %s" % (pattern, err)))


def check_verify(p, fails):
    a = p["analysis"]
    if not os.path.isfile(os.path.join(a, "fresh_inputs.py")):
        fails.append(("fresh", "fresh_inputs.py is missing"))
        return
    results = load_json(os.path.join(a, "RESULTS.json"), default={})
    fresh = {c for c in results.get("cases", {}) if c != "C01"}
    if len(fresh) < MIN_FRESH:
        fails.append(("fresh", "RESULTS.json has %d fresh case(s), at least %d needed (run dual_run.py)" % (len(fresh), MIN_FRESH)))
    cats = results.get("categories") or {}
    covered, na = cats.get("cases") or {}, cats.get("not_applicable") or {}
    by_cat = {}
    for case, names in covered.items():
        for n in names or []:
            by_cat.setdefault(n, []).append(case)
    project = [r.get("category", "") for r in rule_table(intent(p).get("knowledge", ""), "Fresh-input categories")]
    for cat in GENERAL_CATEGORIES + [c for c in project if c]:
        if str(na.get(cat, "")).strip():
            continue
        if not by_cat.get(cat):
            fails.append(("coverage", "edge category %s has no fresh case and no not_applicable reason" % cat))
    for case in covered:
        if case not in fresh:
            fails.append(("coverage", "categories.json names %s, which is not a fresh case in RESULTS.json" % case))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system")
    ap.add_argument("stage", choices=["analyze", "transform", "verify"])
    ap.add_argument("--task", help="transform: check only the tasks up to this one")
    ap.add_argument("--workspace", default=".")
    a = ap.parse_args(argv)
    p = paths(a.workspace, a.system)
    fails = []
    try:
        if a.stage == "analyze":
            check_analyze(p, fails)
        elif a.stage == "transform":
            check_transform(p, fails, a.task)
        else:
            check_verify(p, fails)
    except InputError as err:
        print("stage_check: %s" % err, file=sys.stderr)
        return 2
    for check, detail in fails[:60]:
        print("FAIL %s: %s" % (check, detail))
    if len(fails) > 60:
        print("... %d more" % (len(fails) - 60))
    print("PASS" if not fails else "FAIL %d" % len(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
