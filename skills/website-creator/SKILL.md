---
name: website-creator
description: "Build or redesign a landing, marketing or product page: competitor research, German copy, three seeded visual directions, DESIGN.md, slop lint, multi-width render check, stop gate. Use for 'Website bauen', 'Landingpage', 'Seite neu gestalten'."
argument-hint: "[page or route] [optional focus]"
disable-model-invocation: true
hooks:
  Stop:
    - hooks:
        - type: command
          command: "sh -c 'd=\"${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/website-creator}\"; exec python3 \"$d/scripts/run.py\" hook'"
---

# Website Creator

Build or redesign this page in the current project: $ARGUMENTS

Without a page argument, take the public start page if it is unambiguous; otherwise ask which page is meant. A focus (e.g. `Fokus auf Hero und Preise`) orders the work but never skips research, decisions or checks.

`S` below means this skill's directory (`${CLAUDE_SKILL_DIR}`, fallback `~/.claude/skills/website-creator`). All scripts are stdlib Python and take `--help`. Run state lives in `<project>/.website-creator/` (git-ignored by `run.py start`).

## Ground rules

- **Stack from the project.** Use the framework, styling system, i18n and build that are already there. An empty project gets the smallest fitting stack (static HTML/CSS, or Astro when there are several pages); ask before adding a framework.
- **German leads.** Copy is written in German first, following `S/TASTE.md`. A project `TASTE.md` overrides it where they disagree. Other locales are translated afterwards and checked for naturalness (`references/translation.md`).
- **Binding:** logo and brand color, if they exist. Everything else is open. The result relates to an app design system in the project (shared brand color, related type) but does not copy it.
- **testIDs:** every interactive element and landmark gets a stable `data-testid` (`<page>-<element>`). Existing keys, testIDs and routes stay.
- **Browser:** only `pwc --headless` (screenshots, reading competitor pages, render check). Never Claude in Chrome, never Puppeteer.
- **Honest copy:** every claim must be checkable against the implementation or a named source. Unverifiable numbers and invented testimonials are not allowed.

## Phases

Start the run first. From then on, the Stop hook keeps you working until the gate passes, at most 3 rounds:

```bash
python3 S/scripts/run.py start --page "<page>" --src <dir> [--src <dir> …] [--design DESIGN.md]
```

Mark each phase with `run.py phase <name>`.

1. **Survey** (`phase survey`). Read the product: what it really does (the code, not the README), who it is for, existing page, locales, assets, logo, brand color, any app design system and `TASTE.md`. For a redesign, follow `references/redesign.md` first.
2. **Research** (`phase research`). Read `references/research.md`. Fetch the real pages of the three biggest competitors (text and full-page screenshots via pwc) and write `.website-creator/research.md`: URLs, language, date, their scroll argument, visual signature, and what we deliberately do differently. Add at least three current gallery examples (Awwwards, Godly, Land-book …) with source, date and the one principle borrowed, and build the reference board for the directions. Search snippets do not count.
3. **Copy skeleton → decision 1.** Write the section skeleton with headline, core message and key copy in German (TASTE.md). Present it, then `run.py wait copy` and **stop and wait** for the user. After the answer: `run.py decide copy "<what was chosen>"`.
4. **Concept image** (`phase concept`). Read `references/concept.md`. `python3 S/scripts/concept.py check`, then let Codex (subscription only, never an API key) draft the page from the reference board, or take the fallback (local model, HTML mockup), or record the gap. The image feeds the directions; it is not one of them.
5. **Directions → decision 2.** Read `references/direction.md`, `references/looks.md`, `references/centerpiece.md` and `references/motion.md`. Run `python3 S/scripts/seed.py roll --brand <hex>` and develop the three seeded directions into three distinct proposals (layout, type, color posture, imagery, motion tier, source weighting, one sentence on how each one differs from the competitors); one is radical and says which performance budgets it loosens. Write them to `.website-creator/directions.md` and show each as a rendered first-viewport sketch with real color, imagery and motion (screenshot) if feasible. Then `run.py wait direction` and **stop and wait**. After the answer: `seed.py pick N --motion <restrained|signature|video>`, then `run.py decide direction "<N + motion tier + changes>"`.
6. **Design system** (`phase design`). Finish `DESIGN.md` per `references/design-system.md`: tokens in the front matter, rules and recorded deviations in the body. Implement the tokens as CSS custom properties.
7. **Build** (`phase build`). Implement the page per `references/craft.md`, the centerpiece per `references/centerpiece.md`, images per `references/images.md`, motion per `references/motion.md`, video, 3D and demos within the limits of `references/media.md` and the tactile baseline per `references/liveliness.md`. Liveliness first: a demo, an object or a loop that shows the point replaces sections of explanation; keep the copy short (`TASTE.md`, "Weniger Text"). Translate per `references/translation.md`.
8. **Check** (`phase check`). Fix the findings, then run the checks again until they are clean:
   ```bash
   python3 S/scripts/slop_lint.py <src> --out .website-creator/lint.json
   python3 -m http.server 8765 -d <build dir> &   # or the project's dev/preview server
   python3 S/scripts/render_check.py http://localhost:8765/<page> --out .website-creator/render
   ```
   Look at the screenshots in `.website-creator/render/` yourself: the scripts catch mechanics, not taste. Treat the warnings `uniform-sections`, `text-heavy` and `long-paragraph` as a prompt to cut or show instead of tell — a tendency, not a hard limit, so they do not block the gate. Check against the `TASTE.md` checklist and run the polish loop in `references/craft.md`. A finding that is deliberately kept needs `run.py waive <rule> --reason "<why>"` and is listed in the report.
9. **Finish.** `run.py finish` passes only when both decisions are taken, research names three or more competitors and three gallery examples (or a waiver), `concept/concept.md` holds a concept image or a recorded gap, `directions.md` holds three weighted sketches with one radical, the lint and render reports are clean and newer than the sources, and DESIGN.md has `colors:` and `typography:`. Then stop the server and remove temporary files.

If the user stops the work: `run.py abort --reason "<why>"`. `run.py status` shows open checks at any time.

## Report (German)

- Sources: competitor URLs with date, image sources with license.
- Concept image: route (Codex, local, mockup) and what the directions took from it, or the gap and why.
- Chosen direction, motion tier and DESIGN.md decisions.
- Copy sentence pairs: before → after → reason (for a redesign).
- Check results: lint and render summary, widths, waivers with reasons.
- Open proof points: claims that still need evidence from the user.

## Evolve

When the user corrects taste ("zu werblich", "nimm keine Fragen"), record the rule as one line with a reason in the **project's** `TASTE.md` (create it if needed), never in this skill's copy.

## Credits

The references paraphrase ideas from these open-source design skills; no text is copied verbatim:

- `Leonxlnx/taste-skill` (MIT) — hero and moment catalogues, micro-interaction baseline.
- `pbakaus/impeccable` (Apache-2.0) — page modes, committing to a direction, modern platform techniques.
- `Nutlope/hallmark` (MIT) — themes as materials, color posture.
- `anthropics/skills` frontend-design (Apache-2.0) — commit to a bold direction, the hero as the most characteristic element.
- `alchaincyf/huashu-design` (MIT) — direction cards, collision check, hero materials, polish loop.
- `emilkowalski/skills` (MIT) — press and entry scales, easing, uneven stagger.
- `oil-oil/oil-ui` (MIT) — tone dials, named springs, overshoot by area, no quiet safety variant.
- `greensock/gsap-skills` (MIT) — ScrollTrigger batching, horizontal runs, quickTo followers, cleanup.
- `nextlevelbuilder/ui-ux-pro-max-skill` (MIT) — hover, reveal and stagger ranges, carousel controls, verified counts.
- `coreyhaines31/marketingskills` (MIT) — five-second test, one primary action, value labels.
- `ibelick/ui-skills` (MIT) — focus return, form error semantics, structural skeletons, blur limits.
- `elayadesign/ai-design-skills` (MIT) — word-by-word reveal, placeholders instead of invented facts.
- `nexu-io/open-design` (Apache-2.0) — curve vs. spring split, motion accessibility, error copy, the model-default list.
- `heydamir/unslop` by heydamir, licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) — image prompt order, generated object with live HTML overlay, glyph and halftone textures; adapted and paraphrased.
- Two public YouTube videos on Claude-built sites (Opus 5.5 web-design tests; a six-stage build process ending in a scroll-driven video journey) — live re-skin demo, scroll journey with separate mobile clips.
