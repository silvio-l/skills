---
name: openai-image
description: Generate images from a text prompt via the OpenAI Image API (gpt-image-1 / gpt-image-2), writing PNG files to disk. Picks the model automatically — transparent backgrounds use gpt-image-1, everything else uses the higher-quality gpt-image-2. Use when the user wants to create, generate, or render an image, illustration, icon, asset, or graphic from a description, or mentions DALL·E / gpt-image / OpenAI image generation. Self-contained: reads the API key from its own .env.
---

# OpenAI Image

Generate an image from a prompt and save it as PNG. One self-contained Node script, no project dependencies.

## Quick start

```bash
node ~/.claude/skills/openai-image/scripts/generate.mjs \
  --prompt "Tropical palm leaf, watercolor, isolated on transparent background, no shadow" \
  --out ./palm-leaf.png \
  --transparent
```

Without `--transparent`, the higher-quality `gpt-image-2` is used automatically:

```bash
node ~/.claude/skills/openai-image/scripts/generate.mjs \
  --prompt "Caribbean beach bar at golden hour, warm watercolor" \
  --out ./hero.png \
  --size 1536x1024
```

## How it works

- **Model auto-selection:** `--transparent` ⇒ `gpt-image-1` (only model with alpha support); otherwise ⇒ `gpt-image-2` (higher quality, 1K/2K/4K, multilingual text). Override with `--model`.
- **API key:** resolved from `OPENAI_API_KEY` (shell env) → `<skill>/.env` → `./.env`. The key lives in `<skill>/.env`, which is gitignored and never committed.
- **Robustness:** transient errors (HTTP 429 / 5xx / network) are retried with exponential backoff (up to 4 attempts). Fatal 4xx errors print the API body and exit.

## Options

| Flag | Default | Notes |
|---|---|---|
| `--prompt <text>` | — | **Required.** |
| `--out <path>` | `./openai-image-<ts>.png` | Created recursively. |
| `--model <name>` | auto | `gpt-image-1` or `gpt-image-2`. |
| `--size <WxH>` | `1024x1024` | e.g. `1536x1024`, `1024x1536`, `auto`. |
| `--quality <level>` | `high` | `low`/`medium`/`high`/`auto`. |
| `--transparent` | off | Forces `gpt-image-1`. |
| `--n <count>` | `1` | `>1` appends `-1`, `-2`, … to `--out`. |
| `--dry-run` | off | Resolve config + prompt, no API call (free). |

## Prompt tips

- Transparent assets: add `isolated on transparent background, no shadow, no backdrop`.
- Be explicit about style (e.g. `watercolor`, `flat vector`, `photorealistic`) for consistency.
- Use `--dry-run` first to confirm the resolved model/size without spending a credit.

## Setup (first use)

If `<skill>/.env` is missing, create it with one line:

```
OPENAI_API_KEY=sk-…
```

See [`.env.example`](.env.example).
