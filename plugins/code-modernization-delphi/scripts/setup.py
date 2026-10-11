#!/usr/bin/env python3
"""Router, before the first stage: write analysis/<system>/STATUS.json.

    python3 setup.py <system> --source DIR --inputs DIR --knowledge DIR [--workspace DIR]

STATUS.json holds the intent (absolute paths, date, a hash of the legacy source so the proof can tell it was not
touched), the loop limits and empty router state. When the workspace is not inside a git repository it runs
`git init` there, so the router can commit after every agent (modernize-auto.md, "Record"). Refuses a source inside the inputs, a knowledge folder without
SKILL.md and rule.md, and an existing STATUS.json (the router resumes from it instead). Exit 0, or 2 with the reason.
"""
import argparse
import datetime
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import stage_check as sc  # noqa: E402


def setup(p, a):
    if os.path.exists(p["status"]):
        raise sc.InputError("%s exists; the router resumes from it" % p["status"])
    src, inputs, knowledge = (os.path.abspath(x) for x in (a.source, a.inputs, a.knowledge))
    for label, d in (("--source", src), ("--inputs", inputs), ("--knowledge", knowledge)):
        if not os.path.isdir(d):
            raise sc.InputError("%s %s is not a folder" % (label, d))
    if (src + os.sep).startswith(inputs + os.sep):
        raise sc.InputError("--source must not be inside --inputs")
    for f in ("SKILL.md", "rule.md"):
        if not os.path.isfile(os.path.join(knowledge, f)):
            raise sc.InputError("--knowledge has no %s" % f)
    os.makedirs(p["analysis"], exist_ok=True)
    sc.save_json(p["status"], {
        "system": os.path.basename(p["analysis"]),
        "intent": {"goal": "migrate one to one to Java per the domain knowledge",
                   "must_stay_true": "behavior matches exactly on the input domain, quirks included",
                   "mode": "unattended", "source": src, "inputs": inputs, "knowledge": knowledge,
                   "date": datetime.date.today().isoformat(), "source_sha": sc.source_sha(src)},
        "limits": sc.LIMITS, "approved": {}, "stage": "survey", "stages_done": [], "analyzed": [], "task": None,
        "tasks_done": [], "timing": {}, "checks": {},
        "decisions": [], "proposals": [], "blocked": {}, "gate": {}})
    inside = subprocess.run(["git", "-C", p["ws"], "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True).stdout.strip() == "true"
    if not inside:
        subprocess.run(["git", "init", "-q", p["ws"]], check=True)
    print("STATUS.json written; source %s writable; git repository %s" % (
        "is" if os.access(src, os.W_OK) else "is not", "existing" if inside else "created"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("system")
    ap.add_argument("--source", required=True)
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--knowledge", required=True)
    ap.add_argument("--workspace", default=".")
    a = ap.parse_args(argv)
    try:
        setup(sc.paths(a.workspace, a.system), a)
    except sc.InputError as err:
        print("setup: %s" % err, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
