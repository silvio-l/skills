# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual status strings used in this repo's issue files.

Because the issue tracker here is local markdown (see [issue-tracker.md](./issue-tracker.md)), these "labels" are not GitHub labels — they are the value written after `Status:` near the top of each issue file under `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.

| Label in mattpocock/skills | Status string in our files | Meaning                                  |
| -------------------------- | -------------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`             | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`               | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`          | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`          | Requires human implementation            |
| `wontfix`                  | `wontfix`                  | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), write the corresponding string into the issue file's `Status:` line.

Edit the right-hand column to match whatever vocabulary you actually use.
