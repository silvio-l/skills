# apple-notes — Reference

Detailed contract for each subcommand. Single Bash dispatcher (`scripts/apple-notes`) wrapping AppleScript; small Python helper (`scripts/_helper.py`) for HTML→text and base64 image extraction.

## Project structure (the contract)

```
<company_folder>/                    default: Firma (in iCloud)
  <project>/                         per app/repo, manually created in Apple Notes UI
    inbox/                           new issues, untriaged
    ready/                           triaged, ready for work (by agent or human)
    done/                            merged / shipped
    docs/                            templates + briefing — NOT issues
```

`init <project>` enforces this structure. All read subcommands scan **all** subfolders of `<project>` so notes that landed in legacy folders (e.g. a pre-existing `issues/`) still show up in `notes` / `search` output with the legacy folder name as the status column. Writes (`create`, `move`) only address the configured statuses.

## Title-prefix convention

Recommended, surfaced by `triage`, not enforced by `create`:

| Prefix | Meaning |
|--------|---------|
| `BUG:` | Something broken |
| `FEAT:` | Feature request |
| `IDEA:` | Half-baked thought worth keeping |
| `FB:` | User feedback |
| `TECH:` | Tech debt / refactor |

## Body convention

Body is free-form text. Non-technical partners use the BUG / FEAT / IDEA / FB templates seeded under `docs/`, which are intentionally plain (no metadata first-line, no jargon).

Only the **TECH** template (Silvio's own notes) carries a compact `·`-separated metadata first line:

```
TECH · area: app · impact: medium · tags: dispatcher, refactor

Heredocs extrahieren, damit Snippets isoliert reviewbar werden.
```

`triage` does not parse body content — it only scores the title prefix. Agents that want to act on `area` / `impact` metadata from TECH notes can split the first line on `·` and each segment on `:`.

## Subcommands

### `init <project> [--no-docs]` · `init --explain`

Creates the four status folders inside `<project>` (must already exist as a subfolder of the company folder). Seeds `docs/` with five `VORLAGE …` templates and an `Anleitung: Bugs und Feedback einbringen` cheatsheet. **Idempotent**: existing folders / notes are not touched.

`--no-docs` skips template seeding.
`--explain` prints the convention without any AppleScript calls.

### `projects [--json]`

Counts notes recursively (project root + every direct subfolder, one level deep).

### `resolve [REPO]`

Repo-name → project subfolder. Lookup chain: mapping cache → exact lowercase match → substring match → `difflib.get_close_matches` (cutoff 0.6). Caches to `~/.config/claude/apple-notes/mapping.json`. Override: `apple-notes config set-mapping <repo-key> <project>`.

### `notes <project> [--status S] [--preview N] [--limit N] [--json]`

Scans all subfolders of `<project>`. AppleScript pulls `plaintext` (HTML stripped server-side, faster, smaller); skill squashes newlines/tabs to space within each row.

- Default output: grouped by status, `<date>  <title-50>  <preview>` rows.
- `--status` filters to one subfolder.
- `--limit` caps after sort (most-recent-first within each status).

### `get <project> <title> [--format text|html|raw]`

`locate_note` finds which subfolder holds the note (first match wins). Then `body of note` (raw HTML) is fetched.

- `text` (default): replace inline base64 `<img>` with `[image:N]` placeholders, decode block tags to newlines, unescape HTML entities, normalize whitespace.
- `html`: keep HTML, only base64 stripped to placeholders.
- `raw`: untouched body (potentially large; use sparingly).

### `images <project> <title> [--out DIR]`

Same locate-then-fetch. Inline base64 images decoded into `<DIR>/<project-title-slug>/image-NN-<sha8>.<ext>`. Output: JSON `[{index, path, bytes, mime}]`. MIMEs mapped: jpeg/jpg/png/gif/webp/heic/heif/tiff/svg/bmp.

**Limitation**: AppleScript provides no file-path API for non-inline attachments (videos, PDFs, audio, rich-linked images). They appear in the body as `￼` placeholder characters but cannot be extracted by this skill.

### `search <query> [--project NAME] [--preview N] [--json]`

Server-side AppleScript filter: `whose name contains q or plaintext contains q`. Iterates every project + every status subfolder. Default output: `<date>  <project-12>  <status-10>  <title-40>  <preview>`, sorted most-recent first.

### `create <project> <title> [--status S] [--body-file F]`

Body from `--body-file` or stdin. Plain text (no `<`) is wrapped per line in `<div>…</div>`; empty lines become `<div><br></div>`; characters HTML-escaped. HTML markup is passed through verbatim. The note title is prepended as `<div>TITLE</div>` so it renders correctly in Apple Notes UI.

Default status: `inbox`. Validated against the configured `statuses` array.

### `update <project> <title>` · `append <project> <title>`

`update` = full body replacement (keeps the note in its current status folder). `append` = concatenate to existing body. Both auto-locate the note across all subfolders. Both accept body via stdin or `--body-file`.

### `delete <project> <title> --force`

Without `--force`: prints confirmation hint, exits 1. With `--force`: AppleScript `delete note` — Apple Notes moves to **Recently Deleted** (30-day recovery). Permanent deletion requires manually emptying Recently Deleted.

### `move <project> <title> <new-status>`

Status transition inside the same project. `new-status` validated. Notes in non-status folders (legacy) can be moved out of them, but not back into them.

### `triage <project> [--json]`

Scans the `inbox/` folder. For each note, runs exactly one check:

- **prefix** check: title matches `^(BUG|FEAT|IDEA|FB|TECH):\s+\S`.

Output (default): ` ✓ <title-55>  looks good` / ` ⚠ <title-55>  missing-prefix`. JSON adds counts (`ok`, `warn`).

Body content is not scored. The Normalo-templates seed plain free-form text, so any metadata expectation would penalise well-written partner notes. The skill **does not** modify notes during triage. Use the output to guide manual or agent-led follow-up.

### `config show | set <key> <value> | set-mapping <repo-key> <project>`

`set` rewrites top-level string keys in `config.json`. List-valued keys (`statuses`) must be edited in the file directly. `set-mapping` normalizes the repo-key (lowercase + alphanumeric) and writes to `mapping.json`.

## Files

```
~/.config/claude/apple-notes/
├── config.json    account, company_folder, statuses, default_status, default_image_dir
└── mapping.json   repo-key → project-name cache + overrides

/tmp/apple-notes-images/<slug>/   default image extraction target
```

`config.json` is gently migrated on every run — new keys with sane defaults are backfilled, never overwriting.

## Exit codes

- `0` success.
- `1` handled error: bad arg, note not found, ambiguous resolve, AppleScript error surfaced as `ERR:…`. Message on stderr.

## AppleScript caveats

- **Locale-independent dates**: month/day are extracted as integers (`(month of d) as integer` returns 1–12 regardless of system locale) and zero-padded by the skill.
- **No apostrophes in single-quoted heredocs inside `$(…)`**: Bash 3.2's parser breaks on `AppleScript's text item delimiters` inside `out="$(osa … <<'TAG' …)"`. The skill uses `text item delimiters of AppleScript` instead.
- **Reserved word avoidance**: variable names `st`, `from`, `to` collide with AppleScript keywords in some contexts. The skill uses `theStatus`, `fromStatus`, `toStatus`, and avoids one-letter names other than `t` (note title) and `b` (body).
- **`whose` filtering** is case-sensitive on titles. Get the exact title from `notes` output before calling `get` / `move` / `delete`.
- **Argv passing**: every AppleScript runs via `osascript - "$@" <<APPLESCRIPT … APPLESCRIPT`. Args go through argv — no shell-level string interpolation, safe for Unicode and special characters.

## Adding a new status

1. Edit `~/.config/claude/apple-notes/config.json`, append to `statuses`.
2. `apple-notes init <project>` for each project to materialize the new folder.

## Removing the mapping cache

```bash
rm ~/.config/claude/apple-notes/mapping.json
```

Re-resolves on next `resolve` call.

## Reseeding templates

`apple-notes init` is idempotent. If you want to reset the templates to the latest version: delete them in Apple Notes (or via `apple-notes delete <project> "VORLAGE …" --force`), then `apple-notes init <project>` recreates them.
