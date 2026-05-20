---
name: apple-notes
description: Read, search, write, and extract images from Apple Notes on macOS via a single dispatcher script (AppleScript under the hood). Treats subfolders of one configured "company folder" as projects, auto-maps the current git repo to its project subfolder, and enforces a four-folder issue layout (inbox/ready/done/docs) with title-prefix conventions (BUG:/FEAT:/IDEA:/FB:/TECH:) so non-technical collaborators can drop in bug reports that agents can later triage and act on. Use when the user references Apple Notes, says "check my notes", "pull bug reports from Notes", "what did my partner write about this app", wants to extract screenshots from a note, triage the inbox, or move an issue between statuses.
---

# Apple Notes

One dispatcher: `scripts/apple-notes <subcommand>`. AppleScript under the hood. Output is plain text by default, `--json` available where useful.

## Project layout (enforced by `init`, scanned by all reads)

```
Firma/                       ← company folder (configurable; default "Firma" in iCloud)
  HellerIO/                  ← one subfolder per app/repo
    inbox/                   ← new, untriaged
    ready/                   ← triaged, ready for work
    done/                    ← merged / shipped
    docs/                    ← templates, briefing, specs — NOT issues
  Whispaste/
    inbox/  ready/  done/  docs/
```

**Title-prefix convention** (recommended, surfaced by `triage`):
`BUG:` `FEAT:` `IDEA:` `FB:` (user feedback) `TECH:` (tech debt / refactor).

**Body convention**: first non-empty line = compact metadata separated by `·`, rest free-form. Example:
```
BUG · severity: medium · platform: iOS · tags: onboarding, ux

Schieberegler ist zu empfindlich. Beim Loslassen verspringt der Wert …
```

## Quick start

```bash
S=~/.claude/skills/apple-notes/scripts/apple-notes

"$S" init HellerIO            # creates inbox/ready/done/docs + seeds templates+cheatsheet
"$S" resolve                  # auto-map current repo to project (cached)
"$S" notes "$($S resolve)"    # list, grouped by status
"$S" triage HellerIO          # inbox health check (prefix + metadata)
"$S" get HellerIO "BUG: Login flaky"   # plain-text body
"$S" images HellerIO "BUG: Login flaky"  # extract base64 images → JSON paths
```

## Subcommands

| | |
|---|---|
| `init <project>` | Creates the four status folders and seeds `docs/` with five issue templates (`VORLAGE BUG/FEAT/IDEA/FB/TECH`) + an `Anleitung`-cheatsheet for non-technical collaborators. Idempotent; existing notes are never overwritten. `--no-docs` skips the templates. `init --explain` prints the convention. |
| `projects [--json]` | Lists app subfolders of the company folder with note counts. |
| `resolve [REPO]` | Maps a repo name (default: current git toplevel) to a project. Cached at `~/.config/claude/apple-notes/mapping.json`. |
| `notes <project> [--status S] [--limit N] [--preview N] [--json]` | Lists notes; default groups by status. |
| `get <project> <title> [--format text\|html\|raw]` | Reads a note; auto-locates across all status folders. Default `text` strips base64 → `[image:N]`. |
| `images <project> <title> [--out DIR]` | Extracts inline base64 images to `/tmp/apple-notes-images/<slug>/` and prints JSON `[{path,bytes,mime}]`. |
| `search <query> [--project NAME] [--json]` | Full-text across all projects + statuses. |
| `create <project> <title> [--status S] [--body-file F]` | Body on stdin or `--body-file`. Default status: `inbox`. |
| `update <project> <title>` / `append <project> <title>` | Replace / append. Auto-locates the note; status stays. |
| `delete <project> <title> --force` | Moves to "Recently Deleted" (recoverable for 30 days). |
| `move <project> <title> <new-status>` | Status transition: `apple-notes move HellerIO "BUG: …" ready`. |
| `triage <project> [--json]` | Inbox health: per-note score (✓ / ⚠ / ✗) based on title prefix and metadata first-line. |
| `config show \| set <k> <v> \| set-mapping <repo> <project>` | Read/write config + manual repo→project overrides. |

## Token-efficiency rules

1. Default `get` format is `text` — base64 images are placeholders, not the LLM payload.
2. `notes` lists `title + date + 80-char preview`, grouped by status.
3. For screenshots: `images <project> <title>` → temp paths → `Read` each path (multimodal). Never paste raw base64.
4. `search` returns the most recent match first; use `--project NAME` to scope.

## Workflows

**Pull issues from a partner-maintained inbox**
1. `apple-notes triage <project>` — see which inbox notes are well-formed.
2. `apple-notes notes <project> --status inbox` — full list.
3. `apple-notes get <project> <title>` for content; `apple-notes images …` for screenshots.
4. Decide: `apple-notes move <project> <title> ready` (acknowledge, will fix) or `delete --force` (won't fix).
5. After implementation: `apple-notes move <project> <title> done`.

**Onboarding a new project**
1. Create the project subfolder manually in Apple Notes UI (e.g. `Whispaste`).
2. `apple-notes init Whispaste` — folders + templates land.
3. Share the `Anleitung: Bugs und Feedback einbringen` note (in `docs/`) with the human collaborator.

## Setup

First run creates `~/.config/claude/apple-notes/config.json` with defaults:
```json
{
  "account": "iCloud",
  "company_folder": "Firma",
  "statuses": ["inbox", "ready", "done", "docs"],
  "default_status": "inbox",
  "default_image_dir": "/tmp/apple-notes-images"
}
```
Change with `apple-notes config set <key> <value>`. Pre-existing configs are gently migrated on every run.

## macOS permissions

Claude Code's host terminal must have **Automation → Notes** enabled in `System Settings → Privacy & Security`. First invocation triggers the prompt; if denied earlier, toggle it back.

## Limitations

- **Inline base64 only**: only images that Apple Notes stored inline are extractable. Video, audio, PDFs, and richly-linked attachments are flagged in the note body (often as `￼`) but not retrievable via AppleScript.
- **Duplicate titles within a status folder**: AppleScript returns the first match; rename in Apple Notes for disambiguation.
- **Status set is configurable** but enforced by `init` + `move`. Adding a new status: edit `config.json` `statuses` array and re-run `init`.

See [REFERENCE.md](REFERENCE.md) for AppleScript caveats, exit codes, and full subcommand contracts.
