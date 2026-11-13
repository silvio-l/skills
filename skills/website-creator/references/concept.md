# Concept image

Before the three directions are written, an image model draws its own picture of the page. The assistant's directions tend to drift toward the same safe defaults; a picture made from the reference board by a different model is a second opinion that pulls them somewhere else. The concept image is input for the direction phase, not a deliverable and not a mockup to copy.

## Route, in this order

Run `python3 S/scripts/concept.py check`. It reports the first available route:

1. **Codex CLI on the subscription** (`route: codex`). Available only when `codex login status` reports a ChatGPT login. The script removes every API-key variable from the call's environment and refuses an API-key login: there is no paid-key path, ever. A quota that is used up shows as "no image produced" (exit 3); then take the next route.
2. **Local image model** (`route: local`), only if one is already installed (e.g. FLUX.2 [klein] via `mflux-generate` on Apple Silicon). Never download a model of several GB without asking the user first.
3. **HTML mockup by the assistant** (`route: mockup`). A throwaway first-viewport sketch in `.website-creator/sketches/concept.html`, rendered at 1440×900 with `pwc --headless` and saved as an image. Build it fast and loose; it explores, it is not one of the three directions.
4. **Gap** (`route: gap`). If none of these works, record why and carry on. The run never stops at this step; the gap is named in the report.

## Brief for the image model

Write the description into a file (`.website-creator/concept/prompt.txt`) in English, about 80–150 words, in this order:

1. What the product is and does, in one sentence, and for whom.
2. The page mode and the one thing the first viewport must make clear.
3. The strongest principle from each of two or three reference-board images (named, not copied).
4. Material and color posture you want explored, and one you want avoided (the model defaults in `references/direction.md`).
5. The real headline from the copy skeleton, if decision 1 is taken.

Attach the reference board's screenshots (competitors and gallery examples, at most about six) with `--ref`. Then:

```bash
python3 S/scripts/concept.py codex --prompt-file .website-creator/concept/prompt.txt --ref <img> [--ref <img> …] [--count 2]
```

The images land in `.website-creator/concept/` together with `concept.md` (route, date, prompt, references, files). For a fallback image: `concept.py record --route local|mockup --file <img> --tool "<what made it>"`; for the gap: `concept.py record --route gap --reason "<why>"`.

## Using it

- Look at the image yourself and write two or three lines into `concept.md` under `## Taken`: what it does that the assistant would not have done (a color field, a scale jump, a material, a crop).
- At least one of the three directions takes something visible from the concept image and says so under "References" (`references/direction.md`). The image never becomes a direction one to one.
- Text, logos and UI in a generated image are invented; never take copy, claims or brand marks from it.
- A concept image that ends up on the page counts as generated imagery: provenance, prompt and date in `.website-creator/images.md` and the "KI-generiert" credit (`references/images.md`).

## Gate

`run.py` checks `concept`: `concept.md` exists with a known route, and the listed image is in the folder, or the route is `gap` with a reason of at least ten characters. A gap passes the gate on purpose; it is reported, not waived.
