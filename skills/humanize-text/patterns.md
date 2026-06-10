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

Most tier-2 findings are surfaced only when **≥3 tier-2 findings appear
within any 10-line window** (sliding window over sorted line numbers). A
single tier-2 occurrence in isolation is noise; a cluster is a signal that
the paragraph is structurally machine-like.

**Exception:** the high-confidence structural tells `struct_anaphora` and
`struct_adj_tricolon` (in `ALWAYS_SURFACE_IDS`) bypass the cluster gate and
are surfaced even in isolation — a single "Kein X. Kein Y." staccato or
"— groß, klar, motivierend" burst is already a clear tell.

Tier-2 contributes to the **Trust** dimension (−1 per finding, floor 1/10),
regardless of whether it is surfaced.

### Tier 3 — density only (never per-occurrence)

Tier-3 patterns are never surfaced as individual findings. The scorer
emits `tier3_density_hint: true` when the tier-3 count per 100 words
exceeds 3.0.

The two tier-3 patterns differ in how they touch the score:

- **Em-dash (`punct_em_dash`)** — its *density* now drives a real penalty on
  the **Density** dimension (see "Em-dash density" below). A handful of
  intentional em-dashes is free; a text peppered with them is dragged down.
  Individual occurrences are still never surfaced or deducted one-by-one.
- **Generic tricolon (`struct_tricolon`)** — documented only; no regex runs
  and it never affects the score (it cannot be told apart from an ordinary
  enumeration). Its high-confidence sub-variants are detected at tier-2
  instead — see `struct_adj_tricolon` and `struct_anaphora` below.

## Where each tier lives

This matters for reading the JSON: **the two lexicon files
(`lexicon.de.json`, `lexicon.en.json`) contain tier-1 entries only** —
high-confidence word/phrase slop that is almost always worth replacing.
Tier-2 and tier-3 structural tells are **not** lexical; they live in
`structure_patterns.json` (anaphora + adjective-tricolon + negative
parallelism = tier-2, em-dash + generic tricolon = tier-3) because they are
rhetorical/punctuation structures, not vocabulary. So the DE/EN sections
below describe lexical tier-1 only.

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

These are language-neutral and loaded from `structure_patterns.json`. All
run over the same strategy-aware prose segments, so a match inside a `.ts`
comment, code, or an HTML tag is never produced — only real copy.

**Em-dash (U+2014)** — tier-3, density only. Em-dash over-use is a
*frequency* tell, not a per-occurrence one (2026 research: Pangram;
Wikipedia "Signs of AI writing"). The scanner records each occurrence but
**never surfaces it as a finding and never deducts it one-by-one**. What
changed in the 2026 rework: the *density* now feeds the **Density**
dimension (see below), so a text peppered with em-dashes loses points even
though no single dash is flagged.

**Negative parallelism (`struct_neg_parallelism`)** — tier-2, cluster-gated.
A rhetorical template LLMs over-use to perform balance. Detected frames
(DE + EN): "nicht nur … sondern auch", "es geht nicht (nur) um … sondern
um", "not just/only … but (also)", "it's not X, it's Y", "not a X, but a
Y". One instance is valid rhetoric, so it surfaces **only inside a tier-2
cluster** (≥3 tier-2 findings in a 10-line window).

**Anaphora (`struct_anaphora`)** — tier-2, **always surfaced**. Consecutive
sentences/fragments that open with the same word — the "Kein X. Kein Y.
Nur Z." / "No X. No Y." marketing staccato. Fires on a run of **≥3**
consecutive sentences with a shared opener, or **≥2** when the opener is a
negation (kein*/nicht/no/not …). It does **not** collide with ordinary
enumerations ("Python, JavaScript und TypeScript" is one sentence, not
three with a shared opener), and generic openers (der/die/das/the/a/and …)
are stop-listed so they never count by chance.

**Adjective tricolon (`struct_adj_tricolon`)** — tier-2, **always surfaced**.
The clause-final three-word burst — "— groß, klar, motivierend",
"einfach, visuell, motivierend", "fast, clean, reliable". A 2026 German
source (contentconsultants) names "3 kommagetrennte Adjektive nach
Gedankenstrich" explicitly. Two shapes: (1) a dash/colon then exactly three
single-word items at the clause end, (2) a whole short segment that is
nothing but three comma/und-separated single words. The separator between
items 2 and 3 must be a comma or "und/and/&" — never bare whitespace — so
"verschlüsselt, mit Passwort" (two items, one multi-word) is not a triple.

A bare three-word list is inherently ambiguous: "groß, klar, motivierend"
is a tell, but "Lebensmittel, Mobilität, Freizeit" / "groceries, transport,
leisure" is a legitimate enumeration. **German** disambiguates by
capitalisation (nouns are capitalised), so the detector requires the 2nd and
3rd items to be lowercase — a capitalised list is treated as an enumeration
and skipped (this applies to both shapes in DE). **English** has no such
signal, so the whole-segment bare list is *not* detected for English at all;
English relies on the stronger dash/colon shape. This is a deliberate
precision-over-recall choice: it is better to miss an English bare triple
than to flag every three-noun list.

**Generic tricolon (`struct_tricolon`)** — tier-3, documented only. No regex
runs; it never surfaces and never scores. A genuine rhetorical tricolon
cannot be told apart from an ordinary three-item enumeration with surface
heuristics, so only the two high-confidence sub-variants above are detected.

### Em-dash density (soft frequency check)

The single biggest behaviour change of the 2026 rework. Counted in the
**Density** dimension (`slop_scorer._em_dash_penalty`):

- Below `EM_DASH_DENSITY_FLOOR` (1.0 per 100 prose words): **no penalty**.
- Above it: `EM_DASH_PENALTY_SLOPE` (1.2) points per unit, capped at
  `EM_DASH_PENALTY_CAP` (5.0).

This is the "softer" check the per-occurrence model could not express: it
lets deliberate human em-dash style through while dragging down text that
sprinkles them formulaically.

### Prose-only scoring & rhythm neutralisation

Two scorer inputs were fixed so fragment-heavy files (i18n `.ts`) score on
their real copy:

- **Prose extraction** (`slop_scanner.extract_prose_text`): segments shorter
  than 5 words (UI labels like "EN", "App laden", "Premium") are excluded
  from the scoring denominators, so a slop-dense paragraph is no longer
  diluted by dozens of nav strings. Lexical/structural *matching* still runs
  over everything; only Density and Rhythm use the prose-only text.
- **Rhythm neutralisation**: for `.ts` files the Rhythm dimension is held at
  `NEUTRAL_RHYTHM` (5.5). Concatenated independent UI strings have
  meaningless sentence burstiness — they are neither handed a free 10 nor
  punished. Flowing prose (`.md`, `.astro`, `.html`) keeps the real
  burstiness measure.

### Always-surfaced vs cluster-gated tier-2

Tier-2 normally surfaces only inside a cluster. The high-confidence
structural tells (`struct_anaphora`, `struct_adj_tricolon`, listed in
`slop_scorer.ALWAYS_SURFACE_IDS`) bypass the cluster gate and always
surface; only the softer `struct_neg_parallelism` stays cluster-gated.

## What the scanner does NOT detect

- Grammar errors or awkward phrasing that is not in the lexicon.
- Style mismatches (formal vs. informal register).
- Factual errors.
- Repetition of ideas across paragraphs (structural level only).
- Content that is correct but could be shorter.

The scanner is a precision tool for known AI slop patterns, not a
general-purpose grammar checker or style editor.
