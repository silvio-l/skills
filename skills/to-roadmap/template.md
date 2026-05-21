# Output-Template — `.scratch/roadmap.md`

Verwende exakt diese Struktur und Reihenfolge. Sektionen dürfen nicht ausgelassen, umbenannt oder umsortiert werden. Wo eine Tabelle vorgegeben ist, behalte Spaltennamen und -reihenfolge bei.

---

```markdown
# Implementierungs-Roadmap

**Quelle:** <Pfad zum Ideendokument>
**Erstellt:** <ISO-Datum>
**Status:** initial draft

---

## 1. Kurzbewertung des Ideendokuments

- **Produktziel:** <ein Satz>
- **Kernnutzen:** <ein Satz>
- **Wichtigste Nutzerflüsse:** <Aufzählung, 3–6 Punkte>
- **Technische Hauptbereiche:** <Aufzählung der großen Bauteile>
- **Größte Risiken / Blocker:** <Aufzählung>
- **Offene Entscheidungen aus der Quelle:** <Aufzählung — nur was schon im Dokument als offen markiert war>

---

## 2. Feature-Inventar

| Bereich | Feature | Priorität | Abhängigkeiten | Komplexität | Bemerkung |
|---|---|---:|---|---:|---|
| <z. B. Onboarding> | <Feature> | P0 | <vorausgesetzte Features oder „—"> | M | <kurz> |

**Prioritäten:**

- `P0` — zwingend für MVP
- `P1` — wichtig, aber nicht MVP-blockierend
- `P2` — später
- `P3` — optional / nice-to-have

**Komplexität:** `S` / `M` / `L` (klein / mittel / groß).

---

## 3. Technische Abhängigkeitsanalyse

Beschreibe in Stichpunkten:

- Welche Grundlagen zuerst geschaffen werden müssen (Projektsetup, Auth, Storage, …)
- Welche Datenmodelle früh feststehen müssen
- Welche UI-Bereiche von Backend-/State-Logik abhängen
- Welche Features erst später sinnvoll implementierbar sind
- Welche Punkte noch unklar oder riskant sind
- Welche Schritte **parallelisierbar** wären
- Welche Schritte zwingend **sequenziell** erfolgen müssen

---

## 4. Phasenplan

Liste die Phasen mit Einzeiler-Begründung. Standardvorschlag — passe ihn am konkreten Dokument an, lösche / füge hinzu, was passt:

- **Phase 0: Projektgrundlage & Architektur** — <Begründung>
- **Phase 1: Datenmodell & Persistenz** — <Begründung>
- **Phase 2: Kernlogik / Services** — <Begründung>
- **Phase 3: Haupt-UI / zentrale Flows** — <Begründung>
- **Phase 4: Erweiterte Funktionen** — <Begründung>
- **Phase 5: Qualität, Fehlerbehandlung, Edge Cases** — <Begründung>
- **Phase 6: Polishing & Release-Vorbereitung** — <Begründung>

---

## 5. Agentenoptimierte Sprint-Roadmap

Pro Sprint **exakt** dieser Block:

### Sprint <Nr>: <klarer Name>

**Phase:** <Phasennummer + Name>

**Ziel:**
<Kurze Beschreibung des Ergebnisses, 1–3 Sätze.>

**Warum jetzt:**
<Begründung für die Position in der Reihenfolge.>

**Umfang:** klein / mittel / groß

**100k-Token-Eignung:** geeignet / grenzwertig / zu groß

**Umzusetzen:**
- <Konkrete Aufgaben>
- <Betroffene Module>
- <Relevante Datenmodelle>
- <Relevante Screens oder Services>

**Nicht enthalten:**
- <Bewusst ausgeschlossene Dinge, um den Sprint klein zu halten>

**Abhängigkeiten:**
- <Vorherige Sprints, z. B. „Sprint 2, Sprint 4">
- <Offene Entscheidungen, die vorher fallen müssen>
- <Technische Voraussetzungen>

**Akzeptanzkriterien:**
- <Prüfbar 1>
- <Prüfbar 2>
- <Prüfbar 3>

**Risiken / Hinweise für den KI-Coding-Agenten:**
- <Risiko / Stolperstein>
- <Konvention oder Naming, auf die der Agent achten muss>
- <Was leicht ungewollt mit-refaktoriert würde>

---

(Wiederhole Sprint-Block bis alle Sprints aufgeführt sind.)

---

## 6. Empfohlene Reihenfolge

Nummerierte Liste **aller** Sprints in der finalen Umsetzungsreihenfolge:

1. Sprint 1: <Name>
2. Sprint 2: <Name>
3. …

Wenn Sprints parallelisierbar sind, markiere sie mit `‖` und derselben Nummer (z. B. `3a ‖ 3b`).

---

## 7. MVP-Schnitt

Liste die Sprints, die zwingend für ein erstes nutzbares MVP nötig sind:

- Sprint <Nr>: <Name>
- Sprint <Nr>: <Name>
- …

Kurzbegründung, warum genau diese Auswahl den MVP-Vertrag aus Sektion 1 abdeckt.

---

## 8. Spätere Ausbaustufen

Ordne alle nicht-MVP-Sprints in spätere Releases ein:

### Release 1.1 — <Thema>
- Sprint <Nr>: <Name>

### Release 1.2 — <Thema>
- Sprint <Nr>: <Name>

### Backlog (P2/P3, ohne Releasezuordnung)
- Sprint <Nr>: <Name>

---

## 9. Kritische Rückfragen

Nur Fragen, deren fehlende Antwort zu **Fehlplanung oder größerem Rework** führen würde. Keine Wunschliste, keine „nice to know".

1. <Frage> — _blockiert: Sprint X, Sprint Y_
2. <Frage> — _blockiert: …_

Wenn keine Rückfragen offen sind, schreibe: `Keine kritischen Rückfragen offen.`
```
