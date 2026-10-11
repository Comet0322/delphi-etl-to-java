import json
import os
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(os.path.dirname(HERE), "dual_run.py")
PY = shlex.quote(sys.executable)

# legacy-style program: copies T_IN into a table of the db it is given (optionally wrong for ID 2)
DB_WRITER = """
import sqlite3, sys
db, table, bug = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
con = sqlite3.connect(db)
con.execute('CREATE TABLE "%s" (ID INTEGER, NAME TEXT, AMT REAL)' % table)
for i, n, a in con.execute("SELECT ID, NAME, AMT FROM T_IN").fetchall():
    if bug and i == 2:
        a = a + 0.01
    con.execute('INSERT INTO "%s" VALUES (?,?,?)' % table, (i, n, a))
con.commit()
"""
# capture: one table of a db to <out>/T_OUT.csv, NULL as \\N, text quoted
CAPTURE = """
import sqlite3, sys
db, out, table = sys.argv[1], sys.argv[2], sys.argv[3]
cur = sqlite3.connect(db).execute('SELECT * FROM "%s"' % table)
def f(v):
    return "\\\\N" if v is None else ('"' + v.replace('"', '""') + '"' if isinstance(v, str) else repr(v))
with open(out + "/T_OUT.csv", "w") as fh:
    fh.write(",".join('"%s"' % d[0] for d in cur.description) + "\\n")
    for r in cur:
        fh.write(",".join(f(v) for v in r) + "\\n")
"""
# new-style program: writes its result straight to a CSV file, unsorted, NULL as empty
CSV_WRITER = """
import sqlite3, sys
db, out = sys.argv[1], sys.argv[2]
rows = sqlite3.connect(db).execute("SELECT ID, NAME, AMT FROM T_IN ORDER BY ID DESC").fetchall()
with open(out, "w") as fh:
    fh.write('"ID","NAME","AMT"\\n')
    for i, n, a in rows:
        fh.write("%d,%s,%s\\n" % (i, '"' + n.replace('"', '""') + '"', "" if a is None else repr(a)))
"""
FRESH = """
import json, os, sqlite3, sys
out = sys.argv[1]
for n in range(1, 4):
    d = os.path.join(out, "F%02d" % n)
    os.makedirs(d)
    con = sqlite3.connect(os.path.join(d, "in.db"))
    con.execute("CREATE TABLE T_IN (ID INTEGER, NAME TEXT, AMT REAL)")
    con.execute("INSERT INTO T_IN VALUES (?,?,?)", (n, "f", n * 1.5))
    con.commit()
with open(os.path.join(out, "categories.json"), "w") as fh:
    json.dump({"cases": {"F01": ["thresholds"]}}, fh)
"""
EXPECTED = '"ID","NAME","AMT"\n1,"a""q",1.5\n2,"",2.25\n3,"c  ",\\N\n'


class Run(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.inp = os.path.join(self.ws, "inputs")
        self.a = os.path.join(self.ws, "analysis", "s")
        os.makedirs(self.inp)
        os.makedirs(self.a)
        con = sqlite3.connect(os.path.join(self.inp, "in.db"))
        con.execute("CREATE TABLE T_IN (ID INTEGER, NAME TEXT, AMT REAL)")
        con.executemany("INSERT INTO T_IN VALUES (?,?,?)", [(3, "c  ", None), (1, 'a"q', 1.5), (2, "", 2.25)])
        con.commit()
        con.close()
        for name, text in (("dbw.py", DB_WRITER), ("cap.py", CAPTURE), ("csvw.py", CSV_WRITER)):
            self.write(os.path.join(self.ws, name), text)
        self.dump("STATUS.json", {"intent": {"inputs": self.inp, "knowledge": self.ws}})
        self.dump("ANALYSIS.json", {"etls": [{"id": "ETL-001", "outputs": [{"name": "T_OUT", "key": ["ID"]}]}]})

    def write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def dump(self, name, obj):
        self.write(os.path.join(self.a, name), json.dumps(obj))

    def db_side(self, table, bug=False):
        return {"run": "%s dbw.py {work}/in.db %s %d" % (PY, table, int(bug)),
                "capture": "%s {knowledge}/cap.py {work}/in.db {out} %s" % (PY, table)}

    def run_json(self, legacy, new, null="\\N"):
        self.dump("RUN.json", {"csv": {"null": null}, "legacy": legacy, "new": new})

    def go(self, *extra):
        return subprocess.run([sys.executable, RUN, "s", "--workspace", self.ws] + list(extra),
                              capture_output=True, text=True)

    def results(self):
        with open(os.path.join(self.a, "RESULTS.json")) as fh:
            return json.load(fh)

    def test_same_on_both_sides(self):
        self.run_json(self.db_side("T_OUT"), self.db_side("T_OUT_NEW"))
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        c = self.results()["cases"]["C01"]
        self.assertEqual(c["legacy"]["T_OUT"], EXPECTED)
        self.assertEqual(c["tables"]["T_OUT"]["verdict"], "same")
        con = sqlite3.connect(os.path.join(self.inp, "in.db"))   # the input is never written
        self.assertEqual([x[0] for x in con.execute("SELECT name FROM sqlite_master")], ["T_IN"])

    def test_wrong_value_differs_by_key_and_column(self):
        self.run_json(self.db_side("T_OUT"), self.db_side("T_OUT_NEW", bug=True))
        r = self.go()
        self.assertEqual(r.returncode, 1)
        self.assertIn("key 2: AMT legacy=2.25 new=2.26", self.results()["cases"]["C01"]["tables"]["T_OUT"]["diff"])
        self.assertIn("C01 T_OUT differs", r.stdout)

    def test_program_writing_csv_itself_is_sorted_and_null_mapped(self):
        side = {"run": "%s csvw.py {work}/in.db {out}/T_OUT.csv" % PY}
        self.run_json(side, side, null="")
        self.assertEqual(self.go().returncode, 0)
        self.assertEqual(self.results()["cases"]["C01"]["new"]["T_OUT"], EXPECTED)

    def test_recorded_legacy_and_fresh_cases(self):
        os.makedirs(os.path.join(self.inp, "recorded"))
        self.write(os.path.join(self.inp, "recorded", "T_OUT.csv"), '"ID","NAME","AMT"\n3,"c  ",\\N\n1,"a""q",1.5\n2,"",2.25\n')
        self.run_json({"recorded": True, "capture": "cp {input}/recorded/T_OUT.csv {out}/"}, self.db_side("T_OUT_NEW"))
        self.write(os.path.join(self.a, "fresh_inputs.py"), FRESH)
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        res = self.results()
        self.assertEqual(sorted(res["cases"]), ["C01", "F01", "F02", "F03"])
        self.assertIsNone(res["cases"]["F02"]["legacy"])
        self.assertEqual(res["cases"]["F02"]["tables"]["T_OUT"]["verdict"], "no-legacy")
        self.assertEqual(res["categories"]["cases"], {"F01": ["thresholds"]})

    def test_legacy_output_reused_until_input_or_run_changes(self):
        self.run_json(self.db_side("T_OUT"), self.db_side("T_OUT_NEW"))
        self.go()
        self.write(os.path.join(self.ws, "dbw.py"), "raise SystemExit(5)\n")   # legacy would now fail...
        r = self.go()
        self.assertEqual(r.returncode, 1)    # ...and the new side does fail, but the legacy output is reused
        c = self.results()["cases"]["C01"]
        self.assertEqual(c["legacy"]["T_OUT"], EXPECTED)
        self.assertNotIn("legacy", c["errors"])
        self.assertEqual(self.go("--rerun-legacy").returncode, 1)
        self.assertIn("legacy", self.results()["cases"]["C01"]["errors"])

    def test_failed_run_shows_as_missing(self):
        self.run_json(self.db_side("T_OUT"), {"run": "exit 3"})
        self.assertEqual(self.go().returncode, 1)
        c = self.results()["cases"]["C01"]
        self.assertEqual(c["tables"]["T_OUT"]["verdict"], "missing")
        self.assertIn("run failed (exit 3)", c["errors"]["new"])

    def test_read_only_input_is_copied_writable(self):
        os.chmod(os.path.join(self.inp, "in.db"), 0o444)
        os.chmod(self.inp, 0o555)
        try:
            self.run_json(self.db_side("T_OUT"), self.db_side("T_OUT_NEW"))
            r = self.go()
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        finally:
            os.chmod(self.inp, 0o755)

    def test_tests_and_build_are_recorded(self):
        new = dict(self.db_side("T_OUT_NEW"), build="true", test="echo 2 tests; exit 4")
        self.run_json(self.db_side("T_OUT"), new)
        self.go()
        self.assertEqual(self.results()["tests"]["exit"], 4)
        self.run_json(self.db_side("T_OUT"), dict(new, build="echo broken; exit 1"))
        self.assertEqual(self.go().returncode, 1)
        res = self.results()
        self.assertIsNone(res["tests"]["exit"])
        self.assertIn("build failed", res["cases"]["C01"]["errors"]["new"])

    def test_probe_writes_nothing(self):
        self.run_json(self.db_side("T_OUT"), {"run": "true"})
        r = self.go("--probe")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("legacy T_OUT: 3 rows", r.stdout)
        self.assertIn("new T_OUT: missing", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.a, "RESULTS.json")))
        self.run_json({"run": "true"}, {"run": "true"})
        self.assertEqual(self.go("--probe").returncode, 1)

    def test_quoted_field_with_newline_survives(self):
        con = sqlite3.connect(os.path.join(self.inp, "in.db"))
        con.execute("UPDATE T_IN SET NAME = 'two\nlines' WHERE ID = 1")
        con.commit()
        con.close()
        self.run_json(self.db_side("T_OUT"), self.db_side("T_OUT_NEW"))
        self.assertEqual(self.go().returncode, 0)
        self.assertIn('1,"two\nlines",1.5', self.results()["cases"]["C01"]["legacy"]["T_OUT"])

    def test_tables_of_unbuilt_tasks_are_pending(self):
        self.dump("ANALYSIS.json", {"etls": [{"id": "ETL-001", "outputs": [{"name": "T_OUT", "key": ["ID"]}]},
                                             {"id": "ETL-002", "outputs": [{"name": "T_TWO", "key": []}]}],
                                    "tasks": [{"id": "T1", "etls": ["ETL-001"]}, {"id": "T2", "etls": ["ETL-002"]}]})
        self.dump("STATUS.json", {"intent": {"inputs": self.inp, "knowledge": self.ws}, "task": "T1"})
        self.run_json(self.db_side("T_OUT"), self.db_side("T_OUT_NEW"))
        r = self.go()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.results()["cases"]["C01"]["tables"]["T_TWO"]["verdict"], "pending")
        self.dump("STATUS.json", {"intent": {"inputs": self.inp, "knowledge": self.ws}, "task": None})
        self.assertEqual(self.go().returncode, 1)
        self.assertEqual(self.results()["cases"]["C01"]["tables"]["T_TWO"]["verdict"], "missing")

    def test_bad_input(self):
        self.run_json({"run": ""}, self.db_side("T_OUT_NEW"))
        self.assertEqual(self.go().returncode, 2)


if __name__ == "__main__":
    unittest.main()
