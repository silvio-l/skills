# Competitor research

Goal: know what the three biggest competitors say and show, so that our page argues and looks different on purpose. Inspiration, never imitation.

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

## `.website-creator/research.md`

The gate counts distinct competitor hosts in this file (needs three). Structure:

```markdown
# Research: <page>, <date>

## <Competitor> — https://… (de, fetched 2026-11-13)
- Scroll argument: hero promise → proof → … → CTA (one line per section, their words condensed)
- Voice: …
- Visual signature: layout archetype, type, colors, imagery, motion
- Strong: …  Weak/generic: …

## Gaps
Pages or sections that could not be read, and why.

## Our distance
- Message: what we say that none of them can or does.
- Visual: which of their conventions we avoid (e.g. all three use a dark hero with a product screenshot → we don't).
- What we keep because users expect it (e.g. pricing table).
```

The "Our distance" section feeds both decisions: the copy skeleton and each of the three directions must name how they differ.
