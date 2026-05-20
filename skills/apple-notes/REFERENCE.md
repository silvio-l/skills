# apple-notes — Reference

Detailed contract for each subcommand. The skill is a single Bash dispatcher (`scripts/apple-notes`) that wraps AppleScript and pipes results through a small Python helper (`scripts/_helper.py`) for HTML→text and base64 image extraction.

## Subcommands

### `projects [--json]`

Lists subfolders of the company folder.

- **Default output**: `<name>` left-padded to 30 chars + `<count> notes`.
- **`--json`**: array of `{name, notes}`.

### `resolve [REPO]`

Resolves a repo name to a project subfolder name.

- If `REPO` is omitted, derives it from `git rev-parse --show-toplevel` (basename), falling back to `basename $PWD`.
- Lookup order: mapping cache → exact lowercase match → substring match → `difflib.get_close_matches` (cutoff 0.6).
- Caches a successful resolution to `~/.config/claude/apple-notes/mapping.json`.
- Exit 1 if no match or ambiguous; stderr lists the available projects and prints the `config set-mapping` hint.

### `notes <PROJECT> [--limit N] [--preview N] [--json]`

Lists notes in a project. AppleScript-side `plaintext` is read (not HTML), then truncated to 400 chars and squashed (newlines/tabs → space) per row to avoid breaking the record format. Final preview clipped to `--preview` (default 80).

- **Default output**: `YYYY-MM-DD  <title-padded-50>  <preview>`.
- **`--json`**: array of `{title, modified, preview}`.

### `get <PROJECT> <TITLE> [--format text|html|raw]`

Reads a note. AppleScript fetches `body of note` (HTML). Then:

- `text` (default): strip inline base64 → `[image:N]` placeholders, convert block tags to newlines, decode HTML entities, normalize whitespace.
- `html`: keep HTML structure, strip base64 only (replace with placeholders).
- `raw`: full HTML body including base64 (use sparingly; large).

Errors: `ERR:note not found: <title>` if no matching note name.

### `images <PROJECT> <TITLE> [--out DIR]`

Extracts inline base64 images from the note body to a project+title slug subdirectory of `DIR` (default `/tmp/apple-notes-images`). Slug is lowercased alphanumeric+hyphen, max 60 chars.

- Output: JSON array `[{index, path, bytes, mime}]`.
- Files are named `image-NN-<sha256_prefix>.<ext>`. Extensions resolved from MIME (jpg/png/gif/webp/heic/heif/tiff/svg/bmp).
- **AppleScript limitation**: only inline-base64 images are extracted. Attached files (PDFs, audio, non-inlined images) have no accessible file path via AppleScript.

### `search <QUERY> [--project NAME] [--json] [--preview N]`

Full-text search across the company folder (or one project with `--project`). Uses AppleScript `whose name contains q or plaintext contains q`.

- **Default output**: `YYYY-MM-DD  <project-15>  <title-40>  <preview>`, sorted by date descending.
- **`--json`**: array of `{project, title, modified, preview}`.

### `create <PROJECT> <TITLE> [--body-file FILE]`

Creates a new note. Body is read from `--body-file` or stdin.

- If the body contains no `<` character, it's treated as plain text: each line wrapped in `<div>…</div>`, empty lines become `<div><br></div>`, characters HTML-escaped.
- If it contains HTML markup, it's passed through verbatim.
- The note title is also prefixed as `<div>TITLE</div>` to match Apple Notes' convention (the first line becomes the displayed title).

### `update <PROJECT> <TITLE> [--body-file FILE]`

**Full replacement** of the body. Same body-handling as `create`. To append safely, use `append`.

### `append <PROJECT> <TITLE> [--body-file FILE]`

Reads existing body, concatenates new HTML/text. Use for "mark as done", "add fix-commit reference", etc.

### `delete <PROJECT> <TITLE> --force`

Without `--force`, prints a confirmation message and exits 1. With `--force`, AppleScript `delete` — Apple Notes moves the note to **Recently Deleted** (30-day recovery window). Genuinely permanent deletion requires manual emptying of Recently Deleted.

### `move <FROM_PROJECT> <TITLE> <TO_PROJECT>`

Moves a note between subfolders of the company folder. Must be within the same account.

### `config show | set <key> <value> | set-mapping <repo-key> <project>`

- `show`: prints config + mapping JSON.
- `set`: rewrites a key in `config.json`. Recognized keys: `account`, `company_folder`, `default_image_dir`.
- `set-mapping`: lowercases+alphanumerics the repo-key, then maps it to the given project name. Use to break ties or override a wrong fuzzy match.

## Exit codes

- `0` — success.
- `1` — handled error (missing arg, note not found, ambiguous resolve, AppleScript error). Message on stderr.
- non-zero from AppleScript — surfaced as `ERR:<msg>` then re-raised as exit 1.

## File layout

```
~/.config/claude/apple-notes/
├── config.json     # account, company_folder, default_image_dir
└── mapping.json    # repo-key → project-name overrides + cache

~/.cache/claude/apple-notes/    # reserved; currently unused

/tmp/apple-notes-images/<slug>/ # default image extraction target
```

## AppleScript caveats

- **`whose` filtering** is database-level (fast) but case-sensitive on titles. Use exact title from `notes` output.
- **`plaintext` vs `body`**: `plaintext` strips all HTML server-side (faster, smaller). `body` returns raw HTML with inline images. The skill uses `plaintext` for list/search previews, `body` for `get` and `images`.
- **Epoch math**: AppleScript dates are subtracted from `date "Thursday, 1 January 1970 at 00:00:00"` to yield UTC seconds. Locale-independent.
- **Argv passing**: every AppleScript runs as a heredoc with `on run argv`; args go via `osascript - "$@" <<APPLESCRIPT`. No string escaping needed.

## Adding a project

Apple Notes UI: create a new subfolder under the company folder. The skill picks it up automatically (no config change needed). On first `resolve` for a new repo, it caches the match.

## Removing the cache

```bash
rm ~/.config/claude/apple-notes/mapping.json
```

Re-resolves on next `resolve` call.
