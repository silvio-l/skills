# ADR-0002 — `apple-notes` AppleScript-Heredocs extrahieren

- **Status**: accepted
- **Outcome**: rollout
- **Datum**: 2026-05-20
- **Kontext-Issue**: `.scratch/architecture-deepenings/issues/08-apple-notes-applescript-spike.md`
- **Folge-Issue**: `.scratch/architecture-deepenings/issues/09-apple-notes-applescript-rollout.md` — wird mit Roll-out-Vorgabe aus diesem ADR geöffnet

## Kontext

Der `apple-notes` Dispatcher (`scripts/apple-notes`, vor dem Spike 1113 Zeilen) bündelt 14 AppleScript-Snippets als inline bash-Heredocs. Heredocs sind nicht in eigene Editor-Syntax-Highlighting-Modi zu bringen, lassen sich nicht isoliert reviewen, und teilen keinen gemeinsamen Editor-Kontext. Track B4 fragt: lohnt sich die Extraktion in `applescripts/*.applescript`-Dateien?

Spike-Scope laut PRD: zwei repräsentative Heredocs extrahieren, messen, entscheiden.

## Spike-Durchführung

**Zwei Heredocs extrahiert** (jeweils mit `osascript file.applescript "$@"` aufgerufen, reines Argv-Passthrough):

- `applescripts/get_note.applescript` (von `cmd_get`, vorher Zeile 549–563) — read-only, single-note lookup.
- `applescripts/create_note.applescript` (von `cmd_create`, vorher Zeile 758–776) — write path, `<div>`-wrap + body.

Neuer Helfer `osa_file()` im Dispatcher (eine Zeile, parallel zu `osa()`):

```bash
osa_file() { /usr/bin/osascript "$SKILL_DIR/applescripts/$1" "${@:2}"; }
```

## Messdaten

### Zeilenzahl Dispatcher

| Stand | Zeilen |
|---|---|
| Pre-Spike | 1113 |
| Post-Spike (2 von 14 Heredocs extrahiert) | 1080 |
| Reduktion durch 2 Heredocs | **−33 Zeilen** |
| Hochrechnung Voll-Roll-out (alle 14 Heredocs, 355 inline Zeilen) | **−308 bis −341 Zeilen** |
| Erwartete Endgröße nach Voll-Roll-out | ~770–790 Zeilen |

Die Voll-Roll-out-Hochrechnung übersteigt die im Issue genannte Roll-out-Schwelle (`> 100 Zeilen sinken`) um Faktor 3.

### Runtime-Stichprobe

`osascript - <<heredoc` vs. `osascript file.applescript` mit einem trivialen Dummy-Skript (kein Apple-Notes-Zugriff, nur Argv-Echo). Fünf Läufe pro Variante:

| Variante | Lauf 1 (cold) | Lauf 2–5 (warm) |
|---|---|---|
| Heredoc | 0.33 s | 0.02 s |
| File | 0.02 s | 0.02 s |

Nach Warm-Up identisch (~20 ms). File-Variante eliminiert sogar den Cold-Start-Spike. **Keine Runtime-Regression** — wenn überhaupt ein marginaler Vorteil.

### Readability

Subjektive Einschätzung:

- **Bei kleinen Heredocs (12–20 Zeilen, z. B. `get_note`)**: Heredoc und File etwa gleich klar. Heredoc hat den Vorteil „alles an einem Ort", File den Vorteil „eigenes Syntax-Highlighting".
- **Bei großen Heredocs (35+ Zeilen, z. B. `search` ~54 Zeilen, `list` ~48 Zeilen)**: File-Variante deutlich klarer, weil die Bash-Funktion ohne Heredoc-Ballast lesbar wird und der AppleScript-Code im Editor wie AppleScript-Code aussieht.

Verdict: leichter Vorteil für File-Variante, der mit Heredoc-Größe wächst.

### Neue Failure-Modes

- **Datei fehlt**: `osascript` liefert eine klare Fehlermeldung (`cannot read file`). Keine Notwendigkeit für expliziten `[ -f ]`-Check vorab.
- **Permissions**: AppleScript-Dateien müssen lesbar sein, **nicht executable** — `osascript` lädt sie als Quelltext. Damit unkritisch.
- **Pfad-Auflösung**: gelöst über `SKILL_DIR`-Basis (der Dispatcher findet sich bereits via `BASH_SOURCE`/`dirname`). Beim Roll-out via `skills` CLI bleibt die relative Struktur erhalten — getestet durch den hier durchgeführten Spike.

**Keine neuen Klassen von Failure-Modes**, nur leicht andere Wege zu denselben Fehlern.

## Entscheidung

**Roll-out.** Alle drei Kriterien aus der PRD-Roll-out-Regel sind erfüllt:

1. **Zeilenzahl > 100 sinkt** ✓ (Voll-Roll-out-Hochrechnung −308 bis −341 Zeilen).
2. **Readability steigt** ✓ (deutlich bei großen Heredocs, neutral bei kleinen).
3. **Keine neuen Failure-Modes** ✓ (osascript-Fehlermeldungen decken die einzigen zusätzlichen Pfade transparent ab).

Bonus-Beobachtung: Heredoc bei Zeile 549 (`get_note`) und bei der bisherigen Position der `cmd_images`-Logik sind **strukturell identisch**. Bei der Voll-Roll-out-Iteration kann `cmd_images` direkt auf `get_note.applescript` zugreifen statt einen weiteren Heredoc-Klon zu pflegen — kleine zusätzliche Locality-Verbesserung.

## Konsequenzen

- Spike-Stand bleibt: zwei `.applescript`-Dateien existieren, Dispatcher ist 33 Zeilen kürzer, CLI-Vertrag unverändert.
- `09-apple-notes-applescript-rollout.md` wird durch diesen ADR aktiviert. Dort werden die übrigen 12 Heredocs nachgezogen.
- **CLI-Vertrag** (Subkommando-Namen, Flags, Output-Format, Exit-Codes): unverändert vor und nach diesem ADR.
- **Tests**: laut PRD optional, weil Apple-Notes-Tests pre-seeded macOS + Automation-Permissions brauchen. Beschluss hier: Test-Entscheidung wird in Issue 09 getroffen — vermutlich „covered by manual roundtrip" plus Argv-Passthrough-Test auf Dummy-AppleScript-Ebene.
- **Bash-Stil**: Modernisierung des restlichen Dispatchers explizit out-of-scope.

## Nicht-Konsequenzen

- Keine Änderung an `~/.config/claude/apple-notes/config.json` oder am Mapping-Mechanismus.
- Kein neuer Zustand persistiert — die Extraktion ist ein reines „wo lebt der AppleScript-Code"-Refactor.
- Kein Auswirkungen auf die parallele Template-Vereinfachung für Normalo-Partner (separat in Templates / Cheatsheet / Triage durchgeführt).
