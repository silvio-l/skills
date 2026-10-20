# Production brief: Küchenchemie – Nudelwasser-Quiz

> Planned with motion-video-planner on 2026-10-20. Concept A: "Ist das wirklich schneller?", selected by the user (SIMULATED answer, see decisions.md). Timings are PLANNED. There is no voiceover; the timeline follows the on-screen text and SFX cues.

## 0. Start here

You are the production agent for a fully planned short motion-graphics video. Story, copy, look, and timing are decided. Build them faithfully. Change something only when it is technically impossible or when a check in section 9 fails, and log every deviation in `PRODUCTION-LOG.md` with the reason.

**Working directory:** create the HyperFrames project at `video/kuechenchemie-nudelwasser`, relative to the directory in which you start. **Product repository:** none. **Assets** are listed in section 7 with paths relative to `video/kuechenchemie-nudelwasser/`.

**Permissions and limits**
- Allowed: run `npx hyperframes …`; install the npm packages that HyperFrames and its skills need; run `ffmpeg`/`ffprobe` (present on the machine); create files inside the project directory.
- Not allowed without asking the user: installing system software or container runtimes, `render --docker`, any paid generation or paid service (the budget is zero, see section 7), `publish`, uploads, deploys, commits outside the project directory.
- Respect the harness's permission prompts; never work around a denial.

**Step 0 — Verify the environment (record the outputs in PRODUCTION-LOG.md)**
1. `node --version` (needs a current LTS); `npx hyperframes --version`; `npx hyperframes doctor`.
2. Check that the HyperFrames skills are available (`/hyperframes` in your skill list). If they are missing, run `npx skills add heygen-com/hyperframes` and tell the user a session restart is needed. Stop there.
3. `npx hyperframes usage --json`, and note any limits.
4. `npx hyperframes render --help` and `npx hyperframes init --help`: confirm the flag names this brief uses (`--resolution`, `--fps`, quality tier, `--format`). If a name differs, use the installed version's equivalent and log it.
5. Confirm the asset `assets/kuechenchemie-logo.png` in section 7 is present (`ls`). The logo is the user's own file and must be placed by the user before you start. If it is missing, stop and report. Do not draw a substitute.
6. Verify every registry block, transition, and media-effect name in this brief with `npx hyperframes catalog --query "<name>"` and `npx hyperframes media-treatment --capabilities --json`. This brief names one transition (`transitions-push`); no registry block is named. Log the result.

If HyperFrames cannot run at all, stop and report. Do not build a substitute render engine.

**Step 1 — Scaffold and brief**
1. `npx hyperframes init video/kuechenchemie-nudelwasser --resolution portrait` (add `--skill=general-video` if your CLI supports it).
2. Immediately write Appendix A verbatim to `video/kuechenchemie-nudelwasser/BRIEF.md`, and Appendix C verbatim to `video/kuechenchemie-nudelwasser/frame.md`. Copy this file to `video/kuechenchemie-nudelwasser/production-prompt.md`. Stage the section 7 assets into the project.
3. Invoke `/hyperframes`. It finds `BRIEF.md` and runs the workflow `general-video` with no brief questions. **This brief is confirmed by the user**: run no intent interview and no pitch round. The run is autonomous: post checkpoint summaries and continue.
4. Storyboard: none. Work directly from section 5.

**Step 2 — Build in passes (see section 9 for the gates)**
Blocking pass (stills of the whole timeline) → detail pass (look, code-drawn shapes, motion) → sound pass (SFX on their events) → technical gates → frame review → draft render → final render.

**Render approval:** the user approves in advance draft renders for internal review and the final delivery render once every acceptance criterion in section 9 passes. If your workflow still asks "render now, or what changes?", show the preview and ask exactly that once.

## 1. Goal and context

- **Product / topic:** the Instagram account "Küchenchemie", which explains cooking science in German. This video is a quiz about whether salt in pasta water makes the water boil or cook faster.
- **Audience:** German-speaking followers of a cooking-science account (about 4,000 followers); home cooks who salt the water early. Prior knowledge: basic kitchen experience; no physics needed.
- **Core message (one sentence):** Salt raises the boiling point of water only by a fraction of a degree, so it does not make pasta water noticeably faster. (Evidence: Appendix B #1 and #2.)
- **Intended effect:** the viewer answers the quiz in their head, is surprised by how small the effect is, and remembers the thermometer; they recognize their own habit of salting the pot early.
- **Goal priority:** reach → brand recall → conversion (none).
- **Share trigger:** "simple solution": a short, checkable fact forwarded to the friend who salts early. **Rewatch trigger:** the 0,5 °C step on the thermometer is easy to miss on the first watch.
- **CTA:** none. Soft brand close only: the logo lockup with the account name (scene 6).
- **Limits:** no claim beyond Appendix B; no pasta-water concentration figure; no cooking-time figure; no statement that salting is wrong (salt is for flavor); do not name any other account or brand.

## 2. Story

- **Hook (0–3 s):** the first frame is the question on a dark green field: "Salz ins Nudelwasser:" / "Kocht es schneller?". A code-drawn pot in the lower half rattles once. The situation is clear without sound because the question is the full text of the frame.
- **Visual thread:** the thermometer (a vertical scale at the left edge, code-drawn) is planted in scene 1, climbs in scene 3, reveals in scene 4, and returns in scene 6 as the close's background line.
- **Development:** two answer tiles appear, and the viewer gets a quiz pause (no countdown). The tiles lean toward the thermometer as it climbs to 100 °C, with a short deliberate stillness at 100 °C.
- **Climax:** the reveal at 14 s: "Nein." and the zoomed step from 100,0 °C to 100,5 °C on the scale.
- **Resolution:** the explanation with the source number: the salt raises the boiling point by 0,5 °C at 29,2 g per kg water. The hook's question is answered by this number.
- **Close:** the logo lockup (1080×1080 PNG scaled to 640×640 px, centered at y 1150 px) on the dark green field; ambient idle (breathing scale 1–2 %); the three-note motif plays once.
- **Tone:** dry, mildly playful, factual. Avoid mocking the viewer for salting early.

## 3. Format

- Duration (planned): 25 s (tolerance ±1 s; there is no voiceover, so the planned timing is the target)
- Resolution / aspect: 1080×1920 (9:16)
- Frame rate: 30 fps
- Delivery: MP4 H.264 with an AAC stereo SFX track
- Variants: none
- Safe areas: top 270 px, bottom 380 px, sides 64 px. Text and the thermometer stay inside these insets.
- Sound-off: must work without sound: yes. The on-screen text carries the whole quiz; SFX are supporting only.

## 4. Look

- **Brand source of truth:** the two brand colors given by the user (palette below) and the user's logo file `assets/kuechenchemie-logo.png`. Logo, colors, and proportions are strict. No redrawing of the logo.
- **Style:** Swiss / Editorial (dominant), with a Kinetic Typography accent on the reveal word only. Applied as these rules:
  1. Flat color fields only; no gradients, no glow, no shadows.
  2. One accent color: #E8B931. It appears on the answer tiles, the thermometer marker, and the reveal word.
  3. Structure by hairlines of 3 px (at 1080 px width) and one vertical scale; no decorative grid.
  4. Display type is left-aligned, flush-left, ragged-right, on the 64 px side inset.
  5. Motion is confident: entrances `power3.out` at 0.35–0.5 s; the reveal word uses `expo.out` at 0.25 s.
  6. No bounce on text; the pot's rattle is the only overshoot (`back.out(1.4)`, 0.2 s).
  7. Stillness is deliberate: the 100 °C hold (0.5 s) and the stop of the marker in scene 5 (0.8 s).
- **Palette:**
  - ground: `#1F3D2B` (Dunkelgrün, brand, user-supplied)
  - accent: `#E8B931` (Senfgelb, brand, user-supplied)
  - ink on ground: `#FFFFFF`
  - ink on accent: `#1F3D2B`
  - The accent may appear on tiles, the thermometer marker, the reveal word, and the logo's own colors only.
- **Typography:** family Inter (Google Fonts, SIL Open Font License; license captured in SOURCES.md).
  - display: weight 800, 120 px, line-height 1.0, tracking -0.02 em
  - answer tiles: weight 700, 72 px, line-height 1.1
  - explanation: weight 500, 52 px, line-height 1.25
  - labels: weight 600, 40 px, tracking 0.04 em
- **Layout:** 9:16; text zone in the upper part of the safe area; pot and thermometer in the central band (y 760–1400 px); logo lockup centered at y 1150 px. Density contract: one focal element per frame (the question, the tiles, the scale, or the logo), at least two supporting elements, and the persistent thermometer line at x 96 px.
- **Contrast:** text meets WCAG AA. Ink #FFFFFF on #1F3D2B and #1F3D2B on #E8B931 both exceed 4.5:1. Check each frame with `npx hyperframes check`.
- **Logo and product depiction:** `assets/kuechenchemie-logo.png` (square, 1080×1080 raster). Minimum width 320 px. Clear space 60 px on all sides. Never redrawn, distorted, or recolored. No product and no UI are depicted.
- **Motion character:** entrances ease out, exits ease in; overlap offsets of 0.06–0.1 s between tiles; ambient idle of 1–2 % breathing scale on the logo lockup at the close.
- **Transitions:** primary: hard cuts on the action (rattle at 0.0 s, reveal at 14.0 s). Accent: one `transitions-push` (vertical, 0.3 s) at 14.0 s between scene 3 and scene 4, carrying the tiles off the top. Name verified by `npx hyperframes catalog` before use.
- **Negatives:** no purple-blue gradients, no stock photos, no lens flares, no invented UI, no third hue, no countdown timer, no fake poll percentages, no captions that duplicate the on-screen text, no text inside the top 270 px or bottom 380 px.

## 5. Timeline

All times are PLANNED. There is no voiceover; scene times follow the on-screen text and SFX cues. Scenes are contiguous: each starts where the previous ends.

| # | Start | End | Purpose | Voiceover (exact) | On-screen text (exact) |
|---|---|---|---|---|---|
| 1 | 0.0 | 3.0 | hook | — | "Salz ins Nudelwasser:/Kocht es schneller?" |
| 2 | 3.0 | 8.0 | answer options appear | — | "Ja, schneller" / "Nein, gleich" |
| 3 | 8.0 | 14.0 | thinking time, thermometer climbs | — | "Denk kurz nach." |
| 4 | 14.0 | 19.0 | reveal | — | "Nein. Der Effekt ist winzig." |
| 5 | 19.0 | 23.0 | why, with the source number | — | "Der Siedepunkt steigt nur um 0,5 °C/bei 29,2 g Salz pro kg Wasser" |
| 6 | 23.0 | 25.0 | close, logo lockup | — | "Küchenchemie" |

### Scene 1 (0.0–3.0 s): hook
- Composition: back to front: ground `#1F3D2B` full frame; thermometer line at x 96 px, y 300–1500 px, 4 px wide, `#FFFFFF`; pot (code-drawn SVG, `#E8B931`, body 520×360 px, centered x 540, top y 1080 px); display text at x 64 px, y 420 px, 120 px, `#FFFFFF`, two lines.
- Assets: code-drawn: pot (SVG), thermometer line (SVG).
- Action: at 0.0 s the question's first line slams in (`expo.out`, 0.25 s); at 0.3 s the second line follows; at 0.6 s the pot's lid rattles once (2 px horizontal, 0.2 s, `back.out(1.4)`).
- Camera: static.
- Motion/easing: line 1 from y 460 px to 420 px, opacity 0 → 1, 0.25 s, `expo.out`; line 2 same with a 0.3 s delay; pot lid x offset 0 → 2 px → -2 px → 0 px, 0.2 s total, `back.out(1.4)`.
- Transition out: hard cut at 3.0 s onto the answer tiles.
- Audio cues: SFX "tick" at 0.0 s (on line 1); SFX "tick" at 0.3 s (on line 2). No music.

### Scene 2 (3.0–8.0 s): answer options appear
- Composition: back to front: ground; thermometer line; the question text moves to y 300 px and scales to 80 px (`power3.out`, 0.4 s); two answer tiles, each 880×200 px at x 100 px, at y 760 px and y 1020 px, fill `#E8B931`, text `#1F3D2B` 72 px, weight 700.
- Assets: code-drawn: tiles (SVG rectangles, no radius).
- Action: at 3.0 s the question shrinks to the top; at 3.4 s tile 1 slides in from the left (`power3.out`, 0.4 s); tile 2 follows with a 0.1 s offset; from 4.5 s to 8.0 s the tiles wobble one after the other (x ±6 px, 0.3 s each, `sine.inOut`), never together.
- Camera: static.
- Motion/easing: tile 1 x -900 → 100 px, 0.4 s, `power3.out`; tile 2 x -900 → 100 px, 0.4 s, `power3.out`, delay 0.1 s; wobble per tile 0.3 s `sine.inOut`.
- Transition out: hard cut at 8.0 s onto the thermometer climb.
- Audio cues: SFX "whoosh-short" at 3.4 s (tile 1 enters); SFX "tick" at 3.5 s (tile 2 lands). No music.

### Scene 3 (8.0–14.0 s): thinking time, thermometer climbs
- Composition: back to front: ground; thermometer line; mercury bar (`#E8B931`, 24 px wide, x 96 px) rising from y 1500 px (20 °C) to y 420 px (100 °C) on the scale; tiles at the same position, scaled to 92 % and leaning 2° toward the thermometer; text line "Denk kurz nach." 72 px at y 260 px.
- Assets: code-drawn: mercury bar; tick marks at 20, 40, 60, 80, 100 °C (4 px lines, 40 px labels).
- Action: the mercury bar rises over 4.5 s from 8.5 s; both tiles lean toward it from 8.0 s; at 100 °C (12.5 s) the bar holds for 0.5 s (deliberate stillness). After 13.0 s the bar stays at its top; the tiles hold their lean with an ambient idle of 1 % breathing scale.
- Camera: static.
- Motion/easing: bar y 1500 → 420 px over 4.5 s, `sine.inOut`, from 8.5 s; tile lean rotation 0° → 2°, 0.6 s, `power2.out`, from 8.0 s; hold at 100 °C from 12.5 s to 13.0 s.
- Transition out: `transitions-push` (vertical, 0.3 s) at 14.0 s, which carries the tiles off the top.
- Audio cues: SFX "rising-tone" from 8.5 s to 12.5 s (synced to the bar rise); SFX "bell-soft" at 12.5 s (the bar stops). No music.

### Scene 4 (14.0–19.0 s): reveal
- Composition: back to front: ground; thermometer line; scale zoomed on its top (100 °C to 101 °C, labels "100,0 °C" and "100,5 °C" in 120 px weight 800 at x 64 px); a 6 px step marker at 100,5 °C; reveal word "Nein." 180 px, `#E8B931`, weight 800, centered at y 700 px.
- Assets: code-drawn: zoomed scale, step marker.
- Action: at 14.0 s the reveal word "Nein." slams in (`expo.out`, 0.25 s); at 14.5 s the scale zooms to its top (3×, `expo.out`, 0.6 s); at 15.2 s the label "100,5 °C" fades in next to the step; at 16.0 s the subtext "Der Effekt ist winzig." fades in under the reveal word (`power2.out`, 0.4 s).
- Camera: 3× zoom on the scale top from 14.5 s to 15.1 s, then a 4 % push-in over the remaining 3.9 s (`sine.inOut`).
- Motion/easing: reveal word scale 0.6 → 1.0 and opacity 0 → 1 over 0.25 s, `expo.out`; zoom scale 1 → 3 over 0.6 s, `expo.out`; subtext opacity 0 → 1 over 0.4 s, `power2.out`.
- Transition out: hard cut at 19.0 s onto the explanation.
- Audio cues: SFX "impact-clean" at 14.0 s (on "Nein."); SFX "tick" at 15.2 s (on the 100,5 label). No music.

### Scene 5 (19.0–23.0 s): why, with the source number
- Composition: back to front: ground; the explanation text at y 620–900 px, 52 px, weight 500, `#FFFFFF`, at most three lines at width 952 px; a horizontal mini-scale at y 1200 px, 600 px wide, with the 0,5 °C step in `#E8B931`; a marker that stops at the step.
- Assets: code-drawn: mini-scale, marker, bubble.
- Action: at 19.0 s the explanation fades in line by line (`power2.out`, 0.35 s per line, 0.1 s offset); from 20.0 s the marker moves from 100 °C to the 100,5 °C step (0.6 s, `power2.out`) and stops for 0.8 s (deliberate stillness, until 21.4 s); at 21.4 s a bubble pops at the marker (code-drawn circle, expands and fades over 0.3 s).
- Camera: static.
- Motion/easing: lines opacity 0 → 1 and y +20 → 0 px over 0.35 s, `power2.out`; marker x 0 → 380 px over 0.6 s, `power2.out`; bubble scale 0.2 → 1.0 and opacity 1 → 0 over 0.3 s, `expo.out`.
- Transition out: hard cut at 23.0 s onto the logo lockup.
- Audio cues: SFX "bubble-pop" at 21.4 s. No music.

### Scene 6 (23.0–25.0 s): close, logo lockup
- Composition: back to front: ground; thermometer line in the background at 20 % opacity; logo `assets/kuechenchemie-logo.png` scaled to 640×640 px, centered at x 540, y 1150 px; text "Küchenchemie" 52 px weight 600 under the logo at y 1420 px, `#FFFFFF`.
- Assets: exists: `assets/kuechenchemie-logo.png` (user-supplied, see section 7). Code-drawn: thermometer line.
- Action: at 23.0 s the logo fades in (0.4 s); at 23.4 s the account name fades in under it (0.3 s); from 23.7 s to 25.0 s the logo idles (breathing scale 1.00 → 1.02 → 1.00 over 1.3 s).
- Camera: static.
- Motion/easing: logo opacity 0 → 1 over 0.4 s, `power2.out`; logo scale 1.00 → 1.02 → 1.00 over 1.3 s, `sine.inOut`; account name opacity 0 → 1 over 0.3 s.
- Transition out: end of composition; the last frame holds the logo and the name (ambient idle).
- Audio cues: SFX "motif-3-notes" at 23.0 s (the recurring sound motif, three notes, 0.6 s total). No music.

## 6. Audio

- **Voiceover:** no. There is no narration, so no voice engine is needed.
- **Full voiceover script:** none.
- **Pronunciation:** none.
- **Music:** none. Reason: the user chose no music (SIMULATED answer). No music bed, no ducking.
- **Sound effects:** seven SFX, each with source and license capture in SOURCES.md:
  1. "tick": short dry click, 0.05 s, at 0.0 s and 0.3 s (scene 1), at 3.5 s (scene 2), and at 15.2 s (scene 4). Source: bundled library via `/media-use resolve --type sfx` (needs no account), or Openverse.
  2. "whoosh-short": 0.3 s air whoosh at 3.4 s (scene 2). Same source rule.
  3. "rising-tone": 4.0 s rising tone from 8.5 s to 12.5 s (scene 3). Same source rule.
  4. "bell-soft": single soft bell hit, 0.8 s, at 12.5 s (scene 3). Same source rule.
  5. "impact-clean": short low thud, 0.2 s, at 14.0 s (scene 4). Same source rule.
  6. "bubble-pop": small pop, 0.2 s, at 21.4 s (scene 5). Same source rule.
  7. "motif-3-notes": three short bell-like notes (rising, 0.2 s each) at 23.0 s (scene 6). If no fitting sound exists in the bundled library, create it in code: three sine tones at 660, 785, and 990 Hz, 0.2 s each, with 10 ms fades; record "code-generated, no license needed" in SOURCES.md.
  - SFX level: −12 dB peak. No two SFX start within 0.1 s of each other, except the scene 2 whoosh and tick.
- **Sound motif (recurring element):** three rising bell-like notes (item 7). Occurs only at 23.0 s, the close.
- **Captions:** burned-in: no separate caption track. The on-screen text is the quiz copy and is not duplicated as captions.
- **Silence:** not applicable (SFX present). The last 1.0 s after the motif may be silent.

## 7. Assets

Base path: `video/kuechenchemie-nudelwasser/`

| Path | Status | Use | Notes |
|---|---|---|---|
| `assets/kuechenchemie-logo.png` | user | scene 6 lockup | User's own raster logo, 1080×1080 px, not SVG. Not present in the planning environment: the user places it at this path before the executor starts. Use as supplied; minimum width 320 px; clear space 60 px. License: owned by the user (record in SOURCES.md). |
| `code: pot` | create | scene 1 hook | SVG pot in #E8B931, body 520×360 px, lid with a 2 px rattle. |
| `code: thermometer-line` | create | scenes 1–6 | Vertical line 4 px wide, #FFFFFF, 1200 px high, ticks at 20, 40, 60, 80, 100 °C. |
| `code: answer-tiles` | create | scenes 2–3 | Two rectangles 880×200 px, #E8B931, text #1F3D2B 72 px weight 700, no radius. |
| `code: mercury-bar` | create | scene 3 | Vertical bar 24 px wide, #E8B931, rising from 20 °C to 100 °C. |
| `code: zoom-scale` | create | scene 4 | Scale top with labels "100,0 °C" and "100,5 °C" and a 6 px step marker. |
| `code: mini-scale` | create | scene 5 | Horizontal scale 600 px wide with the 0,5 °C step in #E8B931. |
| `code: bubble` | create | scene 5 | Circle 40 px, #FFFFFF stroke 3 px, expands and fades. |
| `sfx/tick.wav` | source | scenes 1, 2, 4 | Bundled library or Openverse via `/media-use resolve --type sfx`; license into SOURCES.md. |
| `sfx/whoosh-short.wav` | source | scene 2 | Same source rule as `sfx/tick.wav`. |
| `sfx/rising-tone.wav` | source | scene 3 | Same source rule as `sfx/tick.wav`. |
| `sfx/bell-soft.wav` | source | scene 3 | Same source rule as `sfx/tick.wav`. |
| `sfx/impact-clean.wav` | source | scene 4 | Same source rule as `sfx/tick.wav`. |
| `sfx/bubble-pop.wav` | source | scene 5 | Same source rule as `sfx/tick.wav`. |
| `sfx/motif-3-notes.wav` | source | scene 6 (motif) | Bundled library; if no fitting sound exists, create in code (see section 6, item 7). |
| `font: Inter` | source | all text | Google Fonts, SIL OFL; license captured in SOURCES.md. Fallback: system sans-serif (no other fallback may be substituted for the bold weight). |

- **Budget for paid generation:** €0, use none. No image generation, no paid TTS, no paid music, no paid SFX.
- **Fonts:** Inter from Google Fonts (weights 500, 600, 700, 800). Fallback: system sans-serif.
- **Creation orders:** each `code:` asset is specified in the section 5 scene blocks and in this table; draw with SVG and GSAP; no external images.

## 8. Technical execution

- **Workflow:** `/general-video`, because the concept is fully specified (scenes, timings, copy, SFX cues) and needs no preset look. `/motion-graphics` is not used because the piece has six scenes, a reveal, and a source-number explanation. `flow: automation`, `storyboard: no` (autonomous; the internal QA passes in section 9 still apply).
- **Skills to load as needed:** `/hyperframes-core` (composition contract), `/hyperframes-animation` (eases, reveal, stillness), `/hyperframes-audio` (SFX levels only; no music bed), `/media-use` (SFX resolve, `--type sfx`), `/hyperframes-cli`. Not needed: `/hyperframes-keyframes` (the only camera move is a 3× scale zoom on one element, which GSAP handles) and `/hyperframes-registry` (no registry block is named).
- **Animation approach:** GSAP paused timeline registered on `window.__timelines`; hand-authored SVG for all shapes. No Three.js. Seeded PRNG for any randomness (none expected). No `fetch`, no live data at render time.
- **Candidate blocks and effects:** none named. Transition: `transitions-push` (verify with `npx hyperframes catalog --query "transitions-push"`).
- **Media integration:** no footage, no video layers, no media effects. The logo is an image layer. Audio is the SFX track only.
- **Output:** `npx hyperframes render` with the quality flag verified in step 0 (the flag name differs by version; use the highest tier the installed version offers). File name: `kuechenchemie-nudelwasser-v1-portrait.mp4`.

## 9. Quality and delivery

**Order of work and gates**
1. **Story pass (before detail):** block every scene with placeholder shapes in final positions and final copy. Run `npx hyperframes snapshot` at each scene midpoint and check: the hook reads at 3 s, each scene has an action and a consequence, the story is clear with sound off.
2. **Sound pass:** place SFX on their visual events (section 6). Music: none.
3. **Detail pass:** full look, motion, transitions (section 4).
4. **Technical gates:** `npx hyperframes lint` and `npx hyperframes check` with zero errors. Fix warnings that affect text occlusion or contrast.
5. **Frame review:** snapshots at 0.0 s (first frame), at the scene midpoints (1.5, 5.5, 11.0, 16.5, 21.0, 24.0 s), at the transition midpoint (14.15 s), and the last frame. Compare them to section 5.
6. **Draft render review:** watch the whole render with sound. Check the acceptance criteria below.
7. **Final render**, then verify the file with ffprobe: 1080×1920, 30 fps, duration 25 ±1 s, H.264, AAC audio stream present.

**Acceptance criteria (all must pass)**
- The first frame is the hook frame (section 2); the question is readable without sound.
- Every on-screen text is visible long enough to read (at least about 1 s per 3–4 words), inside the safe areas, not occluded, AA contrast.
- Every on-screen text matches section 5 exactly.
- SFX land on their visual events within ±2 frames.
- No scene is a static slide: each has the action and consequence in section 5.
- The thermometer is planted in scene 1, climbs in scene 3, reveals in scene 4, and returns in scene 6.
- Logo, colors, and fonts match section 4 exactly; no invented UI, and no claim beyond Appendix B.
- The hook's question is answered at 14.0 s and the explanation runs 19–23 s.
- Duration is 25 s within ±1 s; resolution and fps match section 3.

**Revision priority** when something fails: opening → development → resolution → brand effect. Fix the highest-priority failure first, then re-check every affected scene.

**Iteration budget and stop criteria**
- At most 3 full review cycles (steps 5–6) and 4 draft renders; one final render (+ one re-render if a delivery check fails).
- Change one thing per fix where possible; use absolute targets ("subtext 52 px"), not relative nudges.
- Stop and report instead of looping when the budget is used up, the same failure survives two fix attempts, or a fix would need a decision outside this brief (a new claim, a paid asset, a changed story). Also stop if `assets/kuechenchemie-logo.png` is missing at step 0.

**Source gate (before the first render):** Appendix B row 2 is derived, not directly stated by a fetched source. Look for a second, fetchable source that says salted water does not cook pasta faster. If none is verified, replace scene 4's "Nein. Der Effekt ist winzig." with the same words, and remove any claim about cooking time. Log which version was used.

**Deliverables** in `video/kuechenchemie-nudelwasser/`
- `renders/kuechenchemie-nudelwasser-v1-portrait.mp4`
- the editable HyperFrames project (sources, `BRIEF.md`, `frame.md`, `production-prompt.md`, assets)
- `SOURCES.md`: claim evidence (Appendix B), asset licenses (Inter OFL, each SFX file, the user's logo), voice: none
- `PRODUCTION-LOG.md`: environment versions, verified or replaced names, every deviation with its reason, the commands run and their results (lint, check, snapshot list, ffprobe output), review findings per cycle, known limitations
- Do not claim a check you did not run. If something could not be verified, list it under "Not verified".

## Appendix A: BRIEF.md

```markdown
---
workflow: general-video
flow: automation
storyboard: no
message: "Salz im Nudelwasser verändert den Siedepunkt nur minimal; das Wasser kocht dadurch nicht spürbar schneller."
destination: instagram-reels
aspect: 1080x1920
language: de
audience: "deutschsprachige Follower eines Küchenchemie-Accounts, die beim Kochen Wissenschaft mögen"
length: 25s
narration: no
---

## Intent

A 25-second quiz video for the Instagram account "Küchenchemie": "Warum kocht Nudelwasser mit Salz nicht wirklich schneller?" The viewer sees the question, two answer tiles, a thinking time with a rising thermometer, the reveal "Nein. Der Effekt ist winzig.", and the source number (0,5 °C at 29,2 g salt per kg water). Tone: dry, mildly playful, factual. Fully confirmed; build from production-prompt.md sections 1–9, which this project keeps as the detailed plan.

## Assets

- assets/kuechenchemie-logo.png — user's own square logo (1080×1080), end lockup in scene 6; must be placed before the run
- sfx/*.wav — bundled SFX (see production-prompt.md section 6)

## Customizations

- Quiz pause: no countdown; the answer tiles wobble one after the other, then the thermometer climbs over 4.5 s.
- Hold at 100 °C for 0.5 s before the reveal (deliberate stillness).
- Zoom reveal on the thermometer top from 100,0 °C to 100,5 °C, with the honest unzoomed scale shown in scene 5.
- Three-note sound motif at the close, created in code if no bundled sound fits.

## Notes

- Confirmed brief; do not re-interview. The detailed plan is in production-prompt.md (copy it into the project root).
- No music, no voiceover, no paid generation, no paid services.
- Do not claim a cooking-time effect; use only the boiling-point number from Appendix B #1.
- Only German on-screen text; no English copy.
```

## Appendix B: Sources

| # | Claim or fact used in the video | Evidence |
|---|---|---|
| 1 | Salt raises the boiling point of water by 0.5 °C for 29.2 g of salt per kg of water | https://van.physics.illinois.edu/ask/listing/1457 (answer by "Tom", dated 2007-10-22; fetched 2026-10-20) |
| 2 | Salt does not make pasta water cook faster. Status: derived from #1 (a higher boiling point means the water must reach a slightly higher temperature); not directly stated by a fetched source; see the source gate in section 9. | Derived from row 1; second source not yet fetched (Live Science search snippet only; page not readable, not used as evidence) |
| 3 | The boiling-point effect scales in proportion to salt concentration | https://van.physics.illinois.edu/ask/listing/1457 (same page, fetched 2026-10-20) |

## Appendix C: frame.md

```markdown
---
name: Küchenchemie — video frame spec
description: Flat Swiss-style quiz frame in brand green and mustard, 9:16, no gradients.
colors:
  ground: "#1F3D2B"
  accent: "#E8B931"
  ink: "#FFFFFF"
  ink-on-accent: "#1F3D2B"
typography:
  display: { fontFamily: "Inter", px: 120, weight: 800, lineHeight: 1.0, tracking: "-0.02em" }
  tile: { fontFamily: "Inter", px: 72, weight: 700, lineHeight: 1.1 }
  body: { fontFamily: "Inter", px: 52, weight: 500, lineHeight: 1.25 }
  label: { fontFamily: "Inter", px: 40, weight: 600, tracking: "0.04em", upper: false }
---

## Overview
A flat, quiz-style frame: one dark green ground, one mustard accent, white text. The account's brand colors are strict; no gradients, glow, or shadows. The logo file is used as supplied.

## Do's and Don'ts
- Do: one accent color per frame; hairlines of 3 px; left-aligned display type.
- Don't: gradients, glow, drop shadows, a third hue, stock imagery, invented UI, countdowns.
```
