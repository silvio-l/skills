---
name: context-optimization-audit
description: Audit and optimize Claude Code context bloat across skills, agents, commands, MCP/plugin config, and project instructions. Use when asked to reduce token usage, remove overlap, clean up skills, optimize Claude Code setup, or review loaded context.
---

# Claude Code Context Optimization Audit

Audit all loaded context sources and propose what to cut, merge, condense, disable, or move.
**Do not change anything first.** Produce a plan, wait for approval, then apply only approved changes.

## Goal

Reduce token usage while preserving behavior. Lower duplication, clearer triggers, fewer competing rules, better global/project/task separation.

## Core principle

More instructions is not better. Keep always-loaded context short. Move rarely-used detail into narrowly triggered skills, commands, or reference docs.

## What to inspect

Search all of these (do not assume paths are complete — use `find`, `ls`, `rg`):

- `CLAUDE.md`, `AGENTS.md`
- `.claude/`, `.claude/skills/`, `.claude/agents/`, `.claude/commands/`, `.claude/settings.json`
- `.mcp.json`, `package.json` (Claude/MCP-related scripts)
- Any `agents.json`, `skills.json`, `opencode.json`, or migrated legacy config files
- `~/.claude/` (user-level config, if accessible)
- Project docs repeatedly copied into prompts or agent instructions

## Audit process

### 1. Inventory

For each context source, capture: type · path · size (lines + `chars/4` token estimate) · purpose · trigger · global vs project · recently used or obsolete · overlap · risk · initial recommendation.

### 2. Find duplication and overlap

Check for:
- Same workflow in `CLAUDE.md`, skills, and commands simultaneously
- Old JSON agent definitions alongside current Markdown versions
- Broad skills with imprecise triggers
- Multiple agents with the same role (planner, reviewer, triage)
- MCP instructions duplicated in project docs
- Security/branch/release rules copied across multiple files

Group by topic: git workflow · security · architecture · testing · UI/UX · agent orchestration · MCP usage · deployment.

### 3. Classify each item

See [REFERENCE.md](REFERENCE.md) for full criteria. Labels: **Keep · Condense · Merge · Split · Disable · Delete · Move to project · Move to user · Convert to command · Convert to reference · Lazy-load**

### 4. Check usage evidence

Look for: recent git changes, doc references, active file paths matching the skill, current project stack. Mark uncertain items `needs confirmation` — do not delete based only on absence of evidence.

### 5. Produce approval plan

Output this before touching any file:

```md
## Context Optimization Plan

### Summary
- Current estimated context size:
- Largest sources:
- Main duplication areas:
- Highest-impact cleanup:
- Estimated token reduction:

### Inventory
| Type | Path | Lines | ~Tokens | Purpose | Overlap | Recommendation | Risk |
|---|---|---:|---:|---|---|---|---|

### Proposed changes
#### Keep
#### Condense
#### Merge
#### Disable / Delete
#### Move
#### Convert to command / reference

### Risks
### Files that would change
### Files that would be removed or archived
### Rollback plan

### Approval required
No files will be changed until you approve this plan.
```

### 6. Apply after approval

1. Check git status first.
2. Edit only approved files; do not touch unrelated changes.
3. Prefer surgical edits — preserve important project rules.
4. When deleting files, prefer archiving unless deletion was explicitly approved.
5. Recalculate estimates after changes.
6. Report before/after results using the Final Report format below.

If branch policy is known, follow it. If unknown, do not create or delete branches unless asked.

## Cleanup rules (condensed)

**Condensing:** keep trigger + decision logic + safety boundaries. Remove repeated explanations, motivational text, examples that don't change behavior, long lists replaceable by compact criteria.

**Merging:** choose the clearer file as target, preserve unique behavior from both, remove the weaker duplicate, update all references.

**Deleting/Disabling:** confirm obsolete/unused, check references first, document why removal is safe.

## Special checks

**Markdown vs JSON:** if both versions of an agent/skill exist, identify which is authoritative and archive the obsolete one.

**Global vs project scope:** global = stable personal preferences, universal safety rules, cross-project tooling. Project = architecture, domain terms, branch policy, app-specific rules. Skills/commands = repeatable workflows, optional audits, rarely needed detail.

**MCP/plugin:** remove instructions already covered elsewhere. Disable unused servers if they add noise. Do not remove active servers just to save tokens.

## Final report

```md
## Context Optimization Result

### Changed
### Removed or archived
### Before / after estimate
| Area | Before | After | Reduction |
|---|---:|---:|---:|

### Remaining intentional duplication
### Manual follow-ups
### Verification performed
```

## Non-goals

Do not rewrite application code, change business logic, delete files without approval, remove safety/workflow rules, or pretend token estimates are exact.
