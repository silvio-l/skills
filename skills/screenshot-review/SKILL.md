---
name: screenshot-review
description: "Kompromissloses UI/UX-Audit eines Ordners von App-Screenshots: zieht App-Kontext aus dem Repo, reviewt jeden Screen per Subagent gegen eine 13-Punkte-Rubrik, schreibt abarbeitbare Findings. Use when auditing screenshots, UI-Review, 'Screens prüfen'."
metadata:
  argument-hint: "<screenshot-folder>"
---

# Screenshot Review — Kompromissloses UI/UX-Audit

Du bist der **Orchestrator** eines Senior-UI/UX-Audits über einen Ordner voller
App-Screenshots. Du sammelst Kontext, dispatchst pro Screen einen read-only
Reviewer-Subagenten, aggregierst die Einzelreports zu einem Gesamtbericht. Du
beurteilst **keinen** Screen selbst im Detail — das machen die Subagenten, damit
dein Kontext schlank bleibt (kein einziger Report-Volltext im Orchestrator).

Ergebnis ist ein **Markdown-Report** pro Screen plus ein Gesamtbericht. Das
Format ist bewusst maschinenparsebar (stabile Finding-IDs, Severity-Enum,
imperative Empfehlungen, abschließende Worklist), sodass ein **nachgelagerter
KI-Agent** die Findings ohne Rückfragen abarbeiten kann.

Der Skill ist **plattformagnostisch** mit Flutter-Schwerpunkt (Analysebereich 13).
Er analysiert ausschließlich die **sichtbare** Oberfläche der Screenshots — er
liest keinen Quellcode zur Beurteilung und rendert nichts selbst.

## Where things live

| Concern | File |
|---|---|
| Die 13 Analysebereiche (Audit-Rubrik) | [rubric.md](rubric.md) |
| Finding-Format, Per-Screen-Report, Gesamtbericht | [format.md](format.md) |
| Reviewer-Subagent Prompt-Template | [reviewer.md](reviewer.md) |

Lade die Datei, die du gerade brauchst. SKILL.md ist die always-on-Schicht — halt sie knapp.

## Core Principles

- **Kompromisslos in der Tiefe, verankert im Pixel.** Suche aktiv nach Problemen,
  geh nie davon aus, dass etwas korrekt ist, nimm an, dass Optimierungspotenzial
  existiert — **aber** jedes Finding zeigt auf ein im Screenshot *sichtbares*
  Element. Keine erfundenen Messwerte: aus einem Screenshot sind exakte px/Hex
  geraten, nicht gemessen. Formuliere relativ („Headline kaum schwerer als Body",
  „CTA und Sekundär-Button optisch gleichwertig"), nicht falsch-präzise („auf
  28 px setzen"). Wo Vision an Grenzen stößt (1px-Borders, Shadow-Spread, exakter
  Kontrast), sag das im Finding explizit.
- **Jeder Screen wird unabhängig bewertet.** Analysiere nie mehrere Screens
  gemeinsam — ein Subagent sieht genau einen Screenshot. **Cross-Screen-Konsistenz**
  (Analysebereich 9) ist deshalb kein Per-Screen-Job, sondern ein **Synthese-Schritt**
  des Orchestrators aus den Einzelreports (Phase 2).
- **Context-safe.** Der Reviewer schreibt seinen Report direkt auf Platte und gibt
  dir nur eine kompakte Zusammenfassung zurück (Score + Findings je Severity). Kein
  Report-Volltext, kein Bild-Base64 wandert in deinen aktiven Kontext.
- **Kontext zuerst, dann Audit.** Ohne App-Kontext (Zielgruppe, Zweck, Plattform,
  Design-System) ist ein Zielgruppen-Fit-Urteil (Bereich 11) wertlos. Phase 0 zieht
  den Kontext aus dem Repo und klärt Lücken mit dem User, **bevor** ein Screen
  reviewt wird.
- **Read-only.** Der Skill ändert keinen Quellcode und keine Screenshots. Er
  schreibt ausschließlich in sein Output-Verzeichnis. Niemals committen, mergen,
  pushen — das bleibt User-getrieben.
- **Model-Routing.** Reviewer-Subagenten immer mit `model: claude-sonnet-4-6`
  spawnen (Vision-Design-Urteil; Haiku zu schwach, Opus zu teuer für den
  Mengen-Pass). Einen einzelnen besonders kritischen Screen darfst du auf
  `claude-opus-4-8` eskalieren.

## Ablauf

### Phase 0 — Kontext-Discovery (Orchestrator, einmalig)

1. **Ordner bestimmen.** Argument `<screenshot-folder>`; fehlt es → beim User
   erfragen. Bilder listen (Glob `*.png *.jpg *.jpeg *.webp`, rekursiv). Keine
   Bilder → stopp und melden.
2. **App-Kontext zusammentragen** — best effort, ohne nachzufragen, aus:
   - `CLAUDE.md` (global + Projekt) → Zielgruppe, Stack, Constraints, Designregeln.
   - `design/design-language.md` + `design/tokens.json` (falls vorhanden) → die
     **deklarierte** Designsprache. Das ist die stärkste verfügbare Erwartung; an
     ihr gemessene Abweichungen sind harte Findings, nicht Geschmack.
   - `pubspec.yaml` → Flutter? Material/Cupertino, Plattform-Targets.
   - `README.md` → App-Beschreibung/Zweck.
   - optional `<folder>/manifest.yaml` → Screen→Erwartung-Mapping (Screen-Name,
     Zweck, Figma-node/Mockup-Referenz). Nicht Pflicht.
3. **Briefing destillieren:** Zielgruppe · App-Zweck · Plattform · Design-System ·
   deklarierte Tokens/Erwartungen. Pro Feld: Wert **oder** `UNBEKANNT`.
4. **Feedback-Schleife (Pflicht):** Briefing kompakt zeigen, jedes `UNBEKANNT`
   markieren und gezielt erfragen. Erst nach OK / Ergänzung weiter. Rate keine
   Zielgruppe — ein falsch geratener Zielgruppen-Fit verseucht jeden Screen.

### Phase 1 — Per-Screen-Review (ein Subagent pro Screenshot)

Für jeden Screenshot einen read-only Subagenten spawnen (`subagent_type:
general-purpose`, `model: claude-sonnet-4-6`) mit dem Template aus `reviewer.md`.
Unabhängige Screens dürfen **parallel** laufen (mehrere Tool-Calls in einer
Nachricht; in Batches, um Rate-Limits zu schonen). Jeder Subagent bekommt: das
Kontext-Briefing, den Screenshot-Pfad, den Output-Pfad, sowie die Inhalte von
`rubric.md` und `format.md`. Er liest das Bild, geht alle 13 Bereiche durch,
**schreibt** `<output>/screens/<screen-id>.md` und gibt dir nur die kompakte
Zusammenfassung zurück (siehe `format.md` § Subagent-Rückgabe).

### Phase 2 — Synthese (Orchestrator)

Aus den kompakten Rückgaben den Gesamtbericht `<output>/report.md` bauen (Format
in `format.md` § Gesamtbericht): Score-Tabelle je Screen, alle Critical-Findings
cross-screen, **app-weite Konsistenz-Muster** (gleiche Komponente über Screens
unterschiedlich gestylt — das siehst nur du im Aggregat), eine global priorisierte
Worklist. Dann dem User Output-Pfad + 3-Satz-Fazit nennen.

## Output-Layout

```
.scratch/screenshot-review-<YYYY-MM-DD>/
├── report.md            ← Gesamtbericht (Phase 2)
└── screens/
    ├── <screen-id>.md   ← ein Report pro Screenshot (Phase 1, vom Subagenten)
    └── …
```

`<screen-id>` = Dateiname des Screenshots ohne Endung.

## Quick reference — was tun wann

| Trigger | Action |
|---|---|
| User runs `/screenshot-review <folder>` | Phase 0, Schritt 1 |
| Kontext-Feld `UNBEKANNT` | Feedback-Schleife (Phase 0.4) — nie raten |
| Ordner enthält keine Bilder | Stopp, melden |
| Pro Screenshot | Reviewer-Subagent (`reviewer.md`, Sonnet, parallel in Batches) |
| Alle Screens reviewt | Synthese (Phase 2) → Gesamtbericht |
| Konsistenz über Screens | Nur Phase 2 (Orchestrator-Aggregat), nie im Per-Screen-Pass |

## Was dieser Skill NICHT tut

- Keine Code-Beurteilung und kein Rendern — nur die sichtbaren Screenshots.
- Kein Fix. Er produziert Findings; ein nachgelagerter Agent (z.B. `/ratchet-up`)
  setzt sie um.
- Kein Commit/Merge/Push.
- Keine gemeinsame Beurteilung mehrerer Screens in einem Subagenten.
