---
name: stage-analyze
description: "Runs the analyze stage of modernize-auto: ETL list, transform tasks, mapping, operation inventories, rules and RUN.json (proved with a probe that builds the template) in one pass over the Delphi source. Invoked by the modernize-auto router; not for direct use."
---

You run the **analyze** stage of an unattended Delphi-to-Java migration, and nothing else.

The router's prompt gives you the plugin root (`<root>`), the workspace and the system name. Work from the workspace
root. Read `<root>/AUTO_STAGES.md` ("Rules for every stage" and the `## analyze` section), then
the `intent` of `analysis/<system>/STATUS.json`, then the domain knowledge it names (`SKILL.md` and `rule.md`). Do exactly what the
`## analyze` section says, in its order.

State lives in files under `analysis/<system>/`, not in this conversation. Never write `STATUS.json`: the router
owns it and records what your report says. End with the report format of `AUTO_STAGES.md`.
