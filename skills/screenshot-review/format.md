# Formats — Finding, Per-Screen Report, Subagent Return, Master Report

All formats are deliberately **strict and machine-parseable**: stable IDs, fixed
severity enum, imperative recommendations. A downstream agent (or `/ratchet-up`
via `## Visual expectations`) must be able to work through the findings without
back-and-forth.

---

## Finding Format

Every finding is a Markdown block in exactly this structure:

```md
### <SCREEN-ID>-001 · <Category> · <Severity>

- **Area:** <concrete visible location, e.g. "Header / Main Heading">
- **Observation:** <what is visible in the image — anchored, no judgement>
- **Why problematic:** <effect on user/target audience>
- **Recommendation:** <imperative, actionable instruction; direction not invented number>
- **Expected effect:** <what fixing this achieves>
- **Confidence:** high | medium | low   <!-- low if vision-limited -->
```

Rules:
- **ID** = `<SCREEN-ID>-NNN`, sequential per screen (`<SCREEN-ID>` = filename without
  extension). This makes every recommendation globally uniquely referenceable.
- **Category** = one of the rubric areas, named exactly (e.g. `Typography`,
  `Accessibility`, `Component Quality`).
- **Severity enum:** `Critical` | `High` | `Medium` | `Low`. Calibration:
  - **Critical** — blocks usage/comprehension or violates a *declared* expectation
    from the briefing (token, design-language.md, manifest): clipped text, unreadable
    contrast, unrecognisable primary action, broken layout, wrong token colour against
    declared palette.
  - **High** — significant friction, but not blocking: weak hierarchy,
    inconsistent components, touch targets too small.
  - **Medium** — noticeable weakness without functional damage: spacing rhythm,
    inconsistent corner radii.
  - **Low** — polish/taste: micro-alignment, subtle colour nuance.
- **Confidence `low`** is mandatory when a finding depends on a vision-limited
  detail (1 px border, shadow, exact contrast) — the finding stays, but honestly
  flagged.

---

## Per-Screen Report — `screens/<screen-id>.md`

The reviewer subagent writes **this** file:

```md
# Screen Review: <screen-id>

- **File:** <relative path to screenshot>
- **Platform/Stack:** <from briefing>
- **Reviewed against:** <target audience + declared expectation source, or "no explicit context">

## Scores (0–100)
| Dimension | Score |
|---|---|
| UI Quality | NN |
| UX Quality | NN |
| Accessibility | NN |
| Consistency | NN |
| Audience Fit | NN |

## Findings
<all finding blocks, sorted by severity (Critical first)>

## Critical Issues
<bullet list of Critical finding IDs + one-liner; "none" if none>

## Prioritised Fix Order
1. <finding-ID> — <brief rationale for priority>
2. …
```

Score guideline: do not be generous. A screen with a Critical cannot score above
~50 in any dimension affected by that Critical.

---

## Subagent Return (to the orchestrator — NO report full-text)

The subagent returns **only** this compact line to the orchestrator (context-safe;
the full text lives in the file):

```
<screen-id> | scores: ui=NN ux=NN a11y=NN cons=NN fit=NN | findings: C=n H=n M=n L=n | top: <ID shortest Critical/High description>
```

If the subagent cannot find the screenshot or cannot read the image, it returns
`<screen-id> | ERROR: <reason>` and writes no file.

---

## Master Report — `report.md` (orchestrator, Phase 2)

```md
# Screenshot Review — Master Report (<YYYY-MM-DD>)

- **Folder:** <screenshot-folder>
- **Screens:** <n>
- **App context:** <target audience · purpose · platform · design system (1 line)>

## Score Overview
| Screen | UI | UX | A11y | Consistency | Fit | Critical |
|---|---|---|---|---|---|---|
| <screen-id> | NN | NN | NN | NN | NN | n |
| … |

## Critical Issues (all screens)
<list of all Critical finding IDs with screen + one-liner>

## App-Wide Consistency Patterns
<ONLY here: same component styled differently across screens, inconsistent
AppBars/buttons/spacing scale/corner radii across the folder. Reference the
affected finding IDs from individual reports. Do not invent aggregate
inconsistencies that appear in no individual report.>

## Globally Prioritised Worklist
| # | Finding ID(s) | Screen(s) | Severity | Effort (S/M/L) | Action |
|---|---|---|---|---|---|
| 1 | … | … | Critical | S | <imperative action> |

Order: severity first, equal severity → smaller effort first. App-wide
patterns (one fix clears multiple screens) before single-screen findings.
```
