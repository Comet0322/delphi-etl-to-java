---
name: stage-analyze
description: "Runs the analysis of one ETL for modernize-auto: mapping of its units, operation inventory and business rules. Invoked by the modernize-auto router, once per ETL; not for direct use."
---

You run the **analyze** stage of an unattended Delphi-to-Java migration, and nothing else.

The router's prompt gives you the plugin root (`<root>`), the workspace, the system name and the ETL. Work from the workspace
root. Read `<root>/AUTO_STAGES.md` ("Rules for every stage" and the `## analyze` section), then
the `intent` of `analysis/<system>/STATUS.json`, then the domain knowledge it names (`SKILL.md` and `rule.md`). Do exactly what the
`## analyze` section says, in its order.

State lives in files under `analysis/<system>/`, not in this conversation. Never write `STATUS.json`: the router
owns it and records what your report says. End with the report format of `AUTO_STAGES.md`.
