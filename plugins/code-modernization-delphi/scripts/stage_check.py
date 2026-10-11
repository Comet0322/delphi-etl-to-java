#!/usr/bin/env python3
"""Deterministic check of one modernize-auto stage's output. The router runs it after each stage.

    python3 stage_check.py <system> <analyze|transform|verify> [--workspace DIR]

Prints one line per failed check (`FAIL <check>: <detail>`) and a last line `PASS` or `FAIL <n>`. Exit 0 on pass,
1 on failure, 2 for unusable input. It checks coverage and structure, never behavior (the dual run and the proof
pack do that). Nothing project-specific is written here: project rules come from the domain knowledge's rule.md.

analyze    the required files exist and parse; RUN.json has tables and a way to run or capture each side; its
           tables match ETLS.json outputs; every routine, unit-level global and type the Pascal source declares is
           named in MAPPING.json; every inventory op has op_id, does, a source_loc pointing at real lines, and
           writes/reads lists naming only known output tables; BUSINESS_RULES.md has a P0 card.
transform  every MAPPING routine is a static method, every global a static field and every type a nested class or
           enum of its mapped class; replaced routines have no method; every inventory op has its
           `// ETL-xxx/OP-nn` comment; plus each row of rule.md "Structure checks" (only-in, never,
           same-as-template, exists).
verify     VERIFICATION.json exists; equivalence/fresh/coverage.json maps every general edge category below and
           every row of rule.md "Fresh-input categories" to fresh inputs that exist, or gives a reason it does not
           apply.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import etl_artifacts as ea  # noqa: E402

GENERAL_CATEGORIES = ["null_empty_zero", "thresholds", "rounding_ties", "empty_table", "duplicate_keys",
                      "missing_parent", "large_values", "empty_input_file"]


def word_in(name, text):
    return re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(name), text, re.I) is not None


def check_analyze(p, fails):
    a = p["analysis"]
    for f in ("PREFLIGHT.md", "RUN.json", "ETLS.json", "MAPPING.json", "BUSINESS_RULES.md", "DECISIONS.md"):
        if not os.path.isfile(os.path.join(a, f)):
            fails.append(("files", "%s is missing" % f))
    if not os.path.isdir(os.path.join(p["eq"], "inputs", "C01")):
        fails.append(("files", "equivalence/inputs/C01/ is missing"))
    if fails:
        return
    run = ea.load_json(os.path.join(a, "RUN.json"))
    for side in ("legacy", "new"):
        spec = run.get(side)
        if not isinstance(spec, dict) or not (spec.get("run") or spec.get("capture")):
            fails.append(("run-json", "RUN.json %s needs run or capture" % side))
    etls = ea.load_json(os.path.join(a, "ETLS.json")).get("etls", [])
    ids = [e.get("id") for e in etls]
    outs = {t["name"].upper(): e.get("id") for e in etls for t in (e.get("outputs") or {}).get("tables", [])}
    run_tables = {t.get("name", "").upper(): t.get("etl") for t in run.get("tables", [])}
    if not run_tables:
        fails.append(("run-json", "RUN.json has no tables"))
    if set(outs) != set(run_tables):
        fails.append(("run-tables", "RUN.json tables %s differ from ETLS.json outputs %s" % (sorted(run_tables), sorted(outs))))
    for t, e in run_tables.items():
        if e not in ids:
            fails.append(("run-tables", "RUN.json table %s names ETL %r, not in ETLS.json" % (t, e)))
    mapping_text = ea.read(os.path.join(a, "MAPPING.json"))
    ea.load_json(os.path.join(a, "MAPPING.json"))
    if not os.path.isdir(p["legacy"]):
        fails.append(("source", "legacy/<system> is missing"))
    line_counts = {}
    for f in ea.pascal_files(p["legacy"]):
        line_counts[os.path.basename(f).lower()] = ea.read(f).count("\n") + 1
        unit, rel = ea.scan_unit(f), os.path.relpath(f, p["legacy"])
        for name, line in unit["routines"]:
            if not (word_in(name, mapping_text) or word_in(name.split(".")[-1], mapping_text)):
                fails.append(("mapping-coverage", "routine %s (%s:%d) is not in MAPPING.json" % (name, rel, line)))
        for kind in ("globals", "types"):
            for name, line in unit[kind]:
                if not word_in(name, mapping_text):
                    fails.append(("mapping-coverage", "%s %s (%s:%d) is not in MAPPING.json" % (kind[:-1], name, rel, line)))
    for e in ids:
        try:
            inv = ea.inventory(a, e)
        except ea.ArtifactError as err:
            fails.append(("inventory", str(err)))
            continue
        for op in inv["ops"]:
            oid = op.get("op_id", "?")
            for key in ("op_id", "source_loc", "does"):
                if not op.get(key):
                    fails.append(("inventory", "%s %s has no %s" % (e, oid, key)))
            for key in ("writes", "reads"):
                if not isinstance(op.get(key), list):
                    fails.append(("inventory", "%s %s needs a %s list (may be empty)" % (e, oid, key)))
            for loc in str(op.get("source_loc", "")).split(","):
                m = re.match(r"\s*([\w.]+):(\d+)(?:-(\d+))?\s*$", loc)
                if not m:
                    fails.append(("inventory", "%s %s source_loc %r is not file:line[-line]" % (e, oid, loc.strip())))
                    continue
                n = line_counts.get(m.group(1).lower())
                hi = int(m.group(3) or m.group(2))
                if n is None:
                    fails.append(("inventory", "%s %s cites %s, not a source file" % (e, oid, m.group(1))))
                elif hi > n:
                    fails.append(("inventory", "%s %s cites %s:%d, the file has %d lines" % (e, oid, m.group(1), hi, n)))
            for w in op.get("writes") or []:
                if str(w).split(".")[0].upper() not in outs:
                    fails.append(("inventory", "%s %s writes %s, not an output table" % (e, oid, w)))
    import trace_rules  # noqa: E402
    rules, _ = trace_rules.parse_rules(ea.read(os.path.join(a, "BUSINESS_RULES.md")))
    if not any(r.get("priority") == "P0" for r in rules):
        fails.append(("rules", "BUSINESS_RULES.md has no P0 rule card"))


def class_file(java, cls):
    return os.path.join(java, "src", "main", "java", *cls.split(".")) + ".java"


def under(rel, paths):
    return any(rel == q or (q.endswith("/") and rel.startswith(q)) for q in paths)


def check_transform(p, fails):
    a, java = p["analysis"], p["java"]
    main_root = os.path.join(java, "src", "main", "java")
    mapping = ea.load_json(os.path.join(a, "MAPPING.json"))
    for u in mapping.get("units", []):
        f = class_file(java, u.get("class", ""))
        if not os.path.isfile(f):
            fails.append(("one-to-one", "%s (unit %s) does not exist" % (u.get("class"), u.get("unit"))))
            continue
        text = ea.read(f)
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
            name = ea.lower_camel(r["legacy"])
            if re.search(r"\bstatic\b[^;{=]*\b%s\s*\(" % re.escape(name), text):
                fails.append(("one-to-one", "%s still defines %s, replaced by %s" % (u["class"], name, r.get("capability"))))
    comments = ea.op_comments(java)
    for e in ea.load_json(os.path.join(a, "ETLS.json")).get("etls", []):
        try:
            inv = ea.inventory(a, e["id"])
        except ea.ArtifactError as err:
            fails.append(("op-comments", str(err)))
            continue
        for op in inv["ops"]:
            if op.get("op_id") and "%s/%s" % (e["id"], op["op_id"]) not in comments:
                fails.append(("op-comments", "no // %s/%s comment in the Java" % (e["id"], op["op_id"])))
    # project rules from rule.md
    knowledge = ea.knowledge_dir(a)
    sources = [(os.path.relpath(f, main_root).replace(os.sep, "/"), ea.read(f)) for f in ea.java_sources(java)]
    tables = [t["name"] for t in ea.load_json(os.path.join(a, "RUN.json")).get("tables", [])]
    for row in ea.rule_table(knowledge, "Structure checks"):
        name, kind, pattern = row.get("check", "?"), row.get("kind", ""), row.get("pattern", "")
        paths = [q.strip().strip("`") for q in row.get("paths", "").split(",") if q.strip()]
        try:
            if kind == "only-in":
                rx = re.compile(pattern)
                for rel, text in sources:
                    if not under(rel, paths) and rx.search(text):
                        fails.append(("rule: " + name, "%s matches %s outside %s" % (rel, pattern, ", ".join(paths))))
            elif kind == "never":
                for t in (tables if "{TABLE}" in pattern else [None]):
                    rx = re.compile(pattern.replace("{TABLE}", re.escape(t)) if t else pattern, re.I)
                    for rel, text in sources:
                        if rx.search(text):
                            fails.append(("rule: " + name, "%s matches %s" % (rel, rx.pattern)))
            elif kind == "same-as-template":
                troot = os.path.join(knowledge, "template-project", "src", "main", "java")
                for q in paths:
                    tq, jq = os.path.join(troot, q), os.path.join(main_root, q)
                    if os.path.isfile(tq) or os.path.isfile(jq):
                        pairs = [(q, tq, jq)]
                    else:
                        names = set()
                        for base_dir in (tq, jq):
                            for b, _, ns in os.walk(base_dir):
                                names |= {os.path.relpath(os.path.join(b, n), base_dir) for n in ns}
                        pairs = [(os.path.join(q, n), os.path.join(tq, n), os.path.join(jq, n)) for n in sorted(names)]
                        if not names:
                            fails.append(("rule: " + name, "%s exists neither in the template nor in the Java" % q))
                    for label, x, y in pairs:
                        if not (os.path.isfile(x) and os.path.isfile(y) and ea.read(x) == ea.read(y)):
                            fails.append(("rule: " + name, "%s differs from the template" % label))
            elif kind == "exists":
                for q in paths:
                    if not os.path.exists(os.path.join(main_root, q)):
                        fails.append(("rule: " + name, "%s is missing" % q))
            else:
                fails.append(("rule: " + name, "unknown kind %r in rule.md Structure checks" % kind))
        except re.error as err:
            fails.append(("rule: " + name, "pattern %r is not a valid regex: %s" % (pattern, err)))


def check_verify(p, fails):
    a, eq = p["analysis"], p["eq"]
    if not os.path.isfile(os.path.join(a, "VERIFICATION.json")):
        fails.append(("verify", "VERIFICATION.json is missing"))
    cov = ea.load_json(os.path.join(eq, "fresh", "coverage.json"), required=False)
    if cov is None:
        fails.append(("coverage", "equivalence/fresh/coverage.json is missing"))
        return
    fresh = ea.load_json(os.path.join(eq, "fresh-cases.json"), required=False) or {}
    inputs = {str(c.get("input")) for c in fresh.get("cases", [])}
    project = [r.get("category", "") for r in ea.rule_table(ea.knowledge_dir(a), "Fresh-input categories")]
    covered, na = cov.get("categories") or {}, cov.get("not_applicable") or {}
    for cat in GENERAL_CATEGORIES + [c for c in project if c]:
        if str(na.get(cat, "")).strip():
            continue
        cases = covered.get(cat) or []
        if not cases:
            fails.append(("coverage", "edge category %s has no fresh case and no not_applicable reason" % cat))
        for c in cases:
            if str(c) not in inputs:
                fails.append(("coverage", "category %s names %s, which is not a fresh input in fresh-cases.json" % (cat, c)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system")
    ap.add_argument("stage", choices=["analyze", "transform", "verify"])
    ap.add_argument("--workspace", default=".")
    a = ap.parse_args(argv)
    p = ea.paths(a.workspace, a.system)
    fails = []
    try:
        {"analyze": check_analyze, "transform": check_transform, "verify": check_verify}[a.stage](p, fails)
    except ea.ArtifactError as err:
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
