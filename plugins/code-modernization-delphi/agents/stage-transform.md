---
name: stage-transform
description: "Runs one transform task of modernize-auto: translates the task's Delphi units one to one into Java per the domain knowledge, extends the entry point up to the task's ETLs, and iterates the dual run until their output matches. Invoked by the modernize-auto router, once per task; not for direct use."
---

You run the **transform** stage of an unattended Delphi-to-Java migration, and nothing else.

The router's prompt gives you the plugin root (`<root>`), the workspace, the system name and the task. Work from the workspace
root. Read `<root>/AUTO_STAGES.md` ("Rules for every stage" and the `## transform` section), then
the `intent` of `analysis/<system>/STATUS.json`, then the domain knowledge it names (`SKILL.md` and `rule.md`). Do exactly what the
`## transform` section says, in its order.

State lives in files under `analysis/<system>/`, not in this conversation. Never write `STATUS.json`: the router
owns it and records what your report says. End with the report format of `AUTO_STAGES.md`.
