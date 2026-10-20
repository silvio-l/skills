# Creative principles (design hypotheses and quality criteria)

Load this in phase C before you develop concepts, and in phase D when you write the story and
timeline.

**Status of these principles.** These are the operator's standing preferences, used as design
hypotheses and review criteria. They are not a proven formula for reach. Never promise
virality, reach, or view counts, never invent scores or forecasts, and never present these
principles to the user as research findings. Explicit campaign goals from the user override
them (for example, a pure conversion ad or a recruiting video).

## 1. Goals, in order

1. **Maximum reach**: people watch to the end, rewatch, and share.
2. **Brand recall**, a close second: the viewer remembers whose video it was.
3. **Direct conversion** comes last by default. A CTA may exist, but it does not get to weaken
   the story.

## 2. Share triggers, ranked

1. **"That's so us!"**: a situation the audience recognizes as their own life, team, or habit,
   exaggerated just enough to be funny or painfully true. People share it to say "this is us".
2. **"Why didn't I know there's such a simple solution?"**: a surprising, verifiably simple fix
   for a familiar annoyance. People share it as a useful tip.

Every concept names its share trigger and says concretely who would forward it to whom.

## 3. Rewatch triggers

- **A strong punchline**: a final reveal or twist that recontextualizes what came before, so
  the second viewing shows the setup.
- **Gripping staging**: dense, well-timed action with visual gags and details that cannot all be
  caught the first time.

## 4. What "dynamic" means here

Not constant movement. Dynamic means:
- **rhythmic actions** with a pulse the viewer can feel;
- **precise sync with sound**: hits, whooshes, and ticks land on the frame of the visual event;
- **short contrasts and pauses**: a deliberate beat of stillness before the payoff (comedic
  timing), a sudden quiet after noise;
- **escalation**: each beat is a little bigger, faster, or worse than the last;
- **surprising reactions and visual gags**: an object responds in an unexpected but logical way.

## 5. Elements act, react, and cause consequences

The core anti-pattern is a **slide deck**: element appears, holds, disappears, next element
appears. Instead:
- elements are **characters with intent**: the notification bubble *pushes* the calendar aside,
  the cursor *hesitates*, the stack of tabs *collapses* under its own weight;
- every entrance **is caused by** something (a previous element's motion, a sound, a cut on
  action), and every action **has a consequence** (something moves, breaks, flips, or changes
  color);
- cause and effect stay readable: one consequence at a time for the focal action, with
  supporting reactions staggered after it.

Test for each scene: "What does the main element *do*, and what happens *because of it*?" If the
answer is "it appears", redesign the scene.

## 6. The opening

- **Interest in the first second, situation understood within about 3 seconds.** The outcome
  may stay open, and should.
- Hook mechanisms (choose one per concept and name it):
  - **Curiosity gap**: an unusual image or question that demands a resolution.
  - **Visual surprise**: an impossible or unexpected action in frame one.
  - **Everyday relevance**: the viewer's exact situation, instantly recognizable.
  - **Surprising claim**: a counter-intuitive statement. It **requires checkable evidence**
    (cited in the production prompt), and the video must deliver on it.
- The first frame must already be a frame: no logo intro, no fade from black, no title card,
  no "Hi, in this video …".
- Sound-off safety on social: the hook must work without audio (text plus visual action).

## 7. Preferred dramaturgy (not mandatory)

Recognizable everyday situation → **escalation** with small surprises → **climax** → simple,
understandable **solution or visual punchline** → **visible change** (before vs. after).

In product videos, the product may enter as the **surprising helper**, but only after the problem
has been *experienced* on screen. It does not open the video, and it is not explained in feature
lists.

Alternatives that fit other occasions: a pure gag loop (social), a question → reveal (quiz), a
build-up → lockup (logo), or a mystery → explanation (explainer). Pick what serves the occasion.

## 8. Never

- empty promises, or a hook the ending does not pay off;
- artificial waiting (padding, slow builds without new information);
- unnecessary countdowns, or "wait for it" tricks;
- disappointing resolutions (the reveal is weaker than the setup);
- invented numbers, testimonials, ratings, vote results, or performance promises;
- features that are on the roadmap but presented as available;
- fake UI that shows functions the product does not have.

## 9. Tone is chosen per occasion

Humor (none / dry / absurd), exaggeration, narrator (none / voiceover / on-screen character),
text amount, characters, camera work, pace, and information density all follow the occasion,
audience, and brand. A B2B security product can be funny, but the humor targets the situation,
never the customer's competence. State each choice and its reason in the concept.

## 10. Recognition

Recall comes from **one visual signature plus one recurring element**:
- **Visual signature**: a consistent style grammar (palette discipline, type treatment, motion
  character). See `style-kit.md`.
- **Recurring element**: an object, figure, mascot, shape, or **sound motif** (a 2–4-note sting,
  a characteristic click) that appears early, comes back at the climax, and closes the video. In
  a series it carries over between videos. Planted early and returning later fuller is the
  callback pattern; it must be the *same* element, not a look-alike.
- **Existing brand rules win**: logo usage, colors, fonts, tone, and do's and don'ts from the
  brand sources are constraints, not suggestions. A style from the kit is adapted *to* the brand,
  never the other way round.

## 11. Holds and stillness

Decide per piece and write the decision into the prompt:
- **Ambient idle** (1–2 % breathing scale, slow drift, live details) is the default for end frames
  and resting states. It avoids the "frozen frame" look.
- **Deliberate stillness** is a tool for comedic or dramatic pauses ("short contrasts and pauses").
  Use it on purpose, keep it short (about 0.3–1.2 s), and motivate it (a reaction, a beat of
  silence before the punchline).
- Never leave a hold unspecified.

## 12. Planning heuristics (not hard rules)

- Narration pace: about 2.2–2.7 words per second (130–160 words per minute) for clear delivery;
  dense explainers stay at the low end. Plan the script length from the target duration.
- On-screen text: give a line at least about 1 s per 3–4 words, and never less than about 1.2 s
  for anything meant to be read. Keep it to 1–7 words per beat on social.
- Captions: stay at or below about 17 characters per second.
- Pacing: showreel and social about 1.5–4 s per idea; explainers one idea per scene.
- Type size: display type about 1/10 of the frame width; nothing that must be read below about
  3.5 % of the frame height on mobile.
- Safe areas: on 9:16 social, keep text and faces clear of the top ~14 % and bottom ~20 % (platform
  UI). Name the exact values in the prompt.

Treat these as starting values. The production agent verifies them against the real voiceover
and rendered frames.
