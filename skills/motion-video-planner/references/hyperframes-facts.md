# HyperFrames facts the plan depends on

Load this file in phase D before you write section 8 (Technical execution) of a production
prompt, and whenever a concept depends on a specific HyperFrames capability.

These facts were checked on **2026-10-20** against the HyperFrames docs and the installed
skills (`heygen-com/hyperframes`; CLI `hyperframes@0.8.181`). HyperFrames ships often, so
the production prompt always tells the executing agent to re-verify names and flags on its
installed version (step 0 of the template). Never copy a block name, flag, or provider
from here into a prompt as a guaranteed fact. Mark it as "verify with …".

Sources:
- Prompt Guide overview: https://hyperframes.heygen.com/prompting/overview
- Anatomy of a one-shot prompt: https://hyperframes.heygen.com/prompting/anatomy
- Specification dial: https://hyperframes.heygen.com/prompting/specification-dial
- High-fidelity looks: https://hyperframes.heygen.com/prompting/visual-specs
- Motion that reads premium: https://hyperframes.heygen.com/prompting/motion
- Transitions: https://hyperframes.heygen.com/prompting/transitions
- Vocabulary: https://hyperframes.heygen.com/prompting/vocabulary
- Storyboards: https://hyperframes.heygen.com/prompting/storyboards
- Media and audio: https://hyperframes.heygen.com/prompting/media-and-audio
- Design systems and brand: https://hyperframes.heygen.com/prompting/design-systems
- Generated artwork: https://hyperframes.heygen.com/prompting/generated-artwork
- Runtimes and 3D: https://hyperframes.heygen.com/prompting/runtimes-and-3d
- Data and maps: https://hyperframes.heygen.com/prompting/data-and-maps
- Rendering and output: https://hyperframes.heygen.com/prompting/rendering-and-output
- Iterating: https://hyperframes.heygen.com/prompting/iterating
- Rules and anti-patterns: https://hyperframes.heygen.com/prompting/rules-and-anti-patterns
- Motion graphics: https://hyperframes.heygen.com/prompting/motion-graphics
- Media effects: https://hyperframes.heygen.com/guides/media-effects
- Finish and share: https://hyperframes.heygen.com/guides/export-and-share
- Installed skills: `hyperframes` (SKILL.md, `references/brief-format.md`, `brief-contract.md`,
  `intent-interview.md`, `review-loop.md`, `production-loop.md`, `routes/*.md`) and
  `hyperframes-cli` (SKILL.md, `references/cloud.md`, `init-and-scaffold.md`)

## 1. How a fresh session enters HyperFrames

- `/hyperframes` is the entry point. On a fresh request it runs the **intent layer**: memory
  reads, triage, an optional pitch round, the route's must-have questions, and two run-shape
  questions (storyboard yes/no, automation/companion). It hands over a confirmed brief that
  the workflow's Setup writes to `BRIEF.md` **right after `hyperframes init`**. `init` refuses a
  non-empty directory, so `BRIEF.md` cannot be written before it.
- **`BRIEF.md` is the no-repeat token.** A workflow that finds it asks no brief questions.
  Frontmatter keys: `workflow`, `flow` (`automation` | `companion`), `storyboard` (`yes` | `no`),
  `message`, plus route fields (`destination`, `aspect`, `language`, `audience`, `length`,
  `angle`, `narration`). Body sections: `## Intent`, `## Assets` (`path — what it is, where it
  belongs`), `## Customizations`, `## Notes`.
- **Signals.** "just build it", "decide for me", or "stop asking" during intake lock
  `flow: automation, storyboard: no`, which derives `mode: autonomous`. `automation` + `storyboard: yes`
  derives `collaborative` (waits at each checkpoint). `companion` is always collaborative.
- **Autonomous is not silent.** It posts checkpoint summaries and continues. It still runs and
  stops on `lint` / `check` errors, and it surfaces a missing required capability as a blocker
  instead of dropping it.
- **Rendering is user-gated in every mode.** After checks pass, the workflow opens the Studio
  preview and asks one question: "render now, or what changes?". The production prompt can
  state approval in advance, but the executing agent may still ask that one question. Treat it
  as expected and do not try to suppress it.
- Usage: workflows run `npx hyperframes usage --json` at the start and at milestones. If the
  status is unknown, it is reported, not guessed.
- Project CLI pin: `npx hyperframes@latest upgrade --project . --check` probes, without changing
  anything, whether a scaffolded project's pinned version is behind.

**Consequence for this skill:** the production prompt carries a complete, final `BRIEF.md` in
its appendix and instructs: scaffold with `init`, write that `BRIEF.md` verbatim as the first
action, and then run the named workflow without re-interviewing. That makes the prompt
single-shot apart from the one render question.

## 2. Routes (choose the executor)

| Route | Use when | Notes |
|---|---|---|
| `/motion-graphics` | Short, unnarrated, motion-first unit, usually under 10 s (up to ~30 s): kinetic type, stat hit, chart hit, logo sting, lower-third, map, animated post or headline | Autonomous by design: at most one clarifying question, no storyboard. MP4 by default, or a transparent alpha overlay on request. Narration does not belong here. |
| `/general-video` | Any other custom piece: multi-scene, narrated, brand or sizzle reel, montage, a fully specified concept | Follows a supplied plan. Also hosts every `flow: companion` run. Use it for most prompts from this skill, because the concept is already decided and a preset workflow's own look would fight it. |
| `/product-launch-video` | Promo or site tour built *from a website URL* that the workflow should capture | Captures site assets and brand tokens, and has its own pitch round and preset. Choose it only when site capture is the point, and pre-answer its sell-or-show question and `VO_MODE` in `BRIEF.md`. |
| `/faceless-explainer` | Topic or article explainer with invented visuals, no product | Its own angle and preset. Prefer `/general-video` when the concept and look are already fixed. |
| `/music-to-video` | A supplied track's beat grid drives the cuts | A music bed under narration does not qualify. |
| `/embedded-captions`, `/talking-head-recut` | Existing talking-head footage | Not motion-graphics planning. Route there only if the user's footage is the base. |
| `/slideshow` | A navigable deck | Not a rendered video. |

Specialized narrative workflows are strongest at 30–90 s and capped at about 3 minutes. Anything
clearly longer goes to `/general-video`.

## 3. Prompt anatomy that works (Prompt Guide, Level 2)

Six parts in this order: **Route** (slash command) → **Spec** (duration, resolution) → **Beats**
(timestamped, with pacing cues) → **Copy** (all on-screen text quoted exactly, `/` for line
breaks; unquoted text gets paraphrased) → **Technique** (exact registry block names, or "hand-author")
→ **Negatives** (precise; "no narration" does not mean silence).

Beat formula, per beat: **Element · Motion · Layout · Style · Timing.** Every slot you leave
out, the agent designs on its own.

Do and don't:
- Write holds as an explicit choice: a gentle ambient idle (1–2 % breathing scale, slow drift),
  or a deliberate, motivated still. Compositions hold their last state, so an unspecified hold
  renders as a frozen frame. The docs disagree here: the Motion page says "nothing ever fully
  stops", while the Storyboards page asks for still holds. This skill's rule is to decide per
  piece and state the choice. See `creative-principles.md`.
- If the runtime exceeds the described beats, say what fills the tail.
- Never put two events at the same time unless you say so explicitly. Write "fades out fully by
  4.2 s; at 4.2 s READY stamps in".
- Write "no image or media files", not "no external assets".
- For counters, state the target value only ("counts up to $4.2M"), not "from 0".
- Don't fade one scene out and the next in. Scenes hold their final state, so this produces a
  dip. Name the handoff instead.

**Specification dial:** mood words → style tokens (exact hex values, named textures, type
direction) → full visual spec (every element's shape, color, position, size in px, timing,
easing, back-to-front layer order). Density never hurts fidelity. Pin these explicitly:
3D ("Three.js via the adapter"), sequencing, and any technique a smaller model might miss.

**Density contract** (visual specs page): each frame has one focal element at display scale, at
least two supporting elements on their own cues, and persistent chrome or a "wire". Compose
asymmetrically. Size display type at roughly a tenth of the frame width. Use three depth layers
for parallax. A frame that fills all roles at t=0 reads as a poster, not a scene.

## 4. Motion, transitions, vocabulary

- **Eight premium-motion rules**: ambient idle instead of a frozen end, the camera as an actor
  (one continuous move per scene, 4–8 % push-in or orbit or parallax), overlapping action (no
  shared start or end times; delay supporting elements, never the focal one), compound
  properties only when they tell one story (entrances ease out, exits ease in, moves ease
  in-out), overshoot only on transforms (never on counters), depth planes at distance-matched
  rates, pacing matched to genre (showreel ~1.5–4 s per idea), and reproducible imperfection
  (seeded PRNG, quantized on the integer frame index).
- **Ease vocabulary**: smooth `power2.out`, snappy `power4.out`, bouncy `back.out`, springy
  `elastic.out`, dramatic `expo.out`, dreamy `sine.inOut`. Typical durations: energetic ~0.2 s,
  professional ~0.4 s, luxury ~0.6 s, cinematic 1–2 s.
- **Transitions**: pick one primary transition, plus one or two accents for topic changes or the
  climax. Duration scales with energy: calm 0.5–0.8 s, medium 0.3–0.5 s, high 0.15–0.3 s.
  Candidate names from the docs:
  - Shader: `cross-warp-morph`, `thermal-distortion`, `whip-pan`, `cinematic-zoom`, `ridged-burn`,
    `glitch`, `chromatic-radial-split`, `light-leak`, `gravitational-lens`, `domain-warp-dissolve`,
    `ripple-waves`, `swirl-vortex`, `flash-through-white`, `sdf-iris`
  - CSS: `transitions-blur`, `transitions-dissolve`, `transitions-push`, `transitions-cover`,
    `transitions-scale`, `transitions-destruction`, `transitions-light`, `transitions-mechanical`,
    `transitions-grid`, `transitions-distortion`, `transitions-3d`, `transitions-radial`

  Never invent a name. The executing agent confirms names with the catalog.
- **Registry blocks named in the docs** (candidates, verify before use): `code-typing`,
  `code-diff`, `vfx-shatter`, `apple-money-count`, `x-post`, `data-chart`, `us-map`,
  `us-map-bubble`, `us-map-flow`, `us-map-hex`, `spain-map`, `world-map`, `nyc-paris-flight`,
  `code-particle-assemble`, `swirl-vortex`, `vfx-liquid-background`. The registry holds roughly
  400 items, so search it with `npx hyperframes catalog --query "<look>"` before hand-building
  any named look.
- **Media effects** apply to whole image or video layers only, never to text or regions:
  Blur, Pixelate, Bloom, Tape Damage, Film Artifacts, Scanlines, CRT Curvature, Channel
  Separation, Digital Glitch, Chroma Softening, Halftone, Two-Ink Print, Ordered Dither, Mono
  Screen, ASCII, Engraving, Crosshatch, Kuwahara Paint. Get the exact IDs with
  `npx hyperframes media-treatment --capabilities --json`. Blur, Bloom, and Kuwahara are the most
  expensive to render.
- **Runtimes**: GSAP is the default and rarely needs naming. For real depth, lighting, or a camera,
  name "Three.js via the adapter"; CSS perspective reads flat. For existing animation files, name
  the Lottie file path. Use shader transitions only for the two or three key seams. Seed every
  random layout.

## 5. Audio and media

- **Voiceover (TTS)** engine order: HeyGen (if the account is configured) → ElevenLabs (if a key
  is set) → local Kokoro (no key, no cost). Kokoro voice suggestions from the docs: product demo
  `af_heart`, `af_nova`; tutorial `am_adam`, `bf_emma`; marketing `af_sky`, `am_michael`. Specify
  tone and pace, not "add a voice". Generated narration comes with word timings. **Narration is
  the clock**: visuals land on spoken cues, and the narration never waits for visuals. A new take
  needs new timings.
- Kokoro's voice list is English-first. For German or other narration, the executing agent must
  check which voices the available engine offers for that language before it promises a voice.
  Name the language and the fallback in the prompt.
- **Music**: always give a mood and a loudness target relative to the voice, for example "ducked
  about 12 dB under the voice" or "kept under −18 dB". When a bed plays under a voice, the
  production loop carves it (`hyperframes-audio`). `media-use resolve --type bgm` needs the
  HeyGen CLI or account. Without it, the user supplies a licensed track or the piece runs without
  music.
- **SFX**: `resolve --type sfx` needs no account (Openverse, then a bundled library). Cue each
  effect to a specific moment instead of scattering them. Record the license per file.
- **Silence**: "no narration" removes only the voice. For true silence, say "no audio at all".
- **Captions** come from word timestamps. For existing footage, transcription runs Parakeet if it
  is installed, otherwise Whisper.
- **Cutouts**: `remove-background` is tuned for people. On products, objects, or flat art it
  fails, so say when the subject is not a person.
- **Generated artwork**: code-draw UI, type, geometry, charts, pixel art, and 3D. Generate only
  illustration-led hero art (characters, painterly scenes, sculptural objects) on a solid
  contrasting background (magenta), chroma-key it, keep independently moving parts as code
  layers, and add "minimal, lots of negative space". Image generation runs through `/media-use`
  and may cost money. Budget it explicitly or forbid it.
- **Supplied assets**: always give explicit paths ("use `assets/logo.svg`"). Prefer SVG logos.
  Third-party logos come from the logo cascade and are never redrawn by hand. The user's own
  logo needs a path.

## 6. Brand

Name one **source of brand truth**: `frame.md`, a site, a Figma file, or exact hex values and
font names. Never just write "on-brand". Keep colors, fonts, weight relations, and the light or
dark ground strict. Scale type sizes, border weights, and decorative opacity for video. Delegate
layout, spacing, and motion. `frame.md` frontmatter carries the machine-readable tokens, and its
prose carries the do's and don'ts.

## 7. Rendering and output

- Defaults: 1920×1080, 30 fps, MP4 (H.264). Scaffold presets (`init --resolution`): `landscape`
  1920×1080, `portrait` 1080×1920, `square` 1080×1080, plus `-4k` variants.
- **Transparency** only for overlays (lower-thirds, stings over footage). Use **MOV (ProRes 4444
  with alpha)** for editing tools or **WebM (VP9 with alpha)** for browsers; editors show WebM
  alpha as black. Leave `html` and `body` backgrounds unset. Verify alpha with `ffprobe`
  (`ALPHA_MODE=1`) or the ffmpeg `alphaextract` filter. Transparency on a full-frame design is a
  failure mode. 4K supersampling has no alpha path.
- **60 fps** doubles render work. Use it only for fast motion delivered to high-refresh screens.
  4K costs about 4× per frame and makes files 3–5× larger, and adds no detail to sub-4K media.
- **Quality flag names differ by surface and version.** The local CLI skill documents `--quality
  draft | looks | delivery`, while the cloud, Lambda, and docs pages use `draft | standard | high`.
  The production prompt therefore instructs `npx hyperframes render --help` before the first render.
- **Do not use `render --docker`** unless a container runtime is already installed and permitted
  in the target environment. Local renders need no container.
- Quality gates: `npx hyperframes lint` checks structure, and `npx hyperframes check` runs lint plus
  browser, runtime, layout (`text_occluded`), motion, and WCAG contrast checks. `npx hyperframes
  snapshot --at t1,t2,…` captures stills. `npx hyperframes doctor` diagnoses the environment.
  **Gates prove the composition is well-formed, not that the video is good.** Story, rhythm, and
  sync need human-style review of frames and of the rendered file.
- Review the rendered file, not just the preview: the first and last seconds, captions, cuts, the
  most complex transition, clipped narration, late SFX, an abrupt music end, and the duration,
  dimensions, format, and audio streams.

## 8. Determinism rules the plan must not violate

Register every timeline on `window.__timelines`. No `Math.random()`; use a seeded PRNG. No
`async`, `fetch`, or live data during timeline construction, so bake data in. Timed elements need
`class="clip"` plus `data-start`, `data-duration`, and `data-track-index`. Never fetch at render
time. All media must exist locally before render. A plan that needs live data, real viewer input,
or randomness that differs per render is not producible as specified. Redesign it in the concept
phase.
