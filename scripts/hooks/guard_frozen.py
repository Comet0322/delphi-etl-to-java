#!/usr/bin/env python3
"""PreToolUse hook: refuse edits to frozen files and use of unfreeze.

Reads the hook JSON on stdin. Exit 2 blocks the tool call and shows stderr to
the agent. This is a first line of defence; verify_gate.py re-checks the lock
hashes every round because shell commands can be written to bypass pattern
matching.

The migration project root is the nearest directory (walking up from the
target file, or from the command's cwd) that contains `.charter.lock`.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import freeze  # noqa: E402


def find_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, freeze.LOCK)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    tool = event.get("tool_name", "")
    inp = event.get("tool_input", {}) or {}
    path = inp.get("file_path") or inp.get("notebook_path") or ""
    start = os.path.dirname(os.path.abspath(path)) if path else event.get("cwd") or os.getcwd()
    root = find_root(start)
    if root is None:
        if tool == "Bash" and "unfreeze" in inp.get("command", "") and "freeze.py" in inp.get("command", ""):
            root = find_root(event.get("cwd") or os.getcwd())
        if root is None:
            return 0

    cwd = os.getcwd()
    os.chdir(root)
    try:
        frozen = [os.path.abspath(p) for p in freeze.frozen_paths()]
    finally:
        os.chdir(cwd)
    lock_abs = os.path.join(root, freeze.LOCK)
    # Full paths only (relative to the project root, as stored in the lock, or
    # absolute). Basenames would collide with same-named copies of template files.
    names = []
    for p in frozen:
        names.append(p)
        names.append(os.path.relpath(p, root))
    names.append(freeze.LOCK)

    if tool == "Bash":
        cmd = inp.get("command", "")
        if "unfreeze" in cmd and "freeze.py" in cmd:
            print("BLOCKED: unfreeze is human-only. Stop and ask the user.", file=sys.stderr)
            return 2
        for n in names:
            e = re.escape(n)
            targets_file = (
                re.search(r">>?\s*['\"]?" + e, cmd)                                   # redirection into it
                or re.search(r"\b(sed|perl)\b[^|;&\n]*\s-[A-Za-z]*i[^|;&\n]*" + e, cmd)  # in-place edit
                or re.search(r"\b(tee|truncate|rm|mv|cp|install|dd|ln)\b[^|;&\n]*" + e, cmd)
            )
            if targets_file:
                print("BLOCKED: command appears to modify frozen file %s. "
                      "Report a blocker instead of editing frozen decisions." % n, file=sys.stderr)
                return 2
        return 0

    if path and os.path.abspath(path) in frozen + [lock_abs]:
        print("BLOCKED: %s is frozen. Do not change it; mark the ETL blocked and "
              "describe what decision is needed." % path, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
