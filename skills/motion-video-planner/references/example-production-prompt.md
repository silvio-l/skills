# Example: production prompt (calibration only)

A complete prompt produced by this skill in a validation run: briefing mode, no repository, a knowledge-quiz Reel for a cooking-science account. **The user answers in that run were SIMULATED**, and the account, logo and briefing are test data. Use it to calibrate the level of detail, never as content to copy. It passed `check_prompt.py`. Cold reads by subagents that saw only the prompt went from 17 defects (v1) to 5 blocking decisions (v2) to 4 (this version, before the last fixes). Those four were fixed afterwards, partly by template rules, and not re-reviewed. Expect a strict reader to still find small points; that is normal, not a reason to copy it.

---

# Production brief: Küchenchemie – Nudelwasser-Quiz

> Planned with motion-video-planner on 2026-10-20 (revision 3). Concept A: "Ist das wirklich schneller?", selected by the user. Timings are PLANNED. There is no voiceover; the timeline follows the on-screen text and SFX cues.
> Test provenance (validation run only, not part of the video): the user answers in this plan are SIMULATED. The production run treats them as confirmed.

## 0. Start here

You are the production agent for a fully planned short motion-graphics video. Story, copy, look, and timing are decided. Build them faithfully. Change something only when it is technically impossible or when a check in section 9 fails, and log every deviation in `PRODUCTION-LOG.md` with the reason.

**Your latitude:** this brief fixes what the viewer must notice: copy, order, timing, colors, fonts, sizes, positions of focal elements, and sync points. Details it leaves open (z-order where it is obvious, whether a wobble settles back to rest, which ffmpeg or mixer parameter sets a level, sub-frame easing details) are yours to decide. Decide them in the spirit of section 4 and log them; they are not deviations and need no question.

**Working directory:** create the HyperFrames project at `video/kuechenchemie-nudelwasser`, relative to the directory in which this session starts. **Product repository:** none. **Assets:** every path in section 7 is relative to the project directory `video/kuechenchemie-nudelwasser/` (the base path; init creates it in step 1).

**Permissions and limits**
- Allowed: run `npx hyperframes …` (including the browser binary it downloads itself); install the npm packages and the HyperFrames skills (`npx skills add heygen-com/hyperframes`) that the workflow needs; run `ffmpeg`/`ffprobe` (present on the machine); download the four Inter font files named in section 7 once and copy them into `assets/fonts/` (rules in section 7); create files inside the project directory.
- Not allowed without asking the user: installing system software or container runtimes, `render --docker`, any paid generation or paid service (the budget is zero, see section 7), `publish`, uploads, deploys, commits outside the project directory. The product repository does not exist in this run, so no edits to it are possible.
- Respect the harness's permission prompts; never work around a denial.

**Step 0 — Verify the environment (record the outputs in PRODUCTION-LOG.md)**
1. `node --version` (needs a current LTS); `npx hyperframes --version`; `npx hyperframes doctor`. `doctor` may report Docker as missing; that is expected and ignored (never install Docker). If it asks for system software, stop and report.
2. Check that the HyperFrames skills are available (`/hyperframes` in your skill list). If they are missing, run `npx skills add heygen-com/hyperframes` and tell the user a session restart is needed. Stop there.
3. `npx hyperframes usage --json`, and note any limits.
4. `npx hyperframes render --help` and `npx hyperframes init --help`: confirm the flag names this brief uses (`--resolution`, `--fps`, the quality tier, the output option). If a name differs, use the installed version's equivalent and log it.
5. Section 7 has no `exists` assets. The logo is a `user` asset; it is checked after init (step 1.2), not here.
6. The transition `transitions-push` is an optional candidate (section 8). Check it with `npx hyperframes catalog --query "transitions-push"`. If the catalog offers a vertical direction for a 0.3 s push, you may use it, but only if it matches the scene 3 spec. Otherwise hand-author the push as specified in scene 3. Log which one you used. No registry block is required by this brief.

If HyperFrames cannot run at all, stop and report. Do not build a substitute render engine.

**Step 1 — Scaffold and brief**
1. `npx hyperframes init video/kuechenchemie-nudelwasser --resolution portrait`. Do not pass a skill flag: the workflow is selected by `BRIEF.md` (step 2).
2. Immediately write Appendix A verbatim to `video/kuechenchemie-nudelwasser/BRIEF.md`, and Appendix C verbatim to `video/kuechenchemie-nudelwasser/frame.md`. Copy this file to `video/kuechenchemie-nudelwasser/production-prompt.md`. Stage the section 7 assets into the project. Then check the logo with `ls video/kuechenchemie-nudelwasser/assets/kuechenchemie-logo.png`. If it is present, use it in scene 6. If it is missing, use the stand-in from section 4 and log it as STAND-IN in PRODUCTION-LOG.md.
3. Invoke `/hyperframes`. It finds `BRIEF.md` and runs the workflow `general-video` with no brief questions. **This brief is confirmed by the user**: run no intent interview and no pitch round. The run is autonomous: post checkpoint summaries and continue.
4. Storyboard: none. Work directly from section 5. If the workflow still writes `STORYBOARD.md`, carry over section 5 scene by scene (copy verbatim, planned timings, scene purposes).

**Step 2 — Build in passes (see section 9 for the gates)**
Story pass (blocking stills of the whole timeline) → sound pass (SFX on their events) → detail pass (look, code-drawn shapes, motion, transitions) → technical gates → frame review → draft render → final render.

**Questions to the user:** none, with one exception. "Autonomous" means no intent interview, no pitch round, and checkpoint summaries that do not wait. Draft renders are pre-approved. The workflow's own render gate ("render now, or what changes?") is the single question you ask, once, before the final render, after section 9 passes. Blockers named in this file (for example a missing `user` asset) are reported at that point, not earlier, unless they stop all work. If the logo (`user` asset) is still missing then, deliver everything else (project, draft render with the stand-in, logs), ask once for the file in the same message as the render gate, and end the run; the final render follows when the file arrives.

## 1. Goal and context

- **Product / topic:** the Instagram account "Küchenchemie", which explains cooking science in German. This video is a quiz about whether salt in pasta water makes the water boil or cook faster.
- **Audience:** German-speaking followers of a cooking-science account (about 4,000 followers); home cooks who salt the water early. Prior knowledge: basic kitchen experience; no physics needed.
- **Core message (one sentence):** Salt raises the boiling point of water by a fraction of a degree, so the amount used for pasta does not noticeably change the cooking time (salted water even takes slightly longer to reach the boil). (Evidence: Appendix B #1 and #2.)
- **Intended effect:** the viewer answers the quiz in their head, is surprised by how small the effect is, and remembers the thermometer; they recognize their own habit of salting the pot early.
- **Goal priority:** reach → brand recall → conversion (none).
- **Share trigger:** "simple solution": a short, checkable fact forwarded to the friend who salts early. **Rewatch trigger:** the 0,5 °C step is easy to miss on the first watch.
- **CTA:** none. Soft brand close only: the logo lockup with the account name (scene 6).
- **Limits:** no claim beyond Appendix B; no pasta-water concentration figure; no cooking-time figure in seconds; no statement that salt makes pasta cook faster or slower in practice (the copy says "kaum spürbar", never "nicht"); no statement that salting is wrong (salt is for flavor); do not name any other account or brand.

## 2. Story

- **Hook (0–3 s):** the first frame is the question on a dark green field, in three lines: "Salz ins / Nudelwasser: / Kocht es schneller?". A code-drawn pot in the lower half rattles once at 0.8 s. The situation is clear without sound because the question is the full text of the frame.
- **Visual thread:** the thermometer (a vertical line at the left edge, code-drawn) is planted in scene 1, climbs in scene 3, is zoomed in scene 4, is shown to scale in scene 5 as a mini-scale, and returns in scene 6 as the close's background line.
- **Development:** two answer tiles appear under the question, and the viewer gets a quiz pause (no countdown). The tiles lean toward the thermometer as its mercury bar climbs to 100 °C, with a short deliberate stillness at 100 °C. The correct answer is the second tile, "Kaum spürbar", placed second on purpose; the reveal marks it by movement and zoom, not by colour alone.
- **Climax:** the reveal at 14.0 s: "Kaum." and the zoomed step from 100,0 °C to 100,5 °C.
- **Resolution:** the explanation with the source number: salt raises the boiling point by 0,5 °C at 29,2 g per kg water (scene 5). The hook's question is answered by this number.
- **Close:** the logo lockup (640×640 px, centered) on the dark green field; the account name below it; the three-note motif plays once at 23.0 s; the logo breathes once (scale 1.00 → 1.02 → 1.00, 23.7–25.0 s) and the last frame rests at 1.00.
- **Tone:** dry, mildly playful, factual. Avoid mocking the viewer for salting early.

## 3. Format

- Duration (planned): 25 s (tolerance ±1 s; there is no voiceover, so the planned timing is the target)
- Resolution / aspect: 1080×1920 (9:16)
- Frame rate: 30 fps
- Delivery: MP4 H.264 with an AAC stereo SFX track
- Variants: none
- Safe areas: top 270 px, bottom 380 px (the bottom limit is y 1540), sides 64 px. Text stays in the text lane x 176–1016 (section 4); the thermometer lane x 64–160 holds only the line, the scale ticks, and the step marker.
- Sound-off: must work without sound: yes. The on-screen text carries the whole quiz; SFX are supporting only.

## 4. Look

- **Brand source of truth:** the two brand colors given by the user (palette below) and the user's logo file `assets/kuechenchemie-logo.png`. Colors and logo proportions are strict. No redrawing of the logo.
- **Style:** Swiss / Editorial (dominant), with a Kinetic Typography accent on the reveal word only. Applied as these rules:
  1. Flat color fields only; no gradients, no glow, no shadows.
  2. One accent color, #E8B931. It appears ONLY on: the two answer tiles (scenes 2–3), the mercury bar (scene 3), the zoom step marker (scene 4), the reveal word "Kaum." (scene 4), and the step tick on the mini-scale (scene 5). The reveal word is accent-colored text set directly on the ground, not on a tile; the ground-on-accent rule of the palette does not apply to it, and its contrast is the same 6.5:1 pair. Nothing else is accent-colored; the logo keeps its own colors.
  3. Structure by hairlines of 3 px (at 1080 px width): the thermometer line, the scale ticks, the zoom-group line and its ticks, the mini-scale line, the pot outline, and the bubble outline. Exceptions: the mercury bar (24 px wide, a bar, not a hairline) and the step markers (6 px). No decorative grid.
  4. Display type is flush-left at x 176, ragged-right. Exception: the close (the logo and the name "Küchenchemie") is centered.
  5. Easing: entrances (text lines, tiles, labels, subtexts, logo, name) use `power3.out` at 0.3–0.5 s. The reveal word "Kaum." is the only `expo.out` use (0.25 s). Moves (the question shrink, the tile lean and scale, the push, the bar, the marker, the zoom, the wobble, the breathing) use `sine.inOut`. The bubble pop uses `power3.out`.
  6. Overshoot only on the pot rattle (`back.out(1.4)`, 0.2 s). No bounce on text.
  7. Stillness is deliberate and named per scene: the 100 °C hold (12.5–13.0 s), the stop of the marker (20.6–21.4 s), and the holds listed in section 5.
- **Palette:**
  - ground: `#1F3D2B` (Dunkelgrün, brand, user-supplied)
  - accent: `#E8B931` (Senfgelb, brand, user-supplied)
  - ink on ground: `#FFFFFF` (all text and line work on the ground)
  - ink on accent: `#1F3D2B` (text on the answer tiles)
  - Contrast: white on ground 11.9:1; accent on ground 6.5:1. Both exceed WCAG AA.
- **Typography:** Inter, from local font files (section 7). Weights 500, 600, 700, 800. Tracking as stated; line-heights in px.
  - display (question, scene 1): weight 800, 72 px, line-height 72 px, tracking -0.02 em
  - question after the shrink (scenes 2–3): weight 800, 56 px, line-height 56 px, tracking -0.02 em
  - answer tiles: weight 700, 72 px, line-height 79 px
  - reveal word "Kaum.": weight 800, 180 px, line-height 180 px
  - scale labels in scene 4 ("100,0 °C", "100,5 °C"): weight 800, 72 px, line-height 72 px
  - explanation and subtext: weight 500, 52 px, line-height 65 px
  - labels (scene 3 "Denk kurz nach.", scene 5 scale labels): weight 600, 40 px, line-height 48 px, tracking 0.04 em, sentence case. This is the only place where label tracking and line-height are stated.
  - close name: weight 600, 52 px, line-height 65 px
  - Measured fit: with the official Inter 4.0 ExtraBold file, "Kocht es schneller?" at 72 px measures 702 px before tracking (about 675 px with −0.02 em). That is 84 % of the 840 px text lane, outside the 10 % band around the limit, so the 72 px size stands.
  - Forced line breaks: ` / ` in the copy marks a line break. It is never shown on screen; the line breaks are placed as written in section 5.
- **Layout:** 9:16. Thermometer lane x 64–160 (the line at x 96 px). Text lane x 176–1016 (840 px wide). Vertical zones: question block y 300–468 (scenes 2–3), answer tiles y 760–1220 (scene 2 rest positions), mercury bar y 420–1500, logo box y 640–1280, close name y 1368–1433.
- **Contrast:** see the palette. Every text element is ink on ground or ground on accent.
- **Logo and product depiction:** `assets/kuechenchemie-logo.png` (user-supplied, square, 1080×1080 raster; status `user`). Shown at 640×640 px, centered at (540, 960), with clear space 60 px on all sides (nothing enters the 60 px around the logo box). Never redrawn, distorted, or recolored. No product and no UI are depicted.
  - **Stand-in until the file exists:** the same 640×640 box holds the text "Küchenchemie", weight 800, 84 px, `#FFFFFF`, centered at (540, 960). Log it as STAND-IN in PRODUCTION-LOG.md. It is a placeholder typeset in Inter, not a redraw of the logo. Replace it with the PNG at the same box when the file arrives.
- **Motion character:** entrances ease out, moves ease in-out (see rule 5). Overlap offsets of 0.1–0.2 s between text lines and tiles. Ambient idle only on the logo at the close (one breath, see scene 6).
- **Transitions:** primary: hard cuts at 3.0 s, 8.0 s, 19.0 s, and 23.0 s, each on an action boundary (the question continues across 3.0 s and 8.0 s; the scene changes are the cuts). Accent: one vertical push, hand-authored (section 8), 0.3 s, 13.7–14.0 s, carrying scene 3 off the top and bringing scene 4 in from the bottom.
- **Negatives:** no purple-blue gradients, no stock photos, no lens flares, no invented UI, no third hue, no countdown timer, no fake poll percentages, no captions that duplicate the on-screen text, no text inside the top 270 px or the bottom 380 px, no accent color outside the list in rule 2.

## 5. Timeline

All times are PLANNED. There is no voiceover; scene times follow the on-screen text and SFX cues. Scenes are contiguous: each starts where the previous ends.

| # | Start | End | Purpose | Voiceover (exact) | On-screen text (exact) |
|---|---|---|---|---|---|
| 1 | 0.0 | 3.0 | hook | — | "Salz ins / Nudelwasser: / Kocht es schneller?" |
| 2 | 3.0 | 8.0 | answer options appear (question stays on screen) | — | "Salz ins / Nudelwasser: / Kocht es schneller?" + "Ja, schneller" / "Kaum spürbar" |
| 3 | 8.0 | 14.0 | thinking time, thermometer climbs (question stays on screen) | — | "Salz ins / Nudelwasser: / Kocht es schneller?" + "Denk kurz nach." |
| 4 | 14.0 | 19.0 | reveal | — | "Kaum." / "Der Effekt ist winzig." |
| 5 | 19.0 | 23.0 | why, with the source number | — | "Der Siedepunkt steigt / um 0,5 °C bei 29,2 g / Salz pro kg Wasser" |
| 6 | 23.0 | 25.0 | close, logo lockup | — | "Küchenchemie" |

The question stays on screen from 0.0 s until the scene 3 push starts at 13.7 s, because a viewer without sound must see the question and both options for the whole thinking time. Scene 4 does not show the question.

### Scene 1 (0.0–3.0 s): hook
- Composition: back to front: ground `#1F3D2B` full frame; thermometer line, 3 px, `#FFFFFF`, x 96, y 300–1500; pot (code-drawn SVG, outline only, 3 px `#FFFFFF` stroke, no fill): lid 560×36 px at x 260–820, y 964–1000; body 520×360 px at x 280–800, y 1000–1360; question block, 72 px weight 800, `#FFFFFF`, left at x 176, three lines: line 1 "Salz ins" y 420–492, line 2 "Nudelwasser:" y 492–564, line 3 "Kocht es schneller?" y 564–636.
- Assets: code-drawn: pot (SVG), thermometer line (SVG).
- Action: 0.0 s line 1 enters; 0.2 s line 2; 0.4 s line 3; 0.8 s the pot's lid rattles once (0.2 s). From 1.0 s to 3.0 s everything rests (deliberate still).
- Camera: static.
- Motion/easing: each line y +30 px → 0 and opacity 0 → 1, 0.4 s, `power3.out`; pot lid x 0 → 2 → -2 → 0 px over 0.2 s, `back.out(1.4)`.
- Transition out: hard cut at 3.0 s. The question block is not removed: it continues into scene 2 and shrinks there. The pot is not part of scene 2.
- Audio cues: SFX "tick" at 0.0 s (line 1), 0.2 s (line 2), 0.4 s (line 3). No music.

### Scene 2 (3.0–8.0 s): answer options appear
- Composition: back to front: ground; thermometer line (as scene 1); question block, 56 px weight 800, `#FFFFFF`, left at x 176, top y 300 (line boxes y 300–356, 356–412, 412–468; the block arrives there from scene 1 by the shrink in the action); answer tile 1, 840×200 px, `#E8B931`, x 176–1016, y 760–960, text "Ja, schneller" 72 px weight 700 `#1F3D2B`, centered; answer tile 2, same size and type, x 176–1016, y 1020–1220, text "Kaum spürbar".
- Assets: code-drawn: tiles (SVG rectangles, no radius).
- Action: 3.0–3.4 s the question block shrinks and moves: scale 1.00 → 0.7778 (= 56 / 72) with its transform origin at its top-left corner (176, 420), and its top edge y 420 → 300 (−120 px) over the same 0.4 s; x stays 176. 3.5 s tile 1 slides in from x −900 to x 176 (0.4 s). 3.6 s tile 2 slides in from x −900 to x 176 (0.4 s) and lands at 4.0 s. From 4.5 s to 7.8 s the tiles wobble one at a time: wobble k starts at 4.5 + 0.3k s for k = 0…10; even k wobbles tile 1, odd k wobbles tile 2; each wobble moves x by ±6 px over 0.3 s and returns to x 176. Both tiles rest from 7.8 s to 8.0 s.
- Camera: static.
- Motion/easing: question block scale 1 → 0.7778 and y −120 px, `sine.inOut`, 0.4 s, from 3.0 s; tile slides `power3.out` 0.4 s; wobble `sine.inOut` 0.3 s, amplitude 6 px.
- Transition out: hard cut at 8.0 s. The question and both tiles continue into scene 3.
- Audio cues: SFX "whoosh-short" at 3.5 s (tile 1 enters); SFX "tick" at 4.0 s (tile 2 lands). No music.

### Scene 3 (8.0–14.0 s): thinking time, thermometer climbs
- Composition: back to front: ground; thermometer line (as scene 1); question block (as scene 2, top y 300); label "Denk kurz nach." 40 px weight 600 `#FFFFFF`, left at x 176, box y 500–548, opacity 0 until 8.4 s; scale ticks, 3 px `#FFFFFF`, horizontal, x 120–136, at y 1500 (20 °C), y 1230 (40 °C), y 960 (60 °C), y 690 (80 °C), y 420 (100 °C); mercury bar, 24 px wide, `#E8B931`, x 84–108, bottom fixed at y 1500 (20 °C), top edge at 100 °C = y 420 when full; answer tiles (as scene 2) with transform scale 0.92 and rotate −2° (counter-clockwise), transform origin at each tile's bottom-left corner: (176, 960) for tile 1 and (176, 1220) for tile 2. The resulting corners of tile 1 are top-left (170, 776), top-right (942, 749), bottom-right (948, 933), bottom-left (176, 960); tile 2 is the same shape 260 px lower. Tile tops lean toward the thermometer.
- Assets: code-drawn: mercury bar; scale ticks. No tick labels in this scene: a label at the 100 °C tick would collide with the question block. The scale is labeled in scene 5.
- Action: 8.0 s the tiles start to lean and scale (0.6 s). 8.4 s "Denk kurz nach." fades in (0.3 s). 8.5 s the mercury bar starts to rise and reaches 100 °C at 12.5 s (4.0 s). At 12.5 s the bar stops and the bell sounds; the bar holds for 0.5 s (deliberate stillness, to 13.0 s). From 13.0 s to 13.7 s everything rests. 13.7–14.0 s the push carries scene 3 off the top and brings scene 4 in from the bottom.
- Camera: static.
- Motion/easing: tile lean −2° and scale 1.00 → 0.92, `sine.inOut`, 0.6 s from 8.0 s; label opacity 0 → 1, `power3.out` 0.3 s from 8.4 s; bar top edge y 1500 → 420, `sine.inOut`, 4.0 s from 8.5 s; push as below.
- Transition out: hand-authored vertical push, 0.3 s, 13.7–14.0 s (section 8). Scene 3 group y 0 → −1920 px and scene 4 group y +1920 → 0 px, both `sine.inOut`, both starting at 13.7 s. On screen: at 13.7 s scene 3 is at rest and scene 4 shows only its ground, below the frame; at 13.85 s the frame is split at y 960, with the lower half of scene 3 (its y 960–1920) above and the upper half of scene 4 (its y 0–960) below; at 14.0 s scene 4 is at rest and scene 3 has left the frame.
- Audio cues: SFX "rising-tone" from 8.5 s to 12.5 s (synced to the bar rise); SFX "bell-soft" at 12.5 s (the bar stops). No music.

### Scene 4 (14.0–19.0 s): reveal
- Composition: back to front: ground; zoom group, the magnified thermometer segment at 100 °C: at 1× a 3 px `#FFFFFF` line at x 96 from y 900 to y 1040, with two horizontal ticks running rightward from the line, 24 px long (x 96–120), 3 px: 100,0 at y 1000 and 100,5 at y 960; the group is zoomed about the pivot (96, 1000) and its strokes stay 3 px (non-scaling), so at 3× the line spans y 700–1120 and the ticks are 72 px long (x 96–168); the zoom group is a magnified view, not to scale: its two tick labels are the scale reference, and scene 5 shows the true scale. Labels "100,0 °C" 72 px weight 800 `#FFFFFF`, left at x 176, box y 964–1036 (centered on the 100,0 tick at y 1000); "100,5 °C" 72 px weight 800 `#FFFFFF`, left at x 176, box y 844–916 (centered on the 100,5 tick at y 880 after the zoom). Reveal word "Kaum." 180 px weight 800, `#E8B931`, left at x 176, box y 360–540; subtext "Der Effekt ist winzig." 52 px weight 500 `#FFFFFF`, left at x 176, box y 600–665; step marker, 24×6 px, `#E8B931`, x 64–88, centered at y 880 in screen space (a tab left of the line, so it covers neither the line at x 96 nor the 3× tick).
- Collision check: at 3× the 100,5 tick ends at x 168, 8 px before the label text starts at x 176; the "100,5 °C" text measures 302 px wide, so it spans x 176–478, and its box (y 844–916) clears the reveal word (ends y 540) and the subtext (ends y 665) by at least 179 px, and the 100,0 box (y 964–1036) by 48 px.
- Assets: code-drawn: zoom group (line and two ticks), step marker. The labels and the reveal word are not part of the zoom group and do not scale.
- Action: 13.7–14.0 s only the ground is visible (the push brings it in, see scene 3); the zoom group, labels, reveal word, subtext, and marker stay hidden until 14.0 s. 14.0 s the zoom group becomes visible at 1×, and "Kaum." slams in with the impact sound. 14.5–15.1 s the zoom group goes from 1× to 3× (its 100,5 tick moves from y 960 to y 880, its 100,0 tick stays at y 1000). 14.7 s the "100,0 °C" label fades in (0.3 s). 15.2 s the "100,5 °C" label fades in (0.3 s) and the step marker appears. 16.0 s the subtext fades in (0.4 s). 16.4–19.0 s everything rests (deliberate still).
- Camera: static. The zoom is an element move on the zoom group, not a camera move.
- Motion/easing: reveal word scale 0.6 → 1.0 and opacity 0 → 1 over 0.25 s, `expo.out`; zoom group scale 1 → 3 over 0.6 s, `sine.inOut`; labels and subtext opacity 0 → 1 over 0.3–0.4 s, `power3.out`.
- Transition out: hard cut at 19.0 s onto the explanation.
- Audio cues: SFX "impact-clean" at 14.0 s (on "Kaum."); SFX "tick" at 15.2 s (on the 100,5 label). No music.

### Scene 5 (19.0–23.0 s): why, with the source number
- Composition: back to front: ground; explanation text, 52 px weight 500 `#FFFFFF`, left at x 176, three lines at y 620–685, 685–750, 750–815: "Der Siedepunkt steigt" / "um 0,5 °C bei 29,2 g" / "Salz pro kg Wasser"; honest mini-scale: a 3 px `#FFFFFF` line at y 1200 from x 176 (0 °C) to x 1000 (100 °C), so 1 °C is 8.24 px and 0,5 °C is 4.12 px; end tick at x 176 and end tick at x 1000, each 40 px tall (y 1180–1220), 3 px `#FFFFFF`; step tick, 6 px wide (x 1001–1007), 46 px tall (y 1177–1223), `#E8B931`, for 100,5 °C; marker, 24 px circle, `#FFFFFF` fill, centered at (1000, 1200) at 19.0 s; bubble, 40 px circle, 3 px `#FFFFFF` stroke, visible from 19.0 s, its center always equal to the marker's center; labels, 40 px weight 600 `#FFFFFF`, line-height 48 px: "0 °C" left at x 176, box y 1250–1290; "100 °C" right-aligned to x 1000, box y 1250–1290; "100,5 °C" right-aligned to x 1016, box y 1120–1160.
- Collision check: the "100,5 °C" box (y 1120–1160) clears the bubble (top at y 1180) by 20 px and the step tick (top at y 1177) by 17 px; the "100 °C" box (y 1250–1290) clears the step tick (bottom at y 1223) by 27 px.
- Assets: code-drawn: mini-scale, step tick, marker, bubble.
- Action: 19.0–19.3 s the mini-scale and its labels fade in. 19.0, 19.1, 19.2 s the three explanation lines enter one after another (0.35 s each). 20.0–20.6 s the marker and bubble move together from x 1000 to x 1004 (4 px, the real size of 0,5 °C on this scale) and the marker stops for 0.8 s (deliberate stillness, to 21.4 s). 20.6 s the "100,5 °C" label fades in (0.3 s). 21.4 s the bubble pops: it grows from 40 px to 64 px while fading to 0 over 0.3 s.
- Camera: static.
- Motion/easing: lines opacity 0 → 1 and y +20 → 0 px over 0.35 s, `power3.out`; mini-scale and labels opacity 0 → 1, `power3.out` 0.3 s; marker and bubble x 1000 → 1004 over 0.6 s, `sine.inOut`; "100,5 °C" label `power3.out` 0.3 s; bubble scale 1.0 → 1.6 and opacity 1 → 0 over 0.3 s, `power3.out`.
- Holds: deliberate still from 21.7 s to 23.0 s.
- Transition out: hard cut at 23.0 s onto the logo lockup.
- Audio cues: SFX "bubble-pop" at 21.4 s. No music.

### Scene 6 (23.0–25.0 s): close, logo lockup
- Composition: back to front: ground; thermometer line at 20 % opacity (`#FFFFFF`, x 96, y 300–1500); logo `assets/kuechenchemie-logo.png` at 640×640 px, x 220–860, y 640–1280 (the stand-in from section 4 until the file exists); name "Küchenchemie" 52 px weight 600 `#FFFFFF`, line-height 65 px, centered at x 540, box y 1368–1433.
- Assets: user logo (section 7); code-drawn: thermometer line.
- Action: 23.0 s the logo fades in (0.4 s); 23.4 s the name fades in (0.3 s); 23.7–25.0 s the logo breathes once: scale 1.00 → 1.02 → 1.00 over 1.3 s, and the frame rests at 1.00 at 25.0 s.
- Camera: static.
- Motion/easing: logo opacity 0 → 1, `power3.out` 0.4 s; logo scale 1.00 → 1.02 → 1.00, `sine.inOut`, 1.3 s; name opacity 0 → 1, `power3.out` 0.3 s.
- Transition out: end of composition; the last frame holds the logo and the name at rest.
- Audio cues: SFX "motif-3-notes" at 23.0 s (the recurring sound motif, three notes, 0.6 s total). No music.

## 6. Audio

- **Voiceover:** no. There is no narration, so no voice engine is needed.
- **Full voiceover script:** none.
- **Pronunciation:** none.
- **Music:** none. Reason: no music was requested in the brief. No music bed, no ducking.
- **Sound effects:** seven cue types, eleven events in total, each with source and license capture in SOURCES.md:
  1. "tick": short dry click, 0.05 s, at 0.0 s, 0.2 s, and 0.4 s (scene 1), at 4.0 s (scene 2), and at 15.2 s (scene 4). Source: bundled library via `/media-use resolve --type sfx` (needs no account), or Openverse.
  2. "whoosh-short": 0.3 s air whoosh at 3.5 s (scene 2). Same source rule.
  3. "rising-tone": 4.0 s rising tone from 8.5 s to 12.5 s (scene 3). Same source rule.
  4. "bell-soft": single soft bell hit, 0.8 s, at 12.5 s (scene 3). Same source rule.
  5. "impact-clean": short low thud, 0.2 s, at 14.0 s (scene 4). Same source rule.
  6. "bubble-pop": small pop, 0.2 s, at 21.4 s (scene 5). Same source rule.
  7. "motif-3-notes": three short bell-like notes (rising, 0.2 s each, 0.6 s total) at 23.0 s (scene 6). If no fitting sound exists in the bundled library, create it in code: three sine tones at 660, 785, and 990 Hz, 0.2 s each, with 10 ms fades; record "code-generated, no license needed" in SOURCES.md.
  - SFX level: −12 dB peak. No two SFX start within 0.1 s of each other.
- **Sound motif (recurring element):** three rising bell-like notes (item 7). Occurs only at 23.0 s, the close.
- **Captions:** burned-in: no separate caption track. The on-screen text is the quiz copy and is not duplicated as captions.
- **Silence:** not applicable (SFX present). After the motif ends at 23.6 s, the track is silent to 25.0 s.

## 7. Assets

Base path: `video/kuechenchemie-nudelwasser/` (the project directory). Every path in this table is relative to it and is checked after init (step 1.2).

| Path | Status | Use | Notes |
|---|---|---|---|
| `assets/kuechenchemie-logo.png` | user | scene 6 lockup | User's own square raster logo, 1080×1080 px, PNG. Not present at planning time; the user places it at this path. Until then, use the stand-in in section 4 and log STAND-IN. Shown at 640×640 px; minimum width 320 px; clear space 60 px. License: owned by the user (record in SOURCES.md). |
| `code: pot` | create | scene 1 hook | SVG outline, 3 px `#FFFFFF` stroke, no fill: lid 560×36 px at x 260–820, y 964–1000; body 520×360 px at x 280–800, y 1000–1360. |
| `code: thermometer-line` | create | scenes 1–3 and 6 | 3 px `#FFFFFF` vertical line at x 96, y 300–1500; 20 % opacity in scene 6; absent in scenes 4–5. Scale ticks only in scene 3. |
| `code: answer-tiles` | create | scenes 2–3 | Two rectangles 840×200 px, `#E8B931`, no radius, x 176–1016 (tile 1 y 760–960, tile 2 y 1020–1220); text `#1F3D2B` 72 px weight 700, centered. |
| `code: mercury-bar` | create | scene 3 | 24 px wide `#E8B931` bar, x 84–108, bottom fixed at y 1500, top edge moves from y 1500 to y 420. |
| `code: zoom-scale` | create | scene 4 | Zoom group: 3 px `#FFFFFF` line at x 96 from y 900 to y 1040 (1×); 24 px horizontal ticks running right from x 96 at y 1000 (100,0) and y 960 (100,5) at 1×; pivot (96, 1000); zoom 1 → 3; strokes non-scaling. Step marker: 24×6 px `#E8B931` bar, x 64–88, centered on y 880, screen space. |
| `code: mini-scale` | create | scene 5 | 3 px `#FFFFFF` line at y 1200, x 176 (0 °C) to x 1000 (100 °C); end ticks 40 px tall at both ends; step tick 6 px wide, 46 px tall, `#E8B931`, at x 1001–1007. |
| `code: bubble` | create | scene 5 | Circle, 40 px diameter at start, 3 px `#FFFFFF` stroke, centered on the marker at all times; grows to 64 px while fading out from 21.4 s. |
| `sfx/tick.wav` | source | scenes 1, 2, 4 | Bundled library or Openverse via `/media-use resolve --type sfx`; license into SOURCES.md. |
| `sfx/whoosh-short.wav` | source | scene 2 | Same source rule as `sfx/tick.wav`. |
| `sfx/rising-tone.wav` | source | scene 3 | Same source rule as `sfx/tick.wav`. |
| `sfx/bell-soft.wav` | source | scene 3 | Same source rule as `sfx/tick.wav`. |
| `sfx/impact-clean.wav` | source | scene 4 | Same source rule as `sfx/tick.wav`. |
| `sfx/bubble-pop.wav` | source | scene 5 | Same source rule as `sfx/tick.wav`. |
| `sfx/motif-3-notes.wav` | source | scene 6 (motif) | Bundled library; if no fitting sound exists, create in code (see section 6, item 7). |
| `assets/fonts/Inter-Medium.ttf` | source | weight 500 | Inter, SIL Open Font License 1.1. Source and mapping rule below. |
| `assets/fonts/Inter-SemiBold.ttf` | source | weight 600 | Same source, license, and mapping rule. |
| `assets/fonts/Inter-Bold.ttf` | source | weight 700 | Same source, license, and mapping rule. |
| `assets/fonts/Inter-ExtraBold.ttf` | source | weight 800 | Same source, license, and mapping rule. |

- **Budget for paid generation:** €0, use none. No image generation, no paid TTS, no paid music, no paid SFX.
- **Fonts:** the four Inter files above, local to the project; nothing is fetched at render. Source: the official Inter 4.0 release, `https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip` (the static files in its `extras/ttf/` folder), or the static files of the official Google Fonts family download. Unzip into an empty scratch directory outside the project and copy only the four named files. Mapping rule: accept a file whose name starts with `Inter-` or `Inter_` (not `InterDisplay`) and ends in `-Medium.ttf`, `-SemiBold.ttf`, `-Bold.ttf`, or `-ExtraBold.ttf`; an optical-size infix such as `_18pt` is allowed; copy it under the name in the table. Never use a variable, italic, or Display file. If a file cannot be obtained, stop and report; do not substitute another family.
- **Creation orders** for each `code:` asset: the exact geometry in the scene blocks of section 5 and in this table; draw with SVG and GSAP; no external images.

## 8. Technical execution

- **Workflow:** `/general-video`, because the concept is fully specified (scenes, timings, copy, SFX cues) and needs no preset look. `/motion-graphics` is not used because the piece has six scenes, a reveal, and a source-number explanation. `flow: automation`, `storyboard: no` (autonomous; the internal QA passes in section 9 still apply).
- **Skills to load as needed:** `/hyperframes-core` (composition contract), `/hyperframes-animation` (eases, reveal, stillness), `/hyperframes-audio` (SFX levels only; no music bed), `/media-use` (SFX resolve, `--type sfx`), `/hyperframes-cli`. Not needed: `/hyperframes-keyframes` (the only zoom is a 3× scale on one group, which GSAP handles) and `/hyperframes-registry` (no registry block is required; load it only if you adopt the optional `transitions-push` candidate from step 0.6).
- **Animation approach:** GSAP paused timeline registered as `window.__timelines["<id>"]`, where the key is the root element's `data-composition-id` as `init` writes it (check it in step 1; the key must match). Hand-authored SVG for all shapes. No Three.js. Seeded PRNG for any randomness (none expected). No `fetch`, no live data at render time.
- **Push transition:** hand-authored as specified in scene 3 (Transition out). It is the default. The optional candidate `transitions-push` (step 0.6) may replace it only if its vertical 0.3 s push matches that spec; log which one was used.
- **Candidate blocks and effects:** none required. Optional candidate: `transitions-push` (step 0.6).
- **Media integration:** no footage, no video layers, no media effects. The logo is an image layer (or the stand-in text). Audio is the SFX track only.
- **Output:** `npx hyperframes render` with the quality tier and the output option verified in step 0 (the flag names differ by version; use the highest tier the installed version offers). Output file: `renders/kuechenchemie-nudelwasser-v1-portrait.mp4`, inside the project directory.

## 9. Quality and delivery

**Order of work and gates**
1. **Story pass (before detail):** block every scene with placeholder shapes in final positions and final copy. Run `npx hyperframes snapshot` at each scene midpoint and check: the hook reads at 3 s, each scene has an action and a consequence, the story is clear with sound off.
2. **Sound pass:** place SFX on their visual events (section 6). Music: none.
3. **Detail pass:** full look, motion, transitions (section 4 and section 5).
4. **Technical gates:** `npx hyperframes lint` and `npx hyperframes check` with zero errors. Fix warnings that affect text occlusion or contrast.
5. **Frame review:** snapshots at 0.0 s (first frame), at the scene midpoints (1.5, 5.5, 11.0, 16.5, 21.0, 24.0 s), at the transition midpoint (13.85 s), and the last frame (25.0 s). Compare them to section 5.
6. **Draft render review:** watch the whole render with sound. Check the acceptance criteria below.
7. **Final render**, then verify the file with ffprobe: 1080×1920, 30 fps, duration 25 ±1 s, H.264, AAC audio stream present.

**Acceptance criteria (all must pass)**
- The first frame is the hook frame (section 2); the question is readable without sound.
- Every on-screen text is visible long enough to read (at least about 1 s per 3–4 words), inside the safe areas, not occluded, AA contrast.
- Every on-screen text matches section 5 exactly; line breaks follow the ` / ` marks.
- SFX land on their visual events within ±2 frames.
- No scene is a static slide: each has the action and consequence in section 5.
- The thermometer is planted in scene 1, climbs in scene 3, is zoomed in scene 4, is shown to scale in scene 5, and returns in scene 6.
- Logo, colors, and fonts match section 4 exactly; accent color appears only in the places listed in section 4, rule 2; no invented UI and no claim beyond Appendix B.
- The hook's question is answered at 14.0 s and the explanation runs 19–23 s.
- Duration is 25 s within ±1 s; resolution and fps match section 3.

**Revision priority** when something fails: opening → development → resolution → brand effect. Fix the highest-priority failure first, then re-check every affected scene.

**Iteration budget and stop criteria**
- At most 3 full review cycles (steps 5–6) and 4 draft renders; one final render (+ one re-render if a delivery check fails).
- Change one thing per fix where possible; use absolute targets ("subtext 52 px"), not relative nudges.
- Stop and report instead of looping when the budget is used up, the same failure survives two fix attempts, or a fix would need a decision outside this brief (a new claim, a paid asset, a changed story). A missing logo is not a stop: drafts use the stand-in, and the final render waits for the file (see "Questions to the user").

**Source check (done at planning, 2026-10-20):** Appendix B #1 and #2 were fetched and read. If a URL cannot be reached at render time, do not change the copy; log it and list it under "Not verified".

**Deliverables** in `video/kuechenchemie-nudelwasser/`
- `renders/kuechenchemie-nudelwasser-v1-portrait.mp4`
- the editable HyperFrames project (sources, `BRIEF.md`, `frame.md`, `production-prompt.md`, assets)
- `SOURCES.md`: claim evidence (Appendix B), asset licenses (Inter OFL 1.1, each SFX file, the user's logo), voice: none
- `PRODUCTION-LOG.md`: environment versions, verified or replaced names, every deviation with its reason (including the logo stand-in, if used), the commands run and their results (lint, check, snapshot list, ffprobe output), review findings per cycle, known limitations
- Do not claim a check you did not run. If something could not be verified, list it under "Not verified".

## Appendix A: BRIEF.md

```markdown
---
workflow: general-video
flow: automation
storyboard: no
message: "Salz im Nudelwasser verändert den Siedepunkt nur minimal; an der Kochzeit ändert das kaum etwas."
destination: instagram-reels
aspect: 1080x1920
language: de
audience: "deutschsprachige Follower eines Küchenchemie-Accounts, die beim Kochen Wissenschaft mögen"
length: 25s
narration: no
---

## Intent

A 25-second quiz video for the Instagram account "Küchenchemie": "Salz ins Nudelwasser: Kocht es schneller?" The viewer sees the question, two answer tiles ("Ja, schneller" / "Kaum spürbar"), a thinking time with a rising thermometer, the reveal "Kaum. Der Effekt ist winzig.", and the source number (0,5 °C at 29,2 g salt per kg water). Tone: dry, mildly playful, factual. Confirmed by the user; build from production-prompt.md sections 1–9, which this project keeps as the detailed plan.

## Assets

- assets/kuechenchemie-logo.png — user's own square logo (1080×1080), end lockup in scene 6; if it is missing, use the stand-in from production-prompt.md section 4 and log it
- sfx/*.wav — bundled SFX (see production-prompt.md section 6)
- assets/fonts/Inter-*.ttf — Inter weights 500, 600, 700, 800 (see production-prompt.md section 7)

## Customizations

- Quiz pause: no countdown; the answer tiles wobble one at a time, then the thermometer climbs over 4 s.
- Hold at 100 °C for 0.5 s before the reveal (deliberate stillness).
- Zoom reveal on the thermometer from 100,0 °C to 100,5 °C (labeled range 100–101 °C), then the honest 0–100 °C mini-scale in scene 5 shows the same 0,5 °C step as a few pixels.
- Hand-authored vertical push between scenes 3 and 4 (0.3 s), unless the registry candidate matches the spec.
- Three-note sound motif at the close, created in code if no bundled sound fits.

## Notes

- Confirmed brief; do not re-interview. The detailed plan is in production-prompt.md (copy it into the project root).
- No music, no voiceover, no paid generation, no paid services.
- Do not claim a cooking-time effect or a pasta-cooking effect beyond "kaum spürbar" and "winzig"; use only Appendix B #1 and #2.
- Only German on-screen text; no English copy.
```

## Appendix B: Sources

| # | Claim or fact used in the video | Evidence |
|---|---|---|
| 1 | Salt raises the boiling point of water by 0.5 °C at 29.2 g of salt per kg of water (scene 5: "Der Siedepunkt steigt um 0,5 °C bei 29,2 g Salz pro kg Wasser") | https://van.physics.illinois.edu/ask/listing/1457 (answer dated 2007-10-22; fetched 2026-10-20) |
| 2 | Salt barely changes the cooking speed: copy "Kaum." / "Der Effekt ist winzig." and the answer tile "Kaum spürbar" (not "nicht"). Inference, not a stated claim: derived from #1 and from https://www.sonomamag.com/?p=54935 (fetched 2026-10-20), which states a rise of about 1 °F (about 0.5 °C) for a typical amount of salt and says that in practice salt does not speed cooking because one is unlikely to use enough to matter; "barely noticeable" is our reading of that, not a quote. The quoted English is from the fetch result; the German copy is a translation. | derived from #1 and https://www.sonomamag.com/?p=54935 (fetched 2026-10-20) |

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
  display: { fontFamily: "Inter", px: 72, weight: 800, lineHeight: 1.0, tracking: "-0.02em" }
  question-small: { fontFamily: "Inter", px: 56, weight: 800, lineHeight: 1.0, tracking: "-0.02em" }
  reveal: { fontFamily: "Inter", px: 180, weight: 800, lineHeight: 1.0 }
  tile: { fontFamily: "Inter", px: 72, weight: 700, lineHeight: 1.1 }
  body: { fontFamily: "Inter", px: 52, weight: 500, lineHeight: 1.25 }
  label: { fontFamily: "Inter", px: 40, weight: 600, lineHeight: 1.2, tracking: "0.04em", upper: false }
---

## Overview
A flat, quiz-style frame: one dark green ground, one mustard accent, white text. The accent is reserved for the answer tiles, the mercury bar, the zoom step marker, the reveal word, and the mini-scale step. The account's brand colors are strict; no gradients, glow, or shadows. The logo file is used as supplied.

## Do's and Don'ts
- Do: one accent color, used only in the places listed above; hairlines of 3 px; flush-left display type at x 176.
- Don't: gradients, glow, drop shadows, a third hue, stock imagery, invented UI, countdowns.
```
