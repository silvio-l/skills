# Competitor research

Goal: know what the three biggest competitors say and show, so that our page argues and looks different on purpose, and see what the best pages outside the category do. Inspiration, never imitation.

## Choosing the three

- "Biggest" means the most visible alternatives for the same job: market leader, the product users name when they compare, and the most-searched alternative in the German-speaking market if it differs. Not adjacent tools.
- No obvious competitor (new category): take the three options the user would otherwise reach for, including "doing it by hand" via its most prominent tool, and say so.
- Use the German page if it exists, otherwise the English one. Note which.

## Fetching

Read the real page, never search snippets or memory.

```bash
pwc --headless goto https://example.com/de
pwc --headless snapshot                # text and structure
pwc --headless resize 1440 900
pwc --headless screenshot --filename=<abs>/.website-creator/research/example-1440.png --full-page
pwc --headless resize 375 812
pwc --headless screenshot --filename=<abs>/.website-creator/research/example-375.png --full-page
pwc --headless stop
```

`curl -sL` is fine for static pages; JS-rendered pages need pwc. Dismiss cookie banners before screenshots. If a page blocks automation, record the gap instead of guessing.

## Gallery examples

Competitors show the category's conventions; galleries show what is possible beyond them. Pick at least three current examples (ideally from the last 12 months) that fit the page mode and the product's mood, not the category: a dev tool may borrow from a festival page.

- Sources: Awwwards (Sites of the Day), Godly, Land-book, Lapa Ninja, Siteinspire, One Page Love, SaaS Landing Page, Minimal Gallery, CSS Design Awards.
- Open the gallery entry, then the live site; screenshot the live site at 1440 (and 375 when its mobile view teaches something) into `.website-creator/research/gallery-<name>-1440.png`.
- Per example, name the **one principle** worth borrowing ("the hero is a playable instrument", "one drenched color with white rule ink"), never the whole look.
- A gallery that blocks automation or shows nothing usable goes under `## Gaps` with the reason. If none is reachable, record that and `run.py waive gallery --reason "…"`.

## Reference board

Before the directions phase, put the competitor and gallery screenshots side by side (a throwaway `.website-creator/research/board.html` grid, rendered to `board-1440.png`, is enough) and note for each direction which references feed it and which competitor convention it breaks. The three directions draw on different references; a direction without a reference is fine only when it says so.

## `.website-creator/research.md`

The gate counts distinct competitor hosts outside the `## Gallery` section (needs three, gallery sites never count) and distinct example URLs inside it (needs three, or a waiver). Structure:

```markdown
# Research: <page>, <date>

## <Competitor> — https://… (de, fetched 2026-11-13)
- Scroll argument: hero promise → proof → … → CTA (one line per section, their words condensed)
- Voice: …
- Visual signature: layout archetype, type, colors, imagery, motion
- Strong: …  Weak/generic: …

## Gallery
- https://www.awwwards.com/sites/… → https://live-site.example (Awwwards SOTD, fetched 2026-11-13): principle borrowed — …
- …

## Gaps
Galleries, pages or sections that could not be read, and why.

## Our distance
- Message: what we say that none of them can or does.
- Visual: which of their conventions we avoid (e.g. all three use a dark hero with a product screenshot → we don't).
- What we keep because users expect it (e.g. pricing table).
```

The "Our distance" section feeds both decisions: the copy skeleton and each of the three directions must name how they differ. The gallery principles and the reference board feed the directions.
