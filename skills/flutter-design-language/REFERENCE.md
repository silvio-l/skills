# Flutter Design Language — Referenz

Belegt durch Anthropics `frontend-design`-Skill + Cookbook und eine verifizierte
Deep-Research (Stand Juni 2026). Quellen am Ende.

## Slop-Checkliste (Gate — das alles vermeiden)

Der verifizierte „AI-Design-Fingerabdruck":

- [ ] **Kein Default-Indigo/Purple** (`#4F46E5`, `bg-indigo-500` & Verwandte). Das ist
      der vererbte Tailwind-UI-Button-Default — das verräterischste Slop-Signal.
- [ ] **Keine Default-Fonts:** Inter, Roboto, Poppins, Open Sans, Lato, System-Sans
      ohne anderen Grund. (Anthropic-Cookbook verbietet diese explizit.)
- [ ] **Kein uniformer 16px-Radius** auf allem. Radien bewusst variieren.
- [ ] **Keine reflexhafte zentrierte Hero + ein lila CTA.**
- [ ] **Kein Drei-Icon-Feature-Grid** als Default-Struktur.
- [ ] **Keine zaghafte Palette** (alles entsättigtes Grau-Blau), keine blassen
      Alibi-Schatten, kein Glassmorphism-Overkill, keine Emoji-Bullets.

Plus die drei Cluster, die der `frontend-design`-SKILL.md nennt (auch Defaults):
(1) Creme `#F4F1EA` + High-Contrast-Serif + Terracotta;
(2) Near-Black + ein Acid-Green/Vermilion-Akzent;
(3) Broadsheet-Layout mit Haarlinien, Zero-Radius, dichten Zeitungsspalten.
Legitim *wenn der Brief sie verlangt* — sonst freie Achsen nicht damit füllen.

## Typografie

Anthropics Drei-Teile-Strategie: **(a) jede Dimension einzeln führen, (b) Referenzen
nennen, (c) Defaults verbieten.** Für Fonts heißt das konkret:

- **Meiden:** Inter, Roboto, Poppins, Open Sans, Lato, System-Default.
- **Charakter-Schriften (Beispiele):** Display — Fraunces, Playfair Display, Clash
  Display, Bricolage Grotesque, Space Grotesk; Body — DM Sans, Spline Sans, Satoshi,
  Mulish; Mono/Utility — JetBrains Mono, Space Mono.
- In Flutter via `google_fonts` (schnell) oder gebündelte Asset-Fonts (offline,
  Free-Tier-freundlich, keine Laufzeit-Fetches). Bewusstes Display+Body-Pairing,
  klare Skala mit intentionalen Gewichten.

## Farbe in Flutter (jenseits Seed-Purple)

`ColorScheme.fromSeed(seedColor: …)` nimmt **nur einen** Seed — secondary/tertiary sind
bloße Overrides. Zwei bessere Wege:

1. **`flex_seed_scheme`** (`SeedColorScheme.fromSeeds`): mehrere **Schlüsselfarben**
   (primaryKey/secondaryKey/tertiaryKey) + ein **`FlexTones`-Preset**
   (`vivid`/`soft`/`highContrast`/`chroma`/…) → eine Palette mit Charakter statt
   Ein-Seed-Monokultur. Light + Dark aus denselben Keys.
2. **Hand-autorisiertes `ColorScheme`** aus der bewussten 4–6-Hex-Palette
   (`ColorScheme.light()/dark().copyWith(...)`), wenn die Markenfarben exakt sitzen sollen.

Radius/Elevation/Motion/Sonderfarben, die nicht in `ColorScheme` passen → als
`ThemeExtension` registrieren (z.B. `AppRadius`, `AppElevation`, Brand-Akzente).

## Design-Tokens: drei Stufen, rollenbenannt

Nach W3C-DTCG / Figma-Best-Practice (überlebt Rebrands):

- **primitive** — Rohwerte ohne Bedeutung: `color.amber.500 = #C9892F`, `space.4 = 16`.
- **semantic / `sys.*`** — **Rolle**, nicht Aussehen: `sys.color.brand`,
  `sys.color.surface`, `sys.color.danger`. Aliassiert auf primitive.
- **component** — komponentenspezifisch: `button.bg = sys.color.brand`.

Benenne nie nach Aussehen (`color.purple`) — immer nach Rolle (`sys.color.brand`).
`design_tokens_builder` macht aus `sys.*`-Tokens nativ `ColorScheme`/`TextTheme`;
Light/Dark über Set-Suffixe. (Unsere MCP-native Variante: Figma-Variables zweistufig —
eine *primitive*-Collection + eine *semantic*-Collection, die darauf aliasiert.)

## Figma-Seite

- Zwei Variable-Collections: **Primitive** (Rohwerte) + **Semantic** (Rollen, aliasiert
  auf Primitive). So bleibt ein Rebrand ein Edit an einer Stelle.
- **Text Styles** für die Typo-Rollen (Display/Body/Utility) statt Ad-hoc-Größen — das
  macht später das `figma-to-flutter`-Typo-Mapping exakt statt approximativ.
- Components mit Charakter: das Signature-Element als echte Component.

## Brief-Template (Phase 0, Schritt 2)

```
Subjekt:      <was ist das konkret>
Zielgruppe:   <wer nutzt es>
Eine Aufgabe: <der eine Job des Haupt-Screens>
Risiko:       <das eine begründete ästhetische Risiko>

Color (4–6, benannt + Begründung):
  <name> <#hex>  — <warum gehört das zum Subjekt>
Type:
  Display: <Schrift> — <Charakter>
  Body:    <Schrift>
  Utility: <Schrift/Mono, optional>
Layout:   <ein Satz> + ASCII-Wireframe
Signature: <das eine Memorable, kodiert etwas Wahres>

Verworfene Defaults: <was du bewusst NICHT genommen hast und warum>
```

## Quellen
- Anthropic `frontend-design` Skill (installiert) + Cookbook „Prompting for frontend
  aesthetics" (platform.claude.com/cookbook).
- Deep Research Juni 2026: 925studios, monet.design, prg.sh (Slop-Fingerabdruck);
  dev.to/alanwest (Tailwind `indigo-500`-Ursprung); flex_color_scheme / rydmike,
  Flutter-API (ColorScheme/Seed); Figma design-tokens, W3C DTCG (Token-Tiers);
  simpleclub/design_tokens_builder (`sys.*`→ThemeData).
