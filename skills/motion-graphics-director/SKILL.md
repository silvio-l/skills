---
name: motion-graphics-director
description: Turn a YouTube video's timestamped transcript into on-brand animated motion-graphics Artifacts for its best moments, backed by real researched data. Use for 'Motion Graphics erstellen', animated graphics from video/footage, avoid AI slop graphics.
disable-model-invocation: true
---

# Motion Graphics Director

Finds the moments in a YouTube video worth turning into an animated graphic — a stat, a comparison, a sharp claim — researches the real numbers behind each one, and builds a consistent, on-brand animated Artifact for it. The point isn't "animate everything Claude says"; it's the small number of moments where an animation actually adds something, rendered so they look like one coherent visual system across a whole video (and across every video for the same project) instead of each looking like a fresh, generic AI graphic.

**Scope (v1):** YouTube videos only (input), Artifacts only (output — no browser-driven Claude Design, no video compositing back into the source footage). See "Deliberately out of scope" at the end for why, and what to do if you need either.

## Workflow

### 1. Get the timestamped transcript

Use the `youtube-transcript` skill on the target URL, with its `--timestamps` mode:

```bash
python3 <youtube-transcript skill dir>/scripts/clean_vtt.py transcript.en.vtt --timestamps > transcript_timed.txt
```

This gives `[mm:ss] text` lines — the timestamp is what lets you point back at *when* a moment happens, which you'll need in step 3 and in the final report.

### 2. Load or build the project's design system

Before generating anything, check whether this project already has a `MOTION-DESIGN.md` file (repo root, or wherever the project keeps its domain docs). If it exists, read it and skip straight to step 3 — the whole point of this file is that you build it **once per project** and every video after that reuses it, so graphics from different videos still look like the same system.

If it doesn't exist yet, build it now, interview-style — ask the user rather than guessing:

- **Typography.** If the project has a brand/marketing site, fetch it (`WebFetch`) and look for actual font names — `@font-face`, Google Fonts `<link>` tags, a CSS custom property named `--font-*`. Use what the site actually ships, don't guess from vibes. If there's no site yet, ask the user for a direction and point them at [Fonts In Use](https://fontsinuse.com), [Fontshare](https://www.fontshare.com), and [Google Fonts](https://fonts.google.com) for options. Either way, **never fall back to Inter or another unreflected AI-default font** — that's the single biggest tell that a graphic is generic AI output rather than something designed on purpose.
- **Color palette.** Don't invent a palette here — load the `dataviz` skill (`Skill` tool, `skill: dataviz`) and follow its color formula and validator. That skill already solves accessible categorical/sequential palettes with light/dark handling; this skill only needs to point at it and record the chosen values.
- **Icon pack / Lottie assets (optional).** If the project has a preferred icon set or a LottieFiles account/asset library, record it here. Keep this section light — don't build a new asset pipeline if the project has no existing convention.

Save the result as `MOTION-DESIGN.md` using `references/design-system-template.md` as the shape. Every graphic this skill generates afterwards pulls its fonts/colors from this file, not from whatever the model would pick by default.

### 3. Identify the moments worth animating

Read `transcript_timed.txt` and select moments editorially — the source technique this skill is based on treats this as a curation step, not "animate every sentence." Look for:

- A statistic or number spoken out loud
- A comparison ("X vs Y", "before/after", "5 levels of...")
- A list or sequence the speaker is walking through
- A claim strong enough that seeing it reinforced would land harder than just hearing it

For each one, note its timestamp and the exact spoken line. Skip filler, asides, and moments that are already visual (the speaker sharing their screen, for instance) — those don't need a second, redundant graphic.

Present the candidate list to the user before moving on if this is the first pass on a new video — it's cheap to redirect here and expensive to redo four finished Artifacts because the wrong moments got picked.

### 4. Research real data for each moment — never fabricate

For every selected moment, verify the actual number or fact behind what's spoken, using `WebSearch`/`WebFetch`. The speaker rarely states a source out loud, so the number needs external grounding before it goes in a graphic.

This is a hard rule, not a preference: **if a moment's claim can't be backed by a real, checkable source, do not put a fabricated or estimated number in the graphic.** Either drop that moment, or build the graphic around the claim itself (the words, not an invented statistic) and label it as illustrative rather than data-backed. A wrong number in a confident-looking animated chart is worse than no chart.

### 5. Build one graphic per moment

Fable is this skill's default UI model for the creative build: dispatch the actual
design and build of each graphic through the `Agent` tool with `model: "fable"` set
explicitly. Write a self-contained brief per moment, since the subagent has not seen
this conversation:

- The spoken line and timestamp.
- The verified data from step 4.
- The full `MOTION-DESIGN.md` contract (step 2), so it doesn't invent type or color
  choices — that consistency is what makes a set of graphics read as one system instead
  of N independent AI outputs.
- An instruction to load `artifact-design` first (`Skill` tool, `skill: artifact-design`)
  — required for any Artifact, not specific to this skill — then, depending on what the
  moment needs, `dataviz` for a data comparison/ranking/trend, `artifact-diagramming`
  for a process/sequence/relationship, or nothing further for a pure statement/quote
  treatment.
- The anti-slop checklist below, verbatim, with instructions to self-critique the
  graphic against it before returning — catching these inline is far cheaper than a
  rework round-trip after the fact.
- An instruction to save the result as a local HTML file rather than publish it —
  verification (step 6) happens before publishing, on the orchestrating session, not
  inside the subagent call.

**Anti-slop checklist** — concrete tells of generated-rather-than-designed output
(beyond the "never fall back to Inter" rule in step 2 — this is the same quality gate):

- **Decorative grid-line backgrounds** — a hairline hatch behind ordinary content, not earning its keep as an actual chart/measurement surface.
- **Purple gradient on a light/cream background** as the reflexive "modern AI" default.
- **Numbered markers (01 / 02 / 03)** used as decoration where the content isn't actually an ordered sequence.
- **One accent color used everywhere** instead of a deliberate dominant + sharp-accent pairing.
- **Uniform, scattered micro-animation on every element** instead of one orchestrated moment (the number counting up, the bar growing, the comparison resolving) plus restraint everywhere else — this is the single most common tell in animated graphics specifically, more so than in static design.
- **Decorative strokes/borders by default** — an outline plus a fill on the same shape, a divider that isn't separating anything that needs separating.
- **Hierarchy drift** — a label, badge, or secondary number sized or timed so it competes with the actual stat/claim for attention.

The orchestrating session still checks the same list independently in step 6 — the
brief instruction reduces round-trips, it doesn't replace the check. If a graphic trips
one of these anyway, send it back to the same subagent with the specific defect named
rather than patching it inline yourself.

### 6. Verify before publishing

Don't approve a graphic from having written it — actually render it and watch it. Open the local HTML file with the `claude-in-chrome` tools (announce the automation first, per this environment's automation-announcement rule) and watch the animation play through, not just the first frame. Check `prefers-reduced-motion` is respected (toggle it in Chrome's rendering emulation, or check the CSS handles it). Once it looks right, publish it with the `Artifact` tool, using a title/description that ties it back to the source moment — a graphic that looks right in the markup but reads as generic or breaks on replay isn't done, and doesn't get published as-is.

### 7. Report

Once every selected moment has a graphic, give the user a short table: timestamp → the spoken line → the Artifact link (and local file path, if you also saved a standalone copy). This is the thing the user actually asked for — the individual research and generation steps above are how you get there, not the deliverable itself.

## Boundaries with other skills in this repo (don't duplicate these)

- **`marketing-video-automation`** automates *driving and recording an app* (Maestro/Playwright/AppleScript) for demo videos — a completely different mechanism from generating standalone animated graphics. The only thing worth borrowing from it is `post-production.md`'s `ffmpeg` export conventions, and only if you're doing the video-compositing extension described below.
- **`dataviz`** owns chart/color methodology — load it, don't reimplement palette logic here.
- **`artifact-design`** / **`artifact-diagramming`** own Artifact fundamentals and diagram mechanics — load them, don't re-derive.
- **`frontend-design`** / **`impeccable`** are for app and product UI, not marketing/content motion graphics — not applicable here even though both are about visual quality.

## Deliberately out of scope (v1)

- **Local/non-YouTube footage as input.** The source technique this skill is based on has Claude "watch" arbitrary footage directly; this environment has no verified way to transcribe a local video file with word-level timing the way `youtube-transcript` does for YouTube. Extending to local footage means building and testing that transcription step first — don't improvise it inline the first time this comes up.
- **Compositing the generated graphic back into the source video.** v1 produces standalone graphic Artifacts, matching what the source technique actually saves ("save them on my desktop") rather than a finished edited video. If a future task needs the graphic burned into the footage as an overlay, that's an `ffmpeg` compositing step — reuse `marketing-video-automation/post-production.md`'s export conventions rather than inventing a new one here.
