# Validation notes: scenario 3, delegated logo sting for café "Bohnenwerk"

Date: 2026-10-20. Skill: `/Users/silvio/Documents/Projekte/skills/skills/motion-video-planner/SKILL.md`.
Plan directory: `/Users/silvio/Documents/Projekte/skills/tests/motion-video-planner/validation/3-delegated-logo/`.
No real user; answers are simulated and marked **SIMULATED** in `decisions.md`. Nothing was rendered, installed or published.

## Question count

- Budget used: **2 of 10**.
  - Q1/10 (platform and format), answered by SIMULATED "keine Ahnung, entscheide du alles". This is the "decide everything" case, so phase B stopped.
  - Q2/10 (reserved concept selection, phase C), answered by SIMULATED "nimm, was du für am besten hältst". Delegated, so I took Concept A and said so.
- Summary before Q1 was given (not a question). No follow-ups were asked.

## References loaded and when

| Phase | Loaded | Notes |
|---|---|---|
| Start | `SKILL.md` | |
| A | `references/context-discovery.md` | Read in full. Repo inventory not run (see findings). Workspace checked with `command -v` only. |
| B | `references/interview.md` | Read in full. |
| C | `references/creative-principles.md`, `references/concepts.md`, `references/occasions.md`, `references/style-kit.md` | I read all of `occasions.md` and all of `style-kit.md` (23 KB), though phase C says "the occasion's section" only. Could not tell which looks to pick without reading the kit. |
| D | `references/production-prompt-template.md`, `references/hyperframes-facts.md`, `references/quality-checklist.md`, `scripts/check_prompt.py` (source) | I read the script source to predict what the gate enforces. The skill does not ask for this. |
| D | `references/example-production-prompt.md` | Not loaded; the file does not exist (per the run instructions). |

## check_prompt output (verbatim)

First run, with my first draft (German heading "## 1. Ziel und Kontext"):

```
ERROR  missing section '## 1. Goal and context'

1 error(s), 0 warning(s)
EXIT=1
```

Final run, after the heading fix and one cold-read fix (font download added to Step 0):

```
0 error(s), 0 warning(s)
EXIT=0
```

Command: `python3 .../scripts/check_prompt.py <plan-dir>/production-prompt.md --assets-root <plan-dir>`.

Note: the gate does not check the logo blocker, the font license, or whether the route is right. Those were judged by hand (quality-checklist §1 items 2–6). The cold-read was done by me, not by a subagent; the skill suggests a subagent only "if the run is important".

## Findings

### Critical: delegation is internally contradictory

1. **interview.md, "Delegation"**: "for everything ... stop the interview, decide all open fields". Yet the same section says "if the user also delegates the concept choice ... The reserved selection question is then not asked". The scenario implies the selection question *is* asked and then delegated. The skill does not say whether the reserved selection question survives a "decide everything" answer. I asked it (Q2/10). If it should be skipped, the rule must say so.
2. **Counting**: the rule "one of the 10 is reserved for the concept selection" plus "stop the interview" means the phase-B budget is effectively 1. The skill does not state this.
3. **Delegation of the summary**: "Two visibly separate groups ... Confirmed / Decided" is required at exit, but with full delegation nothing is "confirmed". I kept the group and left the first list empty except the name. Fine, but the skill could say so.

### Critical: missing brand assets (logo, colors, fonts) have no rule

4. **Priority conflict**: context-discovery A8 says "Ask in phase B for brand assets you could not find: a logo file, colors, fonts." interview.md's table ranks assets at #11, below platform (#5). I put platform first. The skill does not say which wins.
5. **No rule for a missing logo when the logo is the subject**. occasions.md (logo section) lists "real logo file (SVG)" and "exact brand colors" as defaults but gives no fallback when they are absent. The interview table has only "code-drawn assets plus licensed SFX". I wrote a blocker in prose (section 0 of the prompt): no final render before a logo file or explicit written approval of a provisional wordmark. That is my decision, not the skill's. The skill should define: is a missing logo a blocker for hand-over, or only for the final render?
6. **Blocker has no field**: `check_prompt.py` has no field for blockers, and the template has no blocker section. The gate passes with the final render gated, so the gate cannot catch a missing logo.

### Critical: inventing a brand identity

7. The skill's hard rules say "no invented facts". They do not say what a *visual* identity may be when no brand exists. I invented: paper ground `#F4EFE6`, ink `#2B1D14`, accent `#B5542D`, Montserrat ExtraBold, a bean motif derived from the name, and the bean-as-"o" idea. I marked all of it PROVISIONAL in the prompt and in `decisions.md`. The skill needs an explicit rule: either a provisional look is allowed (and must be marked), or the production prompt must wait.
8. **Bean motif**: the name "Bohnenwerk" suggests a bean, but the skill says "Recognition: recurring element" with no guidance for deriving it from a name. I flagged it as a derivation, not a brand fact.
9. **Style-kit mismatch**: style-kit says "a style is adapted *to* the brand, never the other way round", but with no brand the adaptation has no target. Bauhaus was picked with no reference to the café.

### Logo sting under /motion-graphics

10. **Conflicting routing guidance**: occasions.md says logo → `/motion-graphics`. hyperframes-facts.md §2 says logo sting → `/motion-graphics`, but also "Use `/general-video` for most prompts from this skill, because the concept is already decided". quality-checklist §1.5 says "narration never in `/motion-graphics`". I followed the logo rule. The skill should say which one wins for a fully specified logo sting.
11. **Name ambiguity**: `/motion-graphics` is the HyperFrames workflow (installed under `~/.claude/skills/motion-graphics`). The repo removed `motion-graphics-director` in commit `1f987a1` (2026-10-20). The skill does not mention that repo skill, so there is no clash in practice. Still, the skill should say explicitly that `/motion-graphics` means the HyperFrames route.
12. **"At most one clarifying question"** (hyperframes-facts §2) conflicts with "This brief is confirmed by the user: run no intent interview" (template step 1.3). I wrote a permission for one question. The skill should settle this for `/motion-graphics`.
13. **Sound motif default**: occasions.md says "a 2–4-note sound motif if audio is wanted". Under "no invented facts" that is an invention, so I wrote no audio at all. That left the "Sound motif" field as "none in this version". The skill does not say that "no audio" is an allowed decision.

### Forced guesses

14. **Share trigger for a logo sting**: creative-principles §2 says "every concept names its share trigger" and gives two options, both about content with a real situation. A logo sting fits neither. I wrote "none strong" and said so honestly. The skill should allow "none, recall piece" for logo stings.
15. **Audience**: interview field #3 says "the segment with the clearest verified pain" as default. With no product data there is no verified pain, so I wrote "Annahme, nicht verifiziert". The skill does not say what to do when the default cannot be applied.
16. **Message**: field #4's default is "the strongest verified benefit". The only verified fact is the name. I used "the name stays in memory", which is brand recall, not a benefit. Again the default cannot be applied.
17. **Platform default**: I picked 9:16 "for reach" as the delegated default. interview.md gives "9:16 for social reach", which fits. OK, no problem here.
18. **Duration**: logo sting 3–6 s (interview), occasions 3–6 s, concepts 5–6 s. I used 6.0 s. No contradiction.
19. **HyperFrames version**: hyperframes-facts.md says "checked on 2026-10-20 ... CLI hyperframes@0.8.181". The CLI is not on PATH here, so I could not check the version. Not verified.

### Process and tooling

20. **`--version` may install**: context-discovery A3.8 says "Use `--version` commands only and install nothing". `npx hyperframes --version` would fetch the package, so it is not install-free. I checked with `command -v` and did not run npx. The production template's step 0 runs `npx hyperframes --version` for the executor, which is correct there but contradicts A3.8 as a planner rule. The skill should name `command -v` as the planner's check.
21. **Repository mode is undefined for this workspace**: the working directory is a git repo (the skill collection), not a product repository. context-discovery A1 says "a product repository". I chose briefing mode and say so in `context.md`. The skill should say what to do when the cwd is a git repo that is not a product.
22. **Plan directory**: context-discovery A7 gives `docs/video-plans/...` or `video-plans/...` for repos, and `video-plans/<date>-<slug>/` for briefing mode. The run instructions gave another path; I followed the run instructions. No conflict, but the skill's default was not used.
23. **Language of the prompt body**: template says body in the conversation language, labels in English. `check_prompt.py` requires English headings exactly. My first draft had a German heading and failed. The template should say the headings are English *even in a German body*, with an example.
24. **Tool hook**: a Bash heredoc to write `decisions.md` was blocked by a machine-wide scan hook (`block-heavy-scan.sh`). I used the Write tool instead. Not a skill issue, but relevant to a planner that writes plan files with heredocs.
25. **Cold-read defect found**: section 7 said "Download einmalig in Schritt 0", but Step 0 did not list the download. Fixed. Only a self-review would catch this; the gate does not.
26. **My own math error**: a rotation formula in scene 1 was wrong in the first draft (I wrote 510°). Fixed to 353°. The gate did not catch it; numeric checks in the prompt are not verified by `check_prompt.py`.

## Summary for the caller

- The delegation path works for the mechanics (2/10 questions, delegated defaults listed, selection asked and delegated), but the skill contradicts itself on whether the selection question still runs after "decide everything".
- A missing logo is the critical gap: no rule says whether it blocks hand-over or only the final render, no rule allows or forbids a provisional brand look, and the gate cannot see the blocker. I handled it with a PROVISIONAL marking and a render gate written in prose.
- Logo-sting routing (`/motion-graphics` vs `/general-video`) is contradictory across the references, and the `/motion-graphics` name is ambiguous with a removed repo skill.
- `check_prompt.py` exits 0 with 0 warnings on the final prompt. The gate is structural only; the blocker, font license, and route were checked by hand.
