# MOTION-DESIGN.md template

Copy this into the project as `MOTION-DESIGN.md` (repo root, alongside other domain docs) the first time `motion-graphics-director` runs on that project. Fill in every section during the step-2 interview; don't leave placeholders in the saved file — a missing value here means the next graphic falls back to generic AI defaults.

```markdown
# Motion Design System

Established: <date>. Reused by every `motion-graphics-director` run in this project — don't recreate it per video.

## Typography

- Primary/display font: <name> — source: <brand site URL, or Fonts In Use / Fontshare / Google Fonts link>
- Body font: <name> — source: <...>
- Never use: Inter (or whatever the project's AI-default was defaulting to before this doc existed)

## Color palette

Chosen via the `dataviz` skill's color formula/validator on <date>. Don't hand-edit these values without rerunning that skill.

- Categorical: <hex list>
- Sequential/diverging (if used): <hex list or scale name>
- Light/dark handling: <how the palette adapts — e.g. same hues, adjusted lightness>

## Icon pack / motion assets (optional)

- Icon set: <name/source, or "none — ask before adding one">
- Lottie library/account: <name/source, or "none">

## Notes

<Anything else a future run needs to stay consistent — e.g. a logo lockup rule, a motion timing convention, a "never do X" from past feedback.>
```
