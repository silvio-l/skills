# Patterns Reference

This document explains what the scanner detects and why. It mirrors what
the lexicon files and `slop_scorer.py` actually implement — no over-claim.

## Tier logic

The scorer in `slop_scorer.py` uses three tiers with distinct surfacing
and scoring rules:

### Tier 1 — always surfaced

Every tier-1 finding is reported and contributes directly to the
**Directness** dimension (−1 per finding, floor 1/10). Tier-1 patterns
are high-confidence slop: the match is almost never correct in human-written
prose.

In the surfaced output (`--mode score`), all tier-1 findings appear.

### Tier 2 — cluster surfaced

Tier-2 findings are surfaced only when **≥3 tier-2 findings appear within
any 10-line window** (sliding window over sorted line numbers). A single
tier-2 occurrence in isolation is noise; a cluster is a signal that the
paragraph is structurally machine-like.

Tier-2 contributes to the **Trust** dimension (−1 per finding, floor 1/10).

### Tier 3 — density hint only

Tier-3 patterns are never surfaced as individual findings. The scorer
instead emits `tier3_density_hint: true` when the tier-3 count per 100
words exceeds 3.0. This hint means "the sentence rhythm feels repetitive"
— it is a prompt to vary structure, not a list of specific replacements.

The Authenticity dimension absorbs tier-3 hits at weight 1.0 (higher than
tier-1 and tier-2 at 0.5 each), because tier-3 patterns reflect a
pervasive structural signature rather than isolated vocabulary leaks.

## DE patterns

### Tier-1 (always replace)

These are hollow transitional openers and certainty phrases that appear
across AI-generated German text regardless of topic. Each has an
`suggested_replacement` in `lexicon.de.json`.

Examples of what the lexicon covers (exact entries are authoritative):

- Transitional openers: "Zudem", "Darüber hinaus", "Im Hinblick auf",
  "In Bezug auf", "Im Rahmen von", "Vor dem Hintergrund"
- Hollow certainty: "Es ist wichtig zu beachten", "Es ist zu beachten",
  "Selbstverständlich"
- Inflation particles that add zero meaning in context

**Nominalstil** — German AI text systematically prefers noun-heavy
constructions ("die Durchführung von Tests" instead of "Tests durchführen").
The lexicon targets the most common nominalisations where the verb form is
unambiguously better. Nominalstil that is domain-appropriate (legal,
technical specs) is not flagged.

### Tier-2 (cluster surfaced)

Structural hedging phrases that sound plausible individually but signal
machine origin when they cluster. Examples:

- "Es gilt zu berücksichtigen"
- "Im Allgemeinen"
- "grundsätzlich" (when used as an opener, not as a qualifier)

### Tier-3 (density hint)

Short filler words and particles that are grammatically correct but
over-represented in AI output: "letztendlich", "insgesamt", "entsprechend"
used as discourse markers. Individual occurrences are acceptable; a high
density per 100 words triggers the hint.

## EN patterns

### Tier-1 (always replace)

Hollow verbs and openers that the `blader/humanizer` and
`conorbronsdon/avoid-ai-writing` communities identified as the clearest
EN AI markers:

- Hollow verbs: "delve", "delve into", "harness", "leverage", "utilize",
  "revolutionize", "transform", "supercharge", "empower"
- Hollow openers: "In today's world", "In today's fast-paced world",
  "It is important to note that", "It is worth noting", "It goes without
  saying", "Needless to say"
- Hollow descriptors: "cutting-edge", "state-of-the-art", "game-changer",
  "seamlessly", "robust" (used generically)

### Tier-2 (cluster surfaced)

Hedging phrases that cluster in AI-generated EN explanatory text:

- "It is crucial to understand"
- "This is a testament to"
- "plays a pivotal role"
- "in the realm of"

### Structure/punctuation patterns (`structure_patterns.json`)

These are language-neutral and loaded from `structure_patterns.json`:

**Em-dash (U+2014)** — tier-1, always surfaced. The em-dash as a
stylistic separator ("tool — it helps") is a strong AI tell. The
scanner flags every occurrence. Suggested replacement: a plain hyphen
or a recast sentence. Note: em-dashes inside JSDoc/code comments in
`.ts` files will also be flagged; use `<!-- humanize:ignore -->` blocks
or the `humanize:ignore-file` marker to exclude code-only files from
scan if desired.

**Negative parallelism** ("nicht nur … sondern auch" / "not just … but
also") — tier-2. One instance is valid rhetoric; a cluster indicates
overuse. Surfaced when it appears in a tier-2 cluster window.

**Tricolon / rule-of-three** — tier-3, density hint only. A genuine
rhetorical tricolon cannot be reliably distinguished from an ordinary
three-item enumeration with surface heuristics. No individual finding
is emitted; only the density hint applies.

## What the scanner does NOT detect

- Grammar errors or awkward phrasing that is not in the lexicon.
- Style mismatches (formal vs. informal register).
- Factual errors.
- Repetition of ideas across paragraphs (structural level only).
- Content that is correct but could be shorter.

The scanner is a precision tool for known AI slop patterns, not a
general-purpose grammar checker or style editor.
