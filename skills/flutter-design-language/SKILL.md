---
name: flutter-design-language
description: Phase-0-Gate gegen KI-Design-Slop für die Figma→Flutter-Pipeline. Erzwingt vor jeglichem Token-/Screen-Bau einen bewussten Design-Plan (Palette, Typo-Pairing, Layout, Signature) und eine Kritik gegen den generischen Default. Use when starting a new Flutter app's visual design, defining a design system/theme from scratch, picking colors/fonts/tokens, or when a design "sieht nach KI aus / generisch / Standard-Lila". Vorstufe zu figma-to-flutter. NICHT für reines Frame→Widget (das macht figma-to-flutter).
---

# Flutter Design Language (Anti-Slop Phase 0)

Bevor in Figma eine Variable oder in Flutter ein `ThemeData` entsteht, wird hier die
**Design-Sprache bewusst entschieden**. Ohne dieses Gate erzeugt die Pipeline sauber
verpackten Slop: `#4F46E5`-Indigo, Default-Roboto/Inter, uniformer 16er-Radius,
zentrierte Hero+CTA, zaghafte Palette.

> Haltung (von Anthropics `frontend-design`): Arbeite wie der Design-Lead eines kleinen
> Studios, das jedem Kunden eine *unverwechselbare* Identität gibt. Templatiges wurde
> schon abgelehnt. Triff bewusste, meinungsstarke Entscheidungen — und **ein** echtes,
> begründbares ästhetisches Risiko.

## Ablauf (Pflicht, in dieser Reihenfolge)

### 1. Im Subjekt verankern
Benenne **ein** konkretes Subjekt, seine Zielgruppe und **die eine Aufgabe** des
Haupt-Screens. Distinktive Entscheidungen kommen aus der Welt des Subjekts (Material,
Artefakte, Vokabular) — nicht aus Design-Defaults. Nutze bekannte Nutzer-Präferenzen.
Pinnst du das nicht, gestaltest du den Durchschnitt.

### 2. Design-Plan = kompaktes Token-System (im Denken erarbeiten)
- **Color:** 4–6 **benannte** Hex-Werte mit Begründung. Keine Default-Brand-Farbe.
  Beschreibe, *warum* diese Palette zum Subjekt gehört.
- **Type:** 2+ Rollen — eine charaktervolle **Display**-Schrift (mit Zurückhaltung
  eingesetzt), eine komplementäre **Body**-Schrift, optional eine **Utility/Mono** für
  Daten/Captions. Konkrete Schriftnamen. Siehe Verbots-/Empfehlungsliste in `REFERENCE.md`.
- **Layout:** Konzept in einem Satz + ASCII-Wireframe. Keine reflexhafte zentrierte
  Hero+CTA, kein Drei-Icon-Grid „weil man das so macht".
- **Signature:** das **eine** Element, an das man sich erinnert und das das Subjekt
  verkörpert. Strukturelle Mittel (Nummerierung, Eyebrows, Divider) müssen etwas
  *Wahres* kodieren, nicht dekorieren.

### 3. Kritik gegen den generischen Default (das eigentliche Gate)
Frage für **jeden** Plan-Teil: „Würde ich bei einem ähnlichen Brief hier landen?"
Wenn ja → es ist ein Default, kein Choice → **überarbeiten und benennen, was du
geändert hast und warum.** Gleiche den Plan gegen die Slop-Checkliste in `REFERENCE.md`
ab. Erst wenn der Plan die Prüfung besteht, geht es weiter.

### 4. Festschreiben
- `design/design-language.md` — Subjekt, Palette (mit Begründung), Typo, Layout,
  Signature, das gewählte Risiko, verworfene Defaults.
- `design/tokens.json` — drei-stufig & **rollenbenannt** (siehe `REFERENCE.md`):
  *primitive* (Roh-Werte) → *semantic/`sys.*`* (Rolle) → *component*. Light **und** Dark.

Danach → `figma-to-flutter`: die Tokens speisen Figma-Variables **und** das Flutter-Theme.

## Harte Regeln

- **Spend boldness in one place.** Das Signature-Element ist das eine Memorable; alles
  drumherum ruhig und diszipliniert. „Vor dem Rausgehen ein Accessoire wieder abnehmen."
- **Begründungspflicht.** Jede Farbe/Schrift/Radius-Entscheidung leitet sich aus
  `design-language.md` ab — keine Werte „aus dem Bauch".
- **Defaults sind verboten, nicht nur unschön.** Die Slop-Checkliste ist ein Gate, kein
  Vorschlag. Wo der Brief eine Richtung *vorgibt* (auch eine „generische"), gewinnt der
  Brief — aber freie Achsen nie mit Defaults füllen.
- **Quality-Floor ohne Ankündigung:** responsive bis Mobile, sichtbarer Fokus,
  `reduced-motion`/Accessibility respektiert, Kontrast geprüft.
- **Motion sparsam.** Ein orchestrierter Moment schlägt verstreute Effekte; zu viel
  Animation *ist* ein Slop-Signal.

## Was dieser Skill NICHT tut
- Keine Frame→Widget-Übersetzung (das ist `figma-to-flutter`).
- Kein blindes Generieren — der Plan + die Kritik passieren **vor** dem ersten Pixel.
