# Context Optimization Reference

## Classification labels

| Label | When to use |
|---|---|
| **Keep** | Focused, not bloated, actively used |
| **Condense** | Useful but too long |
| **Merge** | Strongly overlaps another item |
| **Split** | Contains multiple unrelated responsibilities |
| **Disable** | Rarely used and too broad |
| **Delete** | Obsolete or fully duplicated |
| **Move to project** | Project-specific, should not be global |
| **Move to user** | Stable personal workflow, useful across projects |
| **Convert to command** | Useful only when manually invoked |
| **Convert to reference doc** | Too detailed for loaded context |
| **Lazy-load** | Keep only a short trigger; load detail on demand |

## Context budget targets

### Skill descriptions (frontmatter)
- 1–2 sentences, max 250–400 chars
- Pattern: `Use when asked to <task>. Handles <scope>. Do not use for <non-scope>.`
- Avoid: generic wording, multiple unrelated triggers, project history, implementation policy

### Skill body
- Target: 80–180 lines
- May exceed when: essential procedural steps, prevents high-risk mistakes, replaces multiple older skills
- Remove: long examples, repeated principles, generic advice, duplicate safety rules, detailed tutorials, historical explanations

### Agents
- One job per agent: planner · implementer · reviewer · triage · security-reviewer · ux-reviewer
- Bad: one agent that plans, codes, reviews, releases, and writes docs
- Bad: multiple agents with the same review responsibility
- Project-specific agents must not be stored globally

### Commands vs skills
Commands are better than skills when the task should only run on manual invocation:
release checklist · repo cleanup · dependency audit · skill audit · migration run · documentation generation · one-off maintenance workflows

### CLAUDE.md / project instructions
Keep only durable project rules: purpose · architecture boundaries · required commands · branch policy · coding conventions · forbidden actions · essential security rules. Move detailed workflows into commands or docs.

## Scope guidance

| Scope | Use for |
|---|---|
| Global / user | Stable personal preferences, general coding style, universal safety rules, cross-project tooling |
| Project | Architecture, domain terminology, branch policy, project commands, app-specific UX/deployment rules |
| Skills / commands | Repeatable workflows, optional audits, specialized procedures, rarely needed detail |
