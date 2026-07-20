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
Apply `sys.*` tokens directly to `ColorScheme`/`TextTheme` in code; Light/Dark via
parallel token sets (`primitives_light.dart`/`primitives_dark.dart`, or a single file
with light/dark variants per token).

## Direct-to-Code Tokens (no external design file)

Design tokens are defined **directly in code** — a Dart tokens/theme file — not in an
external design tool synced afterward. The three-tier structure from the previous
section (primitive → semantic/`sys.*` → component) stays the same; only the medium
changes:

- **Primitive tier:** raw values as `Color`/`double` constants in a single
  `AppPrimitives`-style class/file.
- **Semantic tier:** role-named constants/getters (`sys.color.brand`,
  `sys.color.surface`, `sys.color.danger`) that alias into the primitives — feed these
  straight into `ColorScheme.light()/dark().copyWith(...)` or `flex_seed_scheme`'s
  `SeedColorScheme.fromSeeds`.
- **Component tier:** component-specific values (`button.bg = sys.color.brand`) as
  `ThemeExtension`s (`AppRadius`, `AppElevation`, brand accents) or widget-level
  constants referencing the semantic tier.
- Text roles (Display/Body/Utility) become `TextTheme` entries / `TextStyle` constants
  instead of Figma Text Styles — map the font pairing from the Typography section above
  straight into `google_fonts` or bundled asset fonts.

## Reference & Inspiration Gathering

Instead of building mockups in an external design tool first, collect reference and
inspiration directly:

- **Mobbin MCP** (`search_flows` / `search_screens` / `search_sections`) — real
  shipped-app screens and flows to ground a signature decision or a layout pattern in
  something that actually exists, not just training-data instinct.
- **Targeted web search** for the subject's domain (materials, rituals, vocabulary) to
  anchor the palette/type/signature decisions from Steps 1–2 above.
- **Vector over stock photos** still applies without a design tool: hand-author or
  source SVGs (icons, illustrations, a mascot) as project assets consumed via
  `flutter_svg`, colouring them per-context in code rather than baking one export.
  (Stock photos read generic and the user generally does **not** want them.)
- **Personality via a mascot is the strongest "this is *my* app" signature.** Pattern
  from the HellerIO project (`hellerio/assets/images/Helo.svg`): a rounded blob character
  with kawaii eyes + a soft gradient + a small accessory, shipped as a clean **SVG** and
  later animated in **Rive** (idle / hint / wave states). Make the character harmonize
  with the product **name**. A clean flat-but-warm design without a distinctive
  centerpiece reads "safe/boring"; a mascot or a bold signature visual is what delivers
  the wow — it now ships straight as an SVG asset + Flutter widget, no intermediate
  design file.
- **Spacing rhythm = premium.** 8pt grid, generous padding (20–24 screen, 14–16 cards),
  deliberately *varied* radii (not a uniform 16 everywhere), soft shadows for depth.
  Flat single-colour blocks read cheap; depth + one bold signature read premium. Judge
  this by running the app / taking a simulator or device screenshot, not by reviewing an
  external mockup.

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
