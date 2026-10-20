# Video context: Küchenchemie – Quiz-Video Nudelwasser (2026-10-20)

## Sources and coverage
- Mode: briefing (no repository; the working directory was treated as an empty folder)
- Inventory: not run (repository mode only). Briefing material: one user message (German).
- External sources:
  - UIUC Physics "Ask a physicist" answer, https://van.physics.illinois.edu/ask/listing/1457 — read (WebFetch). States: boiling point raised by 0.5 °C for 29.2 g salt per kg water; scaling with concentration is stated as proportional. Does NOT state anything about cooking time.
  - Live Science, "Does salt make water boil faster?", https://livescience.com/56214-does-salt-make-water-boil-faster.html — NOT verifiable: WebFetch returned only the title (truncated). Only the WebSearch snippet was seen ("salt doesn't meaningfully speed boiling", "a teaspoon per liter has a tiny effect"). Treated as an unverified lead.
  - Search snippets only (not opened): Mental Floss, Quick and Dirty Tips. Not used as evidence.
- Gaps:
  - No source found that directly states "salted pasta water does not cook pasta faster". The claim currently rests on the boiling-point source plus physical reasoning (higher boiling point means a higher target temperature). Needs a fetched second source before production, or the claim is reworded.
  - Typical concentration of pasta water is not sourced. No pasta-water figure is used anywhere in the plan.

## Product in one paragraph
Instagram account "Küchenchemie": science behind cooking, about 4,000 followers, German-speaking audience (inferred from the language of the briefing and the account's topic). The content piece is a short knowledge quiz: "Warum kocht Nudelwasser mit Salz nicht wirklich schneller?" The account has no product; the "brand" is the account itself.

## Verified facts (usable in the video)
- Salt raises the boiling point of water; the effect is 0.5 °C at 29.2 g salt per kg water — evidence: UIUC page (external, fetched 2026-10-20).
- The effect scales roughly in proportion to concentration — evidence: UIUC page (same source).

## Documented but unverified
- Salt does not make pasta water reach boiling or cook pasta faster in practice — source: Live Science (snippet only); status: needs check (second fetchable source) or reword to what the physics supports.
- "A teaspoon per liter" effect is "tiny" — source: Live Science snippet; status: needs check.

## Roadmap / not shipped (never claim)
- none (no product)

## Assumptions
- Audience is German-speaking; the video language is German — stated by user implicitly (German briefing, German account topic).
- No product or service is promoted; soft brand close only.
- Goal not stated: reach first, brand recall second (default from interview.md).
- Format: Instagram Reels, 9:16 (1080×1920) — platform given as Instagram; aspect ratio decided by default (creative principles: social 9:16). Stated, not asked.
- Length not stated: default for social quiz 20–30 s (to ask).
- Voice not stated: to ask.
- No paid tools: "Kein Budget für bezahlte Tools" — stated by user on 2026-10-20 → zero paid generation, zero paid TTS/music.
- Font: user says "Schrift ist mir egal" → the planner chooses a free font (Google Fonts only, license OFL) and states it; no font file is available locally.

## Audiences and use cases
- Instagram followers interested in cooking science: recognize the habit of salting the pot early and the habit "es muss schneller gehen"; what changes: the salt does not save time, the reason is a small boiling point shift.

## Differentiation and limits
- Differs by: a myth-check framed as a quiz with pause and reveal (evidence: user's content description).
- Limits and honest caveats: the effect is tiny; the video must not imply that salt is bad for water or that salting is wrong (salting is for flavor).

## Brand sources
- Logo: user-supplied PNG `kuechenchemie-logo.png`, 1080×1080 px, raster. Not present in this environment; to be placed at `assets/kuechenchemie-logo.png` in the production project. No SVG, no light/dark variants known.
- Colors:
  - `#E8B931` Senfgelb — brand color, stated by user
  - `#1F3D2B` Dunkelgrün — brand color, stated by user
- Fonts: none specified ("Schrift ist mir egal"); planner default: a free Google Font (choose at planning, e.g. a sans with bold weight) — assumption.
- Voice and tone: not given; assumption "warm, slightly witty, science-curious".
- Recurring element candidates: none given; plan: a 3-note sound motif (SFX) and a small thermometer/bubble shape (code-drawn).

## Usable assets
| Path | Kind | Size | Usable for |
|---|---|---|---|
| `kuechenchemie-logo.png` (user-supplied, not present here) | raster logo | 1080×1080 | end lockup; must be placed at `assets/kuechenchemie-logo.png` |

## Production environment
- HyperFrames CLI: not checked (running `npx hyperframes --version` would fetch the package; not done, install nothing). Node and npx present (`/Users/silvio/.local/bin/`).
- HyperFrames skills installed: yes (the `hyperframes` skill family is in the session skill list).
- ffmpeg / ffprobe: yes (`/opt/homebrew/bin/`).
- Website for capture: none.

## Open questions for the interview
1. Length of the video (not implied by the platform).
2. Voiceover or not, and in which language/engine (German voice availability is uncertain for free local engines).
3. Tone (dry, playful, plain).
4. Music or sound design only.
5. Concept selection (reserved).
