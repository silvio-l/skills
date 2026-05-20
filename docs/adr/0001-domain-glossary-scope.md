# ADR-0001 — `domain-glossary` retire zugunsten von `/grill-with-docs`

- **Status**: accepted
- **Outcome**: retire
- **Datum**: 2026-05-20
- **Kontext-Issue**: `.scratch/architecture-deepenings/issues/06-domain-glossary-deletion-test.md`
- **Folge-Issue**: `.scratch/architecture-deepenings/issues/07-domain-glossary-implement-decision.md` — Pfad B (retire) verbindlich

## Kontext

Der lokale Skill `domain-glossary` (76 Zeilen Prosa) duplicateet weitgehend, was `mattpocock/skills`' `/grill-with-docs` bereits anbietet: kollaboratives Bauen von `CONTEXT.md` plus ADR-Pflege. Jeder zukünftige `/improve-codebase-architecture`-Lauf würde diese Überlappung erneut aufwerfen, solange die Entscheidung nicht festgeschrieben ist.

Die PRD verlangt einen Deletion-Test entlang dreier Dimensionen — beantwortet hier mit konkreten Belegen.

## Deletion-Test

### Dimension 1 — Deep Skill oder Shallow Wrapper?

`domain-glossary` ist KEIN reiner Wrapper über `/grill-me`, weil er drei eigenständige Bausteine liefert:

- **Decision-Table-Format** (`Current / Problem / Options / Recommendation / Decision needed`) — strukturierter als das offene Interview von `/grill-me`.
- **Hard-Rules-Block** mit expliziter Liste „requires approval"-Aktionen.
- **7-Schritt-Workflow** (analyze → collect → mark → ask → options → wait → write).

Verglichen mit `/grill-with-docs` ist `domain-glossary` aber **deutlich enger**:

| Funktion | `/grill-with-docs` | `domain-glossary` |
|---|---|---|
| CONTEXT.md collaborativ bauen | ja | ja |
| CONTEXT-MAP für Multi-Context-Repos | ja | nein |
| Lazy Creation von `docs/adr/` | ja | nein |
| ADR-Pflege mit drei Bedingungen | ja | nein |
| Cross-Reference mit Code | ja | nein |
| Sharpen-Fuzzy-Language mit Beispielen | ja | nur als Prinzip |
| Decision-Table-Format | implizit | explizit |
| Hard-Rules-Block | nein | ja |

`/grill-with-docs` ist die breitere, besser maintained Quelle. `domain-glossary` ist ein engerer Subset mit drei lokal sinnvollen Bausteinen.

### Dimension 2 — German-Language-Rule, wo gehört sie hin?

Die Regel „CONTEXT.md wird auf Deutsch verfasst, technische Bezeichner bleiben im Original" ist im Skill verankert.

**Redundanz-Befund**: `~/.claude/CLAUDE.md` enthält global bereits „Always communicate with the user in German. […] Technical terms that are more common in English (e.g. 'Provider', 'Widget', 'Branch', 'Commit') may be used as-is within German sentences." Die Regel im Skill ist eine engere Spezialisierung — und genau diese Spezialisierung wird durch die globale Regel implizit schon erzwungen, wenn der Agent CONTEXT.md verfasst.

**Heimat nach retire**: die globale CLAUDE.md-Regel reicht aus. Keine Migration notwendig.

### Dimension 3 — Hard-Rules-Block, generisch oder spezifisch?

Die acht Hard Rules (Introduce term, Rename, Change definition, Remove content, Merge sections, Mark as binding convention, Mark as outdated, Save any file changes) sind alle Spielarten desselben universellen Prinzips: **„dokumentierte Sprache ändert sich nur mit ausdrücklicher menschlicher Zustimmung"**.

Dieses Prinzip ist generisch genug für Upstream. `/grill-with-docs` adressiert es heute implizit über „Update CONTEXT.md inline" + „Offer ADRs sparingly", aber **ohne** explizite Approval-Pflicht.

**Heimat nach retire**: optionaler Upstream-PR an `mattpocock/skills`, der einen vergleichbaren Hard-Rules-Block als optionale Sektion in `/grill-with-docs` einführt. Der PR ist **kein** Blocker für die lokale Entfernung — falls Matt ihn nicht mergt, lebt die Regel als persönliche Erinnerung in Silvios eigener `.claude/CLAUDE.md` weiter.

## Entscheidung

**Retire.** `skills/domain-glossary/` wird gelöscht. Die drei Unique-Value-Bausteine landen folgendermaßen:

- **German-Language-Rule** → nichts zu tun, globale `~/.claude/CLAUDE.md` deckt sie ab.
- **Decision-Table-Format** → fällt weg. `/grill-with-docs`' offener Interview-Stil reicht; das tabellarische Format war Nice-to-have, kein Killer-Feature.
- **Hard-Rules-Block** → optionaler Upstream-PR an `mattpocock/skills`. Wird in Issue 07 (B2-implement) eröffnet. Falls upstream abgelehnt: persönliche Notiz in `~/.claude/CLAUDE.md`.

## Konsequenzen

- `skills/domain-glossary/` wird entfernt (Issue 07).
- `README.md` verliert den `### domain-glossary`-Eintrag und die Zeile in der Prerequisites-Tabelle (Issue 07).
- `CONTEXT.md` enthält aktuell keinen Verweis auf den Skill → kein Edit nötig (verifiziert am 2026-05-20).
- Frische `/domain-glossary`-Aufrufe landen nach dem nächsten Roundtrip ins Leere — beabsichtigt. Stattdessen wird `/grill-with-docs` benutzt.
- Drift zwischen `domain-glossary` und `/grill-with-docs` ist damit dauerhaft ausgeschlossen.
- Künftige `/improve-codebase-architecture`-Läufe finden diesen ADR und schlagen die Frage nicht erneut vor.

## Nicht-Konsequenzen

- Keine API/Trigger-Migration für andere Skills — der Seam von `domain-glossary` war seine Trigger-Phrase, nicht eine programmatische Schnittstelle.
- Keine Tests werden gelöscht — der Skill hatte keine.
