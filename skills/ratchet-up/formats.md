# Issue Formats — Contract and Synonyms

Every issue file under `<feature_path>/issues/` is parsed by the orchestrator using a **format-agnostic synonym lookup** — three concepts must be present, the exact headings are flexible.

The skill accepts output from `/to-issues`, `/triage` (Agent Brief), and the strict greenfield form. Pick one consistently per feature.

---

## 1. Required concepts (synonym lookup)

| Concept | Accepted headings (any one matches; case-insensitive) |
|---|---|
| **Intent** | `## Goal`, `## What to build`, `## Description`, `## Agent Brief`, `## Summary` |
| **Acceptance criteria** | `## Acceptance Criteria`, `## Acceptance criteria`, or a `**Acceptance criteria:**` bold block **inside** `## Agent Brief` |
| **Blocked by** | `## Blocked by` |

Plus a top-level status line. Two forms are accepted (pick one per feature, consistent with the issue body's style):

- **strict / greenfield:** `Status: ready-for-agent`
- **Triage / Agent-Brief markdown:** `- **Status:** ready-for-agent`

Every status grep in `algorithm.md` and `scripts/check-evidence.sh` matches both forms — the issue body decides the style, not the tooling.

**Quality-gate greps** (run by §5 of `algorithm.md`):

```bash
grep -iE "^## (Goal|What to build|Description|Agent Brief|Summary)$" "$issue_path"
grep -iE "^(## Acceptance Criteria|\*\*Acceptance criteria:\*\*)$" "$issue_path"
grep -iE "^## Blocked by$" "$issue_path"
```

If any required row has zero matches → set the issue to `needs-info`, log a one-liner in `deviations.md`, skip the worker. This is the cheapest way to avoid wasting a full Worker+Reviewer cycle on under-specified issues.

Optional sections (no gate failure if absent): `## Scope`, `## Verification`, `## Out of scope`, `## Triage Notes`, `## Parent`, `## Phase`.

---

## 2. Canonical example (strict form — recommended)

```md
Status: ready-for-agent

## Goal
One-sentence intent. What observable behaviour does this issue introduce or change?

## Acceptance Criteria
- [ ] AC1 — observable through public interface
- [ ] AC2 — edge case / null / empty behaviour
- [ ] AC3 — test that proves the behaviour exists

## Blocked by
- issues/01-precondition.md  # or "none"
```

Other formats produced by `/to-issues` and `/triage` are accepted via the synonyms above — no rewriting needed.

---

## 3. Status values

The status machine is intentionally minimal:

```text
ready-for-agent  # eligible for the worker (pending all blockers being `done`)
done             # completed, reviewer-approved, committed
needs-info       # issue under-specified or blocker missing → human input
needs-human      # rework limit hit or reviewer/worker escalated
```

**Transitions handled by the orchestrator:**

```text
ready-for-agent → done            (reviewer APPROVED, commit ok or no-changes)
ready-for-agent → ready-for-agent (gate failed OR reviewer REWORK, rework_count++)
ready-for-agent → needs-info      (issue quality gate failed OR worker BLOCKED)
ready-for-agent → needs-human     (rework_count > limit, NEEDS-REPLAN, malformed retry exhausted)
```

If an issue has no `Status:` line at all, treat it as `needs-info` and surface it in `deviations.md`. Never auto-edit issues outside these transitions.
