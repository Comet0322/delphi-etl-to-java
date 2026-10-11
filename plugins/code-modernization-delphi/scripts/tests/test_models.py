import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        head = fh.read().split("---", 2)[1]
    out = {}
    for line in head.splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


class Models(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "MODELS.json"), encoding="utf-8") as fh:
            self.models = json.load(fh)

    def test_every_stage_agent_matches_its_file(self):
        for name, tier in self.models["agents"].items():
            fm = frontmatter(os.path.join(ROOT, "agents", name + ".md"))
            self.assertEqual(fm.get("name"), name)
            self.assertEqual(fm.get("model"), tier["model"], name)
            self.assertEqual(fm.get("effort"), tier["effort"], name)

    def test_every_stage_in_the_stage_doc_has_an_agent(self):
        with open(os.path.join(ROOT, "AUTO_STAGES.md"), encoding="utf-8") as fh:
            stages = re.findall(r"^## (\w+)$", fh.read(), re.M)
        self.assertEqual(sorted("stage-" + s for s in stages), sorted(self.models["agents"]))

    def test_router_tier_is_set(self):
        self.assertIn(self.models["router"]["model"], ("haiku", "sonnet", "opus", "fable"))


if __name__ == "__main__":
    unittest.main()
