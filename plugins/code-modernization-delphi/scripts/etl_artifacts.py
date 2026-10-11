"""Shared readers for the migration artifacts (stage_check.py, trace_diff.py, write_summary.py).

Standard library only. Everything read is untrusted text: it is parsed, never executed.
"""
import json
import os
import re

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


class ArtifactError(Exception):
    pass


def paths(workspace, system):
    ws = os.path.abspath(workspace)
    a = os.path.join(ws, "analysis", system)
    return {"ws": ws, "analysis": a, "legacy": os.path.join(ws, "legacy", system),
            "java": os.path.join(ws, "modernized", system, "java"), "eq": os.path.join(a, "equivalence")}


def load_json(path, required=True):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        if required:
            raise ArtifactError("%s is missing" % path)
        return None
    except ValueError as err:
        raise ArtifactError("%s is not valid JSON: %s" % (path, err))


def read(path, cap=4 << 20):
    with open(path, "rb") as fh:
        data = fh.read(cap)
    for enc in ("utf-8", "cp950", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def intent(analysis):
    """INTENT.md lines 'Key: value' as a dict (lower-case keys)."""
    out = {}
    try:
        text = read(os.path.join(analysis, "INTENT.md"))
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Za-z][A-Za-z ]+):\s*(.+)$", line)
        if m:
            out[m.group(1).strip().lower()] = m.group(2).strip()
    return out


def pascal_files(legacy):
    out = []
    for base, dirs, names in os.walk(legacy, followlinks=True):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for n in sorted(names):
            if n.lower().endswith(PASCAL_EXT):
                out.append(os.path.join(base, n))
    return out


def strip_pascal(text):
    """Comments and string literals blanked, line structure kept."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = COMMENT.sub(blank, text)
    return STRING.sub(blank, text)


def scan_unit(path):
    """-> {"routines": [(name, line)], "globals": [(name, line)], "types": [(name, line)]} for one Pascal file.

    Routines: every procedure/function/constructor/destructor header outside a class declaration (methods of a
    class are listed with their qualified name, e.g. TMainForm.FormCreate). Globals: names in var/threadvar
    blocks at unit or program level, not inside a routine or a class. Types: names declared in type blocks at
    unit or program level (records, classes, enumerations, aliases).
    """
    lines = strip_pascal(read(path)).split("\n")
    routines, globals_, types, seen_r = [], [], [], set()
    in_type = False
    depth = 0             # nesting of begin/case/try/record/class ... end
    in_header = False     # between a routine header and the begin of its body
    in_var = False
    pending_forward = False
    for no, raw in enumerate(lines, 1):
        line = raw.strip()
        low = line.lower()
        if not line:
            continue
        m = ROUTINE.match(raw)
        if m and depth == 0:
            name = m.group(2)
            key = name.lower()
            # interface declarations, forward and external declarations repeat a header without a body
            if not re.search(r"\b(forward|external)\s*;", low) and key not in seen_r:
                seen_r.add(key)
                routines.append((name, no))
            in_header = not re.search(r"\b(forward|external)\s*;", low)
            in_var = False
            in_type = False
            pending_forward = False
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
            elif word not in ("begin",):
                if word == "end.":
                    break
                if not CLASS_OPEN.search(raw):
                    continue
        if in_type and depth == 0:
            t = re.match(r"^\s*([A-Za-z_]\w*)\s*=", raw)
            if t:
                types.append((t.group(1), no))
        if in_var and depth == 0 and ":" in line and not CLASS_OPEN.search(raw):
            names = line.split(":", 1)[0]
            for n in names.split(","):
                n = n.strip()
                if re.match(r"^[A-Za-z_]\w*$", n):
                    globals_.append((n, no))
        opened = len(OPENERS.findall(low)) + len(CLASS_OPEN.findall(raw))
        closed = len(END.findall(low))
        if opened and in_header and depth == 0 and re.search(r"\bbegin\b", low):
            in_header = False
        depth = max(0, depth + opened - closed)
    return {"routines": routines, "globals": globals_, "types": types}


def inventory(analysis, etl):
    """inventory/<ETL>.json -> {"etl", "ops": [{op_id, source_loc, writes, reads, ...}]}."""
    data = load_json(os.path.join(analysis, "inventory", etl + ".json"))
    ops = data.get("ops") if isinstance(data, dict) else None
    if not isinstance(ops, list):
        raise ArtifactError("inventory/%s.json has no ops list" % etl)
    return data


def java_sources(java_root, part="main"):
    root = os.path.join(java_root, "src", part, "java")
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(dirs)
        for n in sorted(names):
            if n.endswith(".java"):
                out.append(os.path.join(base, n))
    return out


def op_comments(java_root):
    """{op_id: [(rel path, line)]} from '// ETL-001/OP-03' comments in main sources."""
    out = {}
    for f in java_sources(java_root):
        rel = os.path.relpath(f, java_root)
        for no, line in enumerate(read(f).split("\n"), 1):
            for op in OP_ID.findall(line):
                out.setdefault(op, []).append((rel, no))
    return out


def lower_camel(name):
    return name[:1].lower() + name[1:] if name else name


def knowledge_dir(analysis):
    """The domain-knowledge folder named in INTENT.md ('Domain knowledge: <path>')."""
    path = intent(analysis).get("domain knowledge", "")
    if not path or not os.path.isdir(path):
        raise ArtifactError("INTENT.md names no existing 'Domain knowledge' folder")
    return path


def rule_table(knowledge, heading):
    """Rows of the first Markdown table under the rule.md section whose heading contains `heading`.

    -> list of dicts keyed by the header cells (lower case). Cells lose surrounding backticks; `\\|` is a literal |.
    An absent section gives [].
    """
    try:
        lines = read(os.path.join(knowledge, "rule.md")).splitlines()
    except OSError:
        raise ArtifactError("rule.md not found in %s" % knowledge)
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
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        cells = [c.replace("\\|", "|") for c in cells]
        cells = [c[1:-1] if len(c) >= 2 and c[0] == c[-1] == "`" else c for c in cells]
        if header is None:
            header = [c.lower() for c in cells]
        elif all(set(c) <= set("-: ") for c in cells):
            continue
        else:
            rows.append(dict(zip(header, cells)))
    return rows
