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
2. **Research** (`phase research`). Read `references/research.md`. Fetch the real pages of the three biggest competitors (text and full-page screenshots via pwc) and write `.website-creator/research.md`: URLs, language, date, their scroll argument, visual signature, and what we deliberately do differently. Search snippets do not count.
3. **Copy skeleton → decision 1.** Write the section skeleton with headline, core message and key copy in German (TASTE.md). Present it, then `run.py wait copy` and **stop and wait** for the user. After the answer: `run.py decide copy "<what was chosen>"`.
4. **Directions → decision 2.** Read `references/direction.md` and `references/motion.md`. Run `python3 S/scripts/seed.py roll --brand <hex>` and develop the three seeded directions into three distinct proposals (layout, type, palette, imagery, motion tier, one sentence on how each one differs from the competitors). Show each as a rendered first-viewport sketch (screenshot) if feasible. Then `run.py wait direction` and **stop and wait**. After the answer: `seed.py pick N --motion <restrained|signature|video>`, then `run.py decide direction "<N + motion tier + changes>"`.
5. **Design system** (`phase design`). Finish `DESIGN.md` per `references/design-system.md`: tokens in the front matter, rules and recorded deviations in the body. Implement the tokens as CSS custom properties.
6. **Build** (`phase build`). Implement the page per `references/craft.md`, images per `references/images.md`, motion per `references/motion.md`. Translate per `references/translation.md`.
7. **Check** (`phase check`). Fix the findings, then run the checks again until they are clean:
   ```bash
   python3 S/scripts/slop_lint.py <src> --out .website-creator/lint.json
   python3 -m http.server 8765 -d <build dir> &   # or the project's dev/preview server
   python3 S/scripts/render_check.py http://localhost:8765/<page> --out .website-creator/render
   ```
   Look at the screenshots in `.website-creator/render/` yourself: the scripts catch mechanics, not taste. Check against the `TASTE.md` checklist and `references/craft.md`. A finding that is deliberately kept needs `run.py waive <rule> --reason "<why>"` and is listed in the report.
8. **Finish.** `run.py finish` passes only when both decisions are taken, research names three or more competitors, the lint and render reports are clean and newer than the sources, and DESIGN.md has `colors:` and `typography:`. Then stop the server and remove temporary files.

If the user stops the work: `run.py abort --reason "<why>"`. `run.py status` shows open checks at any time.

## Report (German)

- Sources: competitor URLs with date, image sources with license.
- Chosen direction, motion tier and DESIGN.md decisions.
- Copy sentence pairs: before → after → reason (for a redesign).
- Check results: lint and render summary, widths, waivers with reasons.
- Open proof points: claims that still need evidence from the user.

## Evolve

When the user corrects taste ("zu werblich", "nimm keine Fragen"), record the rule as one line with a reason in the **project's** `TASTE.md` (create it if needed), never in this skill's copy.
