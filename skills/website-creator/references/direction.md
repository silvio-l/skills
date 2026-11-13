# Three visual directions

The second decision point. The user chooses one of three proposals that genuinely differ, not three color variants of the same layout.

## Seeding

`seed.py roll --brand <hex>` returns three combinations of layout archetype, type pairing, color posture, surface mode (light, dark, brand-colored), OKLCH palette, motion tier and a source weighting. The three never share a posture or motion tier, and exactly one is **radical**: drenched or full-palette color on the brand surface, signature or video motion, competitors weighted lowest. The seed defaults to project name + date; recent picks (`.website-creator/history.json`) are skipped so projects do not converge on the same look. The seed is a starting point against defaults, not a verdict: change any part that does not fit the product, and say why.

Re-roll with `--seed <word>` when a combination is clearly wrong for the product (e.g. `poster-blocks` for a dense B2B tool), not to get something more familiar.

## Source weighting

Each direction draws on four sources in different shares, and says so:

- **origin-rules** — the skill's craft references (`looks.md`, `centerpiece.md`, motion and liveliness rules).
- **competitors** — the competitor screenshots: conventions users of the category already know.
- **galleries** — the gallery examples on the reference board: what the best pages outside the category do.
- **concept** — the concept image (`references/concept.md`): the image model's own reading of the brief.

The seed proposes the shares (every non-radical direction leads with a different source; the radical one weights competitors at most 10 %). Set them per project: a category with strong conventions (banking, B2B tools) may lean on competitors in the familiar direction, a concept image that missed the point gets a small share. State the final shares in each sketch.

## The radical direction

At least one direction breaks visibly with the competitors: a color field, scale, material or layout none of them uses. It may loosen performance budgets (heavier media, WebGL, longer motion) when it names each loosened budget and the reason, and the report repeats that list. WCAG AA contrast, keyboard use, reduced motion and the strict CSP stay hard limits for it as for every direction.

## Developing each proposal

Read `references/looks.md` (page mode, color posture, named looks, tone dials) and `references/centerpiece.md` first, and open the reference board (`references/research.md`) and the concept image (`.website-creator/concept/`, `references/concept.md`). The three directions span the range from familiar to radical: at least one of them is clearly loud (committed, drenched or full-palette color, a strong centerpiece), and none is a quiet safety copy of another.

For each direction write:

1. **Name and one-sentence idea** — what the page feels like, in product terms ("liest sich wie ein Handbuch", not "modern and clean").
2. **Where boldness is spent** — the one centerpiece and its hero material (`references/centerpiece.md`); the three directions use different materials.
3. **Layout** — archetype applied to *our* sections from the copy skeleton: which section gets which treatment, where the peak sits.
4. **Type** — display/body pairing, scale ratio, one notable typographic move (e.g. tabular numbers in the index, hanging punctuation in the hero).
5. **Color** — posture (restrained, committed, drenched, full palette), surface, ink, brand, accent, and which fields carry color (`field`/`field-ink` from the seed for committed and full palette). Four to six hex values.
6. **Tone dials** — energy, finish, density, weight, seriousness, each with a one-line reason.
7. **Imagery** — what kind and from where (`references/images.md`).
8. **Motion tier** — restrained, signature or video (`references/motion.md`), and what moves.
9. **Distance** — one sentence on how it differs from the three competitors.
10. **References** — which competitor or gallery screenshots it draws on, and the one principle taken from each. At least one direction takes something visible from the concept image and names it.
11. **Sources** — the source weighting in percent, summing to 100, and one line on why.

Collision check before presenting: if two directions share posture, hero material or more than two dial positions, push one of them further.

Render a first-viewport sketch per direction at 1440 and 375 when the stack allows (a throwaway HTML file in `.website-creator/sketches/` is enough) and show the screenshots. A sketch shows color, imagery and motion, not just type on white: the real color fields at their real share, a real image candidate or a crop of the concept image in place, and the signature motion running in CSS (or annotated frame by frame when it cannot run). If sketches are not feasible, describe the first viewport concretely.

## Writing it down

Record the three proposals in `.website-creator/directions.md`, one `## ` section per direction; mark the radical one with `(radical)` in its heading or a `Radical:` line naming the loosened budgets. Each section carries at least these lines:

```markdown
## 2 Poster (radical)
Sources: origin-rules 20%, competitors 5%, galleries 35%, concept 40% — the category is uniform, so look outside it
Color: drenched #ffac95 sheet, #1a1513 ink, #00837a accent
Imagery: concept image crop as the hero ground, halftoned
Motion: signature, headline set in scroll-driven steps
Radical: hero video 2.4 MB (budget 1 MB) because the product is motion
```

The gate (`directions`) checks three sections, a `Sources:` line with percentages that sum to 100, `Color:`, `Imagery:` and `Motion:` lines in each, and at least one radical mark.

## What every direction must avoid

The slop linter enforces the mechanical part. Beyond it:

- Hero = centered headline + subline + two buttons + screenshot below. Allowed only if a direction argues for it.
- Rows of identical cards with an icon tile on top.
- A purple/blue gradient, glow, or "aurora" background as the idea.
- Section after section with the same rhythm (heading, text, three cards).
- Kicker labels above every heading, numbered section labels as decoration.
- Fake social proof (logo walls of unrelated companies, invented quotes).
- The model's own defaults: indigo around `#6366f1` as the brand, a warm cream or off-white surface "for warmth", a two-stop gradient behind the hero, emoji as icons.
- The default section order Hero → Features → Pricing → FAQ → CTA, unless the copy skeleton arrives at it on its own.

## Presenting

Show the three proposals side by side (short, scannable), ask for one number plus the motion tier, and offer to combine named parts ("Layout aus 2, Farben aus 1"). Then `run.py wait direction` and stop.
