# Production brief: WhisPaste „Das Fenster bleibt"

> Planned with motion-video-planner on 2026-10-20. Concept B: „Das Fenster bleibt, wo es ist", selected by the user (Question 5/10, SIMULATED). Timings are PLANNED; final timing follows the recorded dictation audio.

## 0. Start here

You are the production agent for a fully planned short social video. Story, copy, look, and timing are decided. Build them faithfully. Change something only when it is technically impossible or when a check in section 9 fails, and log every deviation in `PRODUCTION-LOG.md` with the reason.

**Working directory:** create the HyperFrames project at `/Users/silvio/Documents/Projekte/video/whispaste-social-b/`. **Product repository:** `/Users/silvio/Documents/Projekte/whispaste`, read-only; never write into it. **Assets** are listed in section 7 with paths relative to `/Users/silvio/Documents/Projekte/whispaste`, except the two user recordings and the SFX, which live in the project directory under `assets/`.

**Permissions and limits**
- Allowed: run `npx hyperframes …`; install the npm packages that HyperFrames and its skills need; run `ffmpeg`/`ffprobe` (present at `/opt/homebrew/bin`); create files inside the project directory.
- Not allowed without asking the user: installing system software or container runtimes (no Docker, no Colima, no Podman), `render --docker`, paid generation (budget is €0), `publish`, uploads, deploys, commits outside the project directory, and any edit to the product repository.
- Respect the harness's permission prompts; never work around a denial.

**Step 0 — Verify the environment (record the outputs in PRODUCTION-LOG.md)**
1. `node --version` (needs a current LTS; v26.7.0 was seen on the planning machine); `npx hyperframes --version` (the CLI was NOT on PATH at planning time, so it is installed through npx); `npx hyperframes doctor`.
2. Check that the HyperFrames skills are available (`/hyperframes` in your skill list). If they are missing, run `npx skills add heygen-com/hyperframes` and tell the user a session restart is needed. Stop there.
3. `npx hyperframes usage --json`, and note any limits.
4. `npx hyperframes render --help` and `npx hyperframes init --help`: confirm the flag names this brief uses (quality tiers, `--format`, `--fps`, `--resolution`). If a name differs, use the installed version's equivalent and log it.
5. Confirm every `exists` asset in section 7 is present (`ls`), and probe the two recordings with `ffprobe`.
6. Verify every registry block, transition, and media-effect name in this brief: `npx hyperframes catalog --query "<name>"` / `npx hyperframes media-treatment --capabilities --json`. This brief names no registry block; if you add one, verify it first.

If HyperFrames cannot run at all, stop and report. Do not build a substitute render engine.

**Step 1 — Scaffold and brief**
1. `npx hyperframes init /Users/silvio/Documents/Projekte/video/whispaste-social-b --resolution portrait` (add `--skill=general-video` if your CLI supports it).
2. Immediately write Appendix A verbatim to `/Users/silvio/Documents/Projekte/video/whispaste-social-b/BRIEF.md`, Appendix C verbatim to `/Users/silvio/Documents/Projekte/video/whispaste-social-b/frame.md`, and copy this file to `/Users/silvio/Documents/Projekte/video/whispaste-social-b/production-prompt.md`. Stage the section 7 assets into `assets/` of the project.
3. Invoke `/hyperframes`. It finds `BRIEF.md` and runs the workflow `general-video` with no brief questions. **This brief is confirmed by the user**: run no intent interview and no pitch round. The run is autonomous: post checkpoint summaries and continue.
4. When the workflow writes `STORYBOARD.md`, carry over section 5 scene by scene (copy verbatim, planned timings, scene purposes).

**Step 2 — Build in passes (see section 9 for the gates)**
Story and rough timing first (blocking pass, stills) → audio (dictation audio aligned, SFX) → re-time to the recordings → full design and motion → polish → checks → review → render.

**Render approval:** the user approves in advance the draft renders for internal review and the final delivery render once every acceptance criterion in section 9 passes. If your workflow still asks "render now, or what changes?", show the preview and ask exactly that once.

## 1. Goal and context

- **Product / topic:** WhisPaste is a free, open-source desktop app for macOS, Windows and Linux. Press a hotkey, speak, and the transcript is written at the cursor in the app you are using. Local speech recognition is the default; cloud providers are optional with the user's own key.
- **Audience:** people who write many messages on their own desktop (knowledge workers, developers, support staff). They recognize writing a short reply in mail or chat while the window stays where it is.
- **Core message (one sentence):** Du sprichst den Satz, und er steht an der Cursor-Position, ohne dass du das Fenster wechselst. (Evidence: Appendix B #1, #2.)
- **Intended effect:** the viewer thinks „so einfach?" and remembers that the window does not change. The viewer learns the app's name and that it works where the cursor is.
- **Goal priority:** reach → brand recall → conversion (conversion not targeted; the CTA is a brand close only).
- **Share trigger:** „simple solution": „Warum wusste ich das nicht?" · **Rewatch trigger:** the last line „Gewechselt hat nur der Text." re-reads the first title at the start.
- **CTA:** none in the action. Brand close only: logo, wordmark, and the URL `whispaste.de` on the last frame (Appendix B #5).
- **Limits:** do not claim speed multipliers, user counts, ratings, prices, or times saved. Do not show the Dock, the redesigned main window, Notes, the Dictionary or Snippets pages, audio import, or any other item of the CHANGELOG „Unreleased" section (not shipped). Do not claim that no data leaves the machine. Do not name competitors. Do not write the word „Spende" or any translation of it. The recording must not show real history entries or any personal data.

## 2. Story

- **Hook (0–3 s):** The first frame is the recording: an empty mail draft in a Mac window, the text cursor blinking in the body. The title „Ich wechsle nicht das Fenster." writes in word by word from 0.5 s to 2.5 s. Nothing moves except the cursor and the title. The situation (a writing window, a cursor, a claim about not switching) is clear by about 3 s without sound.
- **Visual thread:** the text cursor is the recurring element. It blinks in frame 1, is the place where the words land in scene 3, blinks in scene 5, and holds in the close.
- **Development:** scene 2 shows the dictation key press and the overlay coming up (the window does not change). Scene 3 shows the dictated sentence appearing word by word at the cursor, with captions. Scene 4 shows the overlay closing and the cursor resting after the text.
- **Climax:** scene 3, the sentence is complete in the mail body while the window frame does not change.
- **Resolution:** scene 5 answers the title with a deliberate stillness and the line „Gewechselt hat nur der Text." (EN: „Only the text moved.") The hook's promise (no window change) is paid off.
- **Close:** the logo lockup, the wordmark, and `whispaste.de`, then ambient idle (1–2 % breathing scale) on the logo until the end.
- **Tone:** calm, precise, a little dry; the joke is the smallness of the change. Avoid excitement words, exclamation marks, and any hard sell.

## 3. Format

- Duration (planned): 20 s (tolerance ±1 s; final duration follows the recordings).
- Resolution / aspect: 1080×1920 (9:16).
- Frame rate: 30 fps (no 60 fps: the motion is calm).
- Delivery: MP4 H.264 with AAC audio. No transparency.
- Variants: two, both 1080×1920, 20 s, identical picture and timing:
  - `whispaste-social-b-de` — German master: German dictation recording, German title and captions.
  - `whispaste-social-b-en` — English cut: English dictation recording, English title and captions.
- Safe areas (9:16, 1080×1920): top 270 px and bottom 384 px keep free of text and of the logo; sides 64 px. Text may sit between y=270 and y=1536.
- Sound-off: must work without sound. Title and captions carry the message; the hotkey click is decorative.

## 4. Look

- **Brand source of truth:** `assets/icons/logo-dark.svg` (logo), `assets/icons/4.0x/wordmark-dark.png` (wordmark), tokens in `/Users/silvio/Documents/Projekte/whispaste/design-tokens/primitives.tokens.json` and `semantic.dark.tokens.json`. The dark stage is the only mode for this video. Strict: colors and fonts below; no glass, no glow, no gradient.
- **Style:** Swiss/Editorial (dominant), flat. Rules:
  1. Flat color fields only; no drop shadows, no blur, no glow.
  2. One accent: amber (`#FFB547`) on the title keyword „Fenster" only (German) or „window" (English) and nowhere else.
  3. The window stays fixed: no scale, no pan, no tilt on the recorded Mac window other than the initial crop in scene 1 (static).
  4. Hairlines 2 px in `#3D4A66` (glacier.700) as the only structure, under the title and above the wordmark.
  5. Motion: entrances `power3.out` 0.35 s; exits `power2.in` 0.25 s; no bounce, no overshoot.
- **Palette:** ground `#0B122A` (navy.900, the page ground); band `#171D53` (navy.600, only behind the title block); title text `#F0F4FA` (frost.50); secondary text `#ABB8CC` (frost.200, captions); hairlines `#3D4A66`; accent `#FFB547` (amber.400, one word only); cyan `#6FDDF0` (cyan.300) only for the URL `whispaste.de`. Third hue: forbidden.
- **Typography:** display: Bricolage Grotesque Variable (`assets/` path: `/Users/silvio/Documents/Projekte/whispaste/website/public/fonts/bricolage-grotesque-latin-wght-normal.woff2`), weight 700, title size 84 px, line-height 1.02, tracking -0.02 em. Body and captions: Hanken Grotesk Variable (`/Users/silvio/Documents/Projekte/whispaste/website/public/fonts/hanken-grotesk-latin-wght-normal.woff2`), weight 500, caption size 46 px, line-height 1.3, tracking 0. URL: Hanken Grotesk 600, 40 px. Fallback is the system sans; no other font may be substituted. License: both are self-hosted by the website; confirm the license (expected SIL OFL) and record it in `SOURCES.md`.
- **Layout:** one focal element per frame. The recorded window is centered in the frame at full width minus 64 px margins (952 px wide, top edge at y=560 px). Title block: x=64, y=300, width 952 px, on the band colour. Captions: x=64, y=1180, width 952 px, two lines max, centered.
- **Contrast:** every text element meets WCAG AA against its ground: `#F0F4FA` on `#0B122A` and `#171D53` (above 4.5:1); `#ABB8CC` on `#0B122A` is above 4.5:1; `#FFB547` on `#171D53` is above 3:1 for the 84 px title. Verify with the check command.
- **Logo and product depiction:** the logo is `assets/icons/logo-dark.svg` at 320 px width, the wordmark `assets/icons/4.0x/wordmark-dark.png` at 560 px width (797×256 source, do not upscale). Minimum clear space 48 px. Never redraw or distort. The product is shown only as recorded: the mail draft window and the recording overlay. The overlay and the floating button are shipped features (README); the Dock is not (do not use it).
- **Motion character:** calm, continuous. Ambient idle (1–2 % breathing scale on the logo, the cursor blink) instead of frozen holds; one deliberate still in scene 5 of 0.8 s, motivated by the pause before the answer. Durations: entrances 0.35 s, exits 0.25 s, title word-by-word at 0.2 s per word.
- **Transitions:** hard cuts only, cut points on the recording's own events: cut 1 on the hotkey click (3.0 s), cut 2 at 12.0 s when the overlay has fully closed, cut 3 at 18.0 s on the answer's last word. No cross-fades between scenes.
- **Negatives:** no glow, no glass, no gradients, no stock photos, no lens flares, no third hue, no invented UI, no Windows elements, no Dock, no counters, no numbers, no roadmap features, no logo intro before scene 6, no fade from black at the start.

## 5. Timeline

All times are PLANNED and are re-timed to the recorded dictation audio in the audio pass. Scenes are contiguous.

| # | Start | End | Purpose | Voiceover (exact) | On-screen text (exact) |
|---|---|---|---|---|---|
| 1 | 0.0 | 3.0 | hook | — (recording: silent) | „Ich wechsle nicht das Fenster." |
| 2 | 3.0 | 6.0 | key press, overlay opens | — (hotkey click at 3.0 s) | — |
| 3 | 6.0 | 12.0 | dictation lands at the cursor | Recording (DE): „Hallo Maria, danke für die schnelle Antwort, ich schaue heute Nachmittag drauf." | captions, line-broken: „Hallo Maria, danke für die schnelle Antwort, / ich schaue heute Nachmittag drauf." |
| 4 | 12.0 | 15.0 | overlay closed, cursor rests | — | — |
| 5 | 15.0 | 18.0 | answer to the title | — | „Gewechselt hat nur der Text." |
| 6 | 18.0 | 20.0 | close | — | „whispaste.de" (only URL, cyan) |

### English cut (same timing; replaces the German copy in the table above)

| # | Voiceover (EN) | On-screen text (EN) |
|---|---|---|
| 1 | — (recording: silent) | „I don't switch windows." |
| 3 | Recording (EN): „Hi Maria, thanks for the quick reply, I'll look into it this afternoon." | captions, line-broken: „Hi Maria, thanks for the quick reply, / I'll look into it this afternoon." |
| 5 | — | „Only the text moved." |
| 6 | — | „whispaste.de" |

### Scene 1 (0.0–3.0 s): hook
- Composition: back to front: (1) ground `#0B122A` full frame; (2) recorded mail window, 952 px wide, top edge at y=560 px, centered; (3) title block at x=64, y=300, band `#171D53` behind, title text `#F0F4FA`, the word „Fenster" in `#FFB547`; (4) hairline `#3D4A66` 2 px, x=64 to x=1016, at y=520.
- Assets: `assets/recording-de.mov` (German cut) or `assets/recording-en.mov` (English cut), scene 1 frames 0.0–3.0 s, cropped to the mail window.
- Action: frame 0 is the empty mail draft with the cursor blinking. At 0.5 s the title starts; each word enters at 0.2 s intervals (the title has 5 words in DE and 4 in EN: „I don't switch windows."). The title is complete by 2.5 s (DE) and 2.0 s (EN). The cursor keeps blinking through the scene.
- Camera: static.
- Motion/easing: title words: opacity 0 → 1 and y 12 px → 0, 0.35 s, `power3.out`, word offset 0.2 s. Hairline: scaleX 0 → 1, 0.4 s, `power2.out`, at 2.5 s.
- Transition out: hard cut on the hotkey click at 3.0 s.
- Audio cues: silence to 2.9 s; hotkey click SFX at 3.0 s, from the recording.

### Scene 2 (3.0–6.0 s): key press, overlay opens
- Composition: the recorded mail window stays in place; the overlay (from the recording, bottom centre of the window area) appears at 3.1 s. No title; no caption.
- Assets: `assets/recording-de.mov` (or EN) frames 3.0–6.0 s.
- Action: at 3.0 s the hotkey is pressed (click), the overlay with the live waveform opens inside the window area; the cursor stays where it was. The window itself does not change.
- Camera: static.
- Motion/easing: none added in code; the overlay animation is what the recording shows.
- Transition out: cut at 6.0 s into the dictation (scene 3), no fade.
- Audio cues: hotkey click at 3.0 s (from the recording); no other SFX.

### Scene 3 (6.0–12.0 s): dictation lands at the cursor
- Composition: the recorded window; the sentence appears in the mail body at the cursor (from the recording). Captions over the window's lower third at y=1180 px, `#ABB8CC`, 46 px Hanken Grotesk 500, two lines, centered, timed to the word timestamps.
- Assets: `assets/recording-de.mov` (or EN) frames 6.0–12.0 s; captions from word timestamps of the dictation audio (`assets/dictation-de.json` or `assets/dictation-en.json` produced by the audio pass with the same word list as section 5).
- Action: the dictated words appear in the mail body one by one, in the recording; the captions appear word by word in sync, each caption line holds until its last word plus 0.2 s. The sentence is complete at about 11.2 s; the cursor is at the end of the sentence.
- Camera: static.
- Motion/easing: caption lines fade in 0.2 s `power2.out` per line; no motion on the window.
- Transition out: cut at 12.0 s.
- Audio cues: the dictated speech is the recording's own audio (no voiceover track added); no music.

### Scene 4 (12.0–15.0 s): overlay closed, cursor rests
- Composition: the recorded window; the overlay has closed by 13.6 s (fully out by 13.6 s; at 13.6 s the cursor is the only moving element). No captions after 12.2 s.
- Assets: `assets/recording-de.mov` (or EN) frames 12.0–15.0 s.
- Action: overlay closes (recording); the cursor blinks at the end of the sentence; the hold is ambient.
- Camera: static.
- Motion/easing: hold with the cursor blink only (step 0.5 s on, 0.5 s off).
- Transition out: cut at 15.0 s on the next title.
- Audio cues: quiet room tone from the recording; no SFX.

### Scene 5 (15.0–18.0 s): answer to the title
- Composition: the recorded window stays visible at the same position as in scene 4, with a title block at x=64, y=300 (band `#171D53`) over the top of the frame.
- Assets: still frame from `assets/recording-de.mov` at 15.0 s, held (or the same recording, paused, with the cursor blink as the only motion).
- Action: at 15.0 s the title „Gewechselt hat nur der Text." (EN: „Only the text moved.") appears word by word, 0.2 s per word; the word „Text" (EN: „text") is in `#FFB547`. At 16.6 s a deliberate still of 0.8 s (only the cursor blinks), then the window is unchanged to 18.0 s. The point of the scene is that the window is the same.
- Camera: static.
- Motion/easing: title words as in scene 1 (`power3.out`, 0.35 s per word, 0.2 s offset). Deliberate still 16.6–17.4 s. No other motion.
- Transition out: cut at 18.0 s on the logo.
- Audio cues: none; silence for the 0.8 s still.

### Scene 6 (18.0–20.0 s): close
- Composition: ground `#0B122A`; logo `assets/icons/logo-dark.svg` at 320 px width, centered at y=760 px; wordmark `assets/icons/4.0x/wordmark-dark.png` at 560 px width, centered at y=1000 px; URL „whispaste.de" at y=1180 px in `#6FDDF0`, 40 px Hanken Grotesk 600.
- Assets: `assets/icons/logo-dark.svg`, `assets/icons/4.0x/wordmark-dark.png`.
- Action: logo fades in 0.35 s `power3.out` at 18.0 s; the wordmark follows at 18.3 s; the URL at 18.6 s. From 19.0 s the logo idles: breathing scale 1.00 → 1.02 → 1.00 over 2.0 s, `sine.inOut`, until the end.
- Camera: static.
- Motion/easing: logo fade-in 0.35 s `power3.out`; wordmark and URL fade-in 0.35 s `power3.out`; breathing idle `sine.inOut`, 1.00 → 1.02 → 1.00 over 2.0 s, looping from 19.0 s to the end.
- Transition out: none (end of video).
- Audio cues: none.

## 6. Audio

- **Voiceover:** no. The dictated speech is the recording's own audio; no TTS is generated. Pronunciation is the speaker's own.
- **Full dictation scripts** (verbatim, from the recordings; the executor aligns word timestamps in the audio pass):
  - DE: „Hallo Maria, danke für die schnelle Antwort, ich schaue heute Nachmittag drauf."
  - EN: „Hi Maria, thanks for the quick reply, I'll look into it this afternoon."
- **Pronunciation:** none to add; if the recording is unclear, the executor stops and reports (no TTS replacement).
- **Music:** none. Reason: calm sound-off piece, budget €0, no licensed track supplied.
- **Sound effects:**
  1. `sfx/hotkey-click` — a short, dry key click, length 0.12 s, sync point at 3.0 s (scene 2 start); source: the bundled library or Openverse via `/media-use resolve --type sfx` (no account needed); record the license per file in `SOURCES.md`. If the recording already contains the hotkey click at 3.0 s, use the recording's click and do not add the SFX.
- **Sound motif (recurring element):** none; the cursor is visual only.
- **Captions:** burned in, yes. Style: Hanken Grotesk 500, 46 px, `#ABB8CC`, two lines max, centered at y=1180 px, max 34 characters per line, at most 17 characters per second (the DE caption runs 13 cps over 6 s). Captions come from word timestamps; they must not collide with the title block (title only in scenes 1 and 5, captions only in scene 3).
- **Silence:** the piece has no music; scenes 1, 4 and 5 are quiet (room tone from the recording only).

## 7. Assets

Base path: `/Users/silvio/Documents/Projekte/whispaste`

| Path | Status | Use | Notes |
|---|---|---|---|
| `assets/icons/logo-dark.svg` | exists | end lockup, scene 6 | dark variant; 320 px width; never redrawn |
| `assets/icons/4.0x/wordmark-dark.png` | exists | wordmark, scene 6 | 797×256 px source; 560 px width; do not upscale |
| `website/public/fonts/bricolage-grotesque-latin-wght-normal.woff2` | exists | display type (title) | variable font; license to be recorded in `SOURCES.md` |
| `website/public/fonts/hanken-grotesk-latin-wght-normal.woff2` | exists | body, captions, URL | variable font; license to be recorded in `SOURCES.md` |
| `design-tokens/primitives.tokens.json` | exists | colour values in section 4 | read-only reference |
| `assets/recording-de.mov` | user | scenes 1–5, German cut | user recording of the macOS app (not made by the executor): empty mail draft, hotkey press, overlay with live waveform, the German dictation sentence, the overlay closing; only the overlay, the floating button, and the cursor are visible; no real history, no personal data, no Dock. If missing, stop and ask the user; do not substitute a mock. Put the file in the project's `assets/` folder. |
| `assets/recording-en.mov` | user | scenes 1–5, English cut | user recording with the English dictation sentence, same framing and timing as the German one (±0.2 s); if missing, stop and ask the user. |
| `assets/dictation-de.json` | create | caption timing, German | word timestamps produced by the audio pass from `assets/recording-de.mov` (the executor generates this from the file; no external service) |
| `assets/dictation-en.json` | create | caption timing, English | word timestamps produced by the audio pass from `assets/recording-en.mov` |
| `sfx/hotkey-click` | source | scene 2 hit at 3.0 s | bundled library or Openverse via `/media-use resolve --type sfx`; license into `SOURCES.md`; not needed if the recording's own click is used |

- **Budget for paid generation:** €0, use none.
- **Fonts:** the two woff2 files above are the only fonts. Fallback: the system sans. No other family may be substituted.
- **Creation orders:** the two recordings are made by the user before production starts; the executor does not create them. The two dictation JSON files are produced by the audio pass with `ffprobe`/the registered audio tooling available in the workflow; if no word-timestamp tool is available, use the scripted sentence and fixed timings from section 5 and log it as a deviation.

## 8. Technical execution

- **Workflow:** `/general-video`, because the concept is fully specified and the look must not be replaced by a preset; `flow: automation`, `storyboard: no` (autonomous; the internal QA passes in section 9 still apply).
- **Skills to load as needed:** `/hyperframes-core` (composition contract), `/hyperframes-animation` (title word timings), `/hyperframes-audio` (SFX level), `/media-use` (SFX resolve only), `/hyperframes-cli`.
- **Animation approach:** GSAP paused timeline registered on `window.__timelines`; no Three.js; no random layout; no live data, no fetch at render.
- **Candidate blocks and effects:** none required. Hand-author the title and captions; if a named effect is used, verify it first with `npx hyperframes catalog --query "<name>"`.
- **Media integration:** the two recordings as video layers with their own audio (`data-has-audio`), cut to the scene windows in section 5; captions from `assets/dictation-*.json`; the cursor blink as a CSS keyframe.
- **Output:** `npx hyperframes render --help` first, then one render command per variant with the verified flag names, output files `renders/whispaste-social-b-de-v1.mp4` and `renders/whispaste-social-b-en-v1.mp4`.

## 9. Quality and delivery

**Order of work and gates**
1. **Story pass (before detail):** block every scene with placeholder shapes in the final positions and the final copy. Run `npx hyperframes snapshot` at each scene midpoint and check: the hook reads by about 3 s, each scene has an action and a consequence, the story is clear with sound off. Fix the story before styling.
2. **Audio pass:** align the dictation word timestamps to `assets/recording-de.mov` and `assets/recording-en.mov`; re-time scenes to the spoken cues; place the SFX on the hotkey click only.
3. **Detail pass:** full look, title motion, captions, safe areas.
4. **Technical gates:** `npx hyperframes lint` and `npx hyperframes check` with zero errors. Fix warnings that affect text occlusion or contrast.
5. **Frame review:** snapshots of every scene midpoint, every cut point, the first frame, and the last frame. Compare them to section 5.
6. **Draft render review:** watch the whole render with sound. Check the items below.
7. **Final render**, then verify the file (ffprobe, step 8).

**Acceptance criteria (all must pass)**
- The first frame is the hook frame from section 2; the situation is understandable by about 3 s without sound.
- Every on-screen text is visible long enough to read (at least about 1 s per 3–4 words), inside the safe areas, not occluded, AA contrast.
- The dictation audio is complete and not clipped; the captions match the spoken sentence verbatim and are in sync within ±2 frames.
- The hotkey click lands on frame 3.0 s ±2 frames.
- No scene is a static slide: scene 3 shows the text landing at the cursor; scene 2 shows the overlay opening; scene 5 has the deliberate still.
- The recurring element (cursor) appears as specified: frame 1, scene 3, scene 5, close.
- Logo, colors, and fonts match section 4 exactly; no invented UI, no Dock, no Windows elements, no numbers, no claims beyond Appendix B.
- The hook's promise (the window does not change) is paid off by the resolution in scene 5.
- Duration is 20 s within ±1 s; resolution 1080×1920; 30 fps; MP4 H.264 with one AAC stream (verify with `ffprobe`).

**Revision priority** when something fails: opening → development → resolution → brand effect. Fix the highest-priority failure first, then re-check every affected scene.

**Iteration budget and stop criteria**
- At most 3 full review cycles (steps 5–6) and 4 draft renders; one final render per variant (+ one re-render if a delivery check fails).
- Change one thing per fix where possible; use absolute targets ("title 84 px"), not relative nudges.
- Stop and report instead of looping when the budget is used up, when the same failure survives two fix attempts, when a recording is missing, or when a fix would need a decision outside this brief (a new claim, a paid asset, or a changed story).

**Deliverables** in `/Users/silvio/Documents/Projekte/video/whispaste-social-b/`
- `renders/whispaste-social-b-de-v1.mp4` and `renders/whispaste-social-b-en-v1.mp4`
- the editable HyperFrames project (sources, `BRIEF.md`, `frame.md`, `STORYBOARD.md`, `production-prompt.md`, assets)
- `SOURCES.md`: claim evidence (Appendix B), asset licenses (fonts, SFX), the recording origin
- `PRODUCTION-LOG.md`: environment versions, verified names, every deviation with its reason, the commands run and their results (lint, check, snapshot list, ffprobe output), review findings per cycle and what was fixed, known limitations
- Do not claim a check you did not run. If something could not be verified, list it under "Not verified".

## Appendix A: BRIEF.md

```markdown
---
workflow: general-video
flow: automation
storyboard: no
message: "Du sprichst den Satz, und er steht an der Cursor-Position, ohne dass du das Fenster wechselst."
destination: instagram-reels
aspect: 1080x1920
language: de
audience: "Vielschreibende am eigenen Desktop: Mail- und Chat-Antworten"
length: 20s
narration: no
---

## Intent

A 20-second 9:16 social video for WhisPaste, a desktop dictation app. The window stays where it is; the spoken sentence lands at the cursor. Calm, precise, a little dry. German master plus an English cut with the same picture. The full plan is in production-prompt.md in this project root; build from its sections 1–9. This brief is confirmed by the user; do not re-interview.

## Assets

- assets/recording-de.mov — user recording of the Mac app (overlay, cursor, German dictation); to be provided before production
- assets/recording-en.mov — user recording with the English dictation; to be provided before production
- assets/icons/logo-dark.svg — logo for the close
- assets/icons/4.0x/wordmark-dark.png — wordmark for the close

## Customizations

- Captions from word timestamps of the recording (assets/dictation-de.json, assets/dictation-en.json), burned in at y=1180 px, Hanken Grotesk 500, 46 px.
- Title words enter word by word at 0.2 s intervals (Bricolage Grotesque 700, 84 px).

## Notes

- Confirmed brief; do not re-interview. Keep production-prompt.md in the project root.
- No Dock, no unreleased features, no numbers, no claims beyond Appendix B, no Windows elements, no glow or glass, no music, no paid generation.
```

## Appendix B: Sources

| # | Claim or fact used in the video | Evidence |
|---|---|---|
| 1 | Press a hotkey, speak, and the text appears at the cursor in any app (macOS) | `/Users/silvio/Documents/Projekte/whispaste/fastlane/metadata/en-US/description.txt` (first section, "Speech-to-text for your Mac") and `/Users/silvio/Documents/Projekte/whispaste/README.md`, "How It Works" |
| 2 | Recording overlay with a live waveform while the microphone is open | `/Users/silvio/Documents/Projekte/whispaste/README.md`, "Core" list (Recording overlay with waveform) |
| 3 | Auto-paste into any app on macOS | `/Users/silvio/Documents/Projekte/whispaste/README.md`, "Core" list (Auto-paste into any app, macOS/Windows/Linux) |
| 4 | Floating record button (shipped; may be visible in the recording) | `/Users/silvio/Documents/Projekte/whispaste/README.md`, "Core" list (Floating record button) |
| 5 | Destination URL on the close | `/Users/silvio/Documents/Projekte/whispaste/README.md` line 25 (https://whispaste.de) |

Not used on purpose (listed so the executor does not add them): Dock and redesigned main window (CHANGELOG "Unreleased"), Smart Mode, cloud providers, one-time price, time saved (estimate only), Parakeet speed claims ("several times faster", unverified).

## Appendix C: frame.md

```markdown
---
name: WhisPaste — social video frame spec
description: Calm, flat, dark-stage Swiss layout for a 9:16 desktop-dictation clip; one amber word, cyan URL only.
colors:
  ground: "#0B122A"
  band: "#171D53"
  hairline: "#3D4A66"
  text-primary: "#F0F4FA"
  text-secondary: "#ABB8CC"
  accent-amber: "#FFB547"
  link-cyan: "#6FDDF0"
typography:
  display: { fontFamily: "Bricolage Grotesque Variable", px: 84, weight: 700, lineHeight: 1.02, tracking: "-0.02em" }
  body: { fontFamily: "Hanken Grotesk Variable", px: 46, weight: 500, lineHeight: 1.3 }
  label: { fontFamily: "Hanken Grotesk Variable", px: 40, weight: 600, tracking: "0em", upper: false }
---

## Overview
Flat dark stage, one focal element per frame, the recorded Mac window stays fixed. Calm and precise; the joke is how small the change is.

## Do's and Don'ts
- Do: flat colour fields, hairlines 2 px, one amber word per video, ambient idle on the logo.
- Don't: glow, glass, gradients, drop shadows, a third hue, the Dock, invented UI, numbers, the word "Spende".
```
