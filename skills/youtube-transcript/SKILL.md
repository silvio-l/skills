---
name: youtube-transcript
description: Fetch a YouTube video transcript, metadata, and comments reliably via yt-dlp, auto-handling the auto-caption VTT duplicate-line problem. Use for 'YouTube-Transkript holen', get YouTube transcript, transcribe YouTube video, yt-dlp subtitles/captions.
disable-model-invocation: true
---

# YouTube Transcript

Fetch transcript, metadata, and (optionally) comments for a YouTube video via `yt-dlp`, without ever reading a raw caption file directly — its rolling-caption duplication makes naive reads wrong.

## Prerequisites

`yt-dlp` must be installed (`which yt-dlp`; install via `brew install yt-dlp` if missing). Work in a scratch directory — these commands write several files per video.

## 1. Metadata (always do this first — it's cheap and drives every later decision)

```bash
yt-dlp --dump-json --no-warnings "<URL>" > info.json
```

Read from `info.json`: `title`, `channel`, `upload_date` (YYYYMMDD), `duration`, `view_count`, `comment_count`, `description`, `subtitles` (manual caption languages, empty object if none), `automatic_captions` (auto-caption languages, always populated if captions exist at all).

A harmless `WARNING: ... impersonation ...` line may appear — ignore it, it doesn't affect results.

## 2. Transcript

Prefer manual subtitles over auto-captions — they're higher quality and don't need dedup. Check `info.json`'s `subtitles` field first:

```bash
# Manual subs (only if info.json's `subtitles` is non-empty for your target language)
yt-dlp --write-subs --sub-langs "en" --skip-download --sub-format vtt -o "transcript.%(ext)s" "<URL>"

# Auto-captions (fallback — the common case)
yt-dlp --write-auto-subs --sub-langs "en" --skip-download --sub-format vtt -o "transcript.%(ext)s" "<URL>"
```

If `en` isn't in `automatic_captions`, fall back to `en-orig` or the first available language key from that field. If neither `subtitles` nor `automatic_captions` has any entries, the video has no captions at all — report that instead of retrying.

**Never read the resulting `.vtt` file directly.** YouTube's auto-caption VTTs repeat every line twice (a rolling preview, then the finalized block) and carry inline word-timing tags like `<00:00:00.320><c>word</c>`. Always clean it first:

```bash
python3 <skill_dir>/scripts/clean_vtt.py transcript.en.vtt > transcript.txt
```

This strips the tags, drops lines already emitted by a recent cue (windowed, not just "equals the immediately preceding line" — a cue can carry over more than one prior line unchanged), and joins the rest into plain running text. The script has no dependencies beyond the Python standard library and exits with a clear error message for missing/empty/malformed files instead of crashing.

Add `--timestamps` to get `[mm:ss] text` per surviving line instead of a flat paragraph — needed whenever the task requires locating a specific moment in the video (e.g. finding a moment to build a graphic for), not just reading the gist:

```bash
python3 <skill_dir>/scripts/clean_vtt.py transcript.en.vtt --timestamps > transcript_timed.txt
```

## 3. Comments (only fetch if the task actually needs them — costs more time/requests on high-comment videos)

```bash
yt-dlp --write-comments --skip-download --no-warnings -o "comments.%(ext)s" "<URL>"
```

Writes `comments.info.json` with a `comments` array (`text`, `author`, `like_count`, `parent`, ...). Sort by `like_count` descending to surface the most relevant comments first, e.g.:

```bash
python3 -c "
import json
d = json.load(open('comments.info.json'))
for c in sorted(d.get('comments') or [], key=lambda c: c.get('like_count') or 0, reverse=True)[:15]:
    print(c.get('like_count'), c.get('author'), '-', c.get('text')[:200].replace(chr(10),' '))
"
```

## Known pitfalls

- `--skip-download` doesn't always suppress a tiny format download for metadata/comment extraction — that's expected and not a real video download.
- If the URL is one video inside a playlist but you only want that video, add `--no-playlist`.
- Map common failures to a clear message instead of surfacing a raw traceback: private/deleted video, region lock, and "no captions available" are the frequent cases — check `yt-dlp`'s exit code and stderr for these before treating a failure as unexpected.
- If a target language yields no results, list what actually exists in `info.json`'s `automatic_captions`/`subtitles` keys instead of guessing further language codes.
