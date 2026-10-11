import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(os.path.dirname(HERE), "loop_gate.py")


class LoopGate(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.adir = os.path.join(self.ws, "analysis", "s")
        self.eq = os.path.join(self.adir, "equivalence")
        os.makedirs(self.eq)
        os.makedirs(os.path.join(self.ws, "modernized", "s", "java", "src"))
        with open(os.path.join(self.ws, "modernized", "s", "java", "src", "A.java"), "w") as fh:
            fh.write("class A {}")
        self.run_spec = {"adapter": "sqlite", "suffix": "_NEW", "inputs": {"db": "in.db"},
                         "tables": [{"name": "T_A", "etl": "ETL-001"}, {"name": "T_B", "etl": "ETL-002"}],
                         "legacy": {"run": "x"}, "new": {"run": "y"}}
        self.dump("RUN.json", self.run_spec, self.adir)
        self.files = {}

    def dump(self, name, obj, folder=None):
        with open(os.path.join(folder or self.eq, name), "w") as fh:
            json.dump(obj, fh)

    def out(self, side, case, text):
        path = os.path.join(self.eq, side, case + ".csv")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def cases(self, a_new, b_new, extra=None):
        self.out("legacy", "C01-T_A", "a\n1\n")
        self.out("legacy", "C01-T_B", "b\n1\n")
        self.out("new", "C01-T_A", a_new)
        self.out("new", "C01-T_B", b_new)
        cs = [{"id": "C01-T_A", "input": "C01", "legacy": "legacy/C01-T_A.csv", "new": "new/C01-T_A.csv"},
              {"id": "C01-T_B", "input": "C01", "legacy": "legacy/C01-T_B.csv", "new": "new/C01-T_B.csv"}]
        if extra:
            cs[0].update(extra)
        self.dump("cases.json", {"cases": cs})

    def gate(self, record=True):
        args = [sys.executable, GATE, "s", "--workspace", self.ws] + (["--record"] if record else [])
        r = subprocess.run(args, capture_output=True, text=True)
        return r.returncode, r.stdout

    def test_equivalent_then_verify_then_done(self):
        self.cases("a\n1\n", "b\n1\n")
        rc, out = self.gate()
        self.assertIn("ETL-001 EQUIVALENT diffs=0", out)
        self.assertIn("OVERALL VERIFY", out)
        self.assertEqual(rc, 1)
        time.sleep(0.01)
        self.dump("VERIFICATION.json", {"overall": {"verdict": "PROVEN"}, "modules": []}, self.adir)
        rc, out = self.gate()
        self.assertIn("OVERALL DONE", out)
        self.assertEqual(rc, 0)

    def test_one_etl_differs_continue_then_same_diffs_blocks(self):
        self.cases("a\n2\n", "b\n1\n")
        for _ in range(2):
            rc, out = self.gate()
            self.assertIn("ETL-001 CONTINUE diffs=1", out)
            self.assertIn("ETL-002 EQUIVALENT", out)
            self.assertIn("OVERALL CONTINUE", out)
        rc, out = self.gate()
        self.assertIn("ETL-001 BLOCKED:same_diffs", out)
        self.assertIn("OVERALL VERIFY", out)       # the other ETL can still be proven

    def test_report_without_record_does_not_count(self):
        self.cases("a\n2\n", "b\n1\n")
        for _ in range(5):
            self.gate(record=False)
        with open(os.path.join(self.adir, "AUTO_STATUS.json")) as fh:
            self.assertEqual(json.load(fh)["gate"]["etls"]["ETL-001"]["runs"], 0)

    def test_mask_blocks(self):
        self.cases("a\n1\n", "b\n1\n", extra={"mask": [{"regex": "1", "why": "hide"}]})
        rc, out = self.gate()
        self.assertIn("BLOCKED:mask_or_tolerance", out)
        self.assertEqual(rc, 3)

    def test_changed_baseline_blocks(self):
        self.cases("a\n1\n", "b\n1\n")
        self.gate()
        self.out("legacy", "C01-T_A", "a\n9\n")
        self.out("new", "C01-T_A", "a\n9\n")
        rc, out = self.gate()
        self.assertIn("BLOCKED:frozen_changed", out)

    def test_stale_verification_is_ignored(self):
        self.cases("a\n1\n", "b\n1\n")
        self.dump("VERIFICATION.json", {"overall": {"verdict": "PROVEN"}, "modules": []}, self.adir)
        old = time.time() - 100
        os.utime(os.path.join(self.adir, "VERIFICATION.json"), (old, old))
        rc, out = self.gate()
        self.assertIn("OVERALL VERIFY", out)

    def test_not_proven_continues_then_blocks(self):
        self.cases("a\n1\n", "b\n1\n")
        for i in range(3):
            time.sleep(0.01)
            self.dump("VERIFICATION.json", {"overall": {"verdict": "NOT PROVEN", "n": i},
                                            "modules": [{"reasons": ["Canary: no test failed"]}]}, self.adir)
            rc, out = self.gate()
            self.assertIn("Canary: no test failed", out)
        self.assertIn("OVERALL BLOCKED", out)
        self.assertIn("verify_stuck", out)


if __name__ == "__main__":
    unittest.main()
