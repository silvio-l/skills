# Phase D: Production prompt template

Load this after the concept is selected. Also load `hyperframes-facts.md` (for section 8) and
`quality-checklist.md` (for section 9 and the hand-over gate).

The production prompt is a single Markdown file, `<plan-dir>/production-prompt.md`. A fresh
coding-agent session with **no chat history** must be able to execute it end to end. Write it
for a reader who has never seen this conversation, the repository, or the concepts.

## Hard rules

1. **Self-contained.** No "as discussed", "see above", "wie besprochen", or references to the chat
   or to `concepts.md`. Everything the executor needs is in the file, or in a file it names by
   path.
2. **No open creative placeholders.** No `TBD`, `TODO`, `[insert …]`, `<your logo>`, "something
   catchy", or "a fitting sound". Every text is final, every color is a hex value, every font is
   named, every sound is described concretely (character, length, sync point).
3. **Structural labels stay in English**, exactly as in this template: section headings, scene
   field labels, table headers, and asset statuses. That lets `check_prompt.py` verify the file.
   All content (copy, voiceover, descriptions) is in the agreed project language. Quoted
   on-screen and voiceover text is in the video's language.
4. **Timings are marked as planned.** The executor re-times scenes to the real voiceover (word
   timestamps). Planned values are the target, not a contract against the voice.
5. **Every factual claim in the video carries its evidence** (repository path, URL, or "stated by
   the user on <date>"), listed in Appendix B. A claim inferred from a source, not stated in it,
   says so ("derived from #2: …", with the reasoning in one line). If the inference is weak,
   reword the copy to what the source says.
6. **Every asset has a status**: `exists` (path verified now), `user` (the user will supply it,
   not present yet; the executor builds with a marked stand-in and stops before the final
   render until it arrives), `create` (code-drawn by the executor, with an exact spec), `source`
   (fetched from a named free or licensed source, with license capture), or `generate` (paid or
   model generation, only within the budget stated in section 7).
7. **Respect the environment.** Name permission boundaries: what the executor may install (npm
   packages HyperFrames needs: yes; system software, container runtimes, or paid accounts: no,
   unless stated), what it must not touch (the product repository is read-only except the
   output directory), and that it must not publish, deploy, or upload.

Then run the hand-over gate in `quality-checklist.md` §1, including
`scripts/check_prompt.py`, before you show the prompt to the user.

## Template

Replace every `«…»` with final content. Delete optional parts that do not apply (such as a variant
row) rather than leaving them empty. A `«…»` left in the file fails the check.

````markdown
# Production brief: «working title»

> Planned with motion-video-planner on «YYYY-MM-DD». Concept «A/B/C: title», selected by «the
> user | delegated decision». Timings are PLANNED; final timing follows the recorded voiceover.

## 0. Start here

You are the production agent for a fully planned motion-graphics video. Story, copy, look, and
timing are decided. Build them faithfully. Change something only when it is technically impossible
or when a check in section 9 fails, and log every deviation in `PRODUCTION-LOG.md` with the reason.

**Your latitude:** this brief fixes what the viewer must notice: copy, order, timing, colors,
fonts, sizes, positions of focal elements, and sync points. Details it leaves open (z-order where
it is obvious, whether a wobble settles back to rest, which ffmpeg or mixer parameter sets a
level, sub-frame easing details) are yours to decide. Decide them in the spirit of section 4 and
log them; they are not deviations and need no question. If a measured text line does not fit
its lane, reduce that text's size in 2 px steps by at most 15 % and log it; beyond that, keep
the size and break the line at the most natural word boundary, and log that too.

**Working directory:** create the HyperFrames project at `«absolute or repo-relative path, e.g.
video/«slug»»`. **Product repository:** `«path or 'none'»`, read-only except for that project
directory. **Assets** are listed in section 7 with paths relative to `«base path»`.

**Permissions and limits**
- Allowed: run `npx hyperframes …` (including the browser binary it downloads itself); install
  the npm packages and the HyperFrames skills (`npx skills add heygen-com/hyperframes`) that the
  workflow needs; download the font files named in section 4 into the project once; run
  `ffmpeg`/`ffprobe` if present; create files inside the project directory.
- If `doctor` or `render` asks for system software (or suggests Docker), stop and report; do not
  install it.
- Not allowed without asking the user: installing system software or container runtimes,
  `render --docker`, paid generation beyond the budget in section 7, `publish`, uploads, deploys,
  commits outside the project directory, and edits to the product repository.
- Respect the harness's permission prompts; never work around a denial.
- The environment's own rules (`CLAUDE.md`, `AGENTS.md`, user instructions) override this brief's
  tool choices, for example rules about headless screenshots or announcing automation. Follow
  them and log where they changed the method; ask only if a rule makes a required check
  impossible.

**Step 0 — Verify the environment (record the outputs in PRODUCTION-LOG.md)**
1. `node --version` (needs a current LTS); `npx hyperframes --version`; `npx hyperframes doctor`.
2. Check that the HyperFrames skills are available (`/hyperframes` in your skill list). If they are
   missing, run `npx skills add heygen-com/hyperframes` and tell the user a session restart is
   needed. Stop there.
3. `npx hyperframes usage --json`, and note any limits.
4. `npx hyperframes render --help` and `npx hyperframes init --help`: confirm the flag names this
   brief uses (quality tiers, `--format`, `--fps`, `--resolution`). If a name differs, use the
   installed version's equivalent and log it.
5. Confirm every `exists` asset in section 7 is present (`ls`), and probe audio and video with
   `ffprobe` if available.
6. Check Appendix A's frontmatter keys against the installed `hyperframes` skill's brief format
   (`references/brief-format.md`); log any key that differs and use the installed name.
7. Verify every registry block, transition, and media-effect name in this brief:
   `npx hyperframes catalog --query "«name»"` / `npx hyperframes media-treatment --capabilities --json`.
   Replace a missing name with the closest real one and log it; never invent one. A named block
   is a candidate, not a requirement: if it does not fit this format (aspect ratio, direction,
   duration), hand-author the behavior described in section 5 instead. That is authorized.
   `doctor` may report Docker as missing; that is expected and ignored (never install Docker).
If HyperFrames cannot run at all, stop and report. Do not build a substitute render engine.

**Step 1 — Scaffold and brief**
1. `npx hyperframes init «dir» --resolution «landscape|portrait|square»` (add `--skill=«workflow»`
   if your CLI supports it).
2. Immediately write Appendix A verbatim to `«dir»/BRIEF.md`, and Appendix C verbatim to
   `«dir»/frame.md`. Stage the section 7 assets into the project.
3. Invoke `/hyperframes`. It finds `BRIEF.md` and runs the workflow `«workflow»` with no brief
   questions. **This brief is confirmed by the user**: run no intent interview and no pitch round.
   The run is autonomous: post checkpoint summaries and continue.
4. With `storyboard: no` the workflow normally skips its storyboard loop. If it still writes
   `STORYBOARD.md`, carry over section 5 scene by scene (copy verbatim, planned timings, scene
   purposes); otherwise section 5 of this file is the storyboard.

**Step 2 — Build in passes (see section 9 for the gates)**
Story and rough timing first (blocking pass, stills) → audio (voiceover with word timings, music,
SFX) → re-time to the voiceover → full design and motion → transitions → polish → checks → review
→ render.

**Questions to the user:** none, with one exception. "Autonomous" means no intent interview, no
pitch round, and checkpoint summaries that do not wait. Draft renders are pre-approved. The
workflow's own render gate ("render now, or what changes?") is the single question you ask, once,
before the final render, after section 9 passes. Blockers named in this file (for example a
missing `user` asset) are reported at that point, not earlier, unless they stop all work. If a
`user` asset is still missing then, deliver everything else (project, draft render with the
stand-in, logs), ask once for the file, and end the run; the final render follows when it
arrives.

## 1. Goal and context

- **Product / topic:** «one paragraph: what it is, in its own vocabulary»
- **Audience:** «segment, the situation they recognize, prior knowledge»
- **Core message (one sentence):** «…» (evidence: Appendix B #«n»)
- **Intended effect:** «what the viewer should feel, remember, and do; for example "laugh in
  recognition, remember the yellow sticky note, know the app's name"»
- **Goal priority:** «reach → brand recall → conversion | the user's explicit goal»
- **Share trigger:** «…» · **Rewatch trigger:** «…»
- **CTA:** «exact wording and where it appears | none (brand close only)»
- **Limits:** «claims that must not be made; roadmap items to avoid; legal and brand restrictions;
  competitors not to name»

## 2. Story

- **Hook (0–«n» s):** «the exact first frame and first action; the hook mechanism; why the
  situation is clear by about 3 s»
- **Visual thread:** «the recurring element, and how it develops (plant → payoff)»
- **Development:** «escalation beats; what acts, what reacts, what each consequence is»
- **Climax:** «…»
- **Resolution:** «the solution or punchline, and how it pays off the hook»
- **Close:** «the final frame, end state, idle behavior, logo, CTA»
- **Tone:** «humor type, exaggeration level, pace; one sentence on what to avoid»

## 3. Format

- Duration (planned): «n» s (tolerance ±«n» s; final duration follows the voiceover)
- Resolution / aspect: «1080×1920 (9:16)»
- Frame rate: «30» fps «(reason if 60)»
- Delivery: «MP4 H.264 with AAC audio | MOV ProRes 4444 with alpha | WebM VP9 with alpha»
- Variants: «none | list each with resolution and duration and what changes»
- Safe areas: «exact px insets per edge, for example top 270 px, bottom 380 px, sides 64 px for 9:16
  social»
- Sound-off: «must work without sound: yes/no; how»

## 4. Look

- **Brand source of truth:** «path to logo, tokens, frame.md, site; and what is strict»
- **Style:** «dominant style (+ accent and the combination logic)», applied as these rules:
  «5–10 concrete rules: shape language, line weights, textures, depth, what is forbidden»
- **Palette:** «role → #hex (source)»; for example ground `#0b122a`, ink `#ffffff`, accent
  `#6fddf0`; «where the accent may appear»
- **Typography:** «family (file path or how it is loaded; license note)» · display «weight,
  size in px at this resolution, line-height, tracking» · body or labels «…» · caption style «…»
- **Layout:** «grid, focal placement, depth layers, density contract»
- **Contrast:** text meets WCAG AA (4.5:1 for body, 3:1 for large display) against its actual
  background in every frame
- **Logo and product depiction:** «exact files; minimum size; clear space; never redrawn or
  distorted; UI only as shipped, with the source path of each screen»
- **Motion character:** «ease vocabulary and durations; overshoot rules; hold behavior (ambient
  idle vs. deliberate still, and where)»
- **Transitions:** «primary transition (name) + accents (name, at which seam), with durations»
- **Negatives:** «concrete list: for example no purple-blue gradients, no stock photos, no
  lens flares, no invented UI, no third hue»

## 5. Timeline

All times are PLANNED and are re-timed to the recorded voiceover in the audio pass. Scenes are
contiguous: each starts where the previous ends.

| # | Start | End | Purpose | Voiceover (exact) | On-screen text (exact) |
|---|---|---|---|---|---|
| 1 | 0.0 | «e» | «hook» | «"…" or —» | «"…" or —» |
| 2 | «s» | «e» | «…» | «…» | «…» |

### Scene 1 (0.0–«e» s): «name»
- Composition: «back-to-front layers: element, position (px or % of frame), size, color (hex)»
- Assets: «paths or 'code-drawn: …'»
- Action: «what acts, what reacts, the consequence; in order, with times relative to scene start»
- Camera: «static | move with distance and ease, for example "4 % push-in over the whole scene,
  sine.inOut"»
- Motion/easing: «per element: property, from → to, duration, ease, offset»
- Transition out: «name, duration, what drives it | hard cut on «sound/action»»
- Audio cues: «VO line starts at …; SFX "…" at +«t» s synced to «event»; music change»

### Scene 2 («s»–«e» s): «name»
«…same fields…»

## 6. Audio

- **Voiceover:** «yes/no». Voice: «character, gender if relevant, age range, energy; engine
  preference and fallback, for example "HeyGen if configured, else ElevenLabs if a key exists, else
  local Kokoro; for German check that the chosen engine has a German voice, otherwise stop and ask"»
  Tempo: «words per minute»; pauses: «where, how long»
- **Full voiceover script** (verbatim, in the video language; numbered by scene):
  1. «"…"»
- **Pronunciation:** «term → how to say it (IPA or a respelling)»
- **Music:** «mood, tempo (BPM), instrumentation, structure (intro, build, drop at «t», ending);
  level: «e.g. −18 dB under the voice, ducked about 12 dB when the voice is active»; source:
  «user file path | resolve via /media-use if an account is available | none»»
- **Sound effects:** «list: name, character, length, sync point, source (bundled library or
  Openverse via `/media-use resolve --type sfx`); record the license per file»
- **Sound motif (recurring element):** «exact description; where it occurs»
- **Captions:** «burned-in yes/no; style (font, size, position, max characters per line, at most
  ~17 characters per second); from word timestamps; on-screen text and captions must not collide»
- **Silence:** «if no audio: write "no audio at all"»

## 7. Assets

Base path: `«…»`

| Path | Status | Use | Notes |
|---|---|---|---|
| `«assets/logo.svg»` | exists | «end lockup, scene 6» | «light variant; min width 320 px» |
| `«code: sticky-note»` | create | «recurring element» | «exact spec: 280×280 px, #ffd84d, 2° tilt, …» |
| `«sfx/paper-flap»` | source | «scene 2 hit» | «Openverse or the bundled library; license into SOURCES.md» |
| `«assets/screen-recording.mp4»` | user | «scene 3» | «what the user records, exact spec; stand-in until delivered» |

- **Budget for paid generation:** «€0, use none | up to «amount» for «what»»
- **Fonts:** «exact files and project paths (for example `assets/fonts/Inter-ExtraBold.woff2`), where
  each comes from (repo path, or the download URL for step 0), the license; the fallback and what
  may not be substituted». Fonts are local files in the project; nothing is fetched at render.
- **Creation orders** for each `create` and `generate` asset: «complete, executable specification»

## 8. Technical execution

- **Workflow:** `«/general-video | /motion-graphics | …»`, because «reason»; `flow: automation`,
  `storyboard: no` (autonomous; the internal QA passes in section 9 still apply)
- **Skills to load as needed:** `/hyperframes-core` (composition contract), `/hyperframes-animation`,
  `/hyperframes-keyframes` «if camera moves», `/hyperframes-audio` «if music under voice»,
  `/media-use` «for TTS, SFX, music, or images», `/hyperframes-registry` «for named blocks»,
  `/hyperframes-cli`
- **Animation approach:** GSAP paused timeline registered on `window.__timelines`; «Three.js via
  the adapter for …»; seeded PRNG for any randomness; no live data, no fetch at render
- **Candidate blocks and effects** (optional, verify in step 0; section 5 describes the behavior
  so it can be hand-authored): «`name` for scene n, …»
- **Media integration:** «footage `data-has-audio`; transparent cutouts; Lottie files; captions
  track»
- **Output:** «render command per deliverable, using the verified flag names; file names
  `«slug»-v«n»-«variant».mp4`»

## 9. Quality and delivery

**Order of work and gates**
1. **Story pass (before detail):** block every scene with placeholder shapes in final positions and
   final copy. Run `npx hyperframes snapshot` at each scene midpoint and check:
   the hook reads by about 3 s, each scene has an action and a consequence, the story is clear
   with sound off. Fix the story before styling.
2. **Audio pass:** generate the voiceover and get word timings with `npx hyperframes transcribe
   <file>` (local Whisper, no key); re-time scenes to the spoken cues; place SFX on visual events;
   music under the voice at the stated level.
3. **Detail pass:** full look, motion, transitions.
4. **Technical gates:** `npx hyperframes lint` and `npx hyperframes check` with zero errors.
   Fix warnings that affect text occlusion or contrast.
5. **Frame review:** snapshots of every scene midpoint, every transition midpoint, the first frame,
   and the last frame. Compare them to section 5.
6. **Draft render review:** an agent cannot watch a video, so review it the way you can and say
   so: a frame strip every 0.5 s (`ffmpeg -vf fps=2`), the rendered audio track transcribed and
   compared word by word with section 6, SFX onsets measured (for example `ffmpeg -af
   silencedetect`) against their planned events, and `ffprobe` for streams. Check the items
   below. A human watch-through with sound is listed as "Not verified" unless the user did it.
7. **Final render**, then verify the file (step 8).

**Acceptance criteria (all must pass)**
- The first frame is the hook frame from section 2; the situation is understandable by about 3 s
  without sound.
- Every on-screen text is visible long enough to read (at least about 1 s per 3–4 words), inside
  the safe areas, not occluded, AA contrast.
- The voiceover is complete, matches section 6 verbatim, and is not clipped; the pronunciation
  list is honored.
- SFX land on their visual events within ±2 frames; music does not mask the voice.
- No scene is a static slide: each has the action and consequence described in section 5.
- The recurring element appears as specified (plant → payoff → close).
- Logo, colors, and fonts match section 4 exactly; no invented UI or claims.
- The hook's promise is paid off by the resolution.
- Duration is within tolerance; the resolution, fps, codec, and audio streams match section 3
  (verify with `ffprobe`; for alpha check `ALPHA_MODE=1` or the alphaextract filter).

**Revision priority** when something fails: opening → development → resolution → brand effect.
Fix the highest-priority failure first, then re-check every affected scene and transition.

**Iteration budget and stop criteria**
- At most «3» full review cycles (steps 5–6) and «4» draft renders; one final render (+ one
  re-render if a delivery check fails).
- Change one thing per fix where possible; use absolute targets ("title 140 px"), not relative
  nudges.
- Stop and report instead of looping when the budget is used up, or when the same failure
  survives two fix attempts, or when a fix would need a decision outside this brief (a new claim,
  paid asset, or changed story).

**Deliverables** in `«dir»/`
- `renders/«slug»-final.«ext»` (+ variants)
- the editable HyperFrames project (sources, `BRIEF.md`, `frame.md`, `STORYBOARD.md`, assets)
- `SOURCES.md`: claim evidence (Appendix B), asset licenses, voice engine and voice used
- `PRODUCTION-LOG.md`: environment versions, verified or replaced names, every deviation with its
  reason, the commands run and their results (lint, check, snapshot list, ffprobe output),
  review findings per cycle and what was fixed, and known limitations
- Do not claim a check you did not run. If something could not be verified, list it under
  "Not verified".

## Appendix A: BRIEF.md

```markdown
---
workflow: «general-video»
flow: automation
storyboard: no
message: "«one sentence»"
destination: «e.g. instagram-reels»
aspect: «1080x1920»
language: «de»
audience: "«…»"
length: «30s»
narration: «yes | minimal | no»
---

## Intent

«What the video is, for whom, why now, tone in the user's words. Fully confirmed; build from
production-prompt.md sections 1–9, which this project keeps as the detailed plan.»

## Assets

- «path — what it is, where it belongs»

## Customizations

- «each bespoke technique or capability, with enough detail to act on»

## Notes

- Confirmed brief; do not re-interview. The detailed plan is in production-prompt.md (copy it into
  the project root).
- «negatives and constraints»
```

## Appendix B: Sources

| # | Claim or fact used in the video | Evidence |
|---|---|---|
| 1 | «…» | «`path:line` / URL (accessed date) / stated by user on date» |

## Appendix C: frame.md

```markdown
---
name: «Brand» — video frame spec
description: «one line on the look»
colors:
  «role»: "«#hex»"
typography:
  display: { fontFamily: "«family»", px: «n», weight: «n», lineHeight: «n», tracking: "«em»" }
  body: { fontFamily: "«family»", px: «n», weight: «n», lineHeight: «n» }
  label: { fontFamily: "«family»", px: «n», weight: «n», tracking: "«em»", upper: «true|false» }
---

## Overview
«the style in two sentences; the brand's strict rules»

## Do's and Don'ts
- Do: «…»
- Don't: «…»
```
````

## Notes on filling the template

- **Spec density:** give the full visual spec (positions, sizes, hex, timings, eases, layer order)
  for the hook, the climax, and the close. Style tokens are enough for connective scenes.
- **Copy:** quote every on-screen word exactly. Unquoted text gets paraphrased. Mark forced line
  breaks with ` / ` and say once, in section 4, that ` / ` is a line break and never shown.
- **Every element is fully specified where it first appears:** size, weight, and color for every
  text, color for every shape and marker. "Same as the title" is fine when the title is
  specified.
- **Sequencing:** never schedule two focal events at the same instant. Write "fully out by 4.2 s;
  at 4.2 s …".
- **Counters:** state the target value only.
- **Holds:** specify the ambient idle or deliberate stillness everywhere something rests.
- **Tail:** if the duration exceeds the beats, say what fills the remainder.
- **Workflow choice:** see `hyperframes-facts.md` §2. A multi-scene or narrated concept runs in
  `/general-video`. A single motion idea without narration (logo sting, kinetic title, stat
  hit), usually under 10 s and at most about 30 s, runs in `/motion-graphics`. If a short
  unnarrated piece has several story scenes (a quiz with question, pause, and reveal), prefer
  `/general-video`.
- **Several languages:** write one production prompt per language version. The checker validates
  one timeline, and voiceover timing differs per language anyway. Shared assets can be referenced
  by the same paths.
- **Provisional brand:** if no brand exists (no logo, colors, or fonts), the planner proposes a
  look and marks it `PROVISIONAL (proposed by the planner, not a brand rule)` in section 4 and
  Appendix C. A proposed look is a design decision, not a fact, so it needs no evidence, but it
  must never be presented as the existing brand.
- **Language of the prompt body:** the conversation language by default (structural labels stay
  English). If the user prefers, write the body in English and keep the quoted copy in the video
  language.
- **Copy the plan into the project:** the prompt tells the executor to keep `production-prompt.md`
  in the project root, because `BRIEF.md` refers to it.
