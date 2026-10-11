import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Stages(unittest.TestCase):
    def test_every_stage_section_has_an_agent_and_back(self):
        with open(os.path.join(ROOT, "AUTO_STAGES.md"), encoding="utf-8") as fh:
            stages = re.findall(r"^## (\w+)$", fh.read(), re.M)
        agents = sorted(n[:-3] for n in os.listdir(os.path.join(ROOT, "agents")) if n.startswith("stage-"))
        self.assertEqual(sorted("stage-" + s for s in stages), agents)

    def test_stage_agents_name_matches_file(self):
        for n in os.listdir(os.path.join(ROOT, "agents")):
            if n.startswith("stage-"):
                with open(os.path.join(ROOT, "agents", n), encoding="utf-8") as fh:
                    self.assertIn("\nname: %s\n" % n[:-3], fh.read())


if __name__ == "__main__":
    unittest.main()
