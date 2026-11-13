# Craft checklist

What separates a finished page from a generated one. The scripts catch the mechanical part; look at the screenshots for the rest.

## Typography

- Body 16–20px, line-height 1.5–1.7, measure 60–75 characters. Headings tighter (1.05–1.2).
- Scale from DESIGN.md; at least 1.25× between display and body roles so hierarchy is visible.
- `text-wrap: balance` on headings, `text-wrap: pretty` on paragraphs. No orphan word in the hero headline at any width.
- German: `hyphens: auto` with `lang="de"` for narrow columns; never `text-align: justify` without hyphenation.
- Real quotation marks („…“), en dash for ranges (9–17 Uhr), non-breaking space in "z. B.", "100 %", units.
- Load only the weights used; `font-display: swap`; self-host or Google Fonts with `preconnect`. Subset for German (latin + latin-ext).

## Layout

- Spacing from the scale, with rhythm: tight inside groups, generous between sections. Space above a heading > space below.
- No horizontal scroll at 320px. Body text never touches the viewport edge (min 16px gutter).
- The first viewport shows what the product is and the main action, at 375×812 and 1440×900.
- Fewer containers: separate by space and type before reaching for boxes, borders and shadows. No cards in cards.

## Interaction

- Every interactive element has `data-testid`, a visible `:focus-visible` style, and ≥ 44×44px tap area on mobile.
- Links say where they go; buttons say what happens ("Kostenlos testen – ohne Kreditkarte", not "Mehr erfahren").
- Anchor links land below a sticky header (`scroll-margin-top`).
- Forms: labels, autocomplete, inline errors, success state; real backend or none. Errors via `aria-invalid` and `aria-describedby`, and the message says what happened, why, and what to do next.
- One primary action per screen; campaign landing pages reduce the navigation so it does not compete with it.
- Dialogs return focus to the element that opened them. No `tabindex` above 0.
- Loading states mirror the structure of what arrives (skeleton of the real layout), not a generic spinner block.

## Accessibility and semantics

- One `h1`, no skipped levels, landmarks (`header`, `nav`, `main`, `footer`), `<html lang>`.
- Alt text describes the content; decorative images `alt=""`.
- Contrast per DESIGN.md. Never convey meaning by color alone.

## Performance

- Hero image ≤ 200 KB, AVIF/WebP with fallback, explicit `width`/`height`, `fetchpriority="high"` for the LCP image, `loading="lazy"` below the fold.
- No layout shift from fonts or images. JS only for what needs it.
- Meta: title, description, Open Graph image (1200×630), canonical, favicon set.

## Polish loop

After the checks are clean, look at the 1440 and 375 screenshots and answer honestly:

0. Five-second test: shown the first viewport for five seconds, can someone say what the product is, for whom, and what to click?
1. Would a visitor describe the page afterwards in one sentence — and is that sentence about this product?
2. Is the centerpiece the loudest thing, and does it show the product rather than decorate it?
3. Does the skeleton (text greyed out) have a peak, or is it a column of equal blocks?
4. Does every element react to pointer and touch (`references/liveliness.md`)?
5. Is the color posture from the chosen direction actually on screen, or did it drift toward neutral?
6. Is there a screen that only explains in text what could be shown?
7. Is any section there out of habit (logo wall, three cards, FAQ nobody asked for)?
8. What would a top studio change with three more days?

Fix the three worst answers, render again, repeat while a round still finds something substantial. Rebuild a weak part instead of patching it.

## Copy on the page

- TASTE.md checklist passes. Every number and claim has a source.
- Counts (users, downloads, ratings) only when verified, with their date; never a "Join 10,000+" template. Missing facts stay visible placeholders for the user to fill, never invented — and sample data avoids suspiciously round numbers.
- Same term for the same thing everywhere (UI labels match the app).
- Legal pages (Impressum, Datenschutz) linked in the footer for German sites.
