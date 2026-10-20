# Phase A: Context discovery (before the first question)

Goal: know the product, or the topic, well enough that the interview asks only what the material
cannot answer, and that every claim in the later video can be traced to evidence. Output: a
compact, reusable `context.md` (format at the end of this file).

Report honestly what you covered. "I inventoried 3,003 files, read 41, skipped `node_modules/`
and 12 generated files" is a result. "I analyzed the entire repository" is not, unless it is true.

## A1. Decide the mode

| Situation | Mode |
|---|---|
| The working directory (or a path the user named) is the repository of the product the video is about | **Repository mode**: A2–A7 |
| The working directory is a repository, but not of that product (a tools or notes repo, another project) | **Briefing mode**: A8; say why you are not inventorying it |
| No repository, but the user supplied a briefing, URL, documents, transcripts, or examples | **Briefing mode**: A8 |
| Both | Repository mode, then fold the briefing in as an additional source (and note conflicts) |

If the user supplied transcripts, example videos, reference files, or URLs, read them in both
modes. If a source cannot be opened (paywalled, video without a transcript, binary you cannot
inspect), record it as an access gap. Do not describe what it "probably" contains.

## A2. Inventory the whole repository (mechanical, complete)

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/inventory_repo.py" <repo-root> --json <plan-dir>/inventory.json
```

The script lists every file (`git ls-files -co --exclude-standard` in a git repo, otherwise a
filesystem walk), skips dependency, build, and cache directories with stated reasons, and
classifies the rest: code, docs, tests, UI strings, design tokens, marketing, media (with pixel
sizes), generated files, lockfiles, and binaries. It also extracts frequent colors and fonts. It
reads no contents into your context; the Markdown report is a reading map. Classification is
heuristic, so treat every entry as a lead to verify.

If `${CLAUDE_SKILL_DIR}` is not set in your harness, use the directory this `SKILL.md` lives in.

## A3. Read systematically (depth where the video needs it)

Work through these source types in order. Read the files the inventory points to, then follow
references from them. Stop widening a source type once new files only repeat what you know.

1. **Self-description**: README, `CLAUDE.md` / `AGENTS.md` / `CONTEXT.md`, product or feature docs,
   CHANGELOG (what shipped and when), ROADMAP (what has *not* shipped).
2. **Marketing and store copy**: website pages, landing copy, store listings (`fastlane/metadata`,
   store directories), press kits. These hold the existing positioning and the claims the brand
   already makes publicly.
3. **UI strings**: localization files (`*.arb`, `locales/*.json`, `*.strings`, …). These are the
   product's real vocabulary and the most honest feature list. Note the shipped languages.
4. **Implementation**: entry points, feature modules, settings or flags, pricing or plan gates.
   Read enough to confirm or refute each headline claim (A4).
5. **Tests**: tests that cover the claimed features. A tested behavior is stronger evidence than a
   doc sentence.
6. **Design system and brand**: token files, theme code, `frame.md` / `DESIGN.md`, logo files
   (prefer SVG), fonts present in the repo (check the font license if the files are bundled),
   app icons, mascots, and existing illustration style.
7. **Media**: screenshots, demo videos, audio, Lottie, 3D. List what is usable as-is and at what
   resolution.
8. **Production capabilities**: does the target machine have Node.js, `npx hyperframes`,
   `ffmpeg`/`ffprobe`, the HyperFrames skills (`/hyperframes` in the skill list)? Is there a
   website the product-launch workflow could capture? Check, don't assume, and install nothing:
   use `command -v node ffmpeg ffprobe`, `node --version`, and `npx --no-install hyperframes --version`
   (a bare `npx hyperframes` downloads the package). A missing CLI is not a blocker for planning;
   the production prompt's step 0 sets it up. Do this check in briefing mode too.

Skip contents of generated files, lockfiles, vendored dependencies, and binaries. Count and list
them as excluded, with the reason.

## A4. Verify claims against the implementation

For each candidate message the video might make ("works offline", "3× faster", "no account
needed", "supports 7 languages"), classify it:

| Status | Meaning | Allowed in the video? |
|---|---|---|
| **Verified** | Code (and ideally a test) shows it, and you read that code | Yes, with the evidence path in the prompt |
| **Located only** | A search hit (`grep`) points to it, but you did not read the code | Not yet; read it first |
| **Unreleased** | Merged but not in a release yet (for example a CHANGELOG "Unreleased" section) | Only if the user confirms it ships before the video is published (that costs a question); otherwise treat it as roadmap |
| **Documented only** | Docs or marketing say it, code not checked or not found | Only after you check it, or reworded to what is verified |
| **Roadmap** | Planned, flagged off, or in a branch | Never as a current feature |
| **Contradicted** | Code shows otherwise | Never; tell the user |
| **External claim** | Market facts, statistics, competitor claims | Only with a cited, checkable source; otherwise drop it |

Numbers (speed-ups, user counts, ratings, prices) need a source the production agent can see.
If there is none, the claim does not go into the video. Never invent a plausible figure,
testimonial, vote result, or rating.

## A5. Separate current state, roadmap, and assumptions

Keep three lists, each item with an evidence path or "assumption". Product facts come only from
the first list.

## A6. Coverage and gaps

Record: total files inventoried, files actually read (list the important ones), excluded areas
with reasons, sources you could not open (and why), and open questions the interview must
resolve. Never claim completeness you did not achieve.

## A7. Write `context.md`

Location: create a plan directory and tell the user its path.
- In a repository: `docs/video-plans/<YYYY-MM-DD>-<slug>/` if `docs/` exists, otherwise
  `video-plans/<YYYY-MM-DD>-<slug>/` at the repo root. Follow the project's own rules if they
  name another place.
- Without a repository: `video-plans/<YYYY-MM-DD>-<slug>/` in the current working directory.

Do not commit these files unless the user or the project's rules say so.

## A8. Briefing mode (no repository)

Extract the same fields from the briefing and supplied material. Mark everything you could not
verify as "stated by user" (acceptable as a product fact, attributed) or "assumption" (must be
confirmed or kept out of claims). If the user gave a URL, fetch the page and record what it
actually says. Ask in phase B for brand assets you could not find: a logo file, colors, fonts.

## `context.md` format

Keep it to what a planner needs, ideally under ~150 lines. Write it in the conversation language.

```markdown
# Video context: <product or topic> (<date>)

## Sources and coverage
- Mode: repository | briefing | both
- Inventory: <n> files; read <m> (key: `path`, `path`, …); excluded: `node_modules/` (deps), …
- External sources: <url or file> — read | not accessible (<reason>)
- Gaps: <what could not be checked>

## Product in one paragraph
<what it is, for whom, the core benefit, in the product's own vocabulary>

## Verified facts (usable in the video)
- <fact> — evidence: `path:line` or test `path`
## Documented but unverified
- <claim> — source: `path`; status: needs check | reworded to <…>
## Roadmap / not shipped (never claim)
- <item> — `path`
## Assumptions
- <assumption> — why assumed

## Audiences and use cases
- <segment>: <situation they recognize>, <pain>, <what changes with the product>
## Differentiation and limits
- Differs by: <…> (evidence)
- Limits and honest caveats: <…>

## Brand sources
- Logo: `path` (SVG? light/dark variants?)
- Colors: `#hex` role — source `path`
- Fonts: <family> — source `path`; available as files? license?
- Voice and tone: <from copy, with an example line>
- Recurring element candidates: <mascot, icon motif, sound, shape> — source
## Usable assets
| Path | Kind | Size | Usable for |
## Production environment
- HyperFrames CLI: <version | not found>; skills installed: <yes/no>; ffmpeg: <yes/no>
- Website for capture: <url | none>
## Open questions for the interview
1. <question the material cannot answer>
```
