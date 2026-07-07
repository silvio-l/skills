---
name: motion-and-ui-design
description: "Hub for AI-driven web/app UI and motion-graphics design: Claude Design studio workflow, agent-buildable techniques, modern-design principles. Use for 'Claude Design', 'Motion Graphics erstellen', 'App-Prototyp designen', 'Design mit KI'."
---

# Motion & UI Design — AI Design Hub

You are the **router and coach** for AI-driven design work — both the interactive Claude Design studio (`claude.ai/design`) and design Claude Code builds directly as code artifacts. This hub distills the workflow and techniques; it does not duplicate the deeper design skills that already exist in this setup.

## Core principle: design system first

Before building any single artifact — prototype, slide deck, landing page, animation — establish one saved brand source: colors, fonts, logo, tokens. This is the single biggest lever against generic AI-slop output; every artifact generated afterward inherits it and looks like it came from one real company instead of a pile of disconnected AI tools. Skipping this step is the most common mistake. It takes minutes and pays for the rest of the session.

This mirrors the token-first discipline already enforced by `flutter-design-language` and `figma-project-discipline` — same principle, applied to the Claude Design studio.

## Two modes of operation

1. **Drive the studio.** Claude Code cannot remote-control `claude.ai/design` — it is a separate interactive product. What you *can* do: coach the user through the workflow and hand them ready-to-paste prompts. → [studio-workflow.md](studio-workflow.md), [prompts.md](prompts.md).
2. **Build directly.** For UI mockups and motion graphics that fit a self-contained HTML/CSS/JS artifact, build it yourself with the `Artifact` tool instead of sending the user to the studio — faster, and stays in the same session. → [motion-graphics.md](motion-graphics.md) for the agent-buildable variant. For animated data visualization specifically, use the `dataviz` skill instead.

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

Don't duplicate work these skills already own — route to them:

| Task | Skill |
|---|---|
| Design direction / anti-slop for a new web UI | `frontend-design`, `design-taste-frontend`, `impeccable` |
| Flutter design language + tokens | `flutter-design-language` → `figma-to-flutter` |
| Figma file structure / discipline | `figma-project-discipline`, `figma-*` |
| Charts / animated data visualization | `dataviz` |
| Durable modern web-design principles + web→app adaptation | [modern-design.md](modern-design.md) (this skill) |
| Real image assets | `openai-image`, fal.ai (`~/.config/fal/.env`) |
| Deploying the finished site | `netcup-deploy` |
| End-to-end premium web build | `~/.claude/infrastructure/premium-web-loop.md` |

## Volatility warning

The Claude Design studio UI changes frequently — buttons and layout have shifted multiple times in recent months. This skill deliberately teaches durable workflow and principles, not exact click coordinates or screenshots that will go stale.

## Handoff to Claude Code

When a studio artifact is ready, "Send to Claude Code" hands over a build prompt. Don't just prompt it blindly — use a real AI-engineering approach (`ratchet-up`, `to-roadmap`, or `figma-to-flutter` depending on the target stack) so the build stays controlled as the project grows.
