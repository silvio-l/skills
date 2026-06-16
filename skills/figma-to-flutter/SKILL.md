---
name: figma-to-flutter
description: Wandelt einen Figma-Frame (Design-URL mit node-id) in ein präsentationsorientiertes Flutter-Widget, das ausschließlich Theme-Tokens nutzt — assistiert, nicht autonom. Use when the user shares a Figma design URL and wants it built as a Flutter widget/screen, says "Figma in Flutter umsetzen", "diesen Screen bauen", "Figma-Frame zu Widget". NICHT für Code→Figma (dafür figma-generate-design) und NICHT für reine Design-System-Arbeit.
---

# Figma → Flutter

Übersetzt **einen** Figma-Frame in **ein** Flutter-Widget. Der generierte Code ist ein
Gerüst, das ein Mensch reviewt — kein fertiges Produkt. Tokens werden nicht erfunden,
Datenlogik wird nicht mitgeneriert.

Voraussetzung: Du arbeitest in einem Flutter-Projekt mit der Figma-MCP-Anbindung.
Lies `REFERENCE.md` für die Token-Pipeline (Figma Variables → `tokens.dart`).

## Vorbedingungen (sonst STOPP und melden)

1. **Theme-Layer existiert.** `lib/theme/tokens.dart` mit `ColorScheme` (Light/Dark),
   `AppSpacing`, `AppRadius`. Fehlt sie → zuerst die Token-Pipeline aufsetzen
   (siehe `REFERENCE.md`), nicht hardcoden.
2. **Frame nutzt Auto Layout.** Prüfe via `get_metadata`/`get_design_context`. Freehand-
   bzw. absolut positionierte Frames erzeugen kaputtes Mapping — den User warnen, bevor
   du baust.
3. **node-id vorhanden.** Die URL muss `?node-id=…` enthalten. Sonst beim User anfragen.

## Ablauf

1. **URL parsen** → `fileKey` + `nodeId` (in der node-id `-` durch `:` ersetzen).
2. **Kontext holen — zwei Calls, beide nötig:**
   - `get_design_context(fileKey, nodeId)` → strukturierte Layout-/Token-Daten.
   - `get_screenshot(fileKey, nodeId)` → visueller Benchmark. Screenshot lokal nach
     `.scratch/` laden und mit `Read` ansehen.
3. **Token-Namen auflösen:** `get_variable_defs(fileKey, nodeId)` gibt die im Frame
   genutzten Variablen mit Werten — **aber nur für den aktuell aktiven Modus** (i.d.R.
   Light). Nutze die *Namen* (`color/primary`, `space/lg`), um auf die Theme-Primitive
   zu mappen — nie die rohen Hex-/Pixelwerte in den Widget-Code schreiben.
4. **Widget schreiben** nach `lib/ui/<feature>/<name>.dart`:
   - `StatelessWidget`, rein präsentationsorientiert.
   - Daten kommen über Konstruktor-Parameter rein. **Kein** Supabase-/Netzwerk-/
     State-Code im Widget.
   - Werte ausschließlich über Tokens (Mapping-Tabelle unten).
5. **Golden Test** nach `test/ui/<name>_golden_test.dart` (Light + Dark).
6. **`dart analyze` + `flutter test`** laufen lassen. Rot → fixen, nicht weiterbauen.
7. **REVIEW-GATE:** Dem User den Screenshot, das Widget und unsichere Stellen zeigen.
   **Erst nach seinem OK** in `main.dart`/Navigation einhängen. Niemals autonom mergen.

## Mapping-Tabelle (Figma → Flutter)

| Figma                          | Flutter                                        |
|--------------------------------|------------------------------------------------|
| Auto Layout vertikal           | `Column`                                       |
| Auto Layout horizontal         | `Row`                                          |
| Item spacing / gap             | `SizedBox` / `spacing:` aus `AppSpacing`       |
| Padding                        | `Padding(EdgeInsets … AppSpacing)`             |
| Fill-Farbe (Variable)          | `ColorScheme.<slot>` / `ThemeExtension`-Token  |
| Text-Style                     | `TextTheme.<style>` aus `Theme.of(context)`    |
| Corner radius (Variable)       | `BorderRadius.circular(AppRadius.<t>)`         |
| Ellipse als Avatar             | `CircleAvatar` / `ClipOval`                    |
| „Fill container" (FILL)        | `Expanded` / `Flexible`                        |
| Component-Instanz              | bestehendes Flutter-Widget (manuell mappen)    |
| Absolute Position              | `Stack` + `Positioned` — als Smell flaggen     |

## Harte Regeln

- **Keine rohen Werte.** Kein `Color(0x…)`, keine magischen Zahlen für Spacing/Radius.
  Nur Tokens. Verstoß = Stopp und Token nachtragen.
- **Keine Datenlogik.** Kein Supabase, kein `http`, kein State-Management, keine
  Navigation im generierten Widget. Es nimmt Daten als Parameter, sonst nichts.
- **Component-Mappings nicht raten.** Figma Code Connect kann kein Flutter — wenn eine
  Component-Instanz auf kein bekanntes Widget zeigt, **melden statt erfinden**.
- **Vision hat Grenzen.** Layout/Farbe erkennt der Screenshot-Abgleich zuverlässig,
  1px-Borders und Shadow-Spread nicht. Solche Details explizit zum Review markieren.
- **Mensch reviewt jedes Widget vor dem Merge.** Dies ist kein autonomer Codegen.

## Was dieser Skill NICHT tut

- Keine ganze App, keinen Multi-Screen-Flow auf einmal — ein Frame pro Lauf.
- Kein FlutterFlow/Drag-and-Drop-Export.
- Kein Code→Figma (dafür `figma-generate-design`).
