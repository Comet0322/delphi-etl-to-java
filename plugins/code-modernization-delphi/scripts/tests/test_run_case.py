import json
import os
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
RUN_CASE = os.path.join(SCRIPTS, "run_case.py")
COMPARE = os.path.join(SCRIPTS, "compare.py")
COLLECT = os.path.join(SCRIPTS, "collect_sqlite.py")
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


class RunCase(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.inp = os.path.join(self.ws, "inputs", "C01")
        os.makedirs(self.inp)
        con = sqlite3.connect(os.path.join(self.inp, "in.db"))
        con.execute("CREATE TABLE T_IN (ID INTEGER, NAME TEXT, AMT REAL)")
        con.executemany("INSERT INTO T_IN VALUES (?,?,?)", [(3, "c  ", None), (1, 'a"q', 1.5), (2, "", 2.25)])
        con.commit()
        con.close()
        for name, text in (("dbw.py", DB_WRITER), ("csvw.py", CSV_WRITER)):
            with open(os.path.join(self.ws, name), "w") as fh:
                fh.write(text)
        self.eq = os.path.join(self.ws, "analysis", "s", "equivalence")
        os.makedirs(self.eq)
        self.cases = os.path.join(self.eq, "cases.json")

    def db_side(self, table, bug=False, suffix=""):
        return {"run": "%s dbw.py {work}/in.db %s %d" % (PY, table, int(bug)),
                "capture": "%s %s {work}/in.db {out} T_OUT --suffix=%s" % (PY, shlex.quote(COLLECT), suffix)}

    def write_run(self, legacy, new, null="\\N"):
        run = {"tables": [{"name": "T_OUT", "key": ["ID"], "etl": "ETL-001"}], "csv": {"null": null},
               "legacy": legacy, "new": new}
        path = os.path.join(self.ws, "RUN.json")
        with open(path, "w") as fh:
            json.dump(run, fh)
        return path

    def run_case(self, run, *extra):
        return subprocess.run([sys.executable, RUN_CASE, run, "--input", self.inp, "--id", "C01",
                               "--cases", self.cases, "--workspace", self.ws] + list(extra),
                              capture_output=True, text=True)

    def compare(self):
        return subprocess.run([sys.executable, COMPARE, self.cases, "--quiet"], capture_output=True, text=True)

    def read(self, *parts):
        with open(os.path.join(self.eq, *parts)) as fh:
            return fh.read()

    def test_db_capture_both_sides_same(self):
        run = self.write_run(self.db_side("T_OUT"), self.db_side("T_OUT_NEW", suffix="_NEW"))
        r = self.run_case(run)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("legacy", "C01", "T_OUT.csv"), '"ID","NAME","AMT"\n1,"a""q",1.5\n2,"",2.25\n3,"c  ",\\N\n')
        self.assertEqual(self.compare().returncode, 0)
        case = json.loads(self.read("cases.json"))["cases"][0]
        self.assertEqual((case["id"], case["legacy"], case["new"]), ("C01-T_OUT", "legacy/C01/T_OUT.csv", "new/C01/T_OUT.csv"))
        # the input dir is never written
        con = sqlite3.connect(os.path.join(self.inp, "in.db"))
        self.assertEqual([r[0] for r in con.execute("SELECT name FROM sqlite_master")], ["T_IN"])

    def test_a_wrong_value_differs_and_diag_names_the_key(self):
        run = self.write_run(self.db_side("T_OUT"), self.db_side("T_OUT_NEW", bug=True, suffix="_NEW"))
        self.assertEqual(self.run_case(run).returncode, 0)
        self.assertEqual(self.compare().returncode, 1)
        self.assertIn('key 2: "AMT" legacy=2.25 new=2.26', self.read("diag", "C01", "T_OUT.txt"))

    def test_program_that_writes_csv_itself_is_sorted_and_null_mapped(self):
        # the new side writes {out}/T_OUT.csv directly, unsorted, NULL as an empty field: no capture command
        new = {"run": "%s csvw.py {work}/in.db {out}/T_OUT.csv" % PY}
        legacy = {"run": "%s csvw.py {work}/in.db {out}/T_OUT.csv" % PY}
        run = self.write_run(legacy, new, null="")
        self.assertEqual(self.run_case(run).returncode, 0)
        self.assertEqual(self.read("new", "C01", "T_OUT.csv"), '"ID","NAME","AMT"\n1,"a""q",1.5\n2,"",2.25\n3,"c  ",\\N\n')
        self.assertEqual(self.compare().returncode, 0)

    def test_recorded_legacy_output(self):
        rec = os.path.join(self.inp, "recorded")
        os.makedirs(rec)
        with open(os.path.join(rec, "T_OUT.csv"), "w") as fh:
            fh.write('"ID","NAME","AMT"\n3,"c  ",\\N\n1,"a""q",1.5\n2,"",2.25\n')
        legacy = {"recorded": True, "capture": "cp {input}/recorded/T_OUT.csv {out}/"}
        run = self.write_run(legacy, self.db_side("T_OUT_NEW", suffix="_NEW"))
        self.assertEqual(self.run_case(run).returncode, 0)
        self.assertEqual(self.compare().returncode, 0)

    def test_existing_case_fields_kept_and_skip_legacy(self):
        run = self.write_run(self.db_side("T_OUT"), self.db_side("T_OUT_NEW", bug=True, suffix="_NEW"))
        self.run_case(run)
        spec = json.loads(self.read("cases.json"))
        spec["cases"][0]["approvedDifference"] = "a person accepted it"
        with open(self.cases, "w") as fh:
            json.dump(spec, fh)
        r = self.run_case(run, "--skip-legacy")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.read("cases.json"))["cases"][0]["approvedDifference"], "a person accepted it")
        self.assertEqual(self.compare().returncode, 0)

    def test_failed_run_is_reported_and_shows_as_missing(self):
        run = self.write_run(self.db_side("T_OUT"), {"run": "exit 3", "capture": ""})
        self.assertEqual(self.run_case(run).returncode, 1)
        self.assertEqual(self.compare().returncode, 1)
        self.assertIn("new table missing", self.read("diag", "C01", "T_OUT.txt"))

    def test_read_only_input_is_copied_writable(self):
        for base, dirs, names in os.walk(self.inp):
            for n in names:
                os.chmod(os.path.join(base, n), 0o444)
        os.chmod(self.inp, 0o555)
        try:
            run = self.write_run(self.db_side("T_OUT"), self.db_side("T_OUT_NEW", suffix="_NEW"))
            r = self.run_case(run)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.compare().returncode, 0)
        finally:
            os.chmod(self.inp, 0o755)

    def test_fresh_prefix_and_bad_input(self):
        run = self.write_run(self.db_side("T_OUT"), self.db_side("T_OUT_NEW", suffix="_NEW"))
        self.assertEqual(self.run_case(run, "--prefix", "fresh").returncode, 0)
        self.assertEqual(json.loads(self.read("cases.json"))["cases"][0]["legacy"], "fresh/legacy/C01/T_OUT.csv")
        bad = self.write_run({"run": ""}, self.db_side("T_OUT_NEW"))
        self.assertEqual(self.run_case(bad).returncode, 2)

    def test_quoted_field_with_newline_survives(self):
        con = sqlite3.connect(os.path.join(self.inp, "in.db"))
        con.execute("UPDATE T_IN SET NAME = 'two\nlines' WHERE ID = 1")
        con.commit()
        con.close()
        run = self.write_run(self.db_side("T_OUT"), self.db_side("T_OUT_NEW", suffix="_NEW"))
        self.assertEqual(self.run_case(run).returncode, 0)
        self.assertIn('1,"two\nlines",1.5', self.read("legacy", "C01", "T_OUT.csv"))
        self.assertEqual(self.compare().returncode, 0)


if __name__ == "__main__":
    unittest.main()
