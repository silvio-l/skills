# Decisions: Café "Bohnenwerk" logo animation (2026-10-20)

Run type: validation (scenario 3, incomplete briefing with delegation). There is no real user.
Every question below is written as it would have been sent; the answer is **SIMULATED**.

## Summary sent to the user before question 1 (not a question)
Understanding: a café named "Bohnenwerk" wants a logo animation, "irgendwas Cooles". No repository, no logo file,
no colors, no fonts, no budget, no platform, no goal, no message beyond the name. Verified facts: the name only.
Defaults I will use if you do not object: logo sting, 3–6 s, reach first, no invented facts about the café,
zero paid generation. Open: platform, logo file, budget.

## Frage 1/10 — Wo läuft das Video hauptsächlich?
Question 1/10 — Where will the video mainly run?
a) Instagram Reels / TikTok, 9:16 (recommended — the usual channel for a café's local reach; a logo sting is short enough for vertical)
b) Website header or Google Business post, 16:9 (website-first; works with a wider frame)
c) Instagram feed, 1:1 (square post, works in both feed and grid)
d) Several — I'll name them
Or answer freely.

**SIMULATED answer (verbatim, German):** "keine Ahnung, entscheide du alles"

Interpretation: this is the delegation-for-everything case in interview.md ("just decide everything"): stop the
interview, decide all open fields, present the defaults as a list. Question 1 counts toward the budget.

## No further phase-B questions
Delegation "for everything" stops the phase-B interview (interview.md, Delegation). Budget used so far: 1/10.
Open fields that a question would normally have covered (logo file, brand colors/fonts, budget) are decided or
logged as blockers below instead of being asked. See validation-notes.md for the conflict with the
"Ask in phase B for brand assets" rule in context-discovery.md A8. The next question is the reserved concept
selection in phase C, which is question 2/10.

## Decided by me (delegated, with reason)
| Field | Decision | Reason |
|---|---|---|
| Occasion and type | Logo sting / brand lockup, 3–6 s | Stated by the request ("Logo-Animation"); interview.md default for logo sting |
| Communication goal | Reach first, brand recall second; no conversion | No goal signalled; interview.md default. No URL or offer known, so no CTA |
| Audience | Unverified: guests of a local café (assumption) | No segment data; "clearest verified pain" is not available. Flagged as assumption, not as fact |
| Core message | The name "Bohnenwerk" only. No benefit, no claim | No verified benefit exists; a benefit would be invented (Hard rule: evidence over plausibility) |
| Platform and format | 9:16 master (Reels/TikTok), 16:9 not produced | Question 1 delegated; reach-first default from interview.md table row 5 |
| Length | 3–6 s | Logo sting default from interview.md row 6 |
| Language | Conversation language (German) for any spoken or on-screen text; on-screen text is only the name | interview.md row 7 default; the name needs no translation |
| CTA | None beyond the name; no URL (none known) | interview.md row 8: soft brand close without hard sell |
| Voice / sound | No voiceover. Sound-off-safe (the name is readable without audio). SFX only from a free or licensed source, no music unless free and licensed | interview.md row 9 default for social; no sound brief given |
| Style constraints | None given. Derived from the style kit; no brand look claimed | interview.md row 10 default |
| Assets | No logo file, no colors, no fonts. Code-drawn assets only; no invented logo | interview.md row 11 default |
| Budget and limits | Zero paid generation (no TTS, music, image models) | interview.md row 12 default |

## Blockers (decided with a stated consequence, not silently assumed)
1. **Logo file (BLOCKER for the final version).** The café's logo is the subject of a logo animation, so the
   brand must appear. Without a logo file, no final mark can be animated. Decision: the production prompt may
   describe a provisional, code-drawn text-only wordmark of the name, marked PROVISIONAL, with the real logo file
   as a required input before the final render. Nothing in the prompt may present the provisional look as the
   café's identity. Colors and fonts used in the provisional look are generic choices, not brand facts.
2. **Budget**: no blocker (zero paid generation is the default).
3. **Facts about the café**: none will appear in the video (no hours, menu, prices, origin story).

## Phase C — concept selection
The reserved selection question is asked in phase C (see below) and answered by the simulated user as
"nimm, was du für am besten hältst". Per interview.md, the selection question is then not asked again, and I pick
the recommended concept myself and say so.
