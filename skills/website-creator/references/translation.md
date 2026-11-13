# Translation

German is the source. Other locales are written from it afterwards, as if a native copywriter had written the page for that market.

## Process

1. Freeze the German copy first (after decision 1 and the build). Translating a moving target doubles the work.
2. Translate per section, not per key: read the whole German section, then write the target section, then split it back into keys. Keys stay identical across locales.
3. Re-check each locale against the TASTE.md rules that are language-independent: concrete over abstract, no filler, CTAs that say what happens, no unverifiable claims.
4. Read the result in the rendered page at 375px and 1440px: line breaks, button widths, headline length (English is ~10–20 % shorter, French ~15 % longer).

## Naturalness check

For every locale, answer in the report:

- Would a native speaker notice it is translated? Mark sentences that keep German word order, German compound nouns, or German formality.
- Idioms: replaced by local equivalents, not translated literally.
- Address: German "du/Sie" maps to the target market's convention (English "you"; French usually "vous" for products, "tu" only for clearly casual brands; Spanish "tú" is common for consumer apps).
- Typography: quotes (“…” en, « … » fr with thin spaces, „…“ de), decimal separators, date formats, currency position.
- Terms: product UI terms match the app's own localization exactly.

## Mechanics

- Use the project's i18n system; no hardcoded strings in components.
- `<html lang>` per locale, `hreflang` alternates, localized `<title>`, meta description, OG text and image alt.
- Locale files are linted too (`slop_lint.py` checks buzzwords and patterns in German and English copy).
