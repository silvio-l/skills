# Three visual directions

The second decision point. The user chooses one of three proposals that genuinely differ, not three color variants of the same layout.

## Seeding

`seed.py roll --brand <hex>` returns three combinations of layout archetype, type pairing, surface mode (light, dark, brand-colored), OKLCH palette and motion tier. The seed defaults to project name + date; recent picks (`.website-creator/history.json`) are skipped so projects do not converge on the same look. The seed is a starting point against defaults, not a verdict: change any part that does not fit the product, and say why.

Re-roll with `--seed <word>` when a combination is clearly wrong for the product (e.g. `poster-blocks` for a dense B2B tool), not to get something more familiar.

## Developing each proposal

For each direction write:

1. **Name and one-sentence idea** — what the page feels like, in product terms ("liest sich wie ein Handbuch", not "modern and clean").
2. **Layout** — archetype applied to *our* sections from the copy skeleton: which section gets which treatment.
3. **Type** — display/body pairing, scale ratio, one notable typographic move (e.g. tabular numbers in the index, hanging punctuation in the hero).
4. **Color** — surface, ink, brand, accent; where the accent is allowed (rarely more than CTAs and one highlight).
5. **Imagery** — what kind and from where (`references/images.md`).
6. **Motion tier** — restrained, signature or video (`references/motion.md`), and what moves.
7. **Distance** — one sentence on how it differs from the three competitors.

Render a first-viewport sketch per direction at 1440 and 375 when the stack allows (a throwaway HTML file in `.website-creator/sketches/` is enough) and show the screenshots. If sketches are not feasible, describe the first viewport concretely.

## What every direction must avoid

The slop linter enforces the mechanical part. Beyond it:

- Hero = centered headline + subline + two buttons + screenshot below. Allowed only if a direction argues for it.
- Rows of identical cards with an icon tile on top.
- A purple/blue gradient, glow, or "aurora" background as the idea.
- Section after section with the same rhythm (heading, text, three cards).
- Kicker labels above every heading, numbered section labels as decoration.
- Fake social proof (logo walls of unrelated companies, invented quotes).

## Presenting

Show the three proposals side by side (short, scannable), ask for one number plus the motion tier, and offer to combine named parts ("Layout aus 2, Farben aus 1"). Then `run.py wait direction` and stop.
