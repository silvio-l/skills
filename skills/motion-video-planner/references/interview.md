# Phase B: Interview protocol

You talk to the user in their language. Instructions here are in English.

## Budget (hard)

- **At most 10 questions in total for the whole run**, counting every follow-up, clarification, and
  the concept selection. Number them across the run ("Question 3/10", or in German "Frage 3/10").
- **Reserve one question for the concept selection** (phase C). That leaves at most 9 for phase B,
  and fewer is better.
- **One question per message.** No hidden bundles: "Platform and length?" counts as two questions
  and is not allowed. A question may carry a short context line, but it has one decision.
- **At most 4 answer options**, the recommended one first and labelled "(recommended)", each with
  a one-line consequence. Always allow a free answer ("or tell me something else").
- **Wait for the answer** before the next question. Never answer for the user or continue as if
  answered.
- If the budget runs out, stop asking. Decide the rest with stated defaults, and list every
  remaining assumption and every genuine blocker in the summary before phase C.

How to ask:
- If an `AskUserQuestion` tool is available, use it with one question per call.
- Otherwise use plain text: the numbered question, options lettered `a`–`d`, recommendation
  first, then a "free answer" line. The user replies with the letter or their own words.
  Write the question in the conversation language ("Frage 2/10 …", "(empfohlen)", "Oder frei
  antworten."). The example is in English only because this file is. Example:

  ```
  Question 2/10 — Where will the video mainly run?
  a) Instagram Reels / TikTok, 9:16 (recommended — your store copy targets mobile users)
  b) YouTube / website, 16:9
  c) LinkedIn feed, 1:1
  d) Several — I'll name them
  Or answer freely.
  ```

## Before the first question: summarize your understanding

In 5–10 lines: what the product or topic is, who it seems to be for, the strongest verified
benefit, the brand sources you found, the assets available, and what is still open. Also say
which defaults you will use if the user does not object. Ask the first question in the same
message. The summary is not itself a question.

## What may be asked (only if open)

Ask only decisions that the material does not settle and that change the concept or the
production. Priority order, highest first:

| # | Field | Ask when | Default if not asked |
|---|---|---|---|
| 1 | **Occasion and type** (explainer, product, promo, launch, logo, social, quiz, dilemma, …) | the request does not say | inferred from the request; stated |
| 2 | **Communication goal** | the user signals something other than reach (sales, sign-ups, recruiting, education) | reach first, brand recall second; conversion secondary |
| 3 | **Audience** | several segments exist and the choice changes the story | the segment with the clearest verified pain |
| 4 | **Core message** | material supports several and they compete | the strongest *verified* benefit |
| 5 | **Platform and format** | unknown; it changes the aspect ratio, length, and type scale | 9:16 for social reach, 16:9 for website or YouTube |
| 6 | **Length** | the platform does not imply it | social 15–30 s; explainer 45–90 s; logo sting 3–6 s |
| 7 | **Language** (voice, on-screen text) | product ships in several languages or the audience is unclear | conversation language |
| 8 | **CTA** | goal is not pure reach, or the user mentioned one | soft brand close (logo plus product name or URL); no hard sell |
| 9 | **Voice / sound** (voiceover yes/no, humor level, music) | concept-relevant and not inferable | social: sound-off-safe with on-screen text, music and SFX on top; explainer: voiceover |
| 10 | **Style constraints** (brand rules, no-go looks, references they like) | brand sources are thin or the user hinted at a look | derived from brand sources plus the style kit |
| 11 | **Assets** (logo file, footage, mascot, music they own) | brand sources are missing | code-drawn assets plus licensed SFX; no paid generation |
| 12 | **Budget and limits** (paid TTS, music, or image generation; deadline) | the concept would need paid generation | zero paid generation; local or free providers only |

Never ask what the repository or briefing already answers. If you want to confirm a found value,
state it in the summary ("I'll use `#ff5500` and Bricolage Grotesque from `tokens.css`"); the user
can object without spending a question.

## Delegation

If the user says "you decide", "entscheide du", "keine Ahnung, mach du", or similar:
- for one field, take the default, state it with a one-line reason, and move on (that answer still
  counted as a question);
- for everything ("just decide everything"), stop the phase-B interview, decide all open fields,
  and present the defaults as a list. The concept selection question is **still asked** in
  phase C: seeing three concrete concepts often changes a "you decide";
- only if the user explicitly delegated the concept choice as well ("pick the concept yourself
  too"), skip the selection question, take the recommended concept, and say so.
- A delegated *brand* (no logo, colors, or fonts exist) means you propose a provisional look. It
  is marked `PROVISIONAL` in the prompt and never treated as an existing brand rule (see the
  template notes). A missing logo file, when the logo must appear, is listed as an open blocker
  for the final render, not for planning.

## Adaptive order

Ask the question whose answer changes the most downstream. Usually that is the occasion or
goal, then platform, then message. Skip anything a previous answer made moot. If an answer
reveals a conflict with the evidence ("say it's 10× faster" but nothing supports it), raise it
in your next message as a short note with an alternative. That note is not a question. If a
decision is needed, it costs one.

## Exit: brief summary before phase C

Two visibly separate groups, so corrections are easy:
- **Confirmed by you**: each answer, in one line.
- **Decided by me (defaults or delegated)**: each with its reason.
- **Open blockers** (if any): what cannot proceed without the user, for example a missing logo
  when the brand must appear. If there are none, say so.

Then go straight to phase C. There is no extra confirmation question; the concept selection is
the confirmation point.

Log the questions and answers in `<plan-dir>/decisions.md` (numbered, verbatim answers). Mark
simulated answers as **SIMULATED** whenever this protocol is run in a test.
