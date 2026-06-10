# Rewrite Playbook

This document is the binding protocol for the **rewrite mode** of
`humanize-text`. Read it in full before touching any source file.

## When rewrite mode is allowed

Rewrite mode is opt-in. It is triggered only when the user explicitly
asks for a rewrite — phrases like "mach das menschlicher", "rewrite
this to remove the slop", or "apply the humanize suggestions". Scan
and score are always read-only; they never modify files.

**Do not ask the user "should I rewrite?" unprompted.** If scan/score
show findings, report them and wait. Only enter rewrite mode on explicit
request.

## The two-pass protocol

### Pass 1 — script-first diagnosis

Before touching a word, run the scanner and read every finding:

```bash
python3 scripts/humanize.py --mode score --format text <file>
```

Collect:
- All tier-1 findings (always surfaced — must address).
- The always-surfaced structural tells: `struct_anaphora` ("Kein X. Kein Y."
  staccato) and `struct_adj_tricolon` ("— groß, klar, motivierend"). These
  surface even in isolation — address each one.
- Tier-2 cluster findings (`struct_neg_parallelism`, surfaced when ≥3 in a
  10-line window).
- The tier-3 density signals: em-dash density (drives the Density score —
  if it is low, thin out the dashes) and the generic-tricolon hint.
- The five dimension scores (directness, rhythm, trust, authenticity,
  density). For `.ts` dictionaries, rhythm is neutral by design — ignore it.

Do not start rewriting until you can answer: "Exactly which lines and
patterns are the problem?"

### Pass 2 — targeted rewrite

Rewrite **only the lines identified in Pass 1**. Work finding by finding.
After each edit, mentally re-run the match: would the scanner still flag
that line? If yes, the replacement is still slop.

After the full pass, re-run the scorer mentally (or actually) to confirm
the `overall` score moves above the threshold.

## Hard protection rules

### 1. Invent nothing

This is the hardest rule and it is absolute.

- No new facts, numbers, dates, statistics, or claims that were not in
  the original text.
- No invented citations, source names, or attributions.
- No summaries that broaden the scope of the original.
- If a slop phrase is wrapping a real claim ("Es ist wichtig zu beachten,
  dass der Service seit 2022 verfügbar ist"), the claim stays and the
  wrapper goes ("Der Service ist seit 2022 verfügbar").

If removing slop would leave a sentence that requires invented content
to make sense, flag the sentence to the user instead of rewriting it.

### 2. Protect proper nouns

The following names and identifiers must survive every rewrite unchanged:

- Project names: `loam`, `whispaste`, `hellerio`, `skills`
- Organisation names (e.g. "Silvio Lindstedt und Maik Gräfendorf GbR")
- Domain names (e.g. `silvio-lindstedt.de`, `silvio-und-maik.de`)
- Any other proper noun in the original text

If a proper noun is part of a sloppy phrase, split the phrase, not the
name. Example: "Im Bereich von loam" → "Bei loam" (name intact, filler
removed).

### 3. Protect technical terms

Technical vocabulary must not be paraphrased away:

- Language and framework names: Dart, Flutter, TypeScript, Astro, Python
- API / library names, version strings, URLs
- Domain-specific acronyms the original author chose deliberately

When in doubt, ask the user whether a term is intentional.

### 4. Preserve register and tone

Match the register of the original. If the source is terse and technical
(a `.ts` data file), the rewrite must also be terse. If the source is
warm and conversational (a landing-page `.astro` component), stay warm.
Do not upgrade informal copy to formal prose or vice versa.

### 5. Do not rewrite suppressed regions

Lines inside `<!-- humanize:ignore -->` / `<!-- /humanize:ignore -->` and
files with `<!-- humanize:ignore-file -->` are out of scope, even in
rewrite mode.

## What counts as slop (quick reference)

See [patterns.md](patterns.md) for the full tier breakdown. The patterns
most likely to survive in live-site copy:

**DE** — transitional openers: "Zudem", "Darüber hinaus", "Im Hinblick
auf"; hollow certainty: "Es ist wichtig zu beachten", "Es ist zu
beachten"; marketing superlatives: "kinderleicht", "im Handumdrehen",
"mehr denn je"; Nominalstil where a verb form exists.

**EN** — hollow verbs: "delve", "harness", "leverage", "revolutionize";
marketing superlatives: "effortless(ly)", "must-have"; hollow openers: "In
today's …", "It is important to note that", "It is worth noting".

**Structure (both languages)** — anaphora ("Kein X. Kein Y. Nur Z." /
"No X. No Y."), the clause-final adjective triple ("— groß, klar,
motivierend"), negative parallelism ("nicht nur … sondern auch"), and
em-dash over-use. Break the staccato into varied sentences; demote one
adjective or recast the triple; replace em-dashes with commas/parentheses
or a full stop. Vary, don't mechanically substitute.

## Confirmation flow (binding)

1. Run Pass 1. Show the user the score and a list of the targeted lines.
2. Propose the specific replacements for each finding, line by line.
3. Ask once: "Soll ich diese Änderungen anwenden?" (or in EN: "Apply
   these changes?"). Wait for explicit yes/no.
4. On yes: apply the edits. On no: report what you found and stop.
5. Never apply changes before confirmation, even if they are obviously
   correct.

## What rewrite does NOT do

- It does not improve style beyond removing the specific found patterns.
- It does not restructure paragraphs, adjust headings, or expand content.
- It does not fix grammatical errors unrelated to slop.
- It does not generate placeholder text for gaps in the original.

Rewrite is a precision scalpel, not a full copyedit.
