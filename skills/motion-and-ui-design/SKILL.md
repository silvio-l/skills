---
name: motion-and-ui-design
description: "AI web/app design playbook: anti-generic execution loop, code patterns, generated illustrations/icons via fal.ai, Claude Design studio workflow, motion graphics. Use for 'Claude Design', 'Motion Graphics erstellen', 'coole Website/App designen'."
---

# Motion & UI Design — AI Design Execution Playbook

You are both the **coach** for the interactive Claude Design studio (`claude.ai/design`) and the **executor** when design gets built directly as code. Knowing the workflow is not the same as being able to produce something that doesn't look like every other AI-generated site — this skill exists to close that gap, not just describe the studio.

## How to actually design something cool — the loop

This is the core capability, run it every time something visual gets built, studio or direct:

1. **Commit to a direction before generating anything.** Not "clean and modern" — a named aesthetic direction with a reason it fits the subject. → [cool-craft.md](cool-craft.md)'s direction library and Gate 0.
2. **Lay tokens before components.** Colors, type, spacing, radius — declared once, referenced everywhere. → the token starter in [patterns.md](patterns.md).
3. **Build** — in the studio (→ [studio-workflow.md](studio-workflow.md)) or directly as a code artifact (→ [motion-graphics.md](motion-graphics.md), [patterns.md](patterns.md)). If the direction calls for real illustration, iconography, or imagery beyond what code can draw, generate it directly via the `fal.ai` MCP tools rather than deferring — → [assets.md](assets.md).
4. **Run the visual self-verify loop.** Render or screenshot what got built, critique it against the generic-tells table and litmus checks, iterate. Skipping this step is why AI output defaults to the median — an agent that never looks at what it produced can't tell a purple-gradient default from a deliberate choice. → [cool-craft.md](cool-craft.md).
5. **Escalate for depth, not as a substitute for the loop.** Once this loop has produced something coherent, compose with `impeccable` or `frontend-design` for a brief that genuinely needs deeper taste work.

## Core principle: design system first

Before building any single artifact — prototype, slide deck, landing page, animation — establish one saved brand source: colors, fonts, logo, tokens. This is the single biggest lever against generic AI-slop output; every artifact generated afterward inherits it and looks like it came from one real company instead of a pile of disconnected AI tools. Skipping this step is the most common mistake. It takes minutes and pays for the rest of the session.

This mirrors the token-first discipline already enforced by `flutter-design-language` and `figma-project-discipline` — same principle, applied here to both the Claude Design studio and direct code builds.

## Two modes of operation

1. **Drive the studio.** Claude Code cannot remote-control `claude.ai/design` — it is a separate interactive product. What you *can* do: coach the user through the workflow and hand them ready-to-paste prompts. → [studio-workflow.md](studio-workflow.md), [prompts.md](prompts.md).
2. **Build directly.** For UI mockups and motion graphics that fit a self-contained HTML/CSS/JS artifact, build it yourself with the `Artifact` tool instead of sending the user to the studio — faster, and stays in the same session, and lets you actually run the self-verify loop above. → [motion-graphics.md](motion-graphics.md) and [patterns.md](patterns.md). For animated data visualization specifically, use the `dataviz` skill instead.

## Model choice for design work

Design work escalates upward: **Fable 5 > Opus 4.8 ≥ Sonnet 5** for aesthetic judgment and anti-slop instinct (see the global model-routing rule). For a bounded design subtask dispatched via the `Agent` tool, set `model: fable` or `model: opus` explicitly — the alias, never the full model ID.

## The five studio artifact types

| Artifact | What it is |
|---|---|
| Prototype | A clickable, multi-page working mockup |
| Slides | An on-brand pitch deck, not a generic template |
| Document | A one-page infographic or report |
| Wireframe | A colorless layout skeleton — plan the structure before it's built |
| Animation | A short on-brand motion graphic |

Full recipes, iteration tools, and export paths → [studio-workflow.md](studio-workflow.md).

## Routing table

This skill owns the anti-generic execution loop, code patterns, and asset generation directly — no need to defer for those. Compose with these for deeper or platform-specific work:

| Task | Skill |
|---|---|
| Anti-generic direction, litmus checks, self-verify loop | [cool-craft.md](cool-craft.md) (this skill) |
| Copy-paste code starters (tokens, bento, motion, microinteractions) | [patterns.md](patterns.md) (this skill) |
| Illustrations, icons, symbols, hero imagery — generated directly via the fal.ai MCP | [assets.md](assets.md) (this skill) |
| Durable modern web-design principles + web→app adaptation | [modern-design.md](modern-design.md) (this skill) |
| Deeper taste work for a demanding brief / full design system | `frontend-design`, `design-taste-frontend`, `impeccable` |
| Flutter design language + tokens | `flutter-design-language` → `figma-to-flutter` |
| Figma file structure / discipline | `figma-project-discipline`, `figma-*` |
| Charts / animated data visualization | `dataviz` |
| Deploying the finished site | `netcup-deploy` |
| End-to-end premium web build | `~/.claude/infrastructure/premium-web-loop.md` |

## Volatility warning

The Claude Design studio UI changes frequently — buttons and layout have shifted multiple times in recent months. This skill deliberately teaches durable workflow and principles, not exact click coordinates or screenshots that will go stale.

## Handoff to Claude Code

When a studio artifact is ready, "Send to Claude Code" hands over a build prompt. Don't just prompt it blindly — use a real AI-engineering approach (`ratchet-up`, `to-roadmap`, or `figma-to-flutter` depending on the target stack) so the build stays controlled as the project grows.
