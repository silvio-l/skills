---
name: figma-to-flutter
description: Converts a Figma frame (URL with node-id) into a Flutter widget using only theme tokens. Use when sharing a Figma design URL to build a Flutter widget/screen, 'Figma in Flutter umsetzen', 'diesen Screen bauen', 'Figma-Frame zu Widget'.
---

# Figma → Flutter

Translates **one** Figma frame into **one** Flutter widget. The generated code is a
scaffold for a human to review — not a finished product. Tokens are not invented;
data logic is not generated.

Prerequisite: you are working in a Flutter project with the Figma MCP integration.
Read `REFERENCE.md` for the token pipeline (Figma Variables → `tokens.dart`).

## Preconditions (otherwise STOP and report)

0. **Intentional design language exists.** `design/design-language.md` + a
   *role-named* `design/tokens.json` (from `flutter-design-language`, Phase 0).
   Missing → **run `flutter-design-language` first**, otherwise the pipeline just
   ships neatly packaged slop (Indigo default, Roboto/Inter, uniform radius).
1. **Theme layer exists.** `lib/theme/tokens.dart` with `ColorScheme` (Light/Dark),
   `AppSpacing`, `AppRadius`. Missing → set up the token pipeline first
   (see `REFERENCE.md`), do not hardcode.
2. **Frame uses Auto Layout.** Verify via `get_metadata`/`get_design_context`. Freehand
   or absolutely positioned frames produce broken mapping — warn the user before building.
3. **node-id present.** The URL must contain `?node-id=…`. Otherwise ask the user.

## Procedure

1. **Parse the URL** → `fileKey` + `nodeId` (replace `-` with `:` in the node-id).
2. **Fetch context — two calls, both required:**
   - `get_design_context(fileKey, nodeId)` → structured layout/token data.
   - `get_screenshot(fileKey, nodeId)` → visual benchmark. Save the screenshot locally
     to `.scratch/` and view it with `Read`.
3. **Resolve token names:** `get_variable_defs(fileKey, nodeId)` returns variables used
   in the frame with their values — **but only for the currently active mode** (typically
   Light). Use the *names* (`color/primary`, `space/lg`) to map to theme primitives —
   never write raw hex/pixel values into widget code.
4. **Write the widget** to `lib/ui/<feature>/<name>.dart`:
   - `StatelessWidget`, purely presentational.
   - Data comes in via constructor parameters. **No** Supabase/network/state code in
     the widget.
   - Values exclusively via tokens (mapping table below).
5. **Golden test** to `test/ui/<name>_golden_test.dart` (Light + Dark).
6. **Run `dart analyze` + `flutter test`.** Red → fix, do not build further.
7. **REVIEW GATE:** Show the user the screenshot, the widget, and any uncertain areas.
   **Only after their approval** wire it into `main.dart`/navigation. Never merge autonomously.

## Mapping Table (Figma → Flutter)

| Figma                          | Flutter                                        |
|--------------------------------|------------------------------------------------|
| Auto Layout vertical           | `Column`                                       |
| Auto Layout horizontal         | `Row`                                          |
| Item spacing / gap             | `SizedBox` / `spacing:` from `AppSpacing`      |
| Padding                        | `Padding(EdgeInsets … AppSpacing)`             |
| Fill color (variable)          | `ColorScheme.<slot>` / `ThemeExtension` token  |
| Text style                     | `TextTheme.<style>` from `Theme.of(context)`   |
| Corner radius (variable)       | `BorderRadius.circular(AppRadius.<t>)`         |
| Ellipse as avatar              | `CircleAvatar` / `ClipOval`                    |
| "Fill container" (FILL)        | `Expanded` / `Flexible`                        |
| Component instance             | existing Flutter widget (map manually)         |
| Absolute position              | `Stack` + `Positioned` — flag as a smell       |

## Hard Rules

- **No raw values.** No `Color(0x…)`, no magic numbers for spacing/radius.
  Tokens only. Violation = stop and add the missing token.
- **No data logic.** No Supabase, no `http`, no state management, no navigation in the
  generated widget. It takes data as parameters, nothing else.
- **Do not guess component mappings.** Figma Code Connect does not support Flutter — if a
  component instance does not map to a known widget, **report it instead of inventing one**.
- **Vision has limits.** Screenshot comparison reliably detects layout/color; 1px borders
  and shadow spread it does not. Mark such details explicitly for review.
- **A human reviews every widget before merge.** This is not autonomous codegen.

## What this skill does NOT do

- No full app, no multi-screen flow in one run — one frame per run.
- No FlutterFlow/drag-and-drop export.
- No code→Figma (use `figma-generate-design` for that).
