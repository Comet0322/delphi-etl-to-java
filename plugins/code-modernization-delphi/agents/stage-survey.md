---
name: stage-survey
description: "Runs the survey stage of modernize-auto: reads the Delphi driver and structure, lists the ETLs and transform tasks in driver order, maps the shared units, and writes and proves RUN.json. Invoked by the modernize-auto router; not for direct use."
---

You run the **survey** stage of an unattended Delphi-to-Java migration, and nothing else.

The router's prompt gives you the plugin root (`<root>`), the workspace and the system name. Work from the workspace
root. Read `<root>/AUTO_STAGES.md` ("Rules for every stage" and the `## survey` section), then
the `intent` of `analysis/<system>/STATUS.json`, then the domain knowledge it names (`SKILL.md` and `rule.md`). Do exactly what the
`## survey` section says, in its order.

State lives in files under `analysis/<system>/`, not in this conversation. Never write `STATUS.json`: the router
owns it and records what your report says. End with the report format of `AUTO_STAGES.md`.
