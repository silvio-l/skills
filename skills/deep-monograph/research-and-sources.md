# Sources, Evidence, and Research Discipline

## Handling user-supplied sources and material

Supplied sources must be evaluated — but are never automatically treated as correct.

They may: co-determine the topic, supply leading questions, provide a starting thesis, contribute practical experience, or represent a position that itself needs critical checking.

For every supplied source, distinguish: verifiable factual claim, interpretation, personal experience, opinion, prognosis, advertising, sales argument, and speculation.

Check central factual claims from supplied sources as independently as possible. If a supplied source deviates from more reliable sources:

1. don't conceal the contradiction,
2. investigate possible causes,
3. check date, definitions, test conditions, and the source's interest position,
4. weight the more reliable evidence higher,
5. present remaining uncertainty transparently.

A supplied source bindingly shapes the *investigation subject* — it does not automatically shape the *result*.

## Video and audio sources

When a YouTube video or comparable audiovisual source is supplied, do the following as far as technically possible:

1. capture title, channel, creator, publication date, and description.
2. retrieve existing subtitles or the full transcription.
3. check whether the transcription is complete and plausible.
4. break the content into central topic blocks.
5. extract core statements, arguments, concrete claims, numbers, examples, recommendations, and recognizable assumptions.
6. distinguish fact, opinion, experience, advertising, and speculation within it.
7. check central factual claims against independent sources.
8. fold relevant aspects into the leading questions, research plan, and outline.
9. transparently flag missing or unreliable transcriptions.
10. **never claim to have fully evaluated the video when only the title, description, or short excerpts were actually available.**

The video may shape the topic and investigative angle, but it never substitutes for critical review.

## Source hierarchy

Prefer, generally, in this order:

1. laws, regulations, standards, and technical standards,
2. scientific primary sources and original datasets,
3. official technical documentation and specifications,
4. independent trade publications and traceable tests,
5. qualified practice reports,
6. forums, social media, and individual opinions — supplementary only.

A source's position in this hierarchy is not an automatic quality verdict — always check its suitability for the *specific* statement it's backing.

Examples: manufacturer documentation is well suited to prove an officially supported feature exists; it is poorly suited to prove that feature is superior to a competitor's. A practical test can deliver real-world performance figures; it does not replace a technical specification. A forum thread can flag that a problem exists; it does not establish how common that problem generally is.

## Evidence matrix

Maintain, for all essential factual claims, an evidence matrix with at least these columns:

| Field | Meaning |
|---|---|
| Claim | the concrete statement being checked |
| Statement type | verified finding, manufacturer claim, experience value, plausible inference, editorial recommendation, or open question — see §Statement types |
| Source | the supporting source |
| Source class | primary source, official documentation, independent secondary source, or experience report |
| Publication date | temporal placement |
| Currency check | still valid, probably valid, outdated, or unclear |
| Cross-check | second independent source present or not |
| Contradictions | conflicting sources or definitions |
| Certainty | high, medium, or low |
| Usage | which chapter or section uses it |
| Formulation | secured finding, cautious framing, or open question |

In single-response mode this matrix stays internal working state. In workspace mode, maintain it as `working/evidence-matrix.md`.

## Statement types — keep them distinct

Classify, mentally and where useful visibly:

- **Verified finding** — sufficiently backed by reliable, fitting sources.
- **Manufacturer claim** — published by the provider itself; not automatically independently confirmed.
- **Experience value** — a plausible observation from practical use, whose general applicability may be limited.
- **Plausible inference** — a traceable conclusion drawn from multiple findings.
- **Editorial recommendation** — a weighing made against openly disclosed criteria.
- **Open question** — not reliably decidable given the available source situation.

Never manufacture false certainty by blurring these categories together.

## Adaptive research saturation

Don't end research just because a fixed source count was hit. Research counts as sufficiently saturated only once:

- **Question coverage** — every central leading and sub-question is answered, or explicitly marked as currently not reliably answerable.
- **Evidence coverage** — every essential factual claim has an adequate basis; especially important, surprising, disputed, or consequential claims are cross-checked as independently as possible.
- **Source saturation** — further research steps mostly return repetition, not significant new findings.
- **Contradiction resolution** — relevant contradictions have been investigated; conflicts that can't be resolved are presented openly rather than hidden.
- **Perspective coverage** — important technical variants, counter-positions, drawbacks, and limits have been considered.
- **Practice coverage** — enough material exists to transfer the topic to realistic private-use scenarios.
- **Currency check** — time-dependent claims have been checked as close to the actual research completion date as possible.

Combine this with a hard technical safety limit to prevent endless loops. Guideline: normally three thorough research cycles (broad orientation → technical depth → targeted gap-closing and contradiction resolution — see `process.md` Phase 5); further cycles only for genuinely central gaps; never more full cycles than the time/cost/runtime budget can responsibly support.

If a technical limit is reached before saturation, document explicitly: remaining knowledge gaps, weakly supported claims, unresolved contradictions, and sensible starting points for future research. Never fake complete clarification.

## Partial research failure

A single failed lookup is not a license to invent. When a specific research step for a central claim returns nothing useful — no results, only marketing copy, or mutually contradictory noise — try one alternative angle or query formulation. If that also fails to produce a fitting source, classify the claim as an **open question**, note the attempted angles in the evidence matrix (or, in workspace mode, in `working/open-questions.md`), and move on. Never let one dead-end search quietly turn into a plausible-sounding but unsourced statement.

## Currency and timeliness

The work should be as current as technically possible at creation time. Use every available research tool consistently to check time-dependent facts up to the actual moment research concludes. Name a concrete research/currency cutoff date in the finished work.

Distinguish clearly between: time-stable fundamentals, the current state as of the research date, version-dependent properties, short-term-variable prices, availability, license terms, announced-but-unshipped features, actually available features, prognoses, rumors, and secured developments.

Don't write "The product supports feature X" when the more precise statement is "According to the manufacturer's documentation, version X supports the feature as of [research date]." Mark fast-aging information explicitly as a snapshot. Additionally convey time-stable decision criteria so a reader can independently judge later changes without this text needing an update.

In workspace mode, maintain `output/update-notes.md` listing: sections that age particularly fast, the relevant versions referenced, prices/availability, legal or license-relevant statements, and recommended points to revisit on a future update.

If live research capability is unavailable, state that plainly — never present possibly outdated model knowledge as though it were current, verified research.

## Citation practice in the finished work

Use a reader-friendly hybrid citation style.

**Cite immediately, inline**, for: concrete numbers, measured values, study results, benchmarks, legal statements, current developments, disputed claims, surprising or consequential facts, and literal or paraphrased quotes.

**Cite at the section level** for: consolidated technical explanations, historical overviews, or statements resting on multiple combined sources.

Mark manufacturer claims explicitly as such. Keep source finding, interpretation, and editorial recommendation visibly separate — never let a recommendation read as though it were the source's own conclusion.

Add an ordered source list, ideally with author/institution, title, publication date, version, source type, and retrieval date.

**Never invent** sources, URLs, titles, authors, publication dates, quotes, studies, standards, version numbers, or measured values. If a source can no longer be found or is only known indirectly, do not use it as a load-bearing citation.
