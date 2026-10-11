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
import stage_check as ck  # noqa: E402

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
        self.src = os.path.join(self.ws, "src")
        self.inputs = os.path.join(self.ws, "inputs")
        self.java = os.path.join(self.ws, "modernized", "s", "java")
        self.knowledge = os.path.join(self.ws, "knowledge")
        for d in (self.src, self.inputs):
            os.makedirs(d)
        for name, text in (("uOrders.pas", UNIT), ("uCommon.pas", COMMON), ("Main.dpr", PROGRAM)):
            self.write(os.path.join(self.src, name), text)
        tcore = os.path.join(self.knowledge, "template-project", "src", "main", "java", "etl", "core")
        os.makedirs(tcore)
        for n, t in CORE.items():
            self.write(os.path.join(tcore, n), t)
        self.write(os.path.join(self.knowledge, "rule.md"), RULES)
        self.write(os.path.join(self.knowledge, "SKILL.md"), "x\n")
        r = self.script("setup.py", "--source", self.src, "--inputs", self.inputs, "--knowledge", self.knowledge)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.dump("RUN.json", {"legacy": {"run": "x", "capture": "y"}, "new": {"run": "x"}})
        self.analysis = {
            "etls": [{"id": "ETL-001", "name": "orders", "entry": "uOrders.RunOrders",
                      "outputs": [{"name": "T_OUT", "key": ["ID"]}], "depends_on": []}],
            "mapping": {"units": [
                {"unit": "uOrders", "class": "etl.units.Orders",
                 "routines": [{"legacy": "RunOrders", "java": "runOrders"}, {"legacy": "Fmt", "java": "fmt"}],
                 "globals": [{"legacy": "GTotal", "java": "gTotal"}, {"legacy": "GCount", "java": "gCount"}],
                 "types": [{"legacy": "TAcc", "java": "Orders.Acc"}], "replaced": []},
                {"unit": "uCommon", "class": "etl.units.Common", "routines": [], "globals": [],
                 "replaced": [{"legacy": "ExecSql", "capability": "db.exec"}, {"legacy": "GConn", "capability": "db.connect"}]}],
                "driver": {"legacy": ["Main.dpr: TForm1.FormCreate"], "globals": ["Form"], "types": ["TForm1"],
                           "java": "etl.BatchRun"},
                "uncovered": []},
            "inventory": {"ETL-001": [{"op_id": "OP-01", "source_loc": "uOrders.pas:20-23", "does": "write total",
                                       "writes": ["T_OUT.TOTAL"], "reads": []}]},
            "rules": [{"id": "RULE-001", "name": "total", "etl": "ETL-001", "priority": "P0", "source": "uOrders.pas:20-21, 23"}],
            "tasks": [{"id": "T0", "units": ["uCommon"], "etls": []},
                      {"id": "T1", "units": ["uOrders"], "etls": ["ETL-001"]}]}
        self.save()
        main = os.path.join(self.java, "src", "main", "java", "etl")
        for n, t in CORE.items():
            self.write(os.path.join(main, "core", n), t)
        self.write(os.path.join(main, "BatchRun.java"), "class BatchRun { static void run() { Db.open(p); Orders.runOrders(); Db.commit(); } }\n")
        self.write(os.path.join(main, "units", "Orders.java"),
                   "class Orders {\n public static final class Acc { int cnt; }\n public static int gTotal;\n public static int gCount = 0;\n"
                   " public static String fmt(int v) { return \"\"; }\n"
                   " public static void runOrders() {\n  // ETL-001/OP-01\n"
                   "  Db.current().execute(\"INSERT INTO \" + Tables.out(\"T_OUT\") + \" VALUES (1)\");\n }\n}\n")
        self.write(os.path.join(main, "units", "Common.java"), "class Common {}\n")
        self.write(os.path.join(self.java, "src", "test", "java", "etl", "OrdersTest.java"),
                   "class OrdersTest { @Test public void rule001_total() {} }\n")

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def dump(self, rel, obj):
        self.write(os.path.join(self.a, rel), json.dumps(obj))

    def save(self):
        self.dump("ANALYSIS.json", self.analysis)

    def load(self, rel):
        with open(os.path.join(self.a, rel), encoding="utf-8") as fh:
            return json.load(fh)

    def script(self, name, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, name), "s"] + list(args) + ["--workspace", self.ws],
                              capture_output=True, text=True)

    def check(self, stage, *args):
        r = self.script("stage_check.py", stage, *args)
        return r.returncode, r.stdout + r.stderr


class ScanUnit(Fixture):
    def test_routines_and_globals(self):
        u = ck.scan_unit(os.path.join(self.src, "uOrders.pas"))
        self.assertEqual([n for n, _ in u["routines"]], ["RunOrders", "Fmt"])
        self.assertEqual([n for n, _ in u["globals"]], ["GTotal", "GCount"])
        self.assertEqual([n for n, _ in u["types"]], ["TAcc"])
        p = ck.scan_unit(os.path.join(self.src, "Main.dpr"))
        self.assertEqual([n for n, _ in p["routines"]], ["TForm1.FormCreate"])
        self.assertEqual([n for n, _ in p["globals"]], ["Form"])
        self.assertEqual([n for n, _ in p["types"]], ["TForm1"])


class Tasks(Fixture):
    def test_bad_tasks(self):
        self.analysis["etls"].append({"id": "ETL-002", "outputs": [{"name": "T_SUM"}], "depends_on": ["ETL-003"]})
        self.analysis["etls"].append({"id": "ETL-003", "outputs": [{"name": "T_X"}], "depends_on": []})
        self.analysis["tasks"] = [{"id": "T0", "units": ["uCommon"], "etls": []},
                                  {"id": "T1", "units": ["uCommon"], "etls": ["ETL-001", "ETL-002"]},
                                  {"id": "T2", "units": [], "etls": ["ETL-003", "ETL-001"]}]
        self.save()
        rc, out = self.check("analyze")
        self.assertEqual(rc, 1)
        for text in ("unit uCommon is in T0 and T1", "ETL-002 (T1) depends on ETL-003, which no earlier task builds",
                     "ETL-001 is in T1 and T2", "uOrders.pas is in no task's units and is not the driver"):
            self.assertIn(text, out)


class Analyze(Fixture):
    def test_pass(self):
        rc, out = self.check("analyze")
        self.assertEqual(rc, 0, out)

    def test_init_refuses_twice(self):
        r = self.script("setup.py", "--source", self.src, "--inputs", self.inputs, "--knowledge", self.knowledge)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.load("STATUS.json")["intent"]["source"], self.src)

    def test_missing_routine_and_global(self):
        self.analysis["mapping"]["units"][0]["routines"].pop()          # Fmt
        self.analysis["mapping"]["driver"]["globals"] = []              # Form
        self.save()
        rc, out = self.check("analyze")
        self.assertEqual(rc, 1)
        self.assertIn("routine Fmt (uOrders.pas:", out)
        self.assertIn("global Form (Main.dpr:", out)

    def test_bad_inventory_and_rules(self):
        self.analysis["inventory"]["ETL-001"] = [{"op_id": "OP-01", "source_loc": "uOrders.pas:900", "does": "x",
                                                  "writes": ["T_IN.X"]}]
        self.analysis["rules"] = [{"id": "R1", "priority": "P1", "source": "nope.pas:1"}]
        self.save()
        rc, out = self.check("analyze")
        for text in ("the file has", "needs a reads list", "writes T_IN.X, not an output table", "no P0 rule",
                     "is not RULE-nnn", "cites nope.pas"):
            self.assertIn(text, out)


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

    def test_task_scope(self):
        os.remove(os.path.join(self.java, "src", "main", "java", "etl", "units", "Orders.java"))
        rc, out = self.check("transform", "--task", "T0")
        self.assertEqual(rc, 0, out)
        rc, out = self.check("transform", "--task", "T1")
        self.assertIn("etl.units.Orders (unit uOrders) does not exist", out)

    def test_missing_entry_point(self):
        os.remove(os.path.join(self.java, "src", "main", "java", "etl", "BatchRun.java"))
        rc, out = self.check("transform")
        self.assertIn("rule: entry point: etl/BatchRun.java is missing", out)


ALL_CATS = ["null_empty_zero", "thresholds", "rounding_ties", "empty_table", "duplicate_keys", "missing_parent",
            "large_values", "empty_input_file", "date_sentinels"]


class Loop(Fixture):
    """Results as dual_run.py writes them; loop_gate.py and stage_check.py verify read only these."""

    def results(self, new_c01="1,7", fresh=10, categories=None, tests=0):
        cases = {}
        for i in range(fresh + 1):
            cid = "C01" if i == 0 else "F%02d" % i
            legacy = '"ID","TOTAL"\n1,7\n'
            new = '"ID","TOTAL"\n%s\n' % (new_c01 if i == 0 else "1,7")
            same = legacy == new
            cases[cid] = {"legacy": {"T_OUT": legacy}, "new": {"T_OUT": new}, "errors": {},
                          "tables": {"T_OUT": {"verdict": "same" if same else "differs",
                                               "diff": [] if same else ["rows: legacy 1, new 1", "key 1: TOTAL legacy=7 new=8"]}}}
        cats = categories if categories is not None else {"cases": {"F01": ALL_CATS}}
        self.dump("RESULTS.json", {"tests": {"exit": tests, "tail": ""}, "categories": cats, "cases": cases})
        self.write(os.path.join(self.a, "fresh_inputs.py"), "# generator\n")

    def gate(self, *args):
        r = self.script("loop_gate.py", *args)
        return r.returncode, r.stdout + r.stderr

    def test_verify_coverage(self):
        self.results(categories={"cases": {"F01": ALL_CATS[:-2]}})
        rc, out = self.check("verify")
        self.assertIn("empty_input_file has no fresh case", out)
        self.results(categories={"cases": {"F01": ALL_CATS, "F99": ["x"]}})
        rc, out = self.check("verify")
        self.assertIn("names F99, which is not a fresh case", out)
        self.results(categories={"cases": {"F01": ALL_CATS[:-2] + ["date_sentinels"]},
                                 "not_applicable": {"empty_input_file": "no file"}}, fresh=3)
        rc, out = self.check("verify")
        self.assertIn("3 fresh case(s), at least 10", out)
        self.results(categories={"cases": {"F01": ALL_CATS[:-2] + ["date_sentinels"]},
                                 "not_applicable": {"empty_input_file": "no file"}})
        rc, out = self.check("verify")
        self.assertEqual(rc, 0, out)

    def test_no_results_means_verify_then_done(self):
        rc, out = self.gate("--record")
        self.assertIn("OVERALL VERIFY", out)
        self.results()
        rc, out = self.gate("--record")
        self.assertEqual(rc, 0, out)
        self.assertIn("ETL-001 EQUIVALENT diffs=0", out)
        self.assertIn("PROOF PROVEN", out)

    def test_difference_continues_with_trace_then_same_diffs_blocks(self):
        self.results(new_c01="1,8")
        rc, out = self.gate("--record")
        self.assertEqual(rc, 1)
        self.assertIn("ETL-001 CONTINUE diffs=1", out)
        self.assertIn("TRACE ETL-001 T_OUT.TOTAL in 1 case(s) (C01) -> OP-01 legacy uOrders.pas:20-23 "
                      "java src/main/java/etl/units/Orders.java:7", out)
        self.gate("--record")
        rc, out = self.gate("--record")
        self.assertEqual(rc, 3)
        self.assertIn("BLOCKED:same_diffs", out)

    def test_dependent_etl_waits_and_is_not_counted(self):
        self.analysis["etls"].append({"id": "ETL-002", "outputs": [{"name": "T_SUM", "key": []}], "depends_on": ["ETL-001"]})
        self.analysis["inventory"]["ETL-002"] = [{"op_id": "OP-01", "source_loc": "uOrders.pas:5", "does": "sum",
                                                  "writes": ["T_SUM"], "reads": ["T_OUT.TOTAL"]}]
        self.save()
        self.results(new_c01="1,8")
        res = self.load("RESULTS.json")
        res["cases"]["C01"]["tables"]["T_SUM"] = {"verdict": "differs", "diff": ["key 1: S legacy=10 new=20"]}
        self.dump("RESULTS.json", res)
        for _ in range(3):
            rc, out = self.gate("--record")
        self.assertIn("ETL-001 BLOCKED:same_diffs", out)
        self.assertEqual(self.load("STATUS.json")["gate"]["etls"]["ETL-002"]["runs"], 0)

    def test_approved_difference_and_stale_results(self):
        self.results(new_c01="1,8")
        status = self.load("STATUS.json")
        status["approved"] = {"C01-T_OUT": "a person accepted it"}
        self.dump("STATUS.json", status)
        rc, out = self.gate()
        self.assertIn("ETL-001 EQUIVALENT", out)
        later = os.path.getmtime(os.path.join(self.a, "RESULTS.json")) + 10
        os.utime(os.path.join(self.java, "src", "main", "java", "etl", "BatchRun.java"), (later, later))
        rc, out = self.gate()
        self.assertIn("OVERALL VERIFY", out)

    def test_proof_failures(self):
        self.results(tests=1)
        os.remove(os.path.join(self.java, "src", "test", "java", "etl", "OrdersTest.java"))
        rc, out = self.gate("--record")
        self.assertIn("proof not met: tests pass: exit 1", out)
        self.assertIn("no test names RULE-001", out)
        self.assertIn("OVERALL CONTINUE", out)
        with open(os.path.join(self.src, "uOrders.pas"), "a") as fh:
            fh.write("\n")
        rc, out = self.gate()
        self.assertEqual(rc, 3)
        self.assertIn("source_changed", out)

    def test_summary(self):
        self.results(new_c01="1,8")
        self.gate("--record")
        status = self.load("STATUS.json")
        status.update({"timing": {"analyze": {"start": "10:00", "end": "10:02"}}, "checks": {"analyze": "PASS"},
                       "decisions": [{"id": "D-001", "stage": "analyze", "question": "q", "decision": "d",
                                      "source": "assumed", "affects": "ETL-001"}],
                       "blocked": {"ETL-001": {"tried": ["x"], "needs": "a person"}}, "proposals": ["add rule"]})
        self.dump("STATUS.json", status)
        self.dump("AUDIT.json", {"findings": [{"severity": "low", "where": "uOrders.pas:3", "issue": "off by one"}]})
        self.assertTrue(os.path.isdir(os.path.join(self.ws, ".git")))      # setup.py created the repository
        subprocess.run("git add -A -- analysis/s modernized/s && git -c user.name=t -c user.email=t@t commit -q "
                       "-m '[s][survey] PASS' -- analysis/s modernized/s", shell=True, cwd=self.ws, check=True)
        r = self.script("summary.py")
        rc, out = r.returncode, r.stdout + r.stderr
        self.assertEqual(rc, 0, out)
        with open(os.path.join(self.a, "SUMMARY.md")) as fh:
            text = fh.read()
        for want in ("Gate: **CONTINUE**", "Proof: **NOT PROVEN**", "| ETL-001 | CONTINUE | 1 | 1 |",
                     "| analyze | 10:00 | 10:02 | PASS |", "ETL-001: tried x; needs a person", "Assumed decisions (1 of 1)",
                     "**low** uOrders.pas:3: off by one", "- add rule", "[s][survey] PASS"):
            self.assertIn(want, text)


if __name__ == "__main__":
    unittest.main()
