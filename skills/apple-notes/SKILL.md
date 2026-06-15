---
name: apple-notes
description: Read, search, write Apple Notes on macOS and extract their images. Enforces an inbox/ready/done/docs layout per project. Use when the user references Apple Notes, "check my notes", "pull bug reports from Notes", or extract screenshots.
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

**Title-prefix convention** (the only requirement, surfaced by `triage`):
`BUG:` `FEAT:` `IDEA:` `FB:` (user feedback) `TECH:` (tech debt / refactor).

**Body**: free-form text. Non-technical partners write plain prose using the BUG / FEAT / IDEA / FB templates seeded under `docs/`. Only the TECH template (Silvio's own notes) carries a compact `·`-separated metadata first line — agents and `triage` do not require it for any other prefix.

## What each folder means → which one to read

Pick the folder by **intent**. Crucial: a bare `notes <project>` lists *every* status, and `search` spans *every* project + status — so neither answers "what's new". Both will surface long-done and ready items as if they were fresh. This is the #1 mistake: do not answer an "incoming" question from `search` or an unscoped `notes`.

| Folder | Meaning | Read it when the user asks… |
|--------|---------|------------------------------|
| `inbox` | New, untriaged — the **only** "new" surface | "newest bugs", "what's new", "what did my partner report", "any new feedback", "triage the inbox" → `notes <project> --status inbox` (or `triage <project>`) |
| `ready` | Triaged, accepted, waiting for work | "what's ready", "next task", "the backlog" → `notes <project> --status ready` |
| `done` | Merged / shipped — history only | "what shipped", "already fixed", "what's done" → `notes <project> --status done` |
| `docs` | Templates, briefing, specs — **never issues** | only when explicitly asked for a template/spec; never list these as bugs/issues |

**Default rule:** any request about *incoming / new / latest / unhandled / untriaged* items ⇒ scope to **`--status inbox`**. Only widen to `ready`/`done`, or fall back to `search`, when the user *explicitly* asks for those statuses or for an across-everything lookup. When unsure which folder the user means, ask — don't silently pull from all of them.

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
| `get <project> <title> [--format text\|html\|raw]` | Reads a note; auto-locates across all status folders. `<title>` may be the exact name, a truncated/ellipsis title as listed, a prefix, or a raw note `id`. Default `text` strips base64 → `[image:N]`. |
| `images <project> <title> [--out DIR]` | Extracts inline base64 images to `/tmp/apple-notes-images/<slug>/` and prints JSON `[{path,bytes,mime}]`. |
| `search <query> [--project NAME] [--json]` | Full-text across all projects + statuses. |
| `create <project> <title> [--status S] [--body-file F]` | Body on stdin or `--body-file`. Default status: `inbox`. |
| `update <project> <title>` / `append <project> <title>` | Replace / append. Auto-locates the note; status stays. |
| `delete <project> <title> --force` | Moves to "Recently Deleted" (recoverable for 30 days). |
| `move <project> <title> <new-status>` | Status transition: `apple-notes move HellerIO "BUG: …" ready`. |
| `triage <project> [--json]` | Inbox health: per-note score (✓ / ⚠) based on whether the title carries one of the configured prefixes (`BUG:` / `FEAT:` / `IDEA:` / `FB:` / `TECH:`). Body content is no longer scored. |
| `config show \| set <k> <v> \| set-mapping <repo> <project>` | Read/write config + manual repo→project overrides. |

## Token-efficiency rules

1. Default `get` format is `text` — base64 images are placeholders, not the LLM payload.
2. `notes` lists `title + date + 80-char preview`, grouped by status.
3. For screenshots: `images <project> <title>` → temp paths → `Read` each path (multimodal). Never paste raw base64.
4. `search` returns the most recent match first; use `--project NAME` to scope.

## Workflows

**Verify every write.** `move`, `create`, `update`, and `init` print `OK` or `ERR:…`. After any write, check that line — on `ERR:` surface it and do **not** report success. For `move`, confirm by re-listing: `apple-notes notes <project> --status <new-status>` must now include the note. Never claim a note was moved/created/updated without seeing it land.

**Pull issues from a partner-maintained inbox**
1. `apple-notes triage <project>` — see which inbox notes are well-formed.
2. `apple-notes notes <project> --status inbox` — full list.
3. `apple-notes get <project> <title>` for content; `apple-notes images …` for screenshots.
4. Present your assessment and propose `apple-notes move <project> <title> ready` (acknowledge, will fix) or `delete --force` (won't fix). Wait for explicit user confirmation before running `delete --force` — deletion is destructive and the agent must not decide it autonomously.
5. After implementation: `apple-notes move <project> <title> done`.

**Always close the loop on processed inbox notes (standing reminder rule)**

Whenever you have *acted on* one or more `inbox` notes in a turn — triaged them, diagnosed them, turned them into a plan/PRD, or fixed them — you MUST end that turn by **offering to move those specific notes to `ready`** (acknowledged / will-fix). List the affected note titles and ask explicitly, e.g. "Soll ich diese N Notizen nach `ready` verschieben?".

- This is a standing reminder that fires on **every** such turn, not a one-off.
- **Never move them autonomously.** Always wait for explicit confirmation — the user may have only partly processed a note, or may want to revisit it later.
- `ready` = "acknowledged, will fix". Reserve `done` for after the work ships, and `delete --force` (still confirmation-gated) for "won't fix".
- If the user declines or stays silent, leave the notes in `inbox` and simply re-offer the next time they are processed.

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

## Long titles & truncation

Apple Notes has no separate title field — a note's title **is** its first body line, truncated to ~64 chars + `…` once it gets long. So when a collaborator dumps the whole report into the first line (no line break), the listed title is a truncated ellipsis form while the full text lives in the body.

This is handled transparently: `get`/`update`/`append`/`move`/`delete` resolve a `<title>` that is exact, **truncated**, a prefix, ASCII-`...`, or a raw **note `id`**. For bulletproof addressing across several operations, take the `id` from `notes --json` / `search --json` and pass it as `<title>`. If two notes collide on a prefix, the command aborts as `ambiguous` and asks for the id.

To *prevent* the problem at the source, the seeded `Anleitung`/templates ask collaborators to keep the first line a short title and put detail in the lines below.

## Limitations

- **Inline base64 only**: only images that Apple Notes stored inline are extractable. Video, audio, PDFs, and richly-linked attachments are flagged in the note body (often as `￼`) but not retrievable via AppleScript.
- **Duplicate / prefix-colliding titles**: when a title query ties across notes, the command aborts as ambiguous — disambiguate with the note `id` (from `--json`) or rename in Apple Notes.
- **Status set is configurable** but enforced by `init` + `move`. Adding a new status: edit `config.json` `statuses` array and re-run `init`.

See [REFERENCE.md](REFERENCE.md) for AppleScript caveats, exit codes, and full subcommand contracts.
