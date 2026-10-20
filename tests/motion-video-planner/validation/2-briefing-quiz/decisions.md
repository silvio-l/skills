# Decisions: Küchenchemie quiz video (2026-10-20)

Question budget: 10 total. Used: 5 (4 in phase B, 1 reserved selection). Remaining: 5.
All user answers below are **SIMULATED** (test run, no real user).

## Understanding sent before the first question (summary, not a question)
- Product/topic: Instagram account "Küchenchemie", cooking science, about 4,000 followers.
- Video: quiz, "Warum kocht Nudelwasser mit Salz nicht wirklich schneller?"
- Strongest verified benefit: the boiling-point effect of salt is real but tiny (UIUC: 0.5 °C at 29.2 g/kg).
- Brand sources: two hex colors (#E8B931, #1F3D2B). No font, no SVG logo; logo PNG 1080×1080 supplied by the user (not present in this environment).
- Assets: only the user's logo (to be placed); everything else code-drawn.
- Open: length, voice, tone, music, concept selection.
- Defaults I will use unless objected: 9:16 Instagram Reels, 1080×1920, 30 fps, German on-screen text, zero paid tools, soft brand close, reach first.

## Question 1/10 — Wie lang soll das Video sein?
a) 25 s (recommended — quiz rhythm: question 3 s, thinking time 5 s, reveal and explanation about 12 s, close 3 s)
b) 15 s (tight: one question, one reveal, little room for the explanation)
c) 40 s (room for a second fact, but Instagram retention risk grows)
Or answer freely.

**Answer (SIMULATED):** a

## Question 2/10 — Soll es eine Sprechstimme geben?
a) Keine Stimme: Text auf dem Bild plus Sound-Effekte (recommended — works sound-off; no paid TTS; no German voice engine has been verified for the free local option)
b) Deutsche Stimme über einen Dienst mit Konto (HeyGen/ElevenLabs) — paid or account-bound, conflicts with "kein Budget"
c) Deutsche Stimme lokal (Kokoro) — only after a German voice is confirmed; currently unverified
Or answer freely.

**Answer (SIMULATED):** a

## Question 3/10 — Welcher Ton passt zum Account?
a) Trocken-verschmitzt, Wissenschaft mit Augenzwinkern (recommended — matches "Wissenschaft beim Kochen" without mocking the viewer)
b) Albern und überdreht (more gags, risk of drifting from the facts)
c) Sachlich-erklärend (calm, no gags)
Or answer freely.

**Answer (SIMULATED):** a

## Question 4/10 — Musik?
a) Keine Musik, nur wenige Sound-Effekte plus ein kurzes Drei-Ton-Motiv (recommended — no account needed for music; motif is the recurring element)
b) Lizenzfreies Musikbett (needs a source; the free music path via the registry requires an account, so the user would supply a file)
c) Eigene Musik (user supplies file)
Or answer freely.

**Answer (SIMULATED):** a

## Question 5/10 — Welches Konzept soll ich in den Produktionsprompt überführen? (reserved selection)
a) Konzept A: "Ist das wirklich schneller?" (recommended — question, held thinking time, reveal with a thermometer scale)
b) Konzept B: "Der ungeduldige Kochtopf" (everyday relevance, escalation, visual punchline)
c) Konzept C: "Wasser auf der Waage" (visual surprise, build-up to a scale reveal)
d) Mix: tell me which parts
Or answer freely.

**Answer (SIMULATED):** a

## Decided by me (defaults or delegated, not asked)
- Format and aspect: Instagram Reels, 9:16, 1080×1920, 30 fps, MP4 H.264. Reason: platform is given; social default (planning rule).
- Goal: reach first, brand recall second; conversion none (soft close only). Reason: no goal stated; default.
- Quiz type: knowledge quiz with one correct answer. Reason: question has a checkable answer; occasion is "quiz" (given).
- Language: German for on-screen text and any copy. Reason: briefing language and account topic.
- Font: free Google Font, OFL license; chosen at planning (see production prompt). Reason: user has no preference ("Schrift ist mir egal").
- Logo: user-supplied PNG, used only as the end lockup. Reason: only logo supplied.
- Workflow: `/general-video`, flow automation, storyboard no. Reason: fully specified concept, narration none; `/motion-graphics` is limited to shorter unnarrated pieces (under ~30 s, motion-first), and a 25 s quiz with a reveal is closer to the general-video path the facts file recommends for fixed concepts.
- Budget: zero paid generation, zero paid TTS, zero paid music. Reason: user stated no budget for paid tools.
- Evidence scope: the only figure used is 0.5 °C at 29.2 g/kg (UIUC). No pasta-water concentration is stated.

## Open blockers
- None for the planning. Production blockers to note: the logo file must be placed by the user at `assets/kuechenchemie-logo.png` before production; "does not cook faster" needs a second fetchable source (see context.md, gaps).
