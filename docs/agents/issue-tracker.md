# Issue tracker: Local Markdown

Issues and PRDs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The PRD, if any, is `.scratch/<feature-slug>/PRD.md`
- Implementation issues are `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`
- Triage state is recorded as a `Status:` line near the top of each issue file — see [triage-labels.md](./triage-labels.md) for the role strings
- Comments and conversation history append to the bottom of each file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Note on `.scratch/` being gitignored

`.scratch/` is currently listed in `.gitignore` — it was originally intended as a local-only scratch space. That means issues stored here will **not be pushed** to GitHub by default.

That is the intentional posture for this repo: this is a Skill-Source-Repository with a "edit here → push → roundtrip" workflow (see `CLAUDE.md`). Issues here are private working notes, not shared tracking. If at some point you want to surface issues publicly, either:

- remove `.scratch/` from `.gitignore`, or
- switch to GitHub Issues by re-running `/setup-matt-pocock-skills`.
