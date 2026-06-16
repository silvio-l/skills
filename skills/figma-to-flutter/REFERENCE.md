# Token-Pipeline: Figma Variables → Flutter

Voraussetzung des Skills. Einmal pro Projekt aufsetzen, danach bei Token-Änderungen
neu generieren. Ziel: Tokens sind **compile-time Dart-Code**, nie zur Laufzeit geparst.

## Empfohlen: MCP-nativ (Figma Variables)

Wenn die Tokens als **Figma Variables** gepflegt sind (das native Token-Primitiv):

1. `get_variable_defs(fileKey, nodeId)` liefert Name→Wert der im Frame genutzten
   Variablen. **Wichtige Grenze:** nur der *aktive Modus* (i.d.R. Light). Für
   Light **und** Dark beide Modi aus den Variable-Definitionen übernehmen — der
   Per-Node-Call gibt nicht beide gleichzeitig.
2. Werte in `design/tokens.json` festhalten (Quelle der Wahrheit, beide Modi).
3. Schreibe im Projekt einen Generator `tool/gen_tokens.dart` (der Skill liefert ihn
   nicht mit — er ist projektspezifisch), der `lib/theme/tokens.dart` erzeugt:
   - `ColorScheme` Light + Dark (`ColorScheme.light()/dark().copyWith(...)`).
   - `AppSpacing`, `AppRadius` als `static const double`.
4. `dart run tool/gen_tokens.dart` → generierte Datei trägt einen
   `// GENERATED … DO NOT EDIT`-Header.
5. Stabile `lib/theme/app_theme.dart` (nicht generiert) baut daraus die `ThemeData`.

`tokens.json`-Form:

```json
{
  "color":  { "primary": { "light": "#C9892F", "dark": "#E8B563" }, "...": {} },
  "space":  { "sm": 8, "md": 16, "lg": 24, "xl": 32 },
  "radius": { "md": 12, "lg": 20 }
}
```

Mapping auf Material-3-`ColorScheme`-Slots: `primary`/`onPrimary`/`surface`/`onSurface`/
`surfaceContainerHighest` (≈ surfaceVariant)/`onSurfaceVariant`/`outline`. Slots ohne
Token behalten die Material-Defaults über `copyWith`.

**Anti-Slop bei der Farbe:** Die Palette stammt aus `flutter-design-language` (Phase 0),
nicht aus `ColorScheme.fromSeed(seedColor: <eine Farbe>)` — ein einzelner Seed erzeugt
die generische Ein-Farb-Monokultur (und per Default das berüchtigte Indigo). Für ein
seed-basiertes, aber charaktervolles Schema `flex_seed_scheme`
(`SeedColorScheme.fromSeeds` mit primaryKey/secondaryKey/tertiaryKey + `FlexTones`)
nutzen; für exakte Markenfarben das `ColorScheme` direkt aus den Tokens bauen.

## Alternative: Tokens Studio

Nutzt das Projekt bereits das **Tokens-Studio-Plugin**: Tokens als JSON exportieren und
mit dem Paket `design_tokens_builder` (build_runner) zu `ThemeData` generieren. Gleiches
Prinzip (compile-time Dart), anderer Eingang. Das Plugin lässt sich **nicht** über MCP
auslösen — der Export bleibt ein manueller Schritt in Figma.

## Drift mechanisch verhindern

Nach dem Codegen einen Lint setzen, der **rohe Hex-Farben im App-Code verbietet** (Dart
`custom_lint`, CI-gated). Fängt nur rohe Literale, nicht falsche Token-Wahl — aber
schließt den häufigsten Drift-Vektor. Spacing/Radius analog: nur `AppSpacing`/`AppRadius`,
keine magischen Zahlen.
