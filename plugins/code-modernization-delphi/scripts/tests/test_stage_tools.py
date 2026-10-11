import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
import etl_artifacts as ea  # noqa: E402

UNIT = """unit uOrders;
{$mode delphi}
interface
uses SysUtils, uCommon;
type
  TAcc = record
    Cnt: Integer;
  end;
var
  GTotal, GCount: Integer;   // two globals
procedure RunOrders;
implementation
{ procedure Fake; in a comment }
function Fmt(V: Integer): string;
var
  Local: Integer;
begin
  Local := V;
  Result := IntToStr(Local);
end;
procedure RunOrders;
var
  Q: Integer;
begin
  case Q of
    1: GTotal := 1;
  end;
  ExecSql('INSERT INTO T_OUT VALUES (1)');
end;
end.
"""
COMMON = """unit uCommon;
interface
var
  GConn: Pointer;
procedure ExecSql(const S: string);
implementation
procedure ExecSql(const S: string);
begin
end;
end.
"""
PROGRAM = """program Main;
uses uOrders;
type
  TForm1 = class
  private
    FDb: string;
  public
    procedure FormCreate;
  end;
procedure TForm1.FormCreate;
begin
end;
var
  Form: TForm1;
begin
  RunOrders;
end.
"""
CORE = {"Db.java": "class Db {}\n", "Tables.java": "class Tables {}\n"}
RULES = """# Mapping rules

## 7. Structure checks

| Check | Kind | Pattern | Paths |
|---|---|---|---|
| connection only in BatchRun | only-in | `\\bDb\\.(open\\|commit\\|rollback)\\s*\\(` | `etl/BatchRun.java` |
| no JDBC outside core | only-in | `\\bjava\\.sql\\b\\|\\bDriverManager\\b` | `etl/core/` |
| core unchanged | same-as-template | | `etl/core/` |
| outputs through Tables.out | never | `\\b(INSERT\\s+INTO\\|DELETE\\s+FROM)\\s+{TABLE}\\b` | |
| entry point | exists | | `etl/BatchRun.java` |

## 8. Fresh-input categories

| Category | Cover |
|---|---|
| date_sentinels | dates |
"""


class Fixture(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.a = os.path.join(self.ws, "analysis", "s")
        self.src = os.path.join(self.ws, "legacy", "s")
        self.java = os.path.join(self.ws, "modernized", "s", "java")
        self.knowledge = os.path.join(self.ws, "knowledge")
        for d in (self.a, self.src, os.path.join(self.a, "inventory"), os.path.join(self.a, "equivalence", "inputs", "C01")):
            os.makedirs(d)
        for name, text in (("uOrders.pas", UNIT), ("uCommon.pas", COMMON), ("Main.dpr", PROGRAM)):
            self.write(os.path.join(self.src, name), text)
        tcore = os.path.join(self.knowledge, "template-project", "src", "main", "java", "etl", "core")
        os.makedirs(tcore)
        for n, t in CORE.items():
            self.write(os.path.join(tcore, n), t)
        self.write(os.path.join(self.knowledge, "rule.md"), RULES)
        self.write(os.path.join(self.a, "INTENT.md"), "Mode: unattended\nDomain knowledge: %s\n" % self.knowledge)
        for f in ("PREFLIGHT.md",):
            self.write(os.path.join(self.a, f), "x\n")
        self.write(os.path.join(self.a, "DECISIONS.md"), "| Id |\n|---|\n| D-001 | x | q | d | assumed | all |\n")
        self.write(os.path.join(self.a, "BUSINESS_RULES.md"),
                   "### RULE-001: total\n**Priority:** P0\n**Confidence:** High\n**Source:** uOrders.pas:20\n")
        self.dump("RUN.json", {"tables": [{"name": "T_OUT", "key": ["ID"], "etl": "ETL-001"}],
                               "legacy": {"run": "x", "capture": "y"}, "new": {"run": "x"}})
        self.dump("ETLS.json", {"etls": [{"id": "ETL-001", "name": "orders", "entry": "uOrders.RunOrders",
                                          "outputs": {"tables": [{"name": "T_OUT", "key": ["ID"]}]}, "depends_on": []}]})
        self.mapping = {"units": [
            {"unit": "uOrders", "class": "etl.units.Orders",
             "routines": [{"legacy": "RunOrders", "java": "runOrders"}, {"legacy": "Fmt", "java": "fmt"}],
             "globals": [{"legacy": "GTotal", "java": "gTotal"}, {"legacy": "GCount", "java": "gCount"}],
             "types": [{"legacy": "TAcc", "java": "Orders.Acc"}], "replaced": []},
            {"unit": "uCommon", "class": "etl.units.Common", "routines": [], "globals": [],
             "replaced": [{"legacy": "ExecSql", "capability": "db.exec"}, {"legacy": "GConn", "capability": "db.connect"}]}],
            "driver": {"legacy": ["Main.dpr: TForm1.FormCreate"], "globals": ["Form"], "types": ["TForm1"], "java": "etl.BatchRun"},
            "uncovered": []}
        self.dump("MAPPING.json", self.mapping)
        self.dump("inventory/ETL-001.json", {"etl": "ETL-001", "ops": [
            {"op_id": "OP-01", "source_loc": "uOrders.pas:20-23", "does": "write total", "writes": ["T_OUT.TOTAL"], "reads": []}]})
        # java
        main = os.path.join(self.java, "src", "main", "java", "etl")
        os.makedirs(os.path.join(main, "units"))
        os.makedirs(os.path.join(main, "core"))
        for n, t in CORE.items():
            self.write(os.path.join(main, "core", n), t)
        self.write(os.path.join(main, "BatchRun.java"), "class BatchRun { static void run() { Db.open(p); Orders.runOrders(); Db.commit(); } }\n")
        self.write(os.path.join(main, "units", "Orders.java"),
                   "class Orders {\n public static final class Acc { int cnt; }\n public static int gTotal;\n public static int gCount = 0;\n"
                   " public static String fmt(int v) { return \"\"; }\n"
                   " public static void runOrders() {\n  // ETL-001/OP-01\n"
                   "  Db.current().execute(\"INSERT INTO \" + Tables.out(\"T_OUT\") + \" VALUES (1)\");\n }\n}\n")
        self.write(os.path.join(main, "units", "Common.java"), "class Common {}\n")

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def dump(self, rel, obj):
        self.write(os.path.join(self.a, rel), json.dumps(obj))

    def check(self, stage):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "stage_check.py"), "s", stage, "--workspace", self.ws],
                           capture_output=True, text=True)
        return r.returncode, r.stdout


class ScanUnit(Fixture):
    def test_routines_and_globals(self):
        u = ea.scan_unit(os.path.join(self.src, "uOrders.pas"))
        self.assertEqual([n for n, _ in u["routines"]], ["RunOrders", "Fmt"])
        self.assertEqual([n for n, _ in u["globals"]], ["GTotal", "GCount"])
        self.assertEqual([n for n, _ in u["types"]], ["TAcc"])
        p = ea.scan_unit(os.path.join(self.src, "Main.dpr"))
        self.assertEqual([n for n, _ in p["routines"]], ["TForm1.FormCreate"])
        self.assertEqual([n for n, _ in p["globals"]], ["Form"])
        self.assertEqual([n for n, _ in p["types"]], ["TForm1"])


class Analyze(Fixture):
    def test_pass(self):
        rc, out = self.check("analyze")
        self.assertEqual(rc, 0, out)

    def test_missing_routine_and_global(self):
        self.mapping["units"][0]["routines"].pop()          # Fmt
        self.mapping["driver"]["globals"] = []              # Form
        self.dump("MAPPING.json", self.mapping)
        rc, out = self.check("analyze")
        self.assertEqual(rc, 1)
        self.assertIn("routine Fmt (uOrders.pas:", out)
        self.assertIn("global Form (Main.dpr:", out)

    def test_bad_inventory(self):
        self.dump("inventory/ETL-001.json", {"ops": [{"op_id": "OP-01", "source_loc": "uOrders.pas:900", "does": "x",
                                                     "writes": ["T_IN.X"]}]})
        rc, out = self.check("analyze")
        self.assertIn("the file has", out)
        self.assertIn("needs a reads list", out)
        self.assertIn("writes T_IN.X, not an output table", out)


class Transform(Fixture):
    def test_pass(self):
        rc, out = self.check("transform")
        self.assertEqual(rc, 0, out)

    def test_structure_violations(self):
        main = os.path.join(self.java, "src", "main", "java", "etl")
        self.write(os.path.join(main, "units", "Common.java"),
                   "import java.sql.DriverManager;\nclass Common { public static void execSql(String s) { Db.commit(); } }\n")
        self.write(os.path.join(main, "units", "Orders.java"),
                   "class Orders { public static void runOrders() { Db.current().execute(\"DELETE FROM T_OUT\"); } }\n")
        self.write(os.path.join(main, "core", "Db.java"), "class Db { /* edited */ }\n")
        rc, out = self.check("transform")
        self.assertEqual(rc, 1)
        for text in ("no nested class or enum Acc", "no static method fmt", "no static field gTotal", "still defines execSql",
                     "rule: no JDBC outside core: etl/units/Common.java matches",
                     "rule: connection only in BatchRun: etl/units/Common.java matches",
                     "rule: core unchanged: etl/core/Db.java differs", "no // ETL-001/OP-01 comment",
                     "rule: outputs through Tables.out: etl/units/Orders.java matches"):
            self.assertIn(text, out)

    def test_missing_entry_point(self):
        os.remove(os.path.join(self.java, "src", "main", "java", "etl", "BatchRun.java"))
        rc, out = self.check("transform")
        self.assertIn("rule: entry point: etl/BatchRun.java is missing", out)


class Verify(Fixture):
    def test_coverage(self):
        eq = os.path.join(self.a, "equivalence")
        self.write(os.path.join(self.a, "VERIFICATION.json"), "{}")
        self.write(os.path.join(eq, "fresh-cases.json"), json.dumps({"cases": [{"id": "F01-T_OUT", "input": "F01"}]}))
        cats = {c: ["F01"] for c in ["null_empty_zero", "thresholds", "rounding_ties", "empty_table", "duplicate_keys",
                                     "missing_parent", "large_values", "date_sentinels"]}
        self.write(os.path.join(eq, "fresh", "coverage.json"), json.dumps({"categories": cats}))
        rc, out = self.check("verify")
        self.assertIn("empty_input_file has no fresh case", out)
        cats["empty_input_file"] = ["F09"]
        self.write(os.path.join(eq, "fresh", "coverage.json"), json.dumps({"categories": cats}))
        rc, out = self.check("verify")
        self.assertIn("names F09, which is not a fresh input", out)
        del cats["empty_input_file"]
        self.write(os.path.join(eq, "fresh", "coverage.json"),
                   json.dumps({"categories": cats, "not_applicable": {"empty_input_file": "the ETL reads no file"}}))
        rc, out = self.check("verify")
        self.assertEqual(rc, 0, out)


class FactsAndTrace(Fixture):
    def test_summary_is_written_from_files(self):
        self.dump("AUTO_STATUS.json", {"system": "s", "timing": {"analyze": {"start": "10:00", "end": "10:02"}},
                                       "checks": {"analyze": "PASS"},
                                       "etls": {"ETL-001": {"stage": "built", "blocked": {"code": "same_diffs", "tried": ["x"], "needs": "a person"}}},
                                       "gate": {"overall": "BLOCKED", "etls": {"ETL-001": {"state": "BLOCKED:same_diffs", "diffs": 2, "runs": 3}}}})
        self.dump("VERIFICATION.json", {"overall": {"verdict": "NOT PROVEN"},
                                        "modules": [{"name": "java", "reasons": ["Same behavior: 2 differ"], "passed": [],
                                                     "notProven": ["It does not cover speed."]}]})
        self.dump("AUDIT.json", {"findings": [{"severity": "low", "kind": "wrong citations", "where": "uOrders.pas:3", "issue": "off by one"}]})
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "write_summary.py"), "s", "--workspace", self.ws],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.a, "AUTO_SUMMARY.md")) as fh:
            text = fh.read()
        for want in ("Gate OVERALL: **BLOCKED**", "Proof pack verdict: **NOT PROVEN**", "not met (java): Same behavior: 2 differ",
                     "| ETL-001 | BLOCKED:same_diffs | 2 | 3 | built |", "| analyze | 10:00 | 10:02 | PASS |",
                     "ETL-001: same_diffs. Tried: x. Needs: a person", "Assumed decisions (1 of 1)",
                     "**low** wrong citations at uOrders.pas:3: off by one", "It does not cover speed."):
            self.assertIn(want, text)

    def test_trace_names_op_lines_and_cascade(self):
        eq = os.path.join(self.a, "equivalence")
        # a second ETL depending on the first, both differing
        etls = {"etls": [
            {"id": "ETL-001", "name": "orders", "outputs": {"tables": [{"name": "T_OUT"}]}, "depends_on": []},
            {"id": "ETL-002", "name": "sums", "outputs": {"tables": [{"name": "T_SUM"}]}, "depends_on": ["ETL-001"]}]}
        self.dump("ETLS.json", etls)
        self.dump("RUN.json", {"tables": [{"name": "T_OUT", "etl": "ETL-001"}, {"name": "T_SUM", "etl": "ETL-002"}],
                               "legacy": None, "new": {"run": "x"}})
        self.dump("inventory/ETL-002.json", {"ops": [{"op_id": "OP-01", "source_loc": "uOrders.pas:5", "does": "sum",
                                                     "writes": ["T_SUM"], "reads": ["T_OUT.TOTAL"]}]})
        for side, out_v, sum_v in (("legacy", "1", "10"), ("new", "2", "20")):
            self.write(os.path.join(eq, side, "C01", "T_OUT.csv"), '"ID","TOTAL"\n1,%s\n' % out_v)
            self.write(os.path.join(eq, side, "C01", "T_SUM.csv"), '"K","S"\n1,%s\n' % sum_v)
        self.write(os.path.join(eq, "diag", "C01", "T_OUT.txt"), 'rows: legacy 1, new 1\nkey 1: "TOTAL" legacy=1 new=2\n')
        self.write(os.path.join(eq, "diag", "C01", "T_SUM.txt"), 'rows: legacy 1, new 1\nkey 1: "S" legacy=10 new=20\n')
        self.write(os.path.join(eq, "cases.json"), json.dumps({"cases": [
            {"id": "C01-T_OUT", "input": "C01", "legacy": "legacy/C01/T_OUT.csv", "new": "new/C01/T_OUT.csv"},
            {"id": "C01-T_SUM", "input": "C01", "legacy": "legacy/C01/T_SUM.csv", "new": "new/C01/T_SUM.csv"}]}))
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "trace_diff.py"), "s", "--workspace", self.ws],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("ETL-001 T_OUT.TOTAL in 1 case(s) -> OP-01 (uOrders.pas:20-23)", r.stdout)
        self.assertIn("[possible cascade from ETL-001]", r.stdout)
        with open(os.path.join(eq, "TRACE.md")) as fh:
            text = fh.read()
        self.assertIn("src/main/java/etl/units/Orders.java:7", text)
        self.assertIn("Possible cascade", text)


if __name__ == "__main__":
    unittest.main()
