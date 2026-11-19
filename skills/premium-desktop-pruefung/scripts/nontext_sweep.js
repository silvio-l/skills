// Collect raw inputs for WCAG 1.4.11 (non-text contrast) of interactive controls; probe.py
// nontext does the compositing. Same use as contrast_sweep.js (a page.evaluate expression).
// No clicks; the only DOM change is a temporary probe element that resolves the canvas colour.
//
// For every visible control it records its own background, opacity and borders, plus the
// ancestor chain (from <html> to the parent) that forms the adjacent background. One state per
// sweep: hover, focus, checked and error states need their own capture.
(() => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const cache = new Map();
  const clamp = (x, hi) => Math.max(0, Math.min(hi, x));
  const rgba = (value) => {
    if (cache.has(value)) return cache.get(value);
    let out;
    const m = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/.exec(value);
    if (m) {
      const a = m[4] === undefined ? 1 : m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
      out = [clamp(+m[1], 255), clamp(+m[2], 255), clamp(+m[3], 255), clamp(a, 1)];
    } else {
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
  const probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;width:0;height:0;background-color:Canvas';
  document.documentElement.appendChild(probe);
  const canvasColor = rgba(getComputedStyle(probe).backgroundColor);
  probe.remove();
  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    else if (typeof el.className === 'string' && el.className.trim()) s += '.' + el.className.trim().split(/\s+/)[0];
    return s;
  };
  const layer = (cs, e) => ({
    element: describe(e),
    background: rgba(cs.backgroundColor),
    opacity: Number(cs.opacity),
    background_image: cs.backgroundImage !== 'none',
    filter: cs.filter !== 'none' || (cs.backdropFilter && cs.backdropFilter !== 'none'),
    blend: cs.mixBlendMode !== 'normal',
  });
  const selector = 'button, input:not([type=hidden]), select, textarea, [role=button], [role=checkbox], [role=radio], '
    + '[role=switch], [role=slider], [role=tab], [role=textbox], [role=combobox], [role=searchbox], [role=spinbutton], '
    + '[contenteditable=""], [contenteditable=true]';
  const items = [];
  for (const el of document.querySelectorAll(selector)) {
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (cs.visibility !== 'visible' || cs.display === 'none' || rect.width < 2 || rect.height < 2) continue;
    const chain = [];
    let invisible = Number(cs.opacity) === 0;
    for (let e = el.parentElement; e; e = e.parentElement) {
      const pcs = getComputedStyle(e);
      if (Number(pcs.opacity) === 0) invisible = true;
      chain.unshift(layer(pcs, e));
    }
    if (invisible) continue;
    const borders = ['top', 'right', 'bottom', 'left'].map((side) => ({
      side,
      width_px: parseFloat(cs.getPropertyValue('border-' + side + '-width')) || 0,
      style: cs.getPropertyValue('border-' + side + '-style'),
      color: rgba(cs.getPropertyValue('border-' + side + '-color')),
    }));
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || '';
    const type = tag === 'input' ? (el.getAttribute('type') || 'text').toLowerCase() : '';
    items.push({
      element: describe(el),
      role: role || (tag === 'input' ? 'input:' + type : tag),
      label: (el.getAttribute('aria-label') || el.textContent || el.getAttribute('placeholder') || '').replace(/\s+/g, ' ').trim().slice(0, 60),
      editable: el.isContentEditable,
      has_text: Boolean((el.textContent || '').trim()) || (tag === 'input' && ['button', 'submit', 'reset'].includes(type)),
      // Checkboxes, radios, sliders, colour/file pickers and selects keep their platform look while
      // appearance is auto, so their computed borders say nothing about what is drawn. Text fields
      // and buttons drop the native look once the author styles a border or background; until then
      // they keep the user-agent inset/outset border, whose computed colour is not what is painted.
      native_appearance: cs.appearance !== 'none' && (tag === 'select'
        || ['checkbox', 'radio', 'range', 'color', 'file'].includes(type)
        || ['inset', 'outset'].includes(cs.borderTopStyle) && cs.borderTopStyle === cs.borderBottomStyle),
      box_shadow: cs.boxShadow !== 'none',
      outline: cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0,
      disabled: Boolean(el.closest(':disabled, [aria-disabled="true"], [inert]')),
      in_viewport: rect.bottom > 0 && rect.top < innerHeight && rect.right > 0 && rect.left < innerWidth,
      control: { ...layer(cs, el), borders },
      chain,
    });
  }
  return {
    url: location.href,
    viewport: [innerWidth, innerHeight],
    device_pixel_ratio: devicePixelRatio,
    canvas: canvasColor[3] === 1 ? canvasColor : [255, 255, 255, 1],
    items,
  };
})()
