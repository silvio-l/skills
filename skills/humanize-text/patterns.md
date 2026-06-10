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

## Where each tier lives

This matters for reading the JSON: **the two lexicon files
(`lexicon.de.json`, `lexicon.en.json`) contain tier-1 entries only** —
high-confidence word/phrase slop that is almost always worth replacing.
Tier-2 and tier-3 are **not** lexical; they live in
`structure_patterns.json` (negative parallelism = tier-2, tricolon =
tier-3) because they are rhetorical structures, not vocabulary. So the
DE/EN sections below describe lexical tier-1 only.

## DE patterns (`lexicon.de.json`, all tier-1)

Each entry carries a German `suggested_replacement` and `rationale`. The
JSON is authoritative; the groupings below are just orientation.

- **Transitional openers / connectives:** "Zudem", "Darüber hinaus",
  "Im Hinblick auf", "Letztendlich".
- **Hollow certainty / hedging preambles:** "Es ist wichtig zu beachten",
  "Es sei darauf hingewiesen", "von entscheidender Bedeutung",
  "Zusammenfassend lässt sich sagen".
- **Marketing superlatives (calques):** "nahtlos" (seamless), "mühelos"
  (effortlessly), "ganzheitlich" (holistic), "bahnbrechend"
  (groundbreaking), "wegweisend", "revolutionär", "unverzichtbar",
  "facettenreich", "tiefgreifend".
- **Dead metaphors / empty role claims:** "spielt eine entscheidende
  Rolle", "ebnet den Weg", "eintauchen" (delve into).
- **Relevance throat-clearing:** "In der heutigen Welt".

### Inflection (`"inflect": true`)

German adjectives and participles almost always appear **declined**
("nahtlose Integration", "ganzheitlichen Ansatz"), so an exact `\b…\b`
match on the lemma would miss most real occurrences. Entries whose endings
are purely **additive** opt in with `"inflect": true`; the scanner then
compiles the trailing boundary as `\w*\b`, matching the stem plus any
declension suffix (-e, -en, -er, -es, -em). It is enabled only for the
adjective/participle entries above, never for phrases, and never for
English (where common forms drop a stem letter — "leverage" →
"leveraging" — so `\w*` would both miss them and over-match). See
`tests/humanize-text/test_inflection.py`.

**Nominalstil** — German AI text leans on noun-heavy constructions ("die
Durchführung von Tests" instead of "Tests durchführen"). This is a known
tell but is *not* in the lexicon: it cannot be matched by a word list
without flagging domain-appropriate technical/legal prose. Left to the
rewrite pass, not the scanner.

## EN patterns (`lexicon.en.json`, all tier-1)

Hollow verbs, descriptors and openers that the `blader/humanizer` and
`conorbronsdon/avoid-ai-writing` communities identified as the clearest EN
AI markers. The JSON is authoritative; groupings are orientation:

- **Hollow verbs:** "delve", "leverage", "utilize", "harness",
  "facilitate", "foster", "underscore", "showcase", "boast", "embark",
  "elevate", "unlock".
- **Inflated descriptors:** "groundbreaking", "robust", "crucial",
  "pivotal", "intricate", "comprehensive", "seamless"/"seamlessly",
  "cutting-edge", "game-changer", "vibrant", "ever-evolving".
- **Showy quantifiers / nouns:** "myriad", "plethora", "tapestry",
  "landscape", "realm", "testament".
- **Stock connectives:** "moreover", "furthermore", "additionally".
- **Hollow openers / framing phrases:** "in today's world", "it's worth
  noting", "it is important to note", "when it comes to", "at the end of
  the day", "in the realm of", "plays a vital role".

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
