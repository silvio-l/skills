// Collect raw contrast inputs from a rendered page; probe.py sweep does the compositing.
// Use as a Playwright evaluate function, e.g. `page.evaluate(fs.readFileSync(path, 'utf8'))`,
// or paste into any tool that evaluates a page expression. No clicks; the only DOM change is a
// temporary probe element that resolves the canvas colour and is removed immediately.
//
// For every visible text node it records the text color and the ancestor chain from <html>
// down to the text's element, each with background color and own opacity. Opacity must be
// applied to the whole subtree (background AND text) of each element; folding it into the
// text color only overstates the contrast of faded/disabled controls.
//
// Visually hidden text (opacity 0 in the chain, clipped screen-reader-only text, 1px boxes,
// off-screen positioning) is skipped and counted in `skipped`, never silently dropped.
// aria-hidden text is kept: it is still visible, and 1.4.3 applies to what users see.
(() => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const cache = new Map();
  const clamp = (x, hi) => Math.max(0, Math.min(hi, x));
  // Normalize any CSS color syntax to 8-bit-range sRGB + alpha.
  const rgba = (value) => {
    if (cache.has(value)) return cache.get(value);
    let out;
    // Computed colors usually serialize as rgb()/rgba() with exact components; parse those directly.
    const m = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/.exec(value);
    if (m) {
      const a = m[4] === undefined ? 1 : m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
      out = [clamp(+m[1], 255), clamp(+m[2], 255), clamp(+m[3], 255), clamp(a, 1)];
    } else {
      // Other syntaxes (oklch, color(), hsl): let the canvas convert. ImageData is already
      // un-premultiplied; dividing by alpha again would push channels past 255.
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = 'rgba(0, 0, 0, 0)';
      ctx.fillStyle = value;
      ctx.fillRect(0, 0, 1, 1);
      const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
      out = [r, g, b, a / 255];
    }
    cache.set(value, out);
    return out;
  };
  // The canvas behind <html> follows the page's color scheme (dark mode paints a dark canvas).
  const probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;width:0;height:0;background-color:Canvas;color:CanvasText';
  document.documentElement.appendChild(probe);
  const canvasColor = rgba(getComputedStyle(probe).backgroundColor);
  probe.remove();
  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    else if (typeof el.className === 'string' && el.className.trim()) s += '.' + el.className.trim().split(/\s+/)[0];
    return s;
  };
  const clipped = (cs, rect) => {
    if (cs.clip && /rect\(\s*0(px)?[ ,]+0(px)?[ ,]+0(px)?[ ,]+0(px)?\s*\)/.test(cs.clip)) return true;
    if (cs.clipPath && /inset\(\s*(50%|100%)/.test(cs.clipPath)) return true;
    return cs.overflow === 'hidden' && rect.width <= 1 && rect.height <= 1;
  };
  const skipped = { opacity_zero: 0, clipped_or_1px: 0, off_screen: 0 };
  const items = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent.replace(/\s+/g, ' ').trim();
    const el = node.parentElement;
    if (!text || !el) continue;
    const style = getComputedStyle(el);
    if (style.visibility !== 'visible' || style.display === 'none') continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const box = range.getBoundingClientRect();
    if (box.width < 1 || box.height < 1) continue;
    const chain = [];
    let hidden = '';
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (Number(cs.opacity) === 0) hidden = hidden || 'opacity_zero';
      else if (clipped(cs, e.getBoundingClientRect())) hidden = hidden || 'clipped_or_1px';
      chain.unshift({
        element: describe(e),
        background: rgba(cs.backgroundColor),
        opacity: Number(cs.opacity),
        background_image: cs.backgroundImage !== 'none',
        filter: cs.filter !== 'none' || (cs.backdropFilter && cs.backdropFilter !== 'none'),
        blend: cs.mixBlendMode !== 'normal',
      });
    }
    const scroll = document.scrollingElement || document.documentElement;
    if (!hidden && (box.right + scrollX < 0 || box.bottom + scrollY < 0 || box.left + scrollX > scroll.scrollWidth + 1000)) {
      hidden = 'off_screen';
    }
    if (hidden) { skipped[hidden] += 1; continue; }
    items.push({
      text: text.slice(0, 80),
      element: describe(el),
      color: rgba(style.color),
      font_size_px: parseFloat(style.fontSize),
      font_weight: Number(style.fontWeight) || 400,
      disabled: Boolean(el.closest(':disabled, [aria-disabled="true"], [inert]')),
      text_shadow: style.textShadow !== 'none',
      in_viewport: box.bottom > 0 && box.top < innerHeight && box.right > 0 && box.left < innerWidth,
      chain,
    });
  }
  return {
    url: location.href,
    viewport: [innerWidth, innerHeight],
    device_pixel_ratio: devicePixelRatio,
    color_scheme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
    canvas: canvasColor[3] === 1 ? canvasColor : [255, 255, 255, 1],
    skipped,
    items,
  };
})()
