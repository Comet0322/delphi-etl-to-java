---
name: stage-verify
description: "Runs the verify stage of modernize-auto: an independent re-check (fresh inputs, clean dual run, proof checks). Fixes nothing. Invoked by the modernize-auto router; not for direct use."
---

You run the **verify** stage of an unattended Delphi-to-Java migration, and nothing else.

The router's prompt gives you the plugin root (`<root>`), the workspace and the system name. Work from the workspace
root. Read `<root>/AUTO_STAGES.md` ("Rules for every stage" and the `## verify` section), then
the `intent` of `analysis/<system>/STATUS.json`, then the domain knowledge it names (`SKILL.md` and `rule.md`). Do exactly what the
`## verify` section says, in its order.

State lives in files under `analysis/<system>/`, not in this conversation. Never write `STATUS.json`: the router
owns it and records what your report says. End with the report format of `AUTO_STAGES.md`.
