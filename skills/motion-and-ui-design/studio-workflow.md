# Claude Design Studio Workflow

The end-to-end pipeline for building a coherent set of on-brand artifacts in the Claude Design studio (`claude.ai/design`), distilled from a full walkthrough of building a fictional SaaS product end to end. Requires at least a paid Claude plan (Pro/Max/Team/Enterprise); usage now runs against the normal plan quota rather than a separate limit.

## 1. Design system (always first)

A design system is the saved brand: logo, color accents and shade ramps, semantic colors (for alerts/states), typography, and core UI components (buttons, tabs, inputs) — plus a sample mockup showing them in context. Set it up once; reuse it for every artifact that follows.

Ways to seed it:
- **Briefing questionnaire** — describe the company/product, audience, and problem it solves. The studio asks targeted follow-ups (design direction, e.g. "clean, analytical, data-forward"; copy language; what surfaces to cover — web app, marketing site, component depth).
- **Upload reference assets** — an existing logo, fonts, or a reference branding image scraped from a design inspiration site. If you upload a reference that visually belongs to another brand, say so explicitly and ask for a fresh identity inspired by it rather than a copy — the studio will otherwise flag the ambiguity itself.
- **Connect real code** — a GitHub repo, an uploaded codebase, or a Figma file. The studio extracts existing styles and tokens from it instead of guessing.

The result is fully editable afterward — per-component feedback, or reopen any piece (like the sample report mockup) in its own edit view.

## 2. Prototype

A clickable, multi-page mockup of the actual product. Ask for it grounded in the design system and describe the core workflow explicitly (e.g. "lands on a dashboard, uploads feedback via CSV or external systems, generates a report from it") — the more concrete the flow, the less back-and-forth. The studio asks a clarifying questionnaire (what the dashboard shows, which external systems to support, how interactive it should be) before building.

**Iteration tools**, available on any generated artifact:
- **Tweaks box** — type a change; it applies immediately.
- **Annotate** — click any spot, leave a comment, the studio addresses it directly. Multiple comments can be queued and sent together.
- **Markup mode** — select a specific element and describe the change for just that element (spacing, wording, behavior).
- **Edit mode** — direct manipulation, including a code-hierarchy panel on the left so you can select the exact underlying element and add CSS if needed.
- **Simple mode** — a no-code adjustment layer for non-technical tweaks.

The studio also self-validates: after a build, it reviews its own UI (screenshotting and checking itself) before handing control back — catching obvious breakage before you do.

## 3. Slides / pitch deck

Generated against the design system, so it looks like a tailor-made product deck rather than a generic template pulled from Canva or PowerPoint. State length (e.g. "10 slides"), raise amount, traction numbers, and ask it to research competitors if you don't want to supply them yourself — it will. Speaker notes come along by default. Share → Send to Canva hands the deck over for further polish using Canva's own tools; the two are complementary, not competitors.

## 4. Document / infographic

A one-page infographic or report, on-brand and pulling in real images if an image-generation connector is set up. Good for something you'd hand directly to a prospect or customer.

## 5. Wireframe

A deliberately colorless, unstyled skeleton — boxes and labels only. The point is to lock the layout of a multi-page site or app *before* any styling work happens, which is what actually saves money: skipping this step and jumping straight to a styled build is the classic way to end up redoing the whole layout once it turns out wrong.

## 6. Animation

Covered in depth in [motion-graphics.md](motion-graphics.md).

## Export and handoff

| Path | Use for |
|---|---|
| PDF / PPTX | Slides, sharing outside the studio |
| Standalone HTML | Embedding an artifact (e.g. an animation) into another project |
| Project archive (ZIP) | Full source, e.g. to convert to MP4 via Claude Desktop co-work |
| Share link | Team review without export |
| **Send to Claude Code** | Hands the finished design over as a build prompt |

See the handoff note in `SKILL.md` before sending anything to Claude Code — don't just prompt it blindly.

## Integrations

- **Real image assets.** The studio can pull from an image-generation connector (MCP) if one is configured. Prefer this repo's own tooling — `openai-image` or fal.ai (`~/.config/fal/.env`) — over ad hoc third-party connectors, for the same reasons documented in the global stack-default rules (credential hygiene, avoiding another SaaS dependency).
- **Canva.** Send-to-Canva is a one-click handoff for further polish; the two tools are complementary.
- **Figma / GitHub import.** Either can seed a design system directly from real code or an existing Figma file, instead of starting from a text briefing.
- **Hosting the finished site.** Once a landing page or prototype is ready to go live, use `netcup-deploy` for this setup's actual hosting target — not a third-party host you don't otherwise use.
