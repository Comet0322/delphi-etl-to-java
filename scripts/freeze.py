#!/usr/bin/env python3
"""Freeze / verify / unfreeze the files a migration run must not change.

  freeze.py freeze                 write .charter.lock (hash of frozen files)
  freeze.py check                  exit 1 if any frozen file changed
  freeze.py unfreeze "<reason>"    HUMAN ONLY: remove lock, log the reason

Frozen set: charter.yaml, compare.yaml, plus every path listed under
`frozen_extra` in charter.yaml (e.g. the domain-knowledge skill files).
"""
import glob
import hashlib
import json
import os
import sys
import time

import yaml

LOCK = ".charter.lock"
LOG = ".charter.unfreeze.log"
BASE = ["charter.yaml", "compare.yaml"]


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def frozen_paths(charter="charter.yaml"):
    paths = [p for p in BASE if os.path.exists(p)]
    if os.path.exists(charter):
        with open(charter, encoding="utf-8") as f:
            extra = (yaml.safe_load(f) or {}).get("frozen_extra", []) or []
        for pattern in extra:
            for hit in glob.glob(pattern, recursive=True):
                if os.path.isfile(hit):
                    paths.append(hit)
    return sorted(set(paths))


def check_lock(lock=LOCK):
    """Return list of problems; empty means OK (or not frozen)."""
    if not os.path.exists(lock):
        return []
    with open(lock, encoding="utf-8") as f:
        locked = json.load(f)["files"]
    problems = []
    for path, digest in locked.items():
        if not os.path.exists(path):
            problems.append("%s (missing)" % path)
        elif sha(path) != digest:
            problems.append(path)
    return problems


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "freeze":
        files = {p: sha(p) for p in frozen_paths()}
        with open(LOCK, "w", encoding="utf-8") as f:
            json.dump({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": files}, f, indent=1)
        print("frozen %d files" % len(files))
        return 0
    if cmd == "check":
        problems = check_lock()
        for p in problems:
            print("CHANGED: " + p)
        return 1 if problems else 0
    if cmd == "unfreeze":
        if len(argv) < 3 or not argv[2].strip():
            print("a reason is required: freeze.py unfreeze \"<reason>\"", file=sys.stderr)
            return 2
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s\t%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), argv[2]))
        if os.path.exists(LOCK):
            os.remove(LOCK)
        print("unfrozen; refreeze after editing")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
