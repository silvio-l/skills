# Flutter Design Language — Reference

Backed by Anthropic's `frontend-design` skill + Cookbook and a verified
deep-research (as of June 2026). Sources at the end.

## Slop Checklist (Gate — avoid all of this)

The verified "AI design fingerprint":

- [ ] **No default indigo/purple** (`#4F46E5`, `bg-indigo-500` and relatives). This is
      the inherited Tailwind UI button default — the most tell-tale slop signal.
- [ ] **No default fonts:** Inter, Roboto, Poppins, Open Sans, Lato, System-Sans
      without another reason. (Anthropic Cookbook forbids these explicitly.)
- [ ] **No uniform 16px radius** on everything. Vary radii deliberately.
- [ ] **No reflexive centred Hero + a purple CTA.**
- [ ] **No three-icon feature grid** as default structure.
- [ ] **No timid palette** (everything desaturated grey-blue), no wan alibi shadows,
      no glassmorphism overkill, no emoji bullets.

Plus the three clusters that `frontend-design`'s SKILL.md names (also defaults):
(1) Cream `#F4F1EA` + high-contrast serif + terracotta;
(2) near-black + one acid-green/vermilion accent;
(3) broadsheet layout with hairlines, zero radius, dense newspaper columns.
Legitimate *if the brief calls for them* — otherwise never fill free axes with them.

## Typography

Anthropic's three-part strategy: **(a) lead each dimension separately, (b) name
references, (c) ban defaults.** For fonts that means concretely:

- **Avoid:** Inter, Roboto, Poppins, Open Sans, Lato, System-Default.
- **Character fonts (examples):** Display — Fraunces, Playfair Display, Clash
  Display, Bricolage Grotesque, Space Grotesk; Body — DM Sans, Spline Sans, Satoshi,
  Mulish; Mono/Utility — JetBrains Mono, Space Mono.
- In Flutter via `google_fonts` (fast) or bundled asset fonts (offline,
  free-tier-friendly, no runtime fetches). Deliberate Display+Body pairing,
  clear scale with intentional weights.

## Colour in Flutter (beyond seed-purple)

`ColorScheme.fromSeed(seedColor: …)` takes **only one** seed — secondary/tertiary are
mere overrides. Two better approaches:

1. **`flex_seed_scheme`** (`SeedColorScheme.fromSeeds`): multiple **key colours**
   (primaryKey/secondaryKey/tertiaryKey) + a **`FlexTones` preset**
   (`vivid`/`soft`/`highContrast`/`chroma`/…) → a palette with character instead of
   single-seed monoculture. Light + Dark from the same keys.
2. **Hand-authorised `ColorScheme`** from the deliberate 4–6-hex palette
   (`ColorScheme.light()/dark().copyWith(...)`), when brand colours must be exact.

Radius/elevation/motion/special colours that don't fit `ColorScheme` → register as a
`ThemeExtension` (e.g. `AppRadius`, `AppElevation`, brand accents).

## Design Tokens: three tiers, role-named

Per W3C DTCG / Figma best practice (survives rebrands):

- **primitive** — raw values with no meaning: `color.amber.500 = #C9892F`, `space.4 = 16`.
- **semantic / `sys.*`** — **role**, not appearance: `sys.color.brand`,
  `sys.color.surface`, `sys.color.danger`. Aliased to primitives.
- **component** — component-specific: `button.bg = sys.color.brand`.

Never name by appearance (`color.purple`) — always by role (`sys.color.brand`).
`design_tokens_builder` turns `sys.*` tokens natively into `ColorScheme`/`TextTheme`;
Light/Dark via set suffixes. (Our MCP-native variant: Figma Variables two-tier —
one *primitive* collection + one *semantic* collection aliased onto it.)

## Figma Side

- Two variable collections: **Primitive** (raw values) + **Semantic** (roles, aliased
  to Primitive). This keeps a rebrand a one-place edit.
- **Text Styles** for typographic roles (Display/Body/Utility) rather than ad-hoc
  sizes — this makes the later `figma-to-flutter` typography mapping exact rather than
  approximate.
- Components with character: the signature element as a real component.

## Brief Template (Phase 0, Step 2)

```
Subject:        <what this concretely is>
Audience:       <who uses it>
One job:        <the single job of the main screen>
Risk:           <the one justified aesthetic risk>

Color (4–6, named + justification):
  <name> <#hex>  — <why this belongs to the subject>
Type:
  Display: <font> — <character>
  Body:    <font>
  Utility: <font/mono, optional>
Layout:   <one sentence> + ASCII wireframe
Signature: <the one memorable thing, encodes something true>

Rejected defaults: <what you deliberately did NOT take and why>
```

## Sources
- Anthropic `frontend-design` skill (installed) + Cookbook "Prompting for frontend
  aesthetics" (platform.claude.com/cookbook).
- Deep Research June 2026: 925studios, monet.design, prg.sh (slop fingerprint);
  dev.to/alanwest (Tailwind `indigo-500` origin); flex_color_scheme / rydmike,
  Flutter API (ColorScheme/Seed); Figma design-tokens, W3C DTCG (token tiers);
  simpleclub/design_tokens_builder (`sys.*`→ThemeData).
