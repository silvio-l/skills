# Token Pipeline: Figma Variables → Flutter

Prerequisite for the skill. Set up once per project, then re-generate whenever tokens
change. Goal: tokens are **compile-time Dart code**, never parsed at runtime.

## Recommended: MCP-native (Figma Variables)

When tokens are maintained as **Figma Variables** (the native token primitive):

1. `get_variable_defs(fileKey, nodeId)` returns the name→value mapping for variables
   used in the frame. **Important limit:** only the *active mode* (typically Light). To
   get both Light **and** Dark, extract both modes from the variable definitions — the
   per-node call does not return both at once.
2. Record values in `design/tokens.json` (source of truth, both modes).
3. Write a generator `tool/gen_tokens.dart` in the project (the skill does not ship one
   — it is project-specific) that produces `lib/theme/tokens.dart`:
   - `ColorScheme` Light + Dark (`ColorScheme.light()/dark().copyWith(...)`).
   - `AppSpacing`, `AppRadius` as `static const double`.
4. `dart run tool/gen_tokens.dart` → the generated file carries a
   `// GENERATED … DO NOT EDIT` header.
5. The stable `lib/theme/app_theme.dart` (not generated) builds the `ThemeData` from it.

`tokens.json` format:

```json
{
  "color":  { "primary": { "light": "#C9892F", "dark": "#E8B563" }, "...": {} },
  "space":  { "sm": 8, "md": 16, "lg": 24, "xl": 32 },
  "radius": { "md": 12, "lg": 20 }
}
```

Mapping to Material 3 `ColorScheme` slots: `primary`/`onPrimary`/`surface`/`onSurface`/
`surfaceContainerHighest` (≈ surfaceVariant)/`onSurfaceVariant`/`outline`. Slots without
a token retain the Material defaults via `copyWith`.

**Anti-slop for color:** The palette comes from `flutter-design-language` (Phase 0),
not from `ColorScheme.fromSeed(seedColor: <one color>)` — a single seed produces the
generic single-color monoculture (and by default the notorious Indigo). For a seed-based
but characterful scheme use `flex_seed_scheme` (`SeedColorScheme.fromSeeds` with
primaryKey/secondaryKey/tertiaryKey + `FlexTones`); for exact brand colors build the
`ColorScheme` directly from tokens.

## Alternative: Tokens Studio

If the project already uses the **Tokens Studio plugin**: export tokens as JSON and
generate `ThemeData` with the `design_tokens_builder` package (build_runner). Same
principle (compile-time Dart), different input. The plugin **cannot** be triggered via
MCP — the export remains a manual step in Figma.

## Mechanically preventing drift

After codegen, add a lint that **forbids raw hex colors in app code** (Dart
`custom_lint`, CI-gated). Catches only raw literals, not wrong token choices — but closes
the most common drift vector. Spacing/radius analogously: only `AppSpacing`/`AppRadius`,
no magic numbers.
