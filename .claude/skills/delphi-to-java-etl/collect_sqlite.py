#!/usr/bin/env python3
"""Capture command of the testbed: dump tables of a SQLite database to one CSV per table, for dual_run.py.

    python3 collect_sqlite.py <db> <out dir> TABLE[,TABLE...] [--suffix _NEW]

Writes <out dir>/<TABLE>.csv for each table, reading <TABLE><suffix> (so the new program's T_X_NEW lands as
T_X.csv). Header of column names in double quotes; NULL as \\N; integers as written; reals as the shortest text
that reads back to the same double; text always in double quotes ("" inside), every character kept; blobs as
0x<hex>. A missing table writes no file, so the comparison reports it missing.

This is one way to capture output. Use it only where the domain knowledge says the programs leave their results
in SQLite tables; a program that writes files, or a database other than SQLite, needs its own capture command.
"""
import argparse
import os
import sqlite3
import sys


def cell(v):
    if v is None:
        return "\\N"
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, bytes):
        return "0x" + v.hex()
    return '"' + str(v).replace('"', '""') + '"'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("db")
    ap.add_argument("out")
    ap.add_argument("tables", help="comma-separated table names")
    ap.add_argument("--suffix", default="", help="read <TABLE><suffix>, write <TABLE>.csv")
    a = ap.parse_args(argv)
    db, out, names, suffix = a.db, a.out, a.tables, a.suffix
    os.makedirs(out, exist_ok=True)
    con = sqlite3.connect(db)
    try:
        for name in [n for n in names.split(",") if n]:
            if not name.replace("_", "").isalnum():
                print("collect_sqlite: bad table name %r" % name, file=sys.stderr)
                return 2
            src = name + suffix
            if not con.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND upper(name)=upper(?)",
                               (src,)).fetchone():
                continue
            cur = con.execute('SELECT * FROM "%s"' % src)
            lines = [",".join(cell(d[0]) for d in cur.description)]
            lines += [",".join(cell(v) for v in row) for row in cur.fetchall()]
            with open(os.path.join(out, name + ".csv"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(lines) + "\n")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
