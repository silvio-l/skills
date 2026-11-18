---
name: redaktion
description: "Write or edit natural, human-sounding explanatory texts for a broad audience (blog posts, newsletters, release announcements, explainers), German first. Use for 'Blogartikel', 'Newsletter', 'Release-Ankündigung', 'Erklärtext', 'blog post'."
argument-hint: "[genre] [topic or file] [optional angle]"
---

# Redaktion

Write or edit this text: $ARGUMENTS

The reader came to understand something, not to be sold to. The text should read like a person who knows the subject explaining it to someone they respect: concrete, calm, sometimes funny, honest about limits. Every fact must come from a source you actually read.

`S` below is this skill's directory (`${CLAUDE_SKILL_DIR}`, fallback `~/.claude/skills/redaktion`).

## Files

- `S/TASTE.md` — the editorial taste: openings, rhythm, explaining, address, structure, endings, humour, what to avoid, before/after pairs in German and English, and how it differs from landing-page copy. Read it before the first draft, every time.
- `S/references/announcements.md` — release announcements, newsletters and milestone posts: how to sound proud without superlative chains. Read it when the text announces something.
- `S/scripts/prose_lint.py` — stdlib linter for generated-text tells (`--rules` lists them, `--stats` shows rhythm). Errors are strong tells, warnings are clusters to review.

## Workflow

1. **Facts first.** Collect what the text may claim from the sources of truth: the code or changelog, merged PRs/issues, release notes, measurements, the product UI, existing docs, the user's brief. Write a short fact list with a source per item (file, PR, URL). Anything you cannot source is either asked for or marked `TODO` in the draft; never fill a gap with a plausible number, quote, date or anecdote.
2. **Read the venue.** If the publication has earlier posts (blog, changelog, newsletter archive), read two or three of them for address (du/Sie/you), length, heading habits and sign-off, and match them unless the brief says otherwise. A project `TASTE.md` or style guide overrides `S/TASTE.md` where they disagree.
3. **Reader and angle.** Name in one line who reads this and what they know beforehand, and in one line the single thing they should understand or be able to do afterwards. Pick the angle that serves that line, then the opening (see TASTE.md "Openings"). If the brief is ambiguous about audience or language, decide sensibly and say so in the report rather than asking.
4. **Outline.** One line per section: the reader's question there and what is new for them. Run the outline test: read only these lines; if they form a tidy summary that could fit any product, the piece has no argument yet.
5. **Draft** in the target language (German first when both are needed; write the English version as its own text from the same fact list, not as a translation of the German sentences).
6. **Lint.** `python3 S/scripts/prose_lint.py draft.md --stats`. Fix every error. Read each warning in context and change it only when the passage reads worse for it; a warning is not a quota. Suppress a deliberate exception with `<!-- prose-ignore: rule -->` on the line before, and mention it in the report.
7. **Read-aloud test.** Read the draft as if speaking it to one person (out loud or line by line in your head). Mark every place where you would run out of breath, where a sentence only exists to sound good, or where you would not say the word to a friend. Rewrite those. Then read only the first sentence of each paragraph and only the headings: does the line of thought survive?
8. **Final check** (all must hold before handing over):
   - Every number, name, date, version, quote and capability matches the fact list; nothing was added during editing. Diff the facts of the final text against the list once more.
   - No hype: at most one superlative, and only when it is measurably true ("the largest update so far" with the count that proves it).
   - No generated-text tells: lint has zero errors; the warnings left are deliberate.
   - The opening says what the text is about within the first two or three sentences; the ending stops on a real point, a next step or an honest open question, not a summary.
   - Limits and open issues the reader would care about are stated plainly.
   - Address, terminology and product names are consistent with the venue and the UI.
   - Links work and point where the text says.

## Editing an existing text

Keep what works: a line that is concrete and sounds like the author stays even if you would have written it differently. Fix in this order: wrong or unsourced facts, structure (opening, order, ending), then sentences. Make the fewest changes that solve the problems you can name, and say what you changed and why.

## Never add these to sound human

Invented personal experience or anecdotes, invented numbers or sources, fake typos or casual filler ("tbh", "ehrlich gesagt" as decoration), staged candour ("I'll be honest"), forced asides, and chopping sentences into fragments for punch. Human texts read human because the author knows something specific, not because of these marks.

## Report

Return the text (or the file path), the fact list with sources, open `TODO`s, lint result, and the few editorial decisions worth knowing (angle, address, what was cut and why).
