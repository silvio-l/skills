# Output Template — `.scratch/roadmap.md`

Use exactly this structure and order. Sections must not be omitted, renamed, or reordered. Where a table is specified, keep column names and order.

---

```markdown
# Implementation Roadmap

**Source:** <path to the idea document>
**Created:** <ISO date>
**Status:** initial draft

---

## 1. Brief Assessment of the Idea Document

- **Product goal:** <one sentence>
- **Core value:** <one sentence>
- **Key user flows:** <list, 3–6 items>
- **Main technical areas:** <list of major components>
- **Biggest risks / blockers:** <list>
- **Open decisions from the source:** <list — only what was already marked as open in the document>

---

## 2. Feature Inventory

| Area | Feature | Priority | Dependencies | Complexity | Note |
|---|---|---:|---|---:|---|
| <e.g. Onboarding> | <Feature> | P0 | <required features or "—"> | M | <brief> |

**Priorities:**

- `P0` — mandatory for MVP
- `P1` — important, but not MVP-blocking
- `P2` — later
- `P3` — optional / nice-to-have

**Complexity:** `S` / `M` / `L` (small / medium / large).

---

## 3. Technical Dependency Analysis

Describe in bullet points:

- What foundations must be established first (project setup, auth, storage, …)
- Which data models must be locked in early
- Which UI areas depend on backend/state logic
- Which features can only be meaningfully implemented later
- Which points are still unclear or risky
- Which steps could be **parallelised**
- Which steps must necessarily be **sequential**

---

## 4. Phase Plan

List the phases with a one-line justification. Default suggestion — adapt to the specific document, remove / add as appropriate:

- **Phase 0: Project Foundation & Architecture** — <justification>
- **Phase 1: Data Model & Persistence** — <justification>
- **Phase 2: Core Logic / Services** — <justification>
- **Phase 3: Main UI / Central Flows** — <justification>
- **Phase 4: Extended Features** — <justification>
- **Phase 5: Quality, Error Handling, Edge Cases** — <justification>
- **Phase 6: Polishing & Release Preparation** — <justification>

---

## 5. Agent-Optimised Sprint Roadmap

**Sprint ID — stable and machine-readable.** Format: `sprint-<two-digit>-<kebab-case-slug>`, e.g. `sprint-03-create-care-object`. The number reflects the initial position; on later reorderings or insertions, **the ID does not change** — the H3 heading "Sprint X" is a reading aid only; the slug remains the stable anchor for all references (feature directory, ratchet-up, manual links).

**Status — sprint lifecycle:** `todo` → `in-progress` → `done`.

- `todo` — Default when created. Sprint is scoped, not yet converted via `/to-prd`.
- `in-progress` — At least one issue from this sprint is being worked on (set by `ratchet-up` or manually).
- `done` — All issues from the corresponding PRD have been marked `done` by `ratchet-up`.

Per sprint, **exactly** this block:

### Sprint <No>: <clear name>

**Sprint-ID:** sprint-<NN>-<kebab-case-slug>

**Status:** todo

**Phase:** <phase number + name>

**Goal:**
<Brief description of the deliverable, 1–3 sentences.>

**Why now:**
<Justification for the position in the sequence.>

**Scope:** small / medium / large

**100k-token suitability:** suitable / borderline / too large

**To implement:**
- <Concrete tasks>
- <Affected modules>
- <Relevant data models>
- <Relevant screens or services>

**Not included:**
- <Things deliberately excluded to keep the sprint small>

**Dependencies:**
- <Prior sprint IDs, e.g. `sprint-02-…`, `sprint-04-…`>
- <Open decisions that must be resolved first>
- <Technical prerequisites>

**Acceptance criteria:**
- <Verifiable 1>
- <Verifiable 2>
- <Verifiable 3>

**Risks / notes for the AI coding agent:**
- <Risk / pitfall>
- <Convention or naming the agent must follow>
- <What might accidentally get refactored along>

---

(Repeat sprint block until all sprints are listed.)

---

## 6. Recommended Order

Numbered list of **all** sprints in the final implementation order — reference sprints by their **sprint ID**, not the H3 number:

1. `sprint-01-<slug>` — <name>
2. `sprint-02-<slug>` — <name>
3. …

If sprints are parallelisable, mark them with `‖` and the same number (e.g. `3a ‖ 3b`). Status is **not** in this list — the single source of truth is the `Status:` field in each sprint block.

---

## 7. MVP Cut

List the sprints that are mandatory for a first usable MVP — reference again by **sprint ID**:

- `sprint-<NN>-<slug>` — <name>
- `sprint-<NN>-<slug>` — <name>
- …

Brief justification of why exactly this selection covers the MVP contract from section 1.

---

## 8. Later Expansion Stages

Assign all non-MVP sprints to later releases:

### Release 1.1 — <Theme>
- `sprint-<NN>-<slug>` — <name>

### Release 1.2 — <Theme>
- `sprint-<NN>-<slug>` — <name>

### Backlog (P2/P3, no release assignment)
- `sprint-<NN>-<slug>` — <name>

---

## 9. Critical Open Questions

Only questions whose missing answer would lead to **misplanning or significant rework**. No wish list, no "nice to know".

1. <Question> — _blocks: `sprint-NN-<slug>`, `sprint-MM-<slug>`_
2. <Question> — _blocks: …_

If no questions are open, write: `No critical open questions.`
```
