---
name: openai-image
description: Generate images from a text prompt via the OpenAI Image API (gpt-image-1/2), writing PNGs to disk; auto-picks the model. Use when the user wants to create, generate, or render an image, icon, or asset, or mentions DALL·E / gpt-image.
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
- **API key:** resolved from `OPENAI_API_KEY` (shell env) → `~/.config/openai-image/.env` → `<skill>/.env` → `./.env`. Keep the key in `~/.config/openai-image/.env` — it lives outside the skill folder, so `skills update` (which wipes and re-writes the skill dir) never deletes it. `<skill>/.env` still works but is erased on every update.
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
- If the request is vague (no style, size, or output path), ask before spending a credit — or run `--dry-run` and confirm the resolved settings with the user first.

## Setup (first use)

Store your key in `~/.config/openai-image/.env` — outside the skill folder, so it survives `skills update`:

```
mkdir -p ~/.config/openai-image
printf 'OPENAI_API_KEY=sk-…\n' > ~/.config/openai-image/.env
```

`<skill>/.env` and a `./.env` in the current directory still work as fallbacks, but the skill dir is wiped on every update — prefer the config path. See [`.env.example`](.env.example).
