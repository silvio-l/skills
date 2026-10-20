# Quality checklist

Two parts. §1 is the planner's own gate before the production prompt goes to the user. §2 is
the background for section 9 of the prompt: the QA protocol the production agent follows. The
template already contains §2 in executable form; read §2 when you adapt budgets or gates to a
specific video.

## §1. Hand-over gate (planner, before showing the prompt)

Run all of it. Report the actual results to the user, including warnings you chose to accept
and why. Never write "checked" for a check you did not run.

### 1. Mechanical check

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_prompt.py" <plan-dir>/production-prompt.md --assets-root <base path of section 7>
```

- Exit code 0 is required. Fix every error and run it again.
- Warnings (reading speed, unchecked asset existence) need a decision: fix it, or keep it and
  say why in the summary to the user.
- The script checks structure only. Items 2–7 below are your judgment.

### 2. Consistency and geometry pass (do the arithmetic, don't eyeball)

All three validation runs of this skill passed the checker and still failed a cold read on
exactly these points. Go through them one by one:
- **Every number that appears twice agrees.** Collect each time (scene bounds, transition
  points, SFX sync points, the holds, idle cycles, the rule sections in §4 and §9) and compare. An
  idle loop or a hold must end at or before the planned duration.
- **Rules versus scenes.** Each rule in section 4 (accent only on …, eases, shadow spec, motion
  durations) is checked against every scene that uses the element. A scene that breaks a rule is
  either changed, or the rule names the exception.
- **Text fits.** Estimate the width of each on-screen line: characters × font size × about 0.55
  (regular or medium sans, weights 400–600), 0.6 (bold or extra-bold sans, 700+), or 0.5
  (condensed). Measure the real font when a line is within 10 % of the limit. Compare it with the safe
  width (frame width minus the side insets) and include overshoot scale-ups. If a line does not
  fit, set the line break or the size in the prompt; do not leave it to the executor. Caption
  limits (characters per line) must hold for the copy as written.
- **Nothing collides.** For each scene, write the vertical (and horizontal, where needed) extent of
  every element, as center ± half size, and check that nothing overlaps unintentionally and that
  stated clear spaces hold. Image sizes come from the asset's real aspect ratio (viewBox or pixel
  size).
- **Count mechanically.** Letter indices, word counts, list positions: count them with a script
  or by writing them out (`B-O-H-N-E-N…` → "O" is letter 2), never from memory.
- **Copy strength matches the source.** "No" needs a source that says no. If the source says
  "negligible", the copy says "barely" or "not noticeably".
- **Honest scales.** A small difference may be magnified (zoom, inset) only with a visible scale
  reference or a label saying it is magnified; otherwise draw it to scale.
- **Allowed versus forbidden.** A limit in section 1 ("no invented logo elements") must not
  forbid what section 7 asks for. Name provisional elements as allowed, explicitly.

### 3. Cold-read test (self-containment)

Read the prompt as an agent that has never seen the chat, the concepts, or the repository:
- Could it start without asking anything? Every path, name, color, font, text, and sound is
  concrete.
- Does any sentence assume knowledge from the planning ("the yellow note" before the note is
  defined, "the usual logo", "the approach we chose")?
- Are the permissions and stop points unambiguous (what to install, what never to touch, when
  to ask the user)?

**If a subagent is available, this cold read is mandatory and done by the subagent**, not by
you: you know the context and will not notice its gaps. Give it only the prompt file (and the
product repository, read-only), forbid it to read the plan files, and ask for: every question it
would have to ask (split into *blocking* and *minor, decidable by the executor under the
brief's latitude rule*), every contradiction, every element without a full spec, and a verdict
(executable as-is / with minor guesses / not executable). Every question is a defect: fix it,
re-run the checker, and repeat the cold read until the verdict is at least "minor guesses" and
the remaining guesses are listed for the user. At most two rounds; then report what is left.
Without subagents, do the cold read yourself after a break (a fresh look at the file only) and
say that it was a self-review.

### 4. Evidence

- Every product claim in the copy appears in Appendix B with a path, URL, or "stated by the user
  on <date>".
- No roadmap item, no contradicted claim, no invented number, testimonial, rating, or vote
  result. Interactive formats (quiz, prediction, comparison, dilemma) reveal facts, never fake
  audience results.
- Every `exists` asset was verified in this session (the script does this with
  `--assets-root`).

### 5. Story and creative fit

- The first frame is the hook, and the situation is clear by about 3 s without sound.
- Each scene has an actor, a reaction, and a consequence. No scene is a text slide.
- The hook's open question is answered, and the answer is worth the wait (no empty promise, no
  artificial countdown, no anticlimax).
- The product enters after the problem was felt, as a surprising helper (or the brief explains
  why another dramaturgy fits better).
- The recurring element is planted, pays off, and appears in the close.
- The selected concept is still recognizable. Details may have changed during writing; the hook,
  protagonist, and dramaturgy may not have changed without telling the user.

### 6. Production realism

- The workflow route fits (`hyperframes-facts.md` §2), especially: narration never in
  `/motion-graphics`.
- Every named block, transition, and effect is either verified now or listed in step 0 for
  verification by the executor.
- Alpha output is only planned in MOV ProRes 4444 or WebM VP9, never in MP4 or at 4K.
- Paid generation appears only with an approved budget. A free path is named for every asset
  that could otherwise need money.
- Timings are marked as planned. The voiceover word count fits the planned durations (about
  2.3–2.8 spoken words per second for German, about 2.5–3 for English). `check_prompt.py` warns
  only above 3.0 words/s; that is the hard ceiling, not the target.
- Every `user` asset is listed for the user in the hand-over message with what exactly to supply
  and by when. The checker warns about each one; that warning stays until the file exists.

### 7. Delivery to the user

Show: the path of `production-prompt.md`, a 5–8 line summary (concept, duration, format,
workflow, assets to create, budget), the check results, the remaining risks, and how to run it:
open a fresh Claude Code session in the target project and say "Execute
`<path>/production-prompt.md`." Offer to adjust; do not start production yourself.

## §2. QA protocol for the production agent (background for section 9)

### Order: story before detail

1. **Blocking pass**: placeholder shapes in final positions, final copy, rough timing. Review
   stills. A story problem found after polishing costs every polished frame again.
2. **Audio pass**: voiceover with word timestamps → re-time scenes → SFX on visual events →
   music under the voice.
3. **Detail pass**: look, motion, transitions.
4. **Technical gates**: `lint` and `check` with zero errors.
5. **Frame review**: first frame, every scene midpoint, every transition midpoint, last frame.
6. **Draft render with sound**, watched in full.
7. **Final render** plus file verification (`ffprobe`: duration, resolution, fps, codec, audio
   streams; alpha if planned).

### Revision priority

Opening → development → resolution → brand effect. A weak opening with a perfect logo lockup is
the worse video. Fix the highest failing level first, then re-check everything the fix touches.

### Budget and stop criteria (defaults; adapt per video)

| Video | Review cycles | Draft renders | Final renders |
|---|---|---|---|
| Logo sting or clip ≤ 10 s | 2 | 3 | 1 (+1 on a delivery-check failure) |
| Social clip 15–45 s | 3 | 4 | 1 (+1) |
| Explainer > 45 s | 3 | 5 | 1 (+1) |

Stop and report, instead of looping, when:
- the budget is used up;
- the same failure survives two fix attempts;
- a fix would need a decision outside the brief (new claim, paid asset, story change);
- the environment blocks an essential step (no HyperFrames, missing voice for the language).

### Honest reporting

`PRODUCTION-LOG.md` contains the commands actually run and their results. Anything not verified
is listed under "Not verified". A render that was not watched with sound is not "reviewed".
