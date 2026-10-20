# Validation notes: motion-video-planner, scenario 2 (briefing only, quiz)

Date: 2026-10-20. Plan dir: `/Users/silvio/Documents/Projekte/skills/tests/motion-video-planner/validation/2-briefing-quiz/`. Skill under test: `/Users/silvio/Documents/Projekte/skills/skills/motion-video-planner/SKILL.md`. No skill file was modified. Nothing was rendered, installed, or sent to a paid service.

## Question count

- 5 of 10 used: 4 interview questions (Q1 length, Q2 voice, Q3 tone, Q4 music) and 1 reserved concept-selection question (Q5). All answers are SIMULATED and logged in `decisions.md`.
- Budget not exhausted; 5 remain unused.

## References loaded and when

| Reference | When loaded | Notes |
|---|---|---|
| `references/context-discovery.md` | Phase A, before any work | Briefing mode (A8) used. Inventory script not run (repository only). |
| `references/interview.md` | Phase B, before the first question | |
| `references/creative-principles.md` | Phase C, before concepts | Whole file read. |
| `references/occasions.md` | Phase C, before concepts | Whole file read; only the "Knowledge quiz" section applied. |
| `references/style-kit.md` | Phase C (look per concept) | Whole file read (23 KB); only Swiss/Editorial, Kinetic Typography, Neo-Brutalism and Wireframe-type rules used. |
| `references/concepts.md` | Phase C | |
| `references/hyperframes-facts.md` | Phase C (feasibility), then Phase D | Read once before concepts. |
| `references/production-prompt-template.md` | Phase D | |
| `references/quality-checklist.md` | Phase D, before the gate | |
| `references/example-production-prompt.md` | Not loaded | File does not exist (as instructed). |
| `scripts/check_prompt.py` | Phase D gate | |
| `scripts/inventory_repo.py` | Not run | Repository mode only. |

External facts: WebSearch and WebFetch were used (as allowed by the test brief). UIUC physics page fetched and read. The Live Science page was not readable (truncated, title only).

## check_prompt output (verbatim)

First run, before fixes:

```
ERROR  line 198: refers to the planning chat or files the executor lacks: | `sfx/whoosh-short.wav` | source | scene 2 | As above. |
ERROR  line 199: refers to the planning chat or files the executor lacks: | `sfx/rising-tone.wav` | source | scene 3 | As above. |
ERROR  line 200: refers to the planning chat or files the executor lacks: | `sfx/bell-soft.wav` | source | scene 3 | As above. |
ERROR  line 201: refers to the planning chat or files the executor lacks: | `sfx/impact-clean.wav` | source | scene 4 | As above. |
ERROR  line 202: refers to the planning chat or files the executor lacks: | `sfx/bubble-pop.wav` | source | scene 5 | As above. |
WARN   scene 5: 15 on-screen words in 4.0 s may be too fast to read

5 error(s), 1 warning(s)
```

Fixes applied: "As above." replaced by "Same source rule as `sfx/tick.wav`." (five rows). Scene 5 on-screen text shortened to 13 words ("Der Siedepunkt steigt nur um 0,5 °C/bei 29,2 g Salz pro kg Wasser").

Final run (command: `python3 .../check_prompt.py <plan-dir>/production-prompt.md --assets-root <plan-dir>`), exit code 0:

```
0 error(s), 0 warning(s)
```

Exit code: 0.

## Findings: where the skill was unclear, contradictory, missing, or forced a guess

### Briefing mode and production environment
1. **Production-environment check is repository-only.** context-discovery A3 item 8 (HyperFrames CLI, ffmpeg, skills) sits under the repository reading steps. A8 (briefing mode) does not mention it, but the context.md format requires a "Production environment" section. I checked with `command -v` (node, npx, ffmpeg, ffprobe) and did not run `npx hyperframes --version`, since that fetches a package. The skill should say how to probe in briefing mode without installing.
2. **Plan-dir location in briefing mode is ambiguous.** A7 says `video-plans/<date>-<slug>/` in the current working directory. If that directory is a git repository (as in this test), that writes into a repo the skill says it must never modify. The test brief overrode the location; the skill should name a rule for this case.
3. **Briefing mode has no rule for source fetching limits.** A1 says to record an unreadable source as an access gap, which I did for Live Science. There is no rule for how to proceed when the only source for a headline claim is unreadable.

### Brand and user-supplied assets
4. **No asset status fits a user-supplied file that is not present yet.** The statuses are `exists` (path verified now), `create`, `source` (fetched from a free or licensed source), and `generate`. The logo was supplied by the user but is not on disk. I used `source` with notes (own file, placed by the user before production). This is a forced guess. The check then does not verify it at all: check_prompt only verifies `exists` rows, so a missing logo passes the gate. Recommendation: add a `provided` status that is verified like `exists` and blocks production when missing, or have check_prompt verify `source` rows that name a local path.
5. **Raster logo vs. "prefer SVG".** hyperframes-facts §5 says prefer SVG logos. The user supplied a 1080×1080 PNG only. The skill gives no rule for a raster-only logo (minimum size, whether to vectorize, whether to ask). I wrote a minimum width of 320 px and clear space of 60 px myself.
6. **Font choice has no guidance.** style-kit and the template ask for a font with a license note, but the skill does not say how to pick one when the user has no preference. I chose Inter (SIL OFL) ad hoc and stated it as a planner default.

### Quiz format without viewer input
7. **Quiz guidance is good but incomplete.** occasions.md gives thinking time (3–6 s), an optional countdown, and resolution with "why", which I used. Missing: (a) how to place the correct answer so it does not become a tell (left/right, length); (b) how to show "options react" without implying the audience voted; (c) what a sound-off quiz needs (the question must be fully on screen, which I wrote as a rule of my own).
8. **Quiz reveal needs a number, and the skill's evidence rule is hard to satisfy here.** creative-principles §8 and quality-checklist §1.3 require each claim to be evidenced. The explanation I wanted ("salt does not make pasta cook faster") is an inference from the boiling-point fact, not a statement in the fetched source. The skill has no evidence status for "derived". I added "derived" as a status label in Appendix B, plus a conditional source gate in section 9 that replaces the wording if a second source is not found. The template has no slot for a conditional claim; it is a workaround.
9. **Live Science URL was only a search snippet.** The snippet said salt does not meaningfully speed up boiling, which is the most direct support for the claim. Because the page was truncated, the claim stays unverified. The skill's rule ("never invent figures; claim needs a source") holds, but the outcome is an open gate rather than a finished prompt.

### Workflow choice
10. **Contradictory route thresholds.** hyperframes-facts §2 says `/motion-graphics` is "usually under 10 s (up to ~30 s)". The template notes (section "Notes on filling the template") say "an unnarrated piece under about 15 s in /motion-graphics". For a 25 s unnarrated quiz, the two sources give different answers. I chose `/general-video` (the facts file's "use it for most prompts from this skill" line) and wrote the reason in section 8. Pick one threshold.
11. **Workflow name list in check_prompt.** WORKFLOWS includes names such as `faceless-explainer` and `slideshow` that the template does not mention. This is harmless but undocumented.

### Interview
12. **Platform given, format not.** "Instagram" fixes the platform but not 9:16 vs. 1:1 or Reels vs. feed. I stated the default (9:16) rather than asking; the skill's rule "never ask what the material answers" supports that, but its platform row still lists format as a question.
13. **Language rule vs. file language.** The skill says context.md is written in the conversation language, while the test brief asked for validation-notes in English. The concept and decision files were written in German content with English structure. Clarify which language applies to planning files when the test or user asks otherwise.

### check_prompt
14. **False positive on normal wording.** The chat-reference pattern `as above` (and `see above`) flags the ordinary English phrase "As above." in a table cell. I had to reword five rows. Either exempt table cells or narrow the pattern (for example `as above` only at line start, or `as discussed above`).
15. **Weak empty-section check.** `check_sections` errors only when a section is empty by the `and` of two tests, which means "no characters at all". A section with only a heading line passes. Low impact, but the intent in the code comment is not met.
16. **Inconsistent voiceover threshold.** check_prompt warns above 3.0 words/s for voiceover, while quality-checklist §1.5 says 2.3–2.8 words/s for German. A German explainer at 2.9 w/s passes silently in the script but fails the checklist.
17. **Source rows only checked for non-empty evidence.** An Appendix B row reading "derived" with any text passes. That is correct for the script's scope, but it means the evidence rule is enforced by judgment only.
18. **Sound-off text check is not automated.** The 3.5 words/s warning is per scene; there is no check that the question is on screen at the start.

### Process gaps (not skill bugs, but observed)
19. **Cold-read test not run.** quality-checklist §1.2 recommends a subagent cold read for important runs. Not done for this scenario; it would be the next check.
20. **Presentation to the user not done.** Phase D asks to present the path, summary, check results, risks, and how to start. The final reply to the requester contains this summary. No artifact was published.
21. **Concept text in concepts.md quotes the old scene-5 copy.** After the check fix, the production prompt has the shorter copy. The concept file is a planning document and was not re-edited.

## Summary of most important findings

1. Asset gate blind spot: a user-supplied logo that is not on disk can pass check_prompt (status `source` is not verified). Needs a `provided` status or verification.
2. check_prompt false positive: "As above." in a table cell fails the gate; the pattern needs narrowing.
3. Evidence for derived claims: no status or template slot for "derived" or conditional claims; the planner had to invent both.
4. Route threshold conflict: `/motion-graphics` at ~30 s (facts) vs. ~15 s (template notes); the 25 s quiz falls in the gap.
5. Briefing mode lacks a production-environment probe and a rule for writing into a repository-cwd.

## Post-run edit by the maintainer (2026-10-20)

After this run the skill gained the asset status `user` (supplied by the user, not present yet; checker warns until it exists). The user-supplied asset rows above were switched to `user`; nothing else in the prompt was changed.

## Revision v2 (after cold read)

Output: `production-prompt.v2.md` in this folder. The original `production-prompt.md` is untouched (md5 `b954781a692a5f005c67d852813ff153` before and after). No skill file was modified. Nothing rendered, installed, or sent to a paid service. The user answers stay SIMULATED (see decisions.md); no new questions were asked.

Second source fetched for the copy decision: https://www.sonomamag.com/?p=54935 (WebFetch, 2026-10-20). The fetch returned a summary with short quoted fragments, not the verbatim page. Its substance: salt raises the boiling point; a typical amount (about an ounce per quart) raises it about 1 °F; in practice salt does not speed cooking because one is unlikely to use enough salt to matter. Appendix B #2 says so and marks the quotes as coming from the fetch result.

### What changed, per reviewer defect

| # | Defect | Fix in v2 |
|---|---|---|
| 1 | Render approval contradicted "autonomous" | Section 0 uses the template's "Questions to the user" wording: draft renders pre-approved; one render question, before the final render. |
| 2 | Logo supplied by user, status wrong | Status `user`; stand-in defined (text "Küchenchemie", Inter 800, 84 px, centered in the 640 px logo box, logged as STAND-IN). Step 0 item 5 and the stop criteria no longer stop on a missing logo. |
| 3 | Source gate was a no-op; "Nein" overstated the source | Second source fetched and read. Copy changed: tile 2 "Nein, gleich" → "Kaum spürbar"; reveal "Nein." → "Kaum."; subtext "Der Effekt ist winzig." kept. Appendix B #2 rewritten with the source's wording. Gate section now says "done at planning". |
| 4 | SIMULATED in header vs "fully confirmed" in Appendix A | SIMULATED kept only in the header blockquote as test provenance. Removed from section 6 and from the video. Appendix A now says "Confirmed by the user". |
| 5 | Pot #E8B931 vs accent rule | Pot is a 3 px white outline (no fill). Accent rule 2 lists every accent use: tiles, mercury bar, zoom step marker, reveal word, mini-scale step tick. |
| 6 | Scene 6 logo overlapped name | Logo box y 640–1280 (centered at y 960); name box y 1368–1433. Gap 88 px, which is ≥ the 60 px clear space. |
| 7 | Scene 3 tiles covered mercury bar | Tiles moved to x 176–1016 (x 176–949 after the 92 % scale). Bar at x 84–108, so 68 px clear. |
| 8 | Scene 3 bar ended 13.0 vs hold 12.5–13.0 vs bell 12.5 | Bar rises 8.5 → 12.5 s (4.0 s, matches rising-tone); bell and stop at 12.5 s; hold to 13.0 s; still to 13.7 s; push 13.7–14.0 s. |
| 9 | Rattle 0.6 s vs 0.0 s | Rattle is at 0.8 s everywhere (scene 1, transitions line). Hook lines at 0.0 / 0.2 / 0.4 s. |
| 10 | "Salz ins Nudelwasser:" at 120 px does not fit | Question at 72 px in three lines ("Salz ins / Nudelwasser: / Kocht es schneller?"); 56 px after the shrink. Longest line 821 px ≤ 840 px lane. |
| 11 | Subtexts, tick labels, markers without spec | Every text and marker now has size, weight, color, box. Scene 3 has no tick labels (they would collide with the question). |
| 12 | Scene 5 mini-scale range and marker start missing | Honest 0–100 °C mini-scale, x 176 → 1000 (8.24 px per °C). Marker starts at 100 °C (x 1000) and moves 4 px to 100,5 °C (x 1004). |
| 13 | "/" line-break convention unstated | Stated in section 4 (typography): never shown on screen. |
| 14 | Fonts not local files | Four Inter `.ttf` files under `assets/fonts/` with the Google Fonts download URL, loaded via `@font-face`; listed in section 7. |
| 15 | Question removal at 8.0 s not explicit | Question stays on screen (sound-off rule in occasions.md requires it through the thinking time). It leaves with the push, 13.7–14.0 s. |
| 16 | Output path inconsistent | `renders/kuechenchemie-nudelwasser-v1-portrait.mp4` in sections 8, 9 and deliverables. |
| 17 | `--skill=` conditional | Removed. Workflow comes from BRIEF.md; init runs without a skill flag. |
| — | Easing rule vs scenes | Rule 5 restated (entrances `power3.out`; `expo.out` only on the reveal word; moves `sine.inOut`; overshoot only on the pot). Every scene's easing was checked against it and changed where it differed. |
| — | Scene 4 zoom scaled labels | Labels and reveal word are outside the zoom group and do not scale. The 4 % push-in was removed (camera static); the zoom is an element move. |
| — | `transitions-push` inconsistent | One transition only, 13.7–14.0 s; direction to be verified with the catalog, with a logged fallback. |

Other changes made while fixing these: the scene 5 explanation is now a 13-word copy with three lines; SFX ticks moved (scene 2 tick 4.0 s, whoosh 3.5 s); hairlines 3 px (were 4 px); bubble sized (40 → 64 px); holds named per scene; BRIEF Notes and Customizations and the frame.md display size (72 px) updated to match.

### Consistency-pass arithmetic

Text widths: estimated as characters × size × factor (0.6 for weights 600–800, 0.55 for weight 500), against the 840 px text lane (x 176–1016). The factor for weight 600 is not in the checklist; 0.6 was used as the conservative value.

| Text | Size / weight | Est. width | Fits 840? |
|---|---|---|---|
| "Salz ins" | 72 / 800 | 346 px | yes |
| "Nudelwasser:" | 72 / 800 | 518 px | yes |
| "Kocht es schneller?" | 72 / 800 | 821 px | yes (19 px margin) |
| "Kocht es schneller?" (shrunk) | 56 / 800 | 638 px | yes |
| "Ja, schneller" (tile) | 72 / 700 | 562 px | yes (tile text box 760 px) |
| "Kaum spürbar" (tile) | 72 / 700 | 518 px | yes |
| "Kaum." (reveal) | 180 / 800 | 540 px | yes |
| "Der Effekt ist winzig." | 52 / 500 | 629 px | yes |
| "Der Siedepunkt steigt" | 52 / 500 | 601 px | yes |
| "um 0,5 °C bei 29,2 g" | 52 / 500 | 572 px | yes |
| "Salz pro kg Wasser" | 52 / 500 | 515 px | yes |
| "100,5 °C" (scene 4 label) | 72 / 800 | 346 px | yes |
| "100,5 °C" (mini-scale label) | 40 / 600 | 192 px | yes |
| "Küchenchemie" (stand-in in 640 box) | 84 / 800 | 605 px | yes (box 640) |
| "Küchenchemie" (name) | 52 / 600 | 374 px | yes |

Vertical extents (safe zone y 270–1540; side inset 64 px; text lane x 176–1016):

| Scene | Elements and y extents | Check |
|---|---|---|
| 1 | question 420–636; pot 964–1360; thermometer line 300–1500 | inside safe zone; no overlap |
| 2 | question 300–468; tile 1 760–960; tile 2 1020–1220 | gap 292 px between question and tiles |
| 3 | question 300–468; "Denk kurz nach." 500–548; tiles 776–960 and 1036–1220 (after scale); bar 420–1500 at x 84–108 | tiles start at x 176, 68 px right of the bar |
| 4 | "Kaum." 360–540; subtext 600–665; "100,5 °C" 844–916; "100,0 °C" 964–1036; step 877–883 (x 64–160) | zoom ticks at 880 and 1000 match the label centers; no overlap |
| 5 | explanation 620–815; "100,5 °C" label 1120–1160; scale 1200; "100 °C" and "0 °C" labels 1250–1290; bubble at most 1168–1232 | bubble clears both label bands |
| 6 | logo 640–1280; name 1368–1433; thermometer at 20 % at x 96 | gap 88 px ≥ 60 px clear space; name ends above 1540 |

Timing sums and sync points: scene durations 3+5+6+5+4+2 = 25 s. Bar 8.5 + 4.0 = 12.5 s; hold to 13.0 s. Push 13.7–14.0 s ends at the scene 4 start. Zoom 14.5 + 0.6 = 15.1 s. Marker stop 20.6 + 0.8 = 21.4 s (bubble). Wobbles 4.5 + 0.3k for k = 0…10, last one ends 7.8 s. Tile 2 lands 3.6 + 0.4 = 4.0 s (tick). Logo idle 23.7 + 1.3 = 25.0 s. Scene 5 lines end 19.2 + 0.35 = 19.55 s.

Rule check: accent appears only in the rule 2 places (scenes 2–5). Every line is 3 px except the listed exceptions. Each scene's easing matches rule 5.

Contrast: white on #1F3D2B 11.9:1; #1F3D2B on #E8B931 6.5:1.

On-screen words per second: scene 1 2.0; scene 2 2.0; scene 3 1.5; scene 4 1.0; scene 5 3.25; scene 6 0.5. Scene 5 is under the checker's 3.5 ceiling but above the checklist's voiceover target (2.3–2.8). Silent text has no target.

### check_prompt.py output (verbatim)

Command: `python3 /Users/silvio/Documents/Projekte/skills/skills/motion-video-planner/scripts/check_prompt.py /Users/silvio/Documents/Projekte/skills/tests/motion-video-planner/validation/2-briefing-quiz/production-prompt.v2.md --assets-root /Users/silvio/Documents/Projekte/skills/tests/motion-video-planner/validation/2-briefing-quiz`

```
WARN   asset assets/kuechenchemie-logo.png: supplied by the user and not present yet; production must stop before the final render until it arrives

0 error(s), 1 warning(s)
```

Exit code: 0. The warning is the expected `user` logo warning.

### Skill instructions that were still unclear or missing

1. **Honest scale versus zoom reveal.** occasions.md says "no truncated axes that exaggerate", but a zoom reveal on a tiny difference is a truncated axis by design. The skill has no rule for it. We used a labeled 100–101 °C zoom, then the honest 0–100 °C scale in the next scene. A rule is needed.
2. **Where the question goes at the reveal.** occasions.md requires the question and options on screen for the whole thinking time, but says nothing about when they leave. The template has no field for it. We set the exit at the push (13.7 s).
3. **Width factor for weights 500 and 600.** The checklist gives only bold (0.6) and regular (0.55). We used 0.6 for 600 and 0.55 for 500.
4. **Reading-speed target for silent text.** The checker warns above 3.5 words/s. The checklist sets targets for voiceover only. No target is stated for on-screen text without voice.
5. **Checker does not verify `source` assets.** Font files and SFX are `source` rows and are not checked, so the executor has to check them in step 0.
6. **Template step 1 `--skill=` conditional.** "add `--skill=…` if your CLI supports it" leaves the executor to decide. We removed it; the template should say which default applies.
7. **Template source-gate paragraph** (section 9) is written for an unverified claim. After verification there is no clean slot for "verified on date X"; the Appendix B evidence column is the only place.
8. **Transform details have no template fields.** Rotation origin, zoom origin, and non-scaling strokes had to be invented per element. The "full visual spec" rule implies them but does not list them.
9. **WebFetch returns summaries, not verbatim pages.** The skill has no rule for citing a fetched page when the tool paraphrases. We marked the quotes as fetch-result text.
10. **Cold read not repeated.** quality-checklist §1.3 makes a subagent cold read mandatory, with at most two rounds. It was not run for v2, because the request asked for the consistency pass only. It should be the next step on `production-prompt.v2.md`.
11. **concepts.md is out of date.** It still shows the v1 copy ("Nein, gleich", "Nein."). The prompt now says "Kaum spürbar" / "Kaum.". The planner should tell the user about the copy change, because the concept is otherwise still recognizable.
