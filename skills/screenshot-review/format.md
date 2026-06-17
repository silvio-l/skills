# Formate — Finding, Per-Screen-Report, Subagent-Rückgabe, Gesamtbericht

Alle Formate sind bewusst **strikt und maschinenparsebar**: stabile IDs, fixes
Severity-Enum, imperative Empfehlungen. Ein nachgelagerter Agent (oder `/ratchet-up`
via `## Visual expectations`) soll die Findings ohne Rückfragen abarbeiten können.

---

## Finding-Format

Jedes Finding ist ein Markdown-Block in exakt dieser Struktur:

```md
### <SCREEN-ID>-001 · <Kategorie> · <Severity>

- **Bereich:** <konkreter sichtbarer Ort, z.B. "Header / Hauptüberschrift">
- **Beobachtung:** <was im Bild sichtbar ist — verankert, ohne Wertung>
- **Warum problematisch:** <Effekt auf Nutzer/Zielgruppe>
- **Empfehlung:** <imperative, umsetzbare Anweisung; Richtung statt erfundener Zahl>
- **Erwarteter Effekt:** <was die Behebung bringt>
- **Konfidenz:** hoch | mittel | gering   <!-- gering, wenn vision-limitiert -->
```

Regeln:
- **ID** = `<SCREEN-ID>-NNN`, fortlaufend pro Screen (`<SCREEN-ID>` = Dateiname ohne
  Endung). Damit ist jede Empfehlung global eindeutig referenzierbar.
- **Kategorie** = einer der Rubrik-Bereiche, exakt benannt (z.B. `Typografie`,
  `Accessibility`, `Komponentenqualität`).
- **Severity-Enum:** `Critical` | `High` | `Medium` | `Low`. Kalibrierung:
  - **Critical** — blockiert Nutzung/Verständnis oder verletzt eine im Briefing
    *deklarierte* Erwartung (Token, design-language.md, manifest): abgeschnittener
    Text, unlesbarer Kontrast, nicht erkennbare Primäraktion, kaputtes Layout, falsche
    Token-Farbe gegen deklarierte Palette.
  - **High** — deutliche Hürde, aber nicht blockierend: schwache Hierarchie,
    inkonsistente Komponenten, zu kleine Touch-Targets.
  - **Medium** — spürbare Schwäche ohne funktionalen Schaden: Spacing-Rhythmus,
    uneinheitliche Rundungen.
  - **Low** — Politur/Geschmack: Mikro-Alignment, dezente Farbnuance.
- **Konfidenz `gering`** ist Pflicht, wenn das Finding an einem vision-limitierten
  Detail hängt (1px-Border, Shadow, exakter Kontrast) — das Finding bleibt, aber
  ehrlich markiert.

---

## Per-Screen-Report — `screens/<screen-id>.md`

Der Reviewer-Subagent schreibt **diese** Datei:

```md
# Screen-Review: <screen-id>

- **Datei:** <relativer Pfad zum Screenshot>
- **Plattform/Stack:** <aus Briefing>
- **Reviewt gegen:** <Zielgruppe + deklarierte Erwartungsquelle, oder "kein expliziter Kontext">

## Scores (0–100)
| Dimension | Score |
|---|---|
| UI-Qualität | NN |
| UX-Qualität | NN |
| Accessibility | NN |
| Konsistenz | NN |
| Zielgruppen-Fit | NN |

## Findings
<alle Finding-Blöcke, nach Severity sortiert (Critical zuerst)>

## Kritische Probleme
<Bullet-Liste der Critical-Finding-IDs + Einzeiler; "keine", wenn keine>

## Priorisierte Behebungsreihenfolge
1. <Finding-ID> — <Kurzbegründung der Priorität>
2. …
```

Score-Leitlinie: nicht großzügig sein. Ein Screen mit einem Critical kann in keiner
Dimension über ~50 liegen, die das Critical betrifft.

---

## Subagent-Rückgabe (an den Orchestrator — KEIN Report-Volltext)

Der Subagent gibt dem Orchestrator **nur** diese kompakte Zeile zurück (context-safe;
der Volltext steht in der Datei):

```
<screen-id> | scores: ui=NN ux=NN a11y=NN cons=NN fit=NN | findings: C=n H=n M=n L=n | top: <ID kürzeste Critical/High-Beschreibung>
```

Findet der Subagent keinen Screenshot oder kann das Bild nicht lesen, gibt er
`<screen-id> | ERROR: <grund>` zurück und schreibt keine Datei.

---

## Gesamtbericht — `report.md` (Orchestrator, Phase 2)

```md
# Screenshot-Review — Gesamtbericht (<YYYY-MM-DD>)

- **Ordner:** <screenshot-folder>
- **Screens:** <n>
- **App-Kontext:** <Zielgruppe · Zweck · Plattform · Design-System (1 Zeile)>

## Score-Übersicht
| Screen | UI | UX | A11y | Konsistenz | Fit | Critical |
|---|---|---|---|---|---|---|
| <screen-id> | NN | NN | NN | NN | NN | n |
| … |

## Kritische Probleme (alle Screens)
<Liste aller Critical-Finding-IDs mit Screen + Einzeiler>

## App-weite Konsistenz-Muster
<NUR hier: gleiche Komponente über Screens unterschiedlich gestylt, uneinheitliche
AppBars/Buttons/Spacing-Skala/Rundungen über den Ordner hinweg. Verweise auf die
betroffenen Finding-IDs aus den Einzelreports. Keine im Aggregat sichtbare
Inkonsistenz erfinden, die in keinem Einzelreport steht.>

## Global priorisierte Worklist
| # | Finding-ID(s) | Screen(s) | Severity | Aufwand (S/M/L) | Maßnahme |
|---|---|---|---|---|---|
| 1 | … | … | Critical | S | <imperative Maßnahme> |

Reihenfolge: Severity zuerst, bei Gleichstand kleinerer Aufwand zuerst. App-weite
Muster (ein Fix räumt mehrere Screens) vor Einzel-Screen-Findings.
```
