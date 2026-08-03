---
name: brainstorming
description: A structured divergent-ideation interview — random domain collisions, inversions, and mutation turn a topic into surprising raw ideas, not the ten obvious ones.
disable-model-invocation: true
---

# Brainstorming

Run this as a radically divergent idea machine, not a helpful assistant reaching for the nearest reasonable answer. The obvious answers are raw material to invert, collide, and mutate — never the deliverable. Every draw in this session comes from `~/.claude/skills/brainstorming/scripts/draw`, which pulls from `deck.json` using real OS entropy: the *process* runs the same seven steps and three gates every time, but the *content* is genuinely random, not a model's idea of randomness (which tends to reach for the same handful of "creative" tropes — fungal networks, ant colonies, quantum whatever — session after session). Each draw is its own shell call — pass the full path every time, never a variable set in an earlier call.

Two kinds of moments in this session: **gates**, where a human judgment call is asked for, one question at a time, with lettered options where choices exist; and everything else, which is agent legwork — generated, not asked about. Collisions, inversions, mutations never become questions.

## Framing gate

Extract topic, the actual question or problem, what's already been tried, and any hard no-gos from context and prior conversation first. Ask only what's genuinely missing, one question at a time. Echo the framing back and wait for explicit confirmation before Step 1 starts.

**Done when:** the user has confirmed the framing as stated, not merely let it pass.

## Step 1 — Familiar territory

Privately list the ten most obvious answers to the framing question. These ten exist only as raw material for the inversions, collisions, and mutations ahead — never present them as a deliverable.

**Done when:** ten obvious answers are logged internally and none has been shown to the user as a proposed idea.

## Step 2 — Lenses

Draw: `~/.claude/skills/brainstorming/scripts/draw --category lenses --count 12`. For each lens, port its underlying mechanism onto the framing question — not its vocabulary. "Ecology" should yield a concept built on carrying capacity or succession, not a concept that merely uses the word "ecosystem."

**Done when:** all 12 lenses have produced one mechanism-based concept each.

## Step 3 — Collisions

Draw: `~/.claude/skills/brainstorming/scripts/draw --category collision_units --collide --count 10`. Each triple looks absurd at first — find the hidden functional principle that makes it a real concept for the framing question before writing the idea down.

**Done when:** all 10 triples have produced at least one concept each, and each concept states the functional principle it found.

## Step 4 — Inversions and contradictions

Work through the full Inversions catalog and the full Contradictions catalog in [`TECHNIQUES.md`](TECHNIQUES.md) — every entry, not a sample. Each contradiction concept states the mechanism that resolves it.

**Done when:** every inversion and every contradiction template has produced one concept.

## Step 5 — Radicality ladder

Generate at least one concept for every one of the five tiers in `TECHNIQUES.md` → Radicality Tiers. Steps 2–4 already clear the 40-concept floor on their own, so this step is done only once all five tiers have actually fired — not by re-counting what Steps 2–4 already produced. Tag each raw concept with the lens, collision triple, inversion, contradiction, or tier it descends from — this tag is what makes Step 7's surprise test checkable later, so it is not optional bookkeeping.

**Done when:** every one of the five tiers has produced at least one concept, and Steps 2–5 combined hold at least 40 distinct tagged raw concepts, no two restating the same core mechanism under different words.

## Selection gate

Present the tagged raw concepts (an index is fine — full detail is not required yet) and recommend roughly ten of the most surprising ones. The user picks which advance to mutation; this call is theirs, not a default.

**Done when:** the user has named which raw concepts move to Step 6.

## Step 6 — Mutation and crossbreeding

Apply every operator in `TECHNIQUES.md` → Mutation Operators to each selected concept, carrying its descent tag forward and adding the operator(s) used.

**Done when:** at least 20 mutated or crossed concepts exist, each traceable to a Step 2–5 raw concept plus the operator applied.

## Step 7 — Surprise filter

Run every surviving concept through `TECHNIQUES.md` → Surprise Test. If a step is landing short of its count or producing near-duplicates, use the Unstuck Card before forcing another synthetic variation.

**Done when:** every surviving concept passes all four Surprise Test conditions, and every discarded concept has a one-line reason for why it failed.

## Final gate

Present the twelve strongest survivors, each with: a short name, the core idea, the unusual principle it rests on, why it is not the obvious answer, which existing process or assumption it breaks, its real benefit, its main risk, a more radical variant, and its full descent chain. Order them by surprise, originality, disruptive potential, and long-term value — not by feasibility alone. Ask the user to accept, reorder, or send any concept back for another mutation pass.

**Done when:** the user has explicitly accepted the twelve or specified which ones go back for revision.

Once the final gate closes, offer once — do not insist — to save the full session (raw concepts, selection, final twelve) as a Markdown file. Save only on a yes.
