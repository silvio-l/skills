# DESIGN.md

Every run ends with a committed `DESIGN.md` at the project root (or the path given to `run.py start --design`). It is the contract for later changes to the page; the slop linter checks colors and fonts against it.

## Format

YAML front matter with tokens, Markdown body with rules. `seed.py pick N` writes a skeleton; finish it by hand.

```markdown
---
colors:
  surface: "#fbfbfa"
  surface-2: "#f1f2ef"
  ink: "#1c211b"
  ink-muted: "#5d665b"
  line: "#dde1da"
  brand: "#398526"
  brand-ink: "#2c6b1c"
  accent: "#c2410c"
typography:
  display: {fontFamily: "Schibsted Grotesk", weight: 700}
  body: {fontFamily: "Source Serif 4", weight: 400, lineHeight: 1.6}
  scale: [14, 16, 20, 25, 31, 39, 49]
rounded: [0, 4, 8, 999]
spacing: {base: 8, steps: [4, 8, 12, 16, 24, 32, 48, 64, 96, 128]}
motion: restrained
breakpoints: [480, 768, 1024, 1440]
---
```

Required by the gate: `colors:` and `typography:`. Every hex the page uses belongs here; one-off colors are a smell.

## Body

1. **Principles** — three to five sentences that decide arguments ("Text trägt die Seite, Bilder belegen", "Akzent nur für die eine Handlung je Abschnitt").
2. **Layout** — archetype, grid, max measure (60–75 characters for body), section spacing rhythm.
3. **Components** — the few that exist (button, link, section header, figure, nav, footer) with states: hover, focus-visible, active, disabled.
4. **Contrast** — the pairs from `seed.py` and any added pairs; body text ≥ 4.5:1, large text and UI ≥ 3:1.
5. **Motion** — tier, durations, easing, what never moves; `prefers-reduced-motion` behavior.
6. **Relation to the app** — if the project has an app design system: what is shared (brand color, maybe body font), what deliberately differs.
7. **Decisions** — dated log of deviations and their reasons. Add to it whenever the page breaks a rule on purpose.

## Implementation

Tokens become CSS custom properties in one place (`:root`), or the project's token system (Tailwind theme, CSS-in-JS theme). Components use tokens, never literals. Use `oklch()` in CSS if the project's browser targets allow; keep the hex values in DESIGN.md as the reference.
