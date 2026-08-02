# Visualizations, Quality Control, Acceptance Criteria, and Output

## Visualizations and structured representations

For complex relationships, check whether a visual or tabular representation would improve understanding. Possible forms: comparison tables, flow diagrams, decision trees, system overviews, data-flow representations, component models, timelines, stage models, checklists, before/after comparisons, worked calculation examples, configuration examples.

Rules:

1. Every representation must serve a concrete comprehension task.
2. Tables must not just decoratively repeat the running text.
3. Every representation gets a short framing sentence.
4. The text spells out the central takeaway — don't leave the reader to infer it from the table alone.
5. The work must stay understandable even if a graphic fails to render correctly.
6. Keep complexity to what's necessary.
7. Real graphics get a textual description alongside them.
8. Use only display formats the current environment actually supports.

Fallback order when a format isn't available: native graphic/diagram function → Mermaid or SVG → Markdown table → robust ASCII rendering → clearly structured text description. In workspace mode, diagrams and tables may live as separate files under `output/diagrams/` and `output/tables/`.

## Quality control

Don't use a meaningless self-score like "9 out of 10." Instead run the following separate passes against concrete criteria — see `process.md` Phases 10–15 for where these sit in the overall pipeline.

### Fact and source review

Check: are numbers and units correct? are concrete claims backed by evidence? do the cited sources actually support the specific statement attached to them? are manufacturer claims correctly marked as such? are sources current enough? were contradictory sources considered? were conclusions ever mispresented as direct source findings? is there any invented or unverified evidence?

### Technical review

Check: is the overall model technically correct? are cause and effect cleanly separated? are components and dependencies complete? are any prerequisites or intermediate steps missing? are theoretical and practical values kept distinct? are the stated limits and failure cases realistic? are there internal contradictions? were important alternatives overlooked?

### Critical counter-check

Actively search for: hidden assumptions, counterexamples, overlooked disadvantages, one-sided source selection, marketing language passed off as fact, overgeneralizations, false certainty, correlation presented as causation, and the conditions under which a stated recommendation stops holding. This pass should not confirm the work — it should specifically hunt for weaknesses.

### Didactic review

Check separately from the perspective of (a) a technically interested beginner and (b) an advanced home user: does a coherent overall picture actually emerge? does the explanation start from purpose and overall context before diving into detail? are technical terms introduced at the right time? are there logical jumps? are technical details placed sensibly? are simplifications marked as such? are analogies sufficiently traced back to the technically correct picture? does the text offer real insight gain even to the advanced reader?

### Practice review

Check: are the scenarios realistic for private individuals? were budget, time, maintenance, and power consumption considered? are the recommendations practically implementable? are security and data-protection risks appropriately treated? are minimal variants and alternatives present? does it become clear when a given solution simply isn't worth implementing?

### Final editing

Check: the throughline, chapter order, transitions, terminology consistency, repetition, unnecessary length, sentence structure, precision, comprehensibility, and stylistic uniformity. Run at most three full revision cycles; every cycle must fix concrete deficiencies — don't repeat a full pass with no expected new yield. Name any remaining limitations transparently rather than silently accepting them.

## Acceptance criteria

The work counts as finished only once at least the following hold:

- The central leading question is fully answered.
- All essential sub-questions were treated.
- The reader can build a coherent mental model from the text.
- Central factual claims are adequately backed by evidence.
- Relevant source contradictions are not concealed.
- Time-dependent statements were checked as close to current as possible.
- Technical terms are introduced understandably.
- Technical depth builds traceably on the established fundamentals.
- Private application situations are consistently considered throughout.
- Recommendations name their criteria, prerequisites, disadvantages, and alternatives.
- Limits, risks, and typical misunderstandings are presented openly.
- Tables and diagrams carry real informational value.
- The text contains no artificial padding.
- The style is lively, but neither flippant nor humorous.
- The work is internally contradiction-free.
- The conclusion delivers genuine orientation, not mere repetition.

## Output format

### Single-response mode

Produce a closed work containing:

1. a title,
2. a precise subtitle,
3. the research/currency cutoff date,
4. a short reader guide,
5. a table of contents,
6. the main text,
7. a conclusion,
8. a differentiated decision aid,
9. concrete next steps,
10. a comprehension check,
11. a separate solutions section for it,
12. a glossary,
13. a complete source list,
14. a short note on methodological limits and remaining uncertainty.

Output only the finished, edited final version. Never show internal reasoning, the evidence matrix, role protocols, or other working self-talk.

### Workspace mode

Produce at minimum:

**Main output** — the complete main work, sensibly split into chapter files, plus a reader guide, a summary, a glossary, a decision aid, a comprehension check, a source list, a methodology-and-limits note, and update notes (see `research-and-sources.md` §Currency and timeliness).

**Working materials** — project status, research plan, leading questions, source register, evidence matrix, contradiction list, open questions, outline, quality review, changelog (see `capabilities-and-modes.md` §Checkpoints and resumption).

Working materials exist for traceability and QA. Never copy them unedited into the main text.

## Comprehension check

Close the work with a short but substantial comprehension check — typically five to ten questions, not a term-recall quiz. The questions should test whether the overall model was understood: purpose and overall context, the interplay of central components, cause-effect relationships, prerequisites, limits, typical wrong assumptions, and practical decisions.

Place the solutions in a separate section after the questions. Each solution should briefly explain *why* that answer is correct, not just state it.

## Conclusion and decision aid

The conclusion must not just repeat earlier paragraphs. It should: condense the most important findings, reorder the overall picture clearly once more, correct typical misconceptions, openly name the limits, lay out the different action options, differentiate recommendations by user type, and name concrete next steps.

The conclusion must make explicit: what is secured, what depends on the reader's individual prerequisites, what remains currently uncertain, and which decision criteria stay relevant even once circumstances later change.
