# Generating Visual Assets: Illustrations, Icons, Symbols, Hero Imagery

A deliberate direction and a clean token system still fall flat if every icon is a generic outline glyph and every hero section is a plain color block — some interfaces genuinely need real illustration, iconography, or imagery to feel finished. This doc makes that self-sufficient: generate the asset directly via the connected `fal.ai` MCP tools (or the `openai-image` skill as a fallback) instead of telling the user to go find something themselves.

## Code first, generated asset second

Not everything that looks like an "asset" should be generated. Simple, geometric icons and decorative graphics are almost always better hand-authored as inline SVG or CSS/Canvas (see [patterns.md](patterns.md)) — crisper at any size, on-brand by construction, zero cost, zero risk of an off-brand render. Reach for generation when the need is genuinely illustrative or photographic: a hero illustration, a textured background, a mascot/brand character, a painterly icon set with a specific artistic style that would be absurd to hand-draw as SVG paths, or a photoreal product/lifestyle image. When in doubt, try the code-first route from `patterns.md` before spending anything on generation.

## Primary path: the fal.ai MCP

When `mcp__fal-ai__*` tools are connected (check with `ToolSearch` if they're deferred), use them directly — no separate script, no manual API calls, no need to touch `~/.config/fal/.env` (the MCP server already holds the credential).

**The flow:**
1. **`recommend_model`** with a plain description of the task (e.g. "flat vector illustration of a coffee roaster," "remove background from a product photo," "generate a set of line icons"). Never guess a model name from memory — always discover the current best option this way, unless the user names a specific model explicitly.
2. **`get_model_schema`** on the chosen endpoint to see the actual required inputs before calling it.
3. **`get_pricing`** on the chosen endpoint — always, before the first real run.
4. **State the model and estimated cost to the user and get a go-ahead before the first real (billed) generation.** This is not optional: a fal.ai run bills the account behind the connected key, which makes it a real-money action, not a free preview. Confirm once per batch of related assets ("I'll generate 4 icons with `fal-ai/…` at ~$X total, OK?"), not once per individual image inside an already-confirmed batch.
5. **`run_model`** for anything that returns quickly (most images); **`submit_job` + `check_job` + `get_job_result`** for anything long-running (video, 3D, training) — `run_model` already tells you when to switch to this path if the wait budget elapses.
6. For image-to-image or edit models that need a reference, **`upload_file`** first (prefer a public URL or the REST direct-upload path it describes for local files) to get a fal.ai CDN URL to pass as input.

## Validated starting points

These are known-good from prior use in this setup (see `~/.claude/infrastructure/fal-ai.md`) — a reasonable first call to `recommend_model`/`search_models` even so, since the catalog moves fast and these may not stay the best option:

| Need | Model | Notes |
|---|---|---|
| Identity-consistent variations from one reference image (on-brand icon variants, consistent mascot poses) | `fal-ai/nano-banana/edit` (Gemini 2.5 Flash Image) | Top pick for staying faithful to a reference while allowing light pose/angle changes. |
| General image generation/edit | `fal-ai/flux-pro/kontext` (or `/kontext/max`) | Alternative to nano-banana; stays more frontal, can distort fine detail more. |
| Clean cutouts / alpha backgrounds | `fal-ai/birefnet` | Background removal with a clean alpha edge — essential before dropping a generated illustration into a UI with its own background. |
| Genuine scalable vector output (real icon sets, not raster pretending to be one) | Recraft-family models (search via `search_models` — the specific endpoint drifts) | The rare model family that outputs actual SVG rather than a raster PNG; worth it specifically when the deliverable is an icon *set* that needs to scale cleanly. |

## Fallback: `openai-image`

When the fal.ai MCP isn't connected in a given session, or the specific need is a transparent-background PNG and `gpt-image-1`'s alpha support is the deciding factor, use the already-installed `openai-image` skill instead — same cost-consent discipline applies (`--dry-run` first for anything vague, confirm the resolved model/size before the first real call).

## After generating: run it back through the loop

A generated asset is not exempt from [cool-craft.md](cool-craft.md)'s self-verify loop — an AI-generated hero image can carry its own version of the generic tells (glossy stock-photo lighting, a generically "AI" gradient background baked into the image itself, uncanny-valley faces) even when the surrounding palette and type are deliberate. Look at what came back before dropping it in: does it actually fit the chosen direction, or does it read as generic in a way the rest of the build doesn't? Regenerate with a more specific prompt (style, lighting, composition named explicitly) rather than accepting the first result by default.

## Cost discipline

Fal.ai is pay-per-use — cents per image for most models, more for video/3D/training. Generate one candidate and confirm it's right before batching a full set (e.g. a 6-icon set), the same discipline already documented in the infra note. `get_pricing` before the first call of a new model, every time — pricing varies a lot by model and isn't safe to assume from a similar-sounding one.
