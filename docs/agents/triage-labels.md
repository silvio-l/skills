# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| --------------------------- | --------------------- | ----------------------------------------- |
| `needs-triage`              | `needs-triage`         | Maintainer needs to evaluate this issue  |
| `needs-info`                | `needs-info`           | Waiting on reporter for more information |
| `ready-for-agent`           | `ready-for-agent`      | Fully specified, ready for an AFK agent  |
| `ready-for-human`           | `ready-for-human`      | Requires human implementation            |
| `wontfix`                   | `wontfix`               | Will not be actioned                     |

There's no external label system here (issue tracker is local markdown, see `issue-tracker.md`) — the right-hand column is identical to the canonical name by design. A `Status:` line near the top of each issue file carries the label string directly.

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.
