# Audit-Rubrik — die 13 Analysebereiche

Der Reviewer geht **jeden** Bereich für seinen einen Screenshot durch. Pro Bereich
gilt: aktiv nach Problemen suchen, nichts als korrekt voraussetzen — aber jedes
Finding auf ein im Bild *sichtbares* Element verankern. Findet ein Bereich nichts,
notier das knapp; erfinde nichts, um die Liste zu füllen.

Querschnitt-Disziplin (gilt überall):
- **Relativ statt falsch-präzise.** Aus einem Screenshot sind exakte px/Hex/Kontrast-
  Ratios geraten. Beschreibe Verhältnisse („Headline kaum schwerer als Body"), nicht
  Absolutwerte. Empfehlungen geben die *Richtung* an („Headline-Gewicht/Größe deutlich
  anheben, Body zurücknehmen"), keine erfundene Zielzahl.
- **Vision-Grenzen deklarieren.** 1px-Borders, Shadow-Spread, exakte Kontrastwerte,
  Sub-Pixel-Alignment erkennt Vision nicht zuverlässig. Wo ein Urteil daran hängt,
  schreib „aus dem Screenshot nicht sicher beurteilbar" ins Finding, statt zu raten.

---

## 1. Erster Eindruck
3-Sekunden-Urteil: modern / hochwertig / vertrauenswürdig / professionell — oder
überladen / leer / inkonsistent / unverständlich? Benenne die Wirkung konkret und
woran sie im Bild hängt.

## 2. Visuelle Hierarchie
Ist sofort klar, was wichtig ist? Klarer Fokuspunkt? Wird Wichtiges hervorgehoben,
Unwichtiges zurückgenommen? Konkurrieren Elemente um Aufmerksamkeit?

## 3. Layout & Spacing
Außen-/Innenabstände, Grid-Konsistenz, Alignment, Padding/Margins, Safe Areas,
visuelle Balance, Rhythmus. Suche: unregelmäßige Abstände, inkonsistente
Einrückungen, visuelle Sprünge, schlecht ausgerichtete Elemente.

## 4. Typografie
Größenverhältnisse, Zeilenhöhe, Lesbarkeit, Gewichtungen, Überschriften-Hierarchie,
Textkontrast, Textlängen/Umbrüche. Suche: zu kleine/große Schrift, inkonsistente
Größen, fehlende Hierarchie, abgeschnittener Text.

## 5. Farben
Palette, Markenwirkung, Konsistenz, Kontrast, Hervorhebungs-/Fokus-/CTA-Farben.
Suche: unnötige Farben, schwache Kontraste, visuelle Unruhe, fehlende Farbstrategie.
Gegen `design/tokens.json` prüfen, falls im Briefing deklariert.

## 6. Komponentenqualität
Jede sichtbare Komponente (Buttons, Cards, Dialoge, Navigation, Listen, Formulare,
Chips, Tabs, Badges, FABs, Suchfelder, Dropdowns): Konsistenz, Größe, Modernität,
erkennbare Klickbarkeit, ausreichend große Touch-Zonen.

## 7. Mobile UX
Thumb-Reachability, Einhand-Bedienung, Informationsdichte, erkennbares
Scroll-Verhalten, Priorisierung. Suche: unnötige Schritte, schlechte Platzierung
wichtiger Aktionen, ergonomische Probleme.

## 8. Accessibility
Farbkontraste (qualitativ, gegen WCAG 2.2 als Maßstab), Schriftgrößen, Touch-Target-
Größe, Lesbarkeit, soweit aus dem Bild ableitbar auch Screenreader-Tauglichkeit
(reine Icon-Buttons ohne Label etc.). Kontrast nie als exakte Ratio behaupten.

## 9. Design-System-Konsistenz (innerhalb des Screens)
Inkonsistenzen *innerhalb dieses einen Screens*: abweichende Rundungen, Schatten,
Größen, Abstände, doppelte Komponenten-Varianten. **Cross-Screen-Konsistenz gehört
NICHT hierher** — die beurteilt der Orchestrator in der Synthese.

## 10. Informationsarchitektur
Verständlichkeit, Gruppierungen, Reihenfolgen, mentale Modelle. Leitfrage:
„Versteht die Zielgruppe sofort, was hier passiert?"

## 11. Zielgruppen-Fit
Passt der Screen zur im Briefing definierten Zielgruppe? Bewerte Sprache,
Komplexität, Informationsdichte, Farbwahl, Emotionalität, Professionalität. Erkläre
jede Abweichung. Ist die Zielgruppe `UNBEKANNT`, überspring diesen Bereich und
vermerk das — rate nicht.

## 12. Emotionale Wirkung
Welche Wirkung transportiert der Screen (modern / altmodisch / technisch /
freundlich / vertrauenswürdig / hochwertig / billig / professionell / verspielt)?
Passt sie zum App-Zweck?

## 13. Flutter-spezifische Qualität
Anzeichen für: unangepasste Standard-Widgets, Material-3-Inkonsistenzen,
inkonsistente AppBars, schwache Responsive-Anpassung, typische Flutter-Anti-Patterns
(z.B. Default-Purple, uniformer 16er-Radius, generische Default-Schrift). Nur
anwenden, wenn das Briefing Flutter als Stack ausweist; sonst überspringen.
