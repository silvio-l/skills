// Collect raw contrast inputs from a rendered page; probe.py sweep does the compositing.
// Use as a Playwright evaluate function, e.g. `page.evaluate(fs.readFileSync(path, 'utf8'))`,
// or paste into any tool that evaluates a page expression. Read-only: no clicks, no mutation.
//
// For every visible text node it records the text color and the ancestor chain from <html>
// down to the text's element, each with background color and own opacity. Opacity must be
// applied to the whole subtree (background AND text) of each element; folding it into the
// text color only overstates the contrast of faded/disabled controls.
(() => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const cache = new Map();
  // Normalize any CSS color syntax (rgb, hsl, oklch, color()) to 8-bit sRGB + alpha.
  const rgba = (value) => {
    if (cache.has(value)) return cache.get(value);
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = 'rgba(0, 0, 0, 0)';
    ctx.fillStyle = value;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    // Canvas stores premultiplied alpha; undo it for the channels (exact for opaque colors).
    const out = a ? [Math.round(r * 255 / a), Math.round(g * 255 / a), Math.round(b * 255 / a), a / 255] : [0, 0, 0, 0];
    cache.set(value, out);
    return out;
  };
  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    else if (typeof el.className === 'string' && el.className.trim()) s += '.' + el.className.trim().split(/\s+/)[0];
    return s;
  };
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
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      chain.unshift({
        element: describe(e),
        background: rgba(cs.backgroundColor),
        opacity: Number(cs.opacity),
        background_image: cs.backgroundImage !== 'none',
        filter: cs.filter !== 'none' || (cs.backdropFilter && cs.backdropFilter !== 'none'),
        blend: cs.mixBlendMode !== 'normal',
      });
    }
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
    canvas: [255, 255, 255, 1], // default canvas; a root/body background paints over it as a chain layer
    items,
  };
})()
