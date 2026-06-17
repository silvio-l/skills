# Audit Rubric — the 13 Analysis Areas

The reviewer works through **every** area for its one screenshot. Per area:
actively look for problems, assume nothing is correct — but anchor every finding
to a *visible* element in the image. If an area yields nothing, note it briefly;
do not invent findings to fill the list.

Cross-cutting discipline (applies everywhere):
- **Relative, not falsely precise.** Exact px/hex/contrast ratios from a screenshot
  are guesswork. Describe proportions ("headline barely heavier than body"), not
  absolute values. Recommendations give the *direction* ("increase headline
  weight/size noticeably, pull body back"), not an invented target number.
- **Declare vision limits.** 1 px borders, shadow spread, exact contrast values,
  sub-pixel alignment are not reliably detectable by vision. Where a judgement
  depends on one of these, write "not confidently assessable from the screenshot"
  in the finding instead of guessing.

---

## 1. First Impression
3-second verdict: modern / high-quality / trustworthy / professional — or
cluttered / empty / inconsistent / unclear? Name the effect concretely and what
in the image produces it.

## 2. Visual Hierarchy
Is it immediately clear what matters? Clear focal point? Are important elements
emphasised, unimportant ones de-emphasised? Do elements compete for attention?

## 3. Layout & Spacing
Outer/inner spacing, grid consistency, alignment, padding/margins, safe areas,
visual balance, rhythm. Look for: irregular spacing, inconsistent indentation,
visual jumps, poorly aligned elements.

## 4. Typography
Size ratios, line height, legibility, weights, heading hierarchy, text contrast,
line lengths/breaks. Look for: text too small/large, inconsistent sizes, missing
hierarchy, clipped text.

## 5. Colours
Palette, brand effect, consistency, contrast, highlight/focus/CTA colours. Look
for: unnecessary colours, weak contrasts, visual noise, missing colour strategy.
Check against `design/tokens.json` if declared in the briefing.

## 6. Component Quality
Every visible component (buttons, cards, dialogs, navigation, lists, forms,
chips, tabs, badges, FABs, search fields, dropdowns): consistency, size,
modernity, recognisable tappability, adequate touch target size.

## 7. Mobile UX
Thumb reachability, one-handed operation, information density, recognisable
scroll behaviour, prioritisation. Look for: unnecessary steps, poor placement of
key actions, ergonomic issues.

## 8. Accessibility
Colour contrasts (qualitative, using WCAG 2.2 as reference), font sizes, touch
target size, legibility, and — where derivable from the image — screen-reader
suitability (icon-only buttons without labels, etc.). Never state contrast as an
exact ratio.

## 9. Design System Consistency (within this screen)
Inconsistencies *within this one screen*: deviating corner radii, shadows, sizes,
spacing, duplicate component variants. **Cross-screen consistency does NOT belong
here** — the orchestrator assesses that in the synthesis.

## 10. Information Architecture
Comprehensibility, groupings, ordering, mental models. Key question:
"Does the target audience immediately understand what is happening here?"

## 11. Audience Fit
Does the screen match the target audience defined in the briefing? Assess language,
complexity, information density, colour choice, emotionality, professionalism.
Explain every deviation. If the target audience is `UNKNOWN`, skip this area and
note it — do not guess.

## 12. Emotional Effect
What effect does the screen convey (modern / dated / technical / friendly /
trustworthy / premium / cheap / professional / playful)? Does it match the app's
purpose?

## 13. Flutter-Specific Quality
Signs of: unstyled default widgets, Material 3 inconsistencies, inconsistent
AppBars, weak responsive adaptation, typical Flutter anti-patterns (e.g.
default purple, uniform 16-radius, generic default font). Apply only if the
briefing declares Flutter as the stack; otherwise skip.
