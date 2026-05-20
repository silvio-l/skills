---
name: apple-notes
description: Read, search, write, and extract images from Apple Notes on macOS via a single dispatcher script (AppleScript under the hood). Treats subfolders of one configured "company folder" as projects, auto-maps the current git repo to its project subfolder, and returns token-efficient plain-text output by default. Use when the user references Apple Notes, says "check my notes", "pull bug reports from Notes", "what did I write about this app in Notes", wants to extract attached images/screenshots, or asks to grab feedback/bug-reports/ideas from a project's Apple Notes folder.
---

# Apple Notes

One dispatcher: `scripts/apple-notes <subcommand>`. All subcommands print to stdout, errors to stderr, exit non-zero on failure.

## Quick start

```bash
SKILL=~/.claude/skills/apple-notes/scripts/apple-notes

# Which project subfolder matches the current repo? (caches the answer)
"$SKILL" resolve

# List notes in that project
PROJECT=$("$SKILL" resolve)
"$SKILL" notes "$PROJECT"

# Read one note as plain text (default; strips base64 images)
"$SKILL" get "$PROJECT" "Bug: Login flaky on iPad"

# Extract embedded images to /tmp/apple-notes-images/<slug>/
"$SKILL" images "$PROJECT" "Bug: Login flaky on iPad"
```

## Mental model

- One configured **company folder** in Apple Notes (default: `Firma` in account `iCloud`) contains one subfolder per app/project (e.g. `HellerIO`, `Whispaste`).
- The skill treats those subfolders as **projects** and maps the current git repo to one of them using `resolve` (fuzzy match + on-disk cache at `~/.config/claude/apple-notes/mapping.json`).
- Notes are addressed by **title** within a project. Bodies are HTML; the skill returns plain text by default to save tokens.

## Token-efficiency rules

1. Default `get` format is `text` — base64 images become `[image:N]` placeholders.
2. `notes` lists title + date + 80-char preview only; use `--preview 0` to suppress preview, `--json` for machine output.
3. Use `images <project> <title>` to extract images into a temp dir, then `Read` the resulting paths (multimodal). Don't dump base64 into the LLM.
4. `search` searches across all projects by default; use `--project <name>` to scope.

## Workflow: pull bug reports / feedback for the current repo

1. `apple-notes resolve` → confirms / picks project subfolder.
2. `apple-notes notes <PROJECT>` → see what's there.
3. `apple-notes search "<keyword>" --project <PROJECT>` or `apple-notes get <PROJECT> "<title>"` to read full content.
4. If a note has screenshots: `apple-notes images <PROJECT> "<title>"` → JSON of saved paths → `Read` each to see them.

## CRUD writes (rare — confirm with user first)

- `create <PROJECT> <TITLE>` — body on stdin or `--body-file`. Plain text is auto-wrapped in `<div>`; raw HTML is passed through.
- `update <PROJECT> <TITLE>` — **full replacement** of body. Read first, edit, write back.
- `append <PROJECT> <TITLE>` — append to existing body (use this to add status / comments).
- `delete <PROJECT> <TITLE> --force` — moves to Recently Deleted in Apple Notes (recoverable for 30 days).
- `move <FROM> <TITLE> <TO>` — between project subfolders.

## Setup

First call creates `~/.config/claude/apple-notes/config.json` with defaults:

```json
{ "account": "iCloud", "company_folder": "Firma", "default_image_dir": "/tmp/apple-notes-images" }
```

Change with `apple-notes config set <key> <value>`. Manual mapping override: `apple-notes config set-mapping <repo-key> <project-name>`.

## macOS permissions

Claude Code's host terminal must have **Automation → Notes** enabled in `System Settings → Privacy & Security`. First invocation triggers the prompt; if it was denied earlier, toggle it in System Settings.

## Limitations & guidance

- **Attachments without inline base64**: AppleScript exposes no file path for attached images that aren't inline. The skill extracts every image that *is* inline (the common case for screenshots pasted directly into a note). Notes with linked rich previews remain inaccessible programmatically — flag this to the user and ask them to paste the image directly.
- **Duplicate titles within a project**: AppleScript returns the first match; rename in Notes if disambiguation matters.
- **Subfolder names must be unique inside the company folder.**

See [REFERENCE.md](REFERENCE.md) for subcommand details, exit codes, and AppleScript caveats.
