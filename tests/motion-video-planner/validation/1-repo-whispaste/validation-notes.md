# Validation notes: motion-video-planner, Scenario 1 (existing repository, WhisPaste)

Plan directory: `/Users/silvio/Documents/Projekte/skills/tests/motion-video-planner/validation/1-repo-whispaste/`
Files: `context.md`, `decisions.md`, `concepts.md`, `production-prompt.md`, this file.
Inventory JSON (outside the plan dir, as instructed): `/private/tmp/claude-501/-Users-silvio-Documents-Projekte-skills/169b11c3-fcdb-418e-92da-63425fb3e425/scratchpad/inv-whispaste.json`
Product repository: read-only; no write, no git command that changes state. (Note: `git status` in the skills repo shows `CLAUDE.md` and `README.md` as modified; I did not touch them.)

## Run summary

- Questions asked: 5 of 10 budget (Q1 platform/format, Q2 core message, Q3 language, Q4 app footage, Q5 concept selection). All answers SIMULATED. Budget unused: 5.
- Concept selection: recommended concept A; SIMULATED user chose B; the prompt follows B (with two logged deviations, see decisions.md).
- Time/effort: about 5 minutes wall clock (15:21 to 15:26 CEST), roughly 45 tool calls. Most effort went into reading reference files (about 75 KB of skill text loaded) and into repo grep-checks.

## References loaded, and when

| Reference | When loaded | Note |
|---|---|---|
| `context-discovery.md` | Phase A start | Read in full. |
| `interview.md` | Phase B start | Read in full. |
| `creative-principles.md` | Phase C start | Read in full. |
| `concepts.md` | Phase C start | Read in full. |
| `occasions.md` | Phase C start | Read in full although only the "Social clip" section is needed (the skill says read only the section). My mistake, not a skill defect, but the instruction is easy to miss. |
| `style-kit.md` | Phase C start | Read in full (23 KB); only Swiss/Editorial and Kinetic Typography were used. |
| `production-prompt-template.md` | Phase D start | Read in full. |
| `hyperframes-facts.md` | Phase D start | Read in full. |
| `quality-checklist.md` | Phase D start | Read in full. |
| `example-production-prompt.md` | Not loaded | Skipped as instructed (file does not exist). |

Scripts run: `scripts/inventory_repo.py` (Phase A, exit 0, 3003 files). `scripts/check_prompt.py` (hand-over gate). I also grepped `check_prompt.py` source after the first run to understand the warnings (this is not part of the normal flow).

## check_prompt output (verbatim)

First run (before fixes):

```
ERROR  line 151: refers to the planning chat or files the executor lacks: - Motion/easing: as above; the end state holds on the idle.
ERROR  line 183: refers to the planning chat or files the executor lacks: | `assets/dictation-en.json` | create | caption timing, English | as above, from `assets/recording-e
ERROR  section 8 does not name the workflow '/general-video' from Appendix A
WARN   scene 1: 11 on-screen words in 3.0 s may be too fast to read
WARN   scene 3: 36 on-screen words in 6.0 s may be too fast to read
WARN   scene 3: 29 voiceover words in 6.0 s exceeds 3.0 words/s

3 error(s), 3 warning(s)
EXIT=1
```

Final run, after fixes:

```
0 error(s), 0 warning(s)
EXIT=0
```

Command used: `PYTHONDONTWRITEBYTECODE=1 python3 /Users/silvio/Documents/Projekte/skills/skills/motion-video-planner/scripts/check_prompt.py /Users/silvio/Documents/Projekte/skills/tests/motion-video-planner/validation/1-repo-whispaste/production-prompt.md --assets-root /Users/silvio/Documents/Projekte/whispaste`

### What the fixes were, and an honesty caveat

- Two "as above" phrases (the checker bans them as chat references, which is a false positive on ordinary English) and one bare "general-video" (needed as `/general-video`) were rewritten. Real fixes.
- The two timing warnings came from the bilingual table: DE and EN copy shared one cell, so the checker summed both languages. I split the EN copy into a second table. This makes the warnings disappear, but the checker now does not check the EN cut's reading speed at all. The EN lines are the same length (13 words over 6 s), so the speed is fine, but the gate did not prove it. Treat this as a checker blind spot, not a clean pass.
- The checker verified the `exists` assets (paths in the WhisPaste repo). It does not check `create` items (the two user recordings and the dictation JSON files), and it does not check `frame.md`.

## Where the skill was unclear, contradictory, missing, or forced me to guess

Be concrete. Ordered by impact.

1. **`npx hyperframes --version` contradicts "install nothing".** Phase A/`hyperframes-facts` and `context-discovery.md` A3.8 say to check the CLI with `--version` and install nothing. A bare `npx hyperframes --version` fetches the package if it is not present. I used `npx --no-install hyperframes --version` (exit 1: not installed) and `command -v hyperframes` (not found). The skill should say `--no-install` explicitly.
2. **No status for user-supplied material.** The asset statuses are `exists | create | source | generate`. Concept B needs two screen recordings the user makes. `create` means "code-drawn by the executor", which is wrong; `source` means "fetched from a free or licensed source". I used `create` with an explanatory note. Add a status such as `user` (provided by the user before production; the executor stops if missing).
3. **Capture dependency is invisible in the effort scale.** Concept B was rated "S" for effort, which is true for the HyperFrames work, but the concept cannot start until the user records footage. The concept template has no field for "blocked on the user". I had to put this into "Asset needs" and "Main risks".
4. **Bilingual productions break the timeline checker.** There is no template pattern for a DE master plus EN cut (both in one scene table), and the checker sums all languages in one cell. Either the template defines a per-language table, or the checker counts per language.
5. **Phase A depth is undefined for large repositories.** "Read systematically" over 3003 files, with "verify every candidate claim against the code", has no budget or minimum evidence level. I had to decide that "grep found it" is weaker than "read it" and to label each claim accordingly. The skill should define evidence levels (existence / read / tested) and a reading budget.
6. **Unreleased work is not a category.** A4 has Verified / Documented only / Roadmap / Contradicted / External. The WhisPaste CHANGELOG "Unreleased" section (merged on `dev`, not shipped) is neither roadmap nor verified. I needed my own category. Add "implemented but unreleased" and say it is not a current feature for marketing.
7. **Conflict between a user answer and the evidence: no rule for "do I spend a question?".** `interview.md` says to raise a conflict "as a short note with an alternative" and to ask only "if a decision is needed". My Q4 answer named the Dock, which is unreleased. I decided alone (floating button instead), noted it in decisions.md, and did not spend a question. The skill should say whether a user-chosen element that is not shipped requires a question.
8. **Language of the question template.** The skill says talk to the user in their language, but the templates (`Question n/10 — …`, options `a)–d)`, "Or answer freely.") are English. The conversation was German. I wrote the questions in English labels with German option text. The skill should say whether the labels are translated.
9. **`example-production-prompt.md` is referenced but missing.** SKILL.md Phase D and the file table both link it. The user told me to skip it; the skill should not link a file that does not exist.
10. **"As above" is banned everywhere.** The checker treats "as above" as a chat reference. That is a reasonable rule, but it flags ordinary English prose. Narrow the pattern (for example, only when it is followed by a concept or chat word) or document the false positive.
11. **Template placeholder for a "no music" choice.** Section 6 says "Music: source: user file path | resolve via /media-use | none". I used "none". Fine, but the checker does not ask for a reason; the template is OK here, the reason is only in my text.
12. **Cold-read test is not independent.** `quality-checklist.md` §1.2 suggests a subagent for the cold read when the run is important. I did it myself, so my cold read is anchored on my own planning. Say explicitly when the reader is the same agent and what that weakens.
13. **Copy in concept vs. prompt drifted.** The concept's scene 5 line ("Und wo ist der Fenster-Wechsel?") was replaced in the prompt ("Gewechselt hat nur der Text.") to answer the title. The skill's C4/D rules say the hook, protagonist and dramaturgy may not change without telling the user; copy changes are allowed. The skill does not say whether copy changes must be logged, so I logged them in decisions.md.
14. **Claims verified only by grep.** Several claims (spoken line breaks, OpenAI/Deepgram, Snippets, time-saved estimate) are supported by code existence, not by reading the implementation or a test. The skill's "Verified" definition in A4 ("code, and ideally a test") does not say whether existence in a grep is enough. I marked them "grep only" in context.md.
15. **Parakeet "several times faster" (README) vs. "about 2.6 times (Metal, compact model)" (Microsoft store copy).** The skill's rule on numbers covers this, but the conflicting-number case is not described. I used neither figure.
16. **Brand-specific rules were only found by reading docs.** The brand glossary (forbidden word "Spende"), the "no glow, no glass" rule and the Mobile-not-planned note came from `docs/zielgruppe.md`, `docs/landingpage-story.md` and the website glossary. The skill's brand step is "brand sources", but does not say where to look first. A short list of places to check (`docs/`, `CONTEXT.md`, glossaries) would have saved time.
17. **Style-kit length versus use.** `style-kit.md` is 23 KB, and I only needed two styles. The skill says "load" the file; it could say "load the two candidate sections", the way `occasions.md` does.
18. **`check_prompt` does not verify the frame.md appendix or the Appendix B paths.** The template makes Appendix B evidence paths mandatory ("path, URL, or stated by the user"), but the checker does not test that the evidence paths exist. I checked a few by hand.

## What worked well

- The phase order and the "one question per message" discipline were easy to follow.
- The question budget (reserved selection question) was clear.
- The template is complete and the sections map well to a HyperFrames brief. Appendix A (BRIEF.md) and Appendix C (frame.md) being given verbatim is a good design.
- The check script catches real problems: stale "as above" text, a missing workflow name in section 8, and unrealistic reading speed. The first run found three errors that were real defects in my first draft.

## Result

The production prompt passes the hand-over gate (exit 0), with the caveats above. It is not ready to execute yet: the two user recordings (DE and EN) must exist, and HyperFrames is not installed on this machine. The planning did not install anything and did not render.

## Post-run edit by the maintainer (2026-10-20)

After this run the skill gained the asset status `user` (supplied by the user, not present yet; checker warns until it exists). The user-supplied asset rows above were switched to `user`; nothing else in the prompt was changed.
