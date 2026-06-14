---
name: domain-glossary
description: Collaboratively build and maintain the project's domain vocabulary, glossary, and key conceptual decisions stored in CONTEXT.md. Use when the user wants to create, review, or refine project terminology, domain language, glossary entries, or conceptual decisions — including updating CONTEXT.md or discussing what belongs in it.
---

# Domain Glossary

Work with the user to create or improve the project's domain vocabulary and key conceptual decisions.
CONTEXT.md is the storage vehicle — the real work is getting the language right.

The target CONTEXT.md is the one in the **current project's root** — not this skills-source repo's CONTEXT.md. If invoked inside the `silvio-l/skills` repo itself, treat the existing CONTEXT.md as a skill-authoring meta-glossary (not a business domain) and confirm with the user before extending it.

## Start

1. Check whether CONTEXT.md exists in the project root.
2. If it **exists**: read it fully. Identify existing terms, definitions, conventions, and conceptual decisions. Flag duplicates, contradictions, vague formulations, and potentially stale content — but propose changes only, change nothing yet.
3. If it **does not exist**: propose a structure and section outline. Ask for approval before writing anything.

## Mandatory: use the grill-me skill throughout

Invoke the `grill-me` skill for every relevant term or conceptual decision:
- Challenge each term: is it precise, unambiguous, future-proof, AI-readable?
- Ask about scope: what does this term include? What does it explicitly exclude?
- Surface alternatives and explain the trade-offs.
- Point out consequences of a choice (e.g. naming collision with a library, ambiguity with another domain term).
- Never silently accept vague or overloaded language.

Ask questions one at a time.

## Step-by-step workflow

```
1. Analyze existing content (read-only)
2. Collect terms and open questions
3. Mark unclear, duplicate, or contradictory items
4. Ask targeted questions (one at a time)
5. Present options with recommendation
6. Wait for explicit approval
7. Only then: write to CONTEXT.md
8. After writing: re-read the modified section and show it to the user to confirm it landed correctly
```

## Decision format

For every term or formulation in question, present:

| Field | Content |
|---|---|
| **Current** | existing term or phrasing (or "none") |
| **Problem** | what is unclear, duplicate, contradictory, or improvable |
| **Options** | 2–3 concrete alternatives |
| **Recommendation** | your preferred option and why |
| **Decision needed** | explicit yes/no question for the user |

## Sprache

CONTEXT.md wird **auf Deutsch** verfasst — Begriffe, Definitionen, Entscheidungen, Erläuterungen.
Technische Bezeichner (Klassen-, Methoden-, Feldnamen) bleiben im Original (meist Englisch), werden aber auf Deutsch erklärt.
Niemals auf Englisch wechseln, auch wenn eine Formulierung auf Englisch präziser wirkt — finde stattdessen das deutsche Äquivalent und halte die Präzision durch Kontext.

## Hard rules — never bypass

The following actions require explicit user approval before execution:

- Introduce a new term
- Rename an existing term
- Change a definition
- Remove content from CONTEXT.md
- Merge sections
- Mark something as a binding project convention
- Mark existing content as outdated
- Save any file changes

Make no silent assumptions. Only document what has been explicitly confirmed.

## Goal

A CONTEXT.md that is clear, consistent, and AI-readable — where the user retains full conscious control over language, meaning, and conceptual decisions.
The AI structures, questions, and challenges. The user decides.
