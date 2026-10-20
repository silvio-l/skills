# Konzepte: WhisPaste Social-Video (9:16, 15–30 s, DE-Master + EN-Schnitt)

Grundlage: `context.md`, `decisions.md`. Kernbotschaft (Q2, frei): „Ich schreibe den Satz, ohne aus dem Fenster zu gehen. Der Cursor bleibt der Held." Keine Zahlen, keine Roadmap-Features, keine Changelog-„Unreleased"-Funktionen als aktuell.

Gemeinsame Regeln für alle drei Konzepte:
- Sicherheitszonen 9:16: oben ~14 % und unten ~20 % frei von Text und Gesicht.
- Sound-off-sicher: jeder Hook funktioniert nur mit Text und Bewegung.
- Logo nur im Abspann, als SVG aus `assets/icons/logo-dark.svg` bzw. `logo-light.svg`.
- Marke: Hanken Grotesk (Fließtext) und Bricolage Grotesque (Display), Navy/Glacier/Amber aus `design-tokens/`. Kein Glas, kein Glow (Zielgruppen-Dokument).
- Wort „Spende" und Entsprechungen sind verboten (Brand-Glossar).

---

### Konzept A: „Schon wieder dieser Satz"

**In one sentence:** Eine Person beantwortet die dritte gleiche Nachricht des Tages, tippt, korrigiert, verliert den Faden, drückt den Hotkey und der Satz steht im Feld, bevor sie den Atem holt.

**First seconds (0–3 s), concretely**
- Picture: Hochkant-Ansicht eines generischen Chat-Feldes (kein echtes Produkt, kein Markenlogo einer Chat-App), darin halb getippt: „Hi, danke für d", Cursor blinkt, rechts oben ein Zähler „Antworten heute: 37".
- Text: „Antworten heute: 37" (Zähler läuft hoch).
- Motion: Die Tasten-Schläge sind als Ticks sichtbar; die Zeile wird gelöscht und neu getippt (Rückschritt als Gag).
- Sound: Tastatur-Klicks, dann ein Schlag bei „37".
- Hook mechanism: everyday relevance („that's so us").

**The story** (ca. 20 s):
1. (0–3 s) Chat-Feld, Zähler 37. Acts: Finger tippen. Reacts: Zähler springt.
2. (3–7 s) Tippen geht schief: Autokorrektur verschluckt ein Wort, Zeile wird gelöscht, neu getippt. Escalation: Benachrichtigung schiebt sich ins Bild, drängt das Feld zur Seite.
3. (7–10 s) Pause (0,8 s Stille) vor dem Griff zur Tastatur. Text: „Dann eben anders."
4. (10–13 s) Hotkey-Keycap im Bild (`Ctrl+Shift+D` als Platzhalter, auf Mac-Variante ⌃⇧D je nach Fassung). Acts: Taste gedrückt. Overlay-Wellenform erscheint am unteren Rand, live.
5. (13–17 s) Gesprochener Satz als Untertitel-Zeile, Wort für Wort; Text erscheint in dem Chat-Feld, an der Cursor-Position, im Takt der Worte.
6. (17–20 s) Zähler steht bei 38. Der Chat sendet, Hand lehnt sich zurück. Text: „Sprich, wo du sonst tippst."
7. (20–22 s) Abspann: Logo-SVG + Wortmarke + „whispaste.de". Kein Hard-Sell.

**Open question that keeps people watching:** Wird der Zähler je unter 37 kommen (läuft nur hoch) und wann wird der Satz tatsächlich geschrieben? Antwort: Bei 13–17 s.

**Share trigger:** „that's so us": wer täglich viele Antworten schreibt, schickt es an die Kollegin im Support-Team mit „Das sind wir".

**Rewatch trigger:** Die Autokorrektur-Panne in Sekunde 4–5 (Wort falsch korrigiert) wird beim zweiten Mal als Rahmen für den Zähler erkannt; der Zählerstand im letzten Bild ist 38 statt 37 (erstes Ansehen: man sieht nur „steigt").

**Product / audience link:** Diktat in beliebige Textfelder (verifiziert: README, store copy „Works in … chat apps"); Zielgruppe „Vielschreibende Wissensarbeiter" (`docs/zielgruppe.md`).
**Recognition:** Visuelle Signatur: flache Schrift-Kinetik in Hanken/Bricolage, Navy-Hintergrund, Amber für den Zähler. Wiederkehrendes Element: die Wellenform des Overlays (erscheint in Sekunde 10–13 und schließt den Abspann).

**Style:** Kinetic Typography (dominant), adapted to the brand: Schrift-Gewichte 700–900 nur für Zähler und Schlüsselwort; Wellenform ist Teil der Typografie, kein Partikel-Effekt. Accent: keiner.
**Duration / format:** 20–22 s, 9:16.
**Effort:** S–M (Typewriter-Effekt und Zähler in GSAP; Wellenform-Animation als Canvas oder SVG-Balken, M).
**Asset needs:** exists: `assets/icons/logo-dark.svg`, `assets/icons/wordmark-dark.png` (4x), Tokens aus `design-tokens/primitives.tokens.json`. to create: generischer Chat-Frame (code-drawn), Wellenform-Komponente. paid: none.
**Main risks:** Die Zeile „Antworten heute: 37" ist eine fiktive Zahl; sie darf nur als Gag stehen und muss im Video als Szenen-Zahl ohne Produktbezug wirken, sonst ist es eine erfundene Metrik (Hard Rule). Der Chat-Frame darf nicht wie eine echte Chat-App aussehen (Markenrechte). Zu viel Text bei Schnelltippen (Lesezeit).

---

### Konzept B: „Das Fenster bleibt, wo es ist"

**In one sentence:** Ein Fenster (Mail-Entwurf auf dem Mac) ist offen; der Cursor steht im Textfeld; eine Hand drückt den Hotkey, spricht einen Satz, und der Text erscheint an genau dieser Stelle, während das Fenster unverändert bleibt; der Cursor wird zum Protagonisten, der nie den Ort wechselt.

**First seconds (0–3 s), concretely**
- Picture: Echte Aufnahme (Mac, Q4 = Ja, nur Overlay, Dock, Cursor, keine echten Verläufe). Frame 1: ein leerer Mail-Entwurf, groß, Cursor blinkt mittig. Rechts unten schwebt die Kontrollschaltfläche (Floating-Button) als Ruhe-Zustand.
- Text: „Ich wechsle nicht das Fenster." (erscheint in Sekunde 0,5–2,5)
- Motion: Cursor blinkt, der Titel „Ich wechsle nicht das Fenster." wird Wort für Wort von links gesetzt; das Mail-Fenster ist fix.
- Sound: Stille (0,8 s) → Hotkey-Klick.
- Hook mechanism: visual surprise (ein Text, der ohne Fensterwechsel entsteht; die Bildfläche bleibt still, während Text entsteht).

**The story** (ca. 20 s):
1. (0–3 s) Leeres Mail-Feld, Titel-Satz. Acts: Cursor. Reacts: nichts.
2. (3–6 s) Hotkey (Keycap im Dock-Button sichtbar). Acts: Overlay klappt unten ein, Wellenform reagiert auf die Stimme (echte Aufnahme).
3. (6–12 s) Gesprochener Satz: „Hallo Maria, danke für die schnelle Antwort, ich schaue heute Nachmittag drauf." Text erscheint am Cursor, Wort für Wort, im Rhythmus der Aufnahme.
4. (12–15 s) Overlay schließt, Cursor sitzt am Ende des Satzes. Acts: Kamera hält still, Ruhe-Zustand (Ambient-Atmung 1–2 %).
5. (15–18 s) Gegenfrage im Text: „Und wo ist der Fenster-Wechsel?" — Antwort: der Cursor blinkt weiter, nichts bewegt sich. Stillstand 0,8 s als Pointe.
6. (18–20 s) Abspann: Logo-SVG, „whispaste.de".

**Open question that keeps people watching:** Kommt der Text tatsächlich an der Cursor-Position an, wenn die App im Vordergrund bleibt? Antwort: Sekunde 6–12, im Bild.

**Share trigger:** „simple solution" („Warum wusste ich das nicht?"): wer Mails im Browser oder Mac-Mail tippt, schickt es an Kollegen mit „das gibt's?".

**Rewatch trigger:** Die Pointe (Sekunde 15–18) zeigt beim zweiten Mal, dass der Fenster-Titel im Hintergrund unverändert bleibt; beim ersten Mal wirkt es wie Stillstand.

**Product / audience link:** Auto-Paste in die aktive App und Overlay mit Live-Wellenform (verifiziert: README „Recording overlay with waveform"; store copy "without leaving your window" ist Q2-Formulierung, siehe `context.md`). Audience: Vielschreibende am eigenen Mac.
**Recognition:** Visuelle Signatur: Schrift im Hanken-Gewicht 500 für den Titel, Navy-Ruhezustand, Amber nur für den Dock-Hotkey. Wiederkehrendes Element: der Cursor (er blinkt vor und nach dem Satz, und in der Schluss-Einstellung).

**Style:** Swiss/Editorial (dominant): strenges Raster, Hairlines, ein Akzent (Amber) — passt zu „kein Glow, flach". Accent: keiner.
**Duration / format:** 18–20 s, 9:16 (Aufnahme hochkant, Mac-Fenster als Ausschnitt; Ränder zurechtgeschnitten).
**Effort:** S (Schnitt, Text-Masken, Zoom in GSAP) plus Aufnahme-Aufwand (M): Fenster-Ausschnitt aus Mac-Aufnahme, Ton einspielen (Kann im Prompt nicht gelöst werden; Aufnahme muss vorliegen).
**Asset needs:** exists: `assets/icons/logo-dark.svg`; Tokens. to create: echte Bildschirmaufnahme (Mac-App mit Demo-Text, nur Overlay/Dock/Cursor, kein echter Verlauf; Ton der Stimme separat aufnehmen oder echte Stimme). paid: none.
**Main risks:** Die Aufnahme muss vor der Produktion existieren; ohne sie fällt das Konzept auf eine Mock-Version zurück (Qualitätsverlust). Die Aussage „ohne Fensterwechsel" muss der tatsächlichen Auto-Paste-Funktion entsprechen und gilt nicht für alle Apps (ein Clipboard-Fallback ist möglich, siehe `CONTEXT.md` §2.4/§2.6). Es darf kein Windows-Element in der Mac-Aufnahme sein.

---

### Konzept C: „Die Wolke vor der Tür"

**In one sentence:** Eine Wolke mit Augen sitzt vor dem Schreibtisch und will mitschreiben; sie wird Stück für Stück ausgesperrt, bis nur noch der lokale Satz übrig bleibt — eine absurde Pointe auf den Satz „Deine Stimme bleibt auf deinem Rechner".

**First seconds (0–3 s), concretely**
- Picture: Ein Schreibtisch in einer flachen Draufsicht; eine stilisierte Wolke (Glacier-Farbe) mit zwei Augen hängt am Fensterrand und lauscht. Der Fensterrahmen ist Navy.
- Text: „Deine Stimme. Dein Rechner." (in den ersten 2 Sekunden)
- Motion: Die Wolke wippt (Ohren-Antwort), dann kippt sie zur Seite zum Schreibtisch.
- Sound: Ein Klick (Ohr-Hinweis) gefolgt von einem leisen Schlag beim Schließen.
- Hook mechanism: surprising claim (Evidenz: Store-Text „Your audio stays on your Mac", `NETWORK.md`: lokale Erkennung; Cloud nur opt-in mit eigenem Schlüssel; Telemetrie ist anonym und enthält kein Audio — **Die Aussage darf nicht "keine Daten" lauten.**)

**The story** (ca. 22–25 s):
1. (0–3 s) Wolke sitzt am Fensterrand. Acts: lauscht. Reacts: Zucken bei Klick.
2. (3–7 s) Wolke klebt sich an die Schreibtischkante, neugierig. Acts: will mit. Reacts: Hotkey-Klick schiebt sie ein Stück zurück.
3. (7–12 s) Escalation: „Cloud-Transkription" als Schild (Bild: OpenAI/Deepgram-Logo verboten) — stattdessen eine Tür mit Schild „Optional, mit eigenem Schlüssel". Die Tür bleibt zu, solange der Schalter auf „lokal" steht.
4. (12–18 s) Die Wolke bekommt keine Worte; der Satz entsteht auf dem Schreibtisch (lokale Erkennung, Overlay-Wellenform).
5. (18–22 s) Pointe: Die Wolke schaut auf die Uhr und geht; Text: „Lokal ist der Standard." mit Fußnote: „Optionale Cloud-Anbieter sind abschaltbar."
6. (22–25 s) Abspann: Logo, whispaste.de.

**Open question that keeps people watching:** Kommt die Wolke rein? Antwort: nie, in Sekunde 22.

**Share trigger:** „that's so us" für Datenschutz-Skeptiker („meine Stimme gehört mir"): sie schicken es an die Person, die bei jeder Cloud-App fragt, wo die Daten bleiben.

**Rewatch trigger:** Im Hintergrund am Fenster steht ein Schild („Telemetrie: aus") — beim zweiten Mal sichtbar; die Fußnote ist die Pointe.

**Product / audience link:** Lokale Erkennung als Default (verifiziert: store copy, README „Offline by default"); Cloud optional (verifiziert: store copy, `lib/core/config/settings_enums.dart` Provider-Enum). Zielgruppe: Datenschutzbewusste Vielschreibende (Zielgruppen-Dokument: „Datenschutzrechtlich heikel" als Problem).
**Recognition:** Visuelle Signatur: flache Glacier-Formen mit Navy-Rahmen; Wolke als Figur. Wiederkehrendes Element: die Wolke (Ohren-Wippen als Motiv, am Ende fehlt sie).

**Style:** Neo-Brutalism (dominant, Akzent-only): harte Schatten-Offsets 6–8 px, dicke Umrisse 4 px, aber auf Brand-Palette abgebildet (Navy, Glacier, Amber). Akzent: keiner. Risiko: der Stil ist für ruhige Marken eher fremd (siehe unten).
**Duration / format:** 22–25 s, 9:16.
**Effort:** S–M (CSS/GSAP; Wolke als SVG, Schalter als SVG).
**Asset needs:** exists: `assets/icons/logo-dark.svg`; Tokens. to create: Wolken-Figur als SVG (code-drawn, keine Fremdgrafik), Schild- und Tür-Grafik. paid: none.
**Main risks:** (1) Die Aussage „deine Stimme bleibt auf deinem Rechner" ist nur mit lokaler Erkennung wahr; das Video muss die Bedingung zeigen (Fußnote), sonst ist es eine unhaltbare Behauptung. (2) Telemetrie ist standardmäßig an (opt-out); das Video darf „keine Daten" nicht behaupten. (3) Neo-Brutalism passt nicht gut zur ruhigen, flachen Markenstimme (`docs/zielgruppe.md`: „Kein Glas, kein Glow", ruhige Oberfläche) — das ist die Bold-Option mit benannter Gefahr.

---

## Vergleich (qualitativ, ohne Scores)

| Kriterium | A „Schon wieder dieser Satz" | B „Das Fenster bleibt" | C „Die Wolke vor der Tür" |
|---|---|---|---|
| Opening (zweite Sekunde packt? Situation klar bei ~3 s?) | Stark: Zähler und Tippfehler sind sofort verständlich. | Mittel: der Titelsatz braucht einen Moment, bis man den Fenster-Kontext versteht. | Stark im Bild, schwächer im Verständnis, ob Lokal-Versprechen gemeint ist. |
| Klarheit (Botschaft beim ersten Sound-off-Ansehen?) | Gut: Hotkey und Satz sind klar, aber der Lokal-Aspekt fehlt. | Gut: der Ablauf (Cursor bleibt, Text kommt) ist vollständig sichtbar. | Mittel: die Pointe erklärt sich nur mit Fußnote. |
| Entwicklung (Escalation, Ursache/Wirkung, keine Folie?) | Gut: Tippfehler → Hotkey → Ergebnis ist eine Kausalkette. | Mittel: ruhiger, mit einem Pausen-Gag; wenig Escalation. | Gut: die Wolke wird Schritt für Schritt ausgesperrt. |
| Überraschung (wo, und verdient?) | Mittel: die Zählerpointe ist Gag, kein Produkt-Beleg. | Stark, aber nur mit der echten Aufnahme verdient. | Stark: die Wolke ist überraschend; der Claim muss wahr bleiben. |
| Auflösung (zahlt das Hook ein? Pointe stark?) | Gut: der Satz steht im Feld, der Zähler sagt „38". | Mittel: die Pointe ist leise. | Gut, wenn die Fußnote sitzt; schwach, wenn sie fehlt. |
| Markenwirkung (Wiedererkennung, wiederkehrendes Element, Markenpassung) | Gut: Wellenform als Motiv, Schrift-Kinetik passt zur Typografie. | Sehr gut: Cursor und echte Oberfläche zeigen das Produkt. | Mittel: Neo-Brutalism passt nicht ideal zur ruhigen Marke. |
| Produktionsrisiko und Aufwand | S–M, keine Abhängigkeit von Aufnahmen. | S + Aufnahme-Abhängigkeit (Mac-Aufnahme muss vorher existieren). | S–M, Claim-Prüfung ist aufwendig (Fußnote, Telemetrie-Wortlaut). |

---

## Empfehlung und Frage

**Empfehlung: Konzept A.** Die stärkste Teilen-Auslösung (wer täglich viel tippt, schickt es an die Kollegin) trifft das Hauptziel Reichweite direkt, und die Kausalkette Tippfehler → Hotkey → Text ist in sekundenschnelle verständlich, ohne Zahl oder Versprechen. Was A dafür aufgibt: Die Privatsphäre-Botschaft bleibt außen vor, und der Zähler-Gag ist eine fiktive Zahl, die sauber als Szenen-Zahl ohne Produktbezug markiert werden muss.

Question 5/10 — Which concept should I turn into the production prompt?
a) Concept A: „Schon wieder dieser Satz" (recommended)
b) Concept B: „Das Fenster bleibt, wo es ist"
c) Concept C: „Die Wolke vor der Tür"
d) Mix: tell me which parts
Or answer freely.

**SIMULATED answer (Frage 5/10):** b) — "Konzept B, weil die Mac-Aufnahme aus Frage 4 ohnehin entsteht und 'der Cursor wechselt das Fenster nicht' die Aussage ist, die wir mit echten Bildern belegen können, ohne fiktive Zähler oder Wolken."

Auswahl-Begründung (ein Satz, wie gefordert): Konzept B, weil die echte Aufnahme aus Q4 die Aussage „ohne Fensterwechsel" belegt, statt sie mit einem Mock zu behaupten.
