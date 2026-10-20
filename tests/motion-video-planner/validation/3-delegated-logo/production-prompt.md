# Production brief: Bohnenwerk Logo-Sting

> Planned with motion-video-planner on 2026-10-20. Concept A: "Die Bohne rollt ins Wort", selected by the user's delegation (the planner decided). Timings are PLANNED; final timing follows the recorded voiceover (here: no voiceover, so the planned timings are final unless the render shows a problem).

## 0. Start here

Du bist der Produktions-Agent für ein vollständig geplantes Motion-Graphics-Video. Story, Text, Look und Timing sind entschieden. Setze sie treu um. Ändere etwas nur, wenn es technisch unmöglich ist oder wenn eine Prüfung aus Abschnitt 9 fehlschlägt, und protokolliere jede Abweichung mit Begründung in `PRODUCTION-LOG.md`.

**Arbeitsverzeichnis:** Lege das HyperFrames-Projekt unter `video/bohnenwerk-logo-sting/` an (relativ zum Verzeichnis, in dem du gestartet wirst). **Produkt-Repository:** keines. **Assets** stehen in Abschnitt 7; ihre Pfade sind relativ zum Projektverzeichnis.

**Blocker (bindend):** Das Café hat bisher nur einen Namen geliefert, kein Logo. Der finale Render darf erst entstehen, wenn der Nutzer eine Logo-Datei unter `assets/logo.svg` im Projekt abgelegt hat, oder wenn er ausdrücklich schriftlich den provisorischen Wortmarken-Stand (Abschnitt 4) freigibt. Bis dahin baust du die Komposition und erstellst höchstens einen Entwurf für die interne Prüfung. Stoppe und melde dem Nutzer den Blocker, statt eine Logo-Form zu erfinden.

**Berechtigungen und Grenzen**
- Erlaubt: `npx hyperframes …` ausführen; die npm-Pakete installieren, die HyperFrames und seine Skills brauchen; `ffmpeg`/`ffprobe` ausführen; Dateien im Projektverzeichnis anlegen; die Schriftdatei aus Abschnitt 7 herunterladen und ihre Lizenz ablegen.
- Nicht erlaubt ohne Rückfrage: Systemsoftware oder Container-Laufzeiten installieren, `render --docker`, bezahlte Generierung (Budget: 0 Euro), `publish`, Uploads, Deploys, Commits außerhalb des Projektverzeichnisses.
- Respektiere Berechtigungs-Prompts des Harness; umgehe keine Ablehnung.
- Kein Live-Abruf während des Renders: alle Medien müssen lokal vorliegen. Keine Fonts aus dem Netz zur Renderzeit.

**Schritt 0 — Umgebung prüfen (Ausgaben in PRODUCTION-LOG.md festhalten)**
1. `node --version`; `npx hyperframes --version`; `npx hyperframes doctor`.
2. Prüfe, ob die HyperFrames-Skills verfügbar sind (`/hyperframes` in deiner Skill-Liste). Falls nicht: `npx skills add heygen-com/hyperframes`, dem Nutzer sagen, dass ein Neustart der Session nötig ist, und dort stoppen.
3. `npx hyperframes usage --json`; Limits notieren.
4. `npx hyperframes render --help` und `npx hyperframes init --help`: die Flag-Namen prüfen (Qualitätsstufe, `--fps`, `--resolution`). Weicht ein Name ab, die gleichwertige Option der installierten Version nutzen und protokollieren.
5. Jedes Asset mit Status `exists` mit `ls` prüfen (aktuell keines). Die Schriftdatei `Montserrat-ExtraBold.ttf` (Google Fonts, OFL 1.1) einmalig nach `assets/fonts/` laden, `OFL.txt` daneben ablegen, dann mit `ls` prüfen.
6. Registry-Blöcke, Übergänge und Effekte in diesem Briefing mit `npx hyperframes catalog --query "<name>"` bzw. `npx hyperframes media-treatment --capabilities --json` prüfen. Diese Brief verwendet keine Blöcke; falls du doch einen einsetzt, prüfe ihn.

Wenn HyperFrames gar nicht läuft, stoppe und melde es. Baue keine eigene Render-Engine.

**Schritt 1 — Scaffold und Briefing**
1. `npx hyperframes init video/bohnenwerk-logo-sting --resolution portrait` (ergänze `--skill=motion-graphics`, falls die CLI das unterstützt).
2. Schreibe Anhang A wortgetreu nach `video/bohnenwerk-logo-sting/BRIEF.md` und Anhang C wortgetreu nach `video/bohnenwerk-logo-sting/frame.md`. Kopiere diese Datei selbst nach `video/bohnenwerk-logo-sting/production-prompt.md`, weil BRIEF.md darauf verweist.
3. Rufe `/hyperframes` auf. Es findet `BRIEF.md` und führt den Workflow `motion-graphics` ohne Briefing-Fragen aus. **Dieses Briefing ist vom Nutzer bestätigt:** führe kein Intent-Interview und keine Pitch-Runde durch. Stelle höchstens die eine Rückfrage, die der Workflow ohnehin vorsieht, und nutze dafür die Vorgabe „Entwurf für interne Prüfung, kein finaler Render vor Logo-Freigabe“.
4. Wenn der Workflow `STORYBOARD.md` schreibt, übernimm Abschnitt 5 Szene für Szene (Text wortgetreu, geplante Zeiten, Szenenzweck).

**Schritt 2 — In Durchgängen bauen (Gates in Abschnitt 9)**
Story und grobes Timing (Blockier-Durchgang mit Platzhalterformen in den Endpositionen) → Detail (Wortmarke, Bohne, Ease) → technische Gates → Frame-Prüfung → Entwurfs-Render → Prüfung → finaler Render (erst nach Logo-Freigabe, siehe Blocker).

**Render-Freigabe:** Der Workflow fragt nach jedem Entwurf „render now, or what changes?“. Diese Frage darfst du stellen; unterdrücke sie nicht.

## 1. Goal and context

- **Produkt / Thema:** Das Café „Bohnenwerk“ (Name vom Nutzer genannt). Sonst keine Fakten: keine Öffnungszeiten, kein Angebot, keine Lage, keine Geschichte im Video. (Evidenz: Anhang B #1–#2)
- **Zielgruppe:** Lokale Café-Gäste. Annahme, nicht verifiziert.
- **Kernbotschaft (ein Satz):** Der Name „Bohnenwerk“ bleibt im Gedächtnis. (Evidenz: Anhang B #1)
- **Beabsichtigte Wirkung:** Der Zuschauer erkennt den Namen beim Lockup und behält ihn; ohne Ton lesbar.
- **Zielpriorität:** Reichweite zuerst, Markenerinnerung danach. Keine Conversion.
- **Share-Trigger:** keiner stark; eine Logo-Animation ist ein Erinnerungsstück. Es wird kein Reichweiten-Versprechen gemacht. **Rewatch-Trigger:** die Bohne wird im Lockup zum „o“; das zeigt sich erst, wenn man die Ausgangsszene kennt.
- **CTA:** keiner (nur die Marke am Ende).
- **Grenzen:** keine Aussagen über Produkte, Preise, Öffnungszeiten, Auszeichnungen, Bewertungen oder Herkunft. Keine erfundenen Logo-Elemente und keine Markenfarben, die der Nutzer nicht bestätigt hat.

## 2. Story

- **Hook (0–2.0 s):** Erstes Bild: warmer Papierhintergrund, links außerhalb des Bildes eine dunkle Bohne. Erste Aktion ab Frame 0: die Bohne rollt von links ins Bild. Keine Blende aus Schwarz, kein Titel. Die Situation (ein Objekt rollt und stoppt) ist nach etwa 1 s klar.
- **Visueller Faden:** Die Bohne ist das wiederkehrende Element. Sie wird eingeführt (Szene 1), wird zum „o“ (Szene 2) und bleibt im Endbild als Teil des Lockups.
- **Entwicklung:** Die Bohne stoppt in der Mitte und wackelt einmal; an der Stelle erscheint der Umriss einer Buchstabenöffnung. Dann wird die Bohne zum „o“, und die übrigen Buchstaben schieben sich nacheinander von außen ein, jeder von dem vorherigen angestoßen.
- **Höhepunkt:** Das Wort BOHNENWERK ist vollständig, mit einem kurzen Überschwingen beim Einrasten.
- **Auflösung:** Das Wort steht still; die Bohne ist als „o“ lesbar.
- **Abschluss:** Endbild: Lockup auf Papier, zentriert; danach ein ruhiges Atmen (Idle 1–2 %) bis zum Ende.
- **Ton:** ruhig, warm, ohne Gag. Vermeide Hektik, Glitzer und jede Andeutung von Qualitätsversprechen.

## 3. Format

- Duration (planned): 6.0 s (tolerance ±0.5 s)
- Resolution / aspect: 1080×1920 (9:16)
- Frame rate: 30 fps
- Delivery: MP4 H.264, ohne Tonspur (kein Audio-Stream)
- Variants: keine (9:16-Master). Keine Quadrat- oder Querversion in diesem Auftrag.
- Safe areas: oben 270 px, unten 380 px, seitlich 64 px. Text und Bohne bleiben im Bereich zwischen diesen Grenzen.
- Sound-off: ja, ohne Ton lesbar. Es gibt keinen Ton.

## 4. Look

- **Brand source of truth:** Keine. Es liegt kein Logo, keine Markenfarbe und keine Schrift vor. Alles hier ist PROVISORISCH. Sobald `assets/logo.svg` und die Markenfarben vorliegen, werden Wortmarke und Farben ersetzt; die Bewegung bleibt.
- **Stil:** Bauhaus (Bewegungslogik: ein Kreis rollt, Buchstaben gleiten). Dominant, kein Akzentstil.
- **Regeln:**
  1. Nur flache Flächen, keine Verläufe, keine Schatten außer einem Kontaktschatten unter der Bohne (2 px Versatz, 0 % Unschärfe).
  2. Die Bohne ist eine Ellipse, 240 × 160 px; ihre Furche (Mittellinie) ist 6 px breit, Farbe Akzent.
  3. Die Bohne rollt ohne Gleiten: Rotation in Grad = zurückgelegte Strecke in px / 120 × 57.3 (Radius 120 px).
  4. Buchstaben gleiten horizontal, ohne Bounce; nur das fertige Wort überschwingt einmal (Schritt 3.2–3.8 s).
  5. Keine dritte Farbe. Keine Zusatzformen außer Bohne und Umriss.
- **Palette:** Grund `#F4EFE6` (Papier); Tinte `#2B1D14` (Wortmarke, Bohne); Akzent `#B5542D` nur auf der Furche der Bohne.
- **Typografie:** Montserrat ExtraBold (Schriftdatei lokal, siehe Abschnitt 7). Wortmarke BOHNENWERK: Größe 120 px, Zeilenhöhe 1.0, Laufweite 0.04 em, Versalien. Kein weiterer Text im Video.
- **Layout:** Wortmarke zentriert, vertikal zentriert (Mitte y = 960 px), horizontal zentriert; Bohne in Szene 1 auf der Mittellinie y = 960 px. Zwei Tiefenebenen: Grund, Objekt. Kein Parallax.
- **Kontrast:** Tinte `#2B1D14` auf `#F4EFE6` erfüllt WCAG AA deutlich.
- **Logo und Produktdarstellung:** Kein Logo vorhanden. Falls `assets/logo.svg` später eintrifft, ersetzt es die Wortmarke vollständig; das Logo wird nicht nachgezeichnet, verzerrt oder neu gesetzt. Mindestbreite 320 px.
- **Bewegungscharakter:** Rollen: `sine.inOut`, 1.0 s. Buchstaben: `power2.out`, 0.35 s, Versatz 0.08 s pro Buchstabe. Einrasten: `back.out(1.4)`, 0.3 s, nur auf der fertigen Wortmarke. Idle: Skalierung 1.00 → 1.015 → 1.00, `sine.inOut`, 1.5 s, ab 4.5 s bis Ende.
- **Übergänge:** keine (durchgehende Timeline, keine Szenenübergänge).
- **Negativliste:** keine Verläufe, keine Stockfotos, keine Lens-Flares, keine Blende aus Schwarz am Anfang, keine dritte Farbe, keine erfundene UI, kein Glitzer, kein Schatten-Overkill, keine Wortmarke außer BOHNENWERK.

## 5. Timeline

Alle Zeiten sind PLANNED. Es gibt keine Sprachspur; die Zeiten bleiben, sofern der Entwurf sie nicht als unlesbar zeigt.

| # | Start | End | Purpose | Voiceover (exact) | On-screen text (exact) |
|---|---|---|---|---|---|
| 1 | 0.0 | 2.0 | Hook: Bohne rollt ein und stoppt | — | — |
| 2 | 2.0 | 3.2 | Bohne wird zum „o“, Buchstaben schieben sich ein | — | BOHNENWERK |
| 3 | 3.2 | 4.5 | Einrasten des Wortes | — | BOHNENWERK |
| 4 | 4.5 | 6.0 | Ruhiges Endbild mit Idle | — | BOHNENWERK |

### Scene 1 (0.0–2.0 s): Bohne rollt ein und stoppt
- Composition: Grund `#F4EFE6` (ganzer Frame); Bohne (Ellipse 240 × 160 px, Füllung `#2B1D14`, Furche `#B5542D` 6 px) auf y = 960 px, Start x = −200 px, Ende x = 540 px (Bildmitte); Kontaktschatten unter der Bohne.
- Assets: code-drawn (`bohne`, siehe Abschnitt 7).
- Action: 0.0–1.0 s Bohne rollt von x = −200 nach x = 540 und dreht sich dabei (Regel 3). 1.0–1.3 s stoppt in der Mitte, wackelt einmal (±6°). 1.3–2.0 s erscheint der Umriss einer Buchstabenöffnung (Kontur `#2B1D14`, 3 px) an der Stelle, an der die Bohne später zum „o“ wird; die Bohne bleibt ruhig.
- Camera: statisch.
- Motion/easing: x: −200 → 540, 1.0 s, `sine.inOut`; rotation: 0 → 353° (Strecke 740 px / 120 × 57.3, Regel 3); wackeln: rotation ±6°, 0.3 s, `sine.inOut`; Umriss: opacity 0 → 1, 0.7 s, `power2.out`.
- Transition out: keine; die nächste Szene beginnt bei 2.0 s, ausgelöst durch den Umriss-Abschluss.
- Audio cues: keine (kein Ton).

### Scene 2 (2.0–3.2 s): Bohne wird zum „o“, Buchstaben schieben sich ein
- Composition: Wortmarke BOHNENWERK (Montserrat ExtraBold, 120 px, Tinte `#2B1D14`), mittig auf y = 960 px. Position 3 der Wortmarke (das „o“ in B-O-H-N-E-N-W-E-R-K, Index 2 ab 1 gezählt) ist der Ort der Bohne: Die Bohne schrumpft auf etwa ein Drittel (Skalierung 1.0 → 0.33) und liegt auf dem „o“; das „o“-Glyph blendet im selben Moment ein, die Bohne überblendet in das Glyph.
- Assets: Schriftdatei `assets/fonts/Montserrat-ExtraBold.ttf` (lokal); Bohne (code).
- Action: 2.0–2.3 s Bohne schrumpft auf Drittelgröße und setzt sich auf die Position des „o“; gleichzeitig blendet das „o“-Glyph ein (0.3 s). 2.2–3.2 s die übrigen Buchstaben gleiten von außen ein, jeder 0.08 s nach dem vorherigen (B, H, N, E, N von links; W, E, R, K von rechts). Jeder Buchstabe wird durch die Bewegung seines Nachbarn angestoßen (Ursache-Wirkung).
- Camera: statisch.
- Motion/easing: Bohne → „o“: 2.0–2.3 s, `power2.out`; Buchstaben von links: x-Versatz −120 px → 0, 0.35 s, `power2.out`, Start 2.2 + 0.08·i s; Buchstaben von rechts analog, +120 px → 0.
- Transition out: keine (Szene 3 startet direkt).
- Audio cues: keine.

### Scene 3 (3.2–4.5 s): Einrasten des Wortes
- Composition: Wortmarke wie Szene 2, vollständig, mittig auf y = 960 px.
- Assets: wie Szene 2.
- Action: 3.2–3.5 s das komplette Wort überschwingt um 3 % in der Skalierung und kommt zurück (ein Einrasten); 3.5–4.5 s Stillstand.
- Camera: statisch.
- Motion/easing: Skalierung 1.0 → 1.03 → 1.0, 0.3 s, `back.out(1.4)`; danach kein Ease.
- Transition out: keine.
- Audio cues: keine.

### Scene 4 (4.5–6.0 s): Ruhiges Endbild mit Idle
- Composition: Lockup wie Szene 3; Kontaktschatten unter der Bohne (das „o“).
- Assets: wie Szene 2.
- Action: ab 4.5 s ruhiges Atmen: Wortmarke Skalierung 1.00 → 1.015 → 1.00 in 1.5 s, zweimal (Gesamt 3 s); das Endbild hält bis 6.0 s.
- Camera: statisch.
- Motion/easing: Skalierung 1.00 → 1.015 → 1.00, `sine.inOut`, 1.5 s, zweimal; ein fertiger Idle, keine Pause.
- Transition out: Ende des Videos.
- Audio cues: keine (kein Ton).

## 6. Audio

- **Voiceover:** nein.
- **Vollständiges Voiceover-Skript:** keines.
- **Aussprache:** nicht relevant.
- **Musik:** keine.
- **Soundeffekte:** keine.
- **Klangmotiv (wiederkehrendes Element):** keines in dieser Version.
- **Untertitel:** nein. Der Name steht im Bild.
- **Stille:** no audio at all. Die Datei enthält keine Tonspur.

## 7. Assets

Basispfad: `video/bohnenwerk-logo-sting/` (Projektverzeichnis)

| Path | Status | Use | Notes |
|---|---|---|---|
| `code: bohne` | create | Wiederkehrendes Element, Szenen 1–4 | Ellipse 240 × 160 px (siehe Regel 2), Füllung `#2B1D14`, Furche 6 px `#B5542D` vertikal mittig, Kontur 3 px `#2B1D14` für den Umriss; als SVG im Projekt (`assets/bohne.svg`), in der Komposition inline |
| `code: wortmarke-provisorisch` | create | Wortmarke BOHNENWERK, Szenen 2–4 | PROVISORISCH: Montserrat ExtraBold 120 px, Laufweite 0.04 em, Versalien, Farbe `#2B1D14`; wird durch `assets/logo.svg` ersetzt, sobald der Nutzer es liefert (siehe Blocker) |
| `assets/fonts/Montserrat-ExtraBold.ttf` | source | Schrift für Wortmarke | Quelle: Google Fonts (Montserrat, SIL Open Font License 1.1); Lizenz als `assets/fonts/OFL.txt` ablegen und in `SOURCES.md` vermerken; Download einmalig in Schritt 0 |

- **Budget für bezahlte Generierung:** 0 Euro. Es wird nichts generiert.
- **Schriften:** Montserrat ExtraBold, als Datei im Projekt; kein Google-Fonts-Link zur Renderzeit. Keine Ersatzschrift ohne Rückfrage.
- **Erstellungsauftrag für `bohne`:** Ellipse, Breite 240 px, Höhe 160 px, Mittelpunkt (0, 0) im lokalen Koordinatensystem; Furche als vertikale Linie 6 px breit in `#B5542D`, von oben bis unten, bei x = 0; Füllung `#2B1D14`; Kontaktschatten als Ellipse 240×40 px, Füllung `#2B1D14`, Deckkraft 0.15, unter der Bohne bei y +100 px, ohne Unschärfe. Keine Verläufe.
- **Erstellungsauftrag für `wortmarke-provisorisch`:** Text „BOHNENWERK“ mit Montserrat ExtraBold, 120 px, Laufweite 0.04 em, Zeilenhöhe 1.0, Farbe `#2B1D14`, zentriert auf (540, 960). Buchstabenpositionen einmalig aus dem Font-Advance ermitteln und als feste Werte im Code eintragen; kein Layout zur Laufzeit.

## 8. Technical execution

- **Workflow:** `/motion-graphics`, weil das Stück kurz, unnarriert und bewegungsgetrieben ist (Logo-Sting, 6 s). `flow: automation`, `storyboard: no` (autonom; die internen Prüfungen aus Abschnitt 9 gelten trotzdem).
- **Skills bei Bedarf:** `/hyperframes-core` (Komposition-Vertrag), `/hyperframes-animation` (Ease-Referenz), `/hyperframes-cli` (Befehle). Kein `/media-use`, kein `/hyperframes-audio`, kein `/hyperframes-keyframes` (Kamera ist statisch).
- **Animationsansatz:** GSAP paused timeline, registriert auf `window.__timelines`. Keine Zufallswerte (kein PRNG nötig). Kein `fetch`, keine Live-Daten.
- **Kandidaten für Blöcke und Effekte (in Schritt 0 prüfen):** keine. Alles wird von Hand mit SVG und GSAP gebaut.
- **Medienintegration:** keine Videos, keine Bilder; nur die Schriftdatei aus Abschnitt 7.
- **Ausgabe:** `npx hyperframes render --help` zuerst; dann einen Entwurf `renders/bohnenwerk-logo-sting-draft.mp4`; der finale Render `renders/bohnenwerk-logo-sting-v1-9x16.mp4` erst nach der Logo-Freigabe (siehe Blocker in Abschnitt 0). Die Flags aus dem Hilfetext verwenden.

## 9. Quality and delivery

**Reihenfolge der Arbeit und Gates**
1. **Story-Durchgang:** Szenen als Platzhalterformen in den Endpositionen bauen. `npx hyperframes snapshot` an jeder Szenenmitte. Prüfen: die Situation (Bohne rollt, stoppt) ist nach etwa 1 s klar; jede Szene hat eine Aktion und eine Folge.
2. **Detail-Durchgang:** Bohne, Wortmarke, Ease, Idle.
3. **Technische Gates:** `npx hyperframes lint` und `npx hyperframes check` ohne Fehler. Warnungen zu Textverdeckung und Kontrast beheben.
4. **Frame-Prüfung:** erster Frame, Szenenmitte jeder Szene, letzter Frame; mit Abschnitt 5 vergleichen.
5. **Entwurfs-Render prüfen:** das ganze Video ansehen. Die Prüfung gilt nur, wenn sie mit Ton gemacht wird; hier ist kein Ton vorgesehen, also reicht eine Sichtprüfung ohne Ton, und das wird im Log vermerkt.
6. **Finaler Render** (nur nach Logo-Freigabe), dann die Datei prüfen (Schritt 8).

**Abnahmekriterien (alle müssen bestehen)**
- Der erste Frame ist der Hook aus Abschnitt 2: Bohne im Bild, rollend, kein Schwarz, kein Titel.
- Die Situation ist ohne Ton nach etwa 3 s verständlich.
- Das Wort BOHNENWERK ist vollständig lesbar, innerhalb der Safe-Areas (oben 270 px, unten 380 px, seitlich 64 px), nicht verdeckt, AA-Kontrast.
- Keine Szene ist ein Diapositiv: jede hat die Aktion und die Folge aus Abschnitt 5.
- Die Bohne erscheint als wiederkehrendes Element (Einführung, „o“, Endbild).
- Logo, Farben und Schrift entsprechen Abschnitt 4. Keine erfundene UI, keine Aussagen über das Café.
- Dauer 6.0 s ±0.5 s; Auflösung 1080×1920; 30 fps; MP4 H.264; keine Tonspur (`ffprobe`).

**Priorität bei Fehlern:** Hook → Entwicklung → Auflösung → Markenwirkung. Den höchsten fehlerhaften Punkt zuerst beheben.

**Iterationsbudget und Stoppkriterien**
- Höchstens 2 volle Prüfzyklen (Schritte 4–5) und 3 Entwurfs-Renders; ein finaler Render (+1 Neurender, falls eine Lieferprüfung scheitert).
- Eine Änderung pro Korrektur; absolute Werte nennen („Wortmarke 120 px“), keine relativen Schübe.
- Stoppen und melden, statt weiterzulaufen, wenn: das Budget aufgebraucht ist; derselbe Fehler nach zwei Korrekturen bleibt; eine Korrektur eine Entscheidung außerhalb dieses Briefings braucht (neue Aussage, bezahlter Asset, geänderte Story); oder das Logo fehlt und der finale Render verlangt wird.

**Abgaben in `video/bohnenwerk-logo-sting/`**
- `renders/bohnenwerk-logo-sting-v1-9x16.mp4` (final, erst nach Logo-Freigabe), `renders/bohnenwerk-logo-sting-draft.mp4` (Entwurf)
- das bearbeitbare HyperFrames-Projekt (Quellen, `BRIEF.md`, `frame.md`, `STORYBOARD.md`, Assets, `production-prompt.md`)
- `SOURCES.md`: Anhang B, Schriftlizenz, Gestaltungsdokumente
- `PRODUCTION-LOG.md`: Umgebungsversionen, geprüfte oder ersetzte Namen, jede Abweichung mit Begründung, ausgeführte Befehle mit Ergebnis (lint, check, snapshot-Liste, ffprobe-Ausgabe), Prüfbefunde je Zyklus, bekannte Grenzen
- Keine Prüfung behaupten, die nicht gelaufen ist. Nicht Geprüftes unter „Not verified“ listen.

## Appendix A: BRIEF.md

```markdown
---
workflow: motion-graphics
flow: automation
storyboard: no
message: "Der Name Bohnenwerk bleibt im Gedächtnis."
destination: instagram-reels
aspect: 1080x1920
language: de
audience: "Lokale Café-Gäste (Annahme, nicht verifiziert)"
length: 6s
narration: no
---

## Intent

Logo-Sting für das Café Bohnenwerk, 6 s, 9:16, ohne Ton. Eine Bohne rollt ein, wird zum „o“ im Namen BOHNENWERK und das Wort rastet ein. Das Briefing ist bestätigt; baue es aus production-prompt.md (Abschnitte 1–9), das in den Projektordner kopiert wurde.

## Assets

- `assets/fonts/Montserrat-ExtraBold.ttf` — Schrift für die provisorische Wortmarke (OFL 1.1)
- `assets/logo.svg` — fehlt; wird vom Nutzer nachgeliefert; bis dahin kein finaler Render

## Customizations

- Bohne als gezeichnete SVG-Ellipse mit Furche, Umriss-Übergang zum „o“ über Glyphenkontur (siehe Abschnitt 7).
- Keine Videos, keine Bilder, keine Tonspur.

## Notes

- Confirmed brief; do not re-interview.
- Keine Aussagen über das Café außer dem Namen. Keine erfundenen Logo-Elemente, Farben oder Schriften außer den in Abschnitt 4 als PROVISORISCH markierten.
- Kein finaler Render vor Logo-Freigabe.
```

## Appendix B: Sources

| # | Claim or fact used in the video | Evidence |
|---|---|---|
| 1 | Das Café heißt „Bohnenwerk“ | stated by user on 2026-10-20 |
| 2 | Keine weiteren Aussagen über das Café (Angebot, Öffnungszeiten, Lage, Geschichte) im Video | Designregel des Briefings, kein Fakt; keine Quelle nötig, weil nichts behauptet wird |
| 3 | Die Bohne als Motiv | Ableitung aus dem Namen; Gestaltungsentscheidung, keine Markeneigenschaft des Cafés (nicht verifiziert) |

## Appendix C: frame.md

```markdown
---
name: Bohnenwerk — Logo-Sting (provisorisch)
description: Bauhaus-Logo-Sting auf Papier, eine Bohne wird zum Buchstaben im Namen; provisorisch bis Logo-Freigabe.
colors:
  ground: "#F4EFE6"
  ink: "#2B1D14"
  accent: "#B5542D"
typography:
  display: { fontFamily: "Montserrat", px: 120, weight: 800, lineHeight: 1.0, tracking: "0.04em" }
  body: { fontFamily: "Montserrat", px: 48, weight: 600, lineHeight: 1.2 }
  label: { fontFamily: "Montserrat", px: 32, weight: 600, tracking: "0.08em", upper: true }
---

## Overview
Ein Logo-Sting im Bauhaus-Stil: flache Flächen, eine Bohne als wiederkehrendes Element, Versalien-Wortmarke. Alle Werte sind provisorisch, bis der Nutzer das echte Logo und die Markenfarben liefert.

## Do's and Don'ts
- Do: Bohne rollt ohne Gleiten; Buchstaben gleiten ohne Bounce; nur das fertige Wort überschwingt einmal.
- Don't: keine Verläufe, keine dritte Farbe, keine Schatten außer dem Kontaktschatten, keine Aussagen über das Café.
```

## Hinweise zur Abnahme

- Das Briefing ist vollständig; die Zeiten sind PLANNED und folgen der Umsetzung nur, wenn ein Entwurf sie als unlesbar zeigt.
