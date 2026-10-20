# Decisions: WhisPaste social video (2026-10-20)

Plan directory: `/Users/silvio/Documents/Projekte/skills/tests/motion-video-planner/validation/1-repo-whispaste/`
Mode: repository (`/Users/silvio/Documents/Projekte/whispaste`, read-only). Inventory JSON: `/private/tmp/claude-501/-Users-silvio-Documents-Projekte-skills/169b11c3-fcdb-418e-92da-63425fb3e425/scratchpad/inv-whispaste.json`.
Context: `context.md` (this directory).

Question budget: 5 of 10 used (4 asked in phase B, 1 reserved for concept selection). Answers marked **SIMULATED** are given by the test driver playing the user.

## Summary before the first question (phase B)

**Understood:** WhisPaste is a free, open-source desktop dictation app (Windows, macOS, Linux): hotkey, speak, text lands at the cursor. Local engines by default, cloud optional with own key, one-time purchase in the stores. Audience per `docs/zielgruppe.md`: people who write a lot on their own desktop.
**Strongest verified benefit:** "Hotkey, speak, text at the cursor, in any app" (store copy, README), with the local/offline default as a second verified pillar.
**Occasion:** social video (from your request). **Goal:** reach first, as you want people to share it; no sales goal signalled.
**Brand sources:** `assets/icons/logo-dark.svg` and `logo-light.svg`, wordmark PNGs, tokens in `design-tokens/`, fonts Hanken Grotesk and Bricolage Grotesque (website global.css), voice "calm, plain, precise". Brand glossary forbids "Spende"/donation.
**Assets:** logo SVG (usable), app screenshots (dark, 2), store screenshots (1440x900). No video footage of the app.
**Constraints noticed:** the Unreleased changelog features (Notes, audio import, redesigned window) are not shipped and must not appear as current features. "Time saved" is an estimate only. Parakeet "several times faster" is unverified.
**Defaults I will use unless you object:** reach first; CTA = soft brand close with the URL whispaste.de (no hard sell); sound-off-safe with on-screen text; no paid generation; code-drawn UI; 15-30 s.
**Open:** platform/format, core message, language, app footage.

---

### Question 1/10 — Platform and format
Context: the aspect ratio and the type scale depend on where it runs first.
a) TikTok / Instagram Reels / YouTube Shorts, 9:16 (recommended — short social clips are watched on phones; 15–30 s)
b) YouTube / website, 16:9 (wider frame, longer hold per beat)
c) LinkedIn / X feed, 1:1 (square, works in both feeds)
d) Several — I'll name them
Or answer freely.

**SIMULATED answer:** a) 9:16 — "Reels und Shorts, bitte hochkant."

### Question 2/10 — Core message
Context: the verified claims compete. Pick the one the video leads with; the others may appear only as a supporting beat.
a) Speed: "Sprechen statt tippen" — hotkey, speak, text at the cursor (recommended — the most direct, verified in store copy and README)
b) Privacy: "Deine Stimme bleibt auf deinem Rechner" — local engine by default (verified, with the cloud-opt-in caveat)
c) Freedom: one-time purchase, no subscription, open source (verified)
d) Any app: works wherever the cursor is (verified, generic)
Or answer freely.

**SIMULATED answer (free text):** "Eigentlich: Ich schreibe den Satz, ohne aus dem Fenster zu gehen. Der Cursor bleibt der Held, nicht die Technik."

### Question 3/10 — Language of voice and on-screen text
Context: the app ships in six interface languages; the audience may be German or English-speaking. Each language is a separate render.
a) German voice-over and on-screen text only (recommended — your store copy and docs are German-first; one render)
b) English only (one render; wider reach, less fit with the German copy)
c) Two versions: German master plus English cut (two renders; roughly double the QA)
d) Several — I'll name them
Or answer freely.

**SIMULATED answer:** c) — "Beide: deutsche Fassung zuerst, englische danach."

### Question 4/10 — App footage
Context: no screen recording of the app exists in the repo; producing one needs the app running and fake dictation text.
a) Code-drawn UI from the design tokens, no recording (recommended — no privacy or store-frame issues, fully reproducible)
b) Real screen recording of the macOS app with demo text
c) Existing repo screenshots (`resources/screenshots/history-*.png`), static
d) Mix: code-drawn UI plus one real recording
Or answer freely.

**SIMULATED answer:** b) — "Echte Aufnahme der Mac-App, aber nur Overlay, Dock und Cursor, keine echten Verläufe, und kein Windows-Fenster drin."

---

Phase B exit (decided by me, defaults or delegated):
- Goal: reach first (your "teilen wollen" signals it; no sales goal asked).
- CTA: soft brand close with whispaste.de, no hard sell (default).
- Sound: sound-off-safe with on-screen text, music and SFX on top (default; no voice-over question asked because the language answer sets it up in both versions).
- Budget: zero paid generation (default; not asked, the concept must not need it).
- Length: 15-30 s (default for social).

Confirmed by you: 9:16 (Q1); core message = "sprechen statt tippen, ohne das Fenster zu verlassen" (Q2 free); German master plus English cut (Q3); real Mac recording limited to overlay, dock and cursor, no real history (Q4).
Open blockers: none. Note: the Mac recording implies the Mac-only framing; store screenshot framing rules do not apply to the video itself but no Windows UI may appear.

**Conflict found after Q4 (noted, not asked, no question spent):** the Q4 answer asked for the Dock in the recording, but the Dock belongs to the redesigned main window, which is listed under CHANGELOG "Unreleased" (not shipped). Decision by me: the recording shows only the released overlay, the floating button and the cursor; the Dock is excluded from concept B and from the production prompt. The user should confirm this in the next message.

---

## Phase C: concepts

Five directions sketched (A: everyday relevance / "that's so us"; B: visual surprise / UI-led; C: surprising claim with a cloud character; D: retro VHS typist, rejected as too far from the calm brand; E: "edit selection by voice" as a before/after, rejected because the edit feature is off by default). Three kept (A, B, C), differing in hook, protagonist, dramaturgy and style family. Details and the qualitative comparison: `concepts.md`.

Recommendation: A (strongest share trigger, shortest causal chain). Question 5/10 (SIMULATED):

Question 5/10 — Which concept should I turn into the production prompt?
a) Concept A: „Schon wieder dieser Satz" (recommended)
b) Concept B: „Das Fenster bleibt, wo es ist"
c) Concept C: „Die Wolke vor der Tür"
d) Mix: tell me which parts
Or answer freely.

**SIMULATED answer:** b) Concept B. One-sentence reason: the real recording from Q4 proves "no window change" instead of a mock.

## Phase D: production prompt

- Written from the template; section 8 names `/general-video` (flow automation, storyboard no).
- Deviation from concept B, logged: scene 5 line changed from "Und wo ist der Fenster-Wechsel?" to "Gewechselt hat nur der Text." (same deliberate-stillness pay-off; the old line read as a question without an answer).
- Deviation from concept B, logged: the keycap on the Dock button was removed (see conflict above).
- Assets: both user recordings (DE and EN) are `create` status but made by the user, not the executor; the prompt stops if they are missing.
- Hand-over gate: `check_prompt.py` exit 0 after fixes (see validation-notes.md for the first run's output).
- Questions used: 5 of 10 (Q1–Q4 in phase B, Q5 the concept selection). Budget remaining: 5, unused.
