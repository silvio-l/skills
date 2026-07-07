# Code Patterns: Copy-Paste Starters

Self-contained snippets for the techniques referenced in [cool-craft.md](cool-craft.md). All are plain HTML/CSS/JS — no external libraries, no external hosts — so they drop straight into an `Artifact`-tool build without violating its CSP (everything inline). Where a heavier library genuinely earns its cost (complex scroll choreography, physics-based motion), that's noted instead of pretending a hand-rolled version is equivalent.

Each pattern is deliberately minimal — a starting point to adapt to the chosen direction (see the direction library in `cool-craft.md`), not a finished component.

## Token starter

Tokens before components — see the "design system first" principle in `SKILL.md`. Three tiers: primitive → semantic → component, matching the convention already used by `flutter-design-language`.

```css
:root {
  /* primitive */
  --color-ink-900: #14110f;
  --color-ink-100: #f5f1ea;
  --color-accent-500: #c65d34; /* pick per direction — this is a placeholder, not a default */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 16px;
  --space-4: 24px;
  --space-5: 40px;
  --space-6: 64px;
  --radius-sm: 4px;
  --radius-md: 12px;
  --font-display: "Bricolage Grotesque", serif; /* swap per chosen direction */
  --font-body: "DM Sans", sans-serif;

  /* semantic — what the primitives mean */
  --color-surface: var(--color-ink-100);
  --color-text: var(--color-ink-900);
  --color-action: var(--color-accent-500);
}

:root[data-theme="dark"] {
  --color-surface: var(--color-ink-900);
  --color-text: var(--color-ink-100);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --color-surface: var(--color-ink-900);
    --color-text: var(--color-ink-100);
  }
}
```

## Bento grid skeleton

Asymmetric, one dominant cell — the antidote to four identical cards.

```css
.bento {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: minmax(120px, auto);
  gap: var(--space-3);
}
.bento > .cell-hero { grid-column: span 2; grid-row: span 2; }
.bento > .cell-wide { grid-column: span 2; }
.bento > .cell { grid-column: span 1; }

@media (max-width: 640px) {
  .bento { grid-template-columns: repeat(2, 1fr); }
  .bento > .cell-hero { grid-column: span 2; }
}
```

## Staggered reveal on scroll

Library-free, using `IntersectionObserver`. For more elaborate scroll choreography (scrubbed timelines, pinned sections), GSAP's ScrollTrigger is the actual right tool — reach for it deliberately rather than fighting this toward something it isn't.

```html
<div class="reveal-group">
  <div class="reveal" style="--delay: 0ms">First</div>
  <div class="reveal" style="--delay: 80ms">Second</div>
  <div class="reveal" style="--delay: 160ms">Third</div>
</div>

<style>
.reveal {
  opacity: 0;
  transform: translateY(16px);
  transition: opacity 0.5s ease, transform 0.5s ease;
  transition-delay: var(--delay, 0ms);
}
.reveal.is-visible { opacity: 1; transform: translateY(0); }
</style>

<script>
const io = new IntersectionObserver((entries) => {
  entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add('is-visible'); });
}, { threshold: 0.2 });
document.querySelectorAll('.reveal').forEach((el) => io.observe(el));
</script>
```

## Custom cursor follow

Subtle by default — a cursor gimmick that lags badly or obscures content is worse than the system cursor.

```html
<div class="cursor-dot"></div>
<style>
.cursor-dot {
  position: fixed; top: 0; left: 0; width: 8px; height: 8px;
  border-radius: 50%; background: var(--color-action);
  pointer-events: none; z-index: 9999;
  transform: translate(-50%, -50%);
  transition: transform 0.08s ease-out;
}
</style>
<script>
const dot = document.querySelector('.cursor-dot');
document.addEventListener('mousemove', (e) => {
  dot.style.left = e.clientX + 'px';
  dot.style.top = e.clientY + 'px';
});
</script>
```

## Smooth scroll / parallax (CSS-only)

`scroll-behavior` plus a CSS-only parallax layer — no JS needed for the common case.

```css
html { scroll-behavior: smooth; }

.parallax-container {
  perspective: 1px;
  height: 100vh;
  overflow-x: hidden;
  overflow-y: auto;
}
.parallax-back {
  transform: translateZ(-1px) scale(2);
}
```

Respect reduced-motion always:

```css
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .reveal { transition: none; opacity: 1; transform: none; }
}
```

## Microinteraction: tactile button press

The felt physicality that separates "OK" from "exceptional" per `cool-craft.md`'s web-vs-app split.

```css
.btn {
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}
.btn:active {
  transform: scale(0.97);
  box-shadow: 0 1px 2px rgba(0,0,0,0.15);
}
```

## Microinteraction: toggle with real state feedback

```html
<button class="toggle" role="switch" aria-checked="false">
  <span class="toggle-thumb"></span>
</button>
<style>
.toggle {
  width: 44px; height: 24px; border-radius: 999px;
  background: var(--color-ink-100); border: none; padding: 2px;
  transition: background 0.2s ease;
}
.toggle[aria-checked="true"] { background: var(--color-action); }
.toggle-thumb {
  display: block; width: 20px; height: 20px; border-radius: 50%;
  background: white; transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.toggle[aria-checked="true"] .toggle-thumb { transform: translateX(20px); }
</style>
<script>
document.querySelector('.toggle').addEventListener('click', function () {
  const checked = this.getAttribute('aria-checked') === 'true';
  this.setAttribute('aria-checked', String(!checked));
});
</script>
```

## Section / page transition

A simple fade-through for section changes within a single-page artifact.

```css
.section {
  opacity: 0;
  animation: section-in 0.4s ease forwards;
}
@keyframes section-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
```

## Flutter translation

Same patterns, native Flutter equivalents — feed these through `flutter-design-language`'s token pipeline first, not as raw values:

| Web pattern | Flutter equivalent |
|---|---|
| Token starter (CSS custom properties) | `design/tokens.json` three-tier system → `ThemeData` extensions, per `flutter-design-language` |
| Bento grid | `StaggeredGrid` (`flutter_staggered_grid_view`) or a hand-built `CustomMultiChildLayout` for full control |
| Staggered reveal on scroll | `AnimatedList` / `SliverAnimatedList`, or `flutter_animate`'s `.animate().fadeIn(delay: ...)` chained per item |
| Tactile button press | `AnimatedScale` on tap-down/tap-up, or `GestureDetector` with an `AnimationController` driving a `ScaleTransition` |
| Toggle with spring feedback | `AnimatedContainer` with a `Curves.elasticOut`-style curve, or `flutter_animate`'s built-in spring curves |
| Section transition | `AnimatedSwitcher` with a custom `transitionBuilder` |

`flutter_animate` is the closest Flutter analog to reaching for framer-motion on web — reasonable to depend on rather than hand-rolling every `AnimationController` when the interaction is standard.
