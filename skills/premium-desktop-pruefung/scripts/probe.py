#!/usr/bin/env python3
"""Read-only HTML discovery, opaque sRGB contrast and rendered text/non-text contrast sweeps; not a conformance scanner."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re


def contrast(fg, bg):
    def lum(color):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('expected opaque sRGB #RRGGBB; composite transparency first')
        rgb = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
        linear = [x/12.92 if x <= .04045 else ((x+.055)/1.055)**2.4 for x in rgb]
        return sum(a*b for a,b in zip(linear, (.2126, .7152, .0722)))
    a,b = sorted((lum(fg), lum(bg)))
    ratio = (b+.05)/(a+.05)
    return dict(ratio=ratio, normal_text_AA=ratio>=4.5, large_text_AA=ratio>=3,
                nontext_threshold=ratio>=3,
                limitation='Threshold measurement only. Verify rendered colors, text size/weight, exemptions and all states.')


def _premultiplied(color):
    r, g, b, a = color
    if not all(isinstance(x, (int, float)) for x in color) or not 0 <= a <= 1:
        raise ValueError('colors must be [r, g, b, alpha] with alpha 0..1')
    return [r / 255 * a, g / 255 * a, b / 255 * a, a]


def _over(top, bottom):
    return [t + b * (1 - top[3]) for t, b in zip(top, bottom)]


def _hex(premultiplied):
    return '#' + ''.join('%02x' % max(0, min(255, round(c * 255))) for c in premultiplied[:3])


def composite(chain, canvas, text=None):
    """Render one pixel through the ancestor chain (outermost first), as browsers do.

    Each element paints its background, then its descendants, and the whole group is then
    faded by the element's own opacity. The text sits inside the innermost group, so every
    ancestor opacity fades text and backgrounds together."""
    content = _premultiplied(text) if text else [0, 0, 0, 0]
    for layer in reversed(chain):
        content = [c * layer['opacity'] for c in _over(content, _premultiplied(layer['background']))]
    result = _over(content, _premultiplied(canvas))
    if abs(result[3] - 1) > 1e-6:
        raise ValueError('canvas must be opaque')
    return _hex(result)


def sweep(path):
    """Evaluate output of scripts/contrast_sweep.js; flags what a DOM chain cannot resolve."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    canvas = data.get('canvas') or [255, 255, 255, 1]
    rows, counts = [], {'fail': 0, 'pass': 0, 'uncertain': 0, 'exempt-candidate': 0}
    for item in data['items']:
        foreground = composite(item['chain'], canvas, item['color'])
        background = composite(item['chain'], canvas)
        measured = contrast(foreground, background)
        bold = item.get('font_weight', 400) >= 700
        large = item['font_size_px'] >= 24 or (bold and item['font_size_px'] >= 18.66)
        required = 3 if large else 4.5
        reasons = [name for name, flag in (
            ('background image or gradient', any(l.get('background_image') for l in item['chain'])),
            ('filter or backdrop filter', any(l.get('filter') for l in item['chain'])),
            ('blend mode', any(l.get('blend') for l in item['chain'])),
            ('text shadow', item.get('text_shadow'))) if flag]
        if item.get('disabled'):
            status = 'exempt-candidate'  # inactive components are exempt from 1.4.3; verify they are truly inactive
        elif reasons:
            status = 'uncertain'
        else:
            status = 'pass' if measured['ratio'] >= required else 'fail'
        counts[status] += 1
        rows.append(dict(text=item['text'], element=item['element'], foreground=foreground, background=background,
                         ratio=round(measured['ratio'], 2), required=required, large=large, status=status,
                         in_viewport=item.get('in_viewport', True), uncertain=reasons))
    order = {'fail': 0, 'uncertain': 1, 'exempt-candidate': 2, 'pass': 3}
    rows.sort(key=lambda r: (order[r['status']], r['ratio']))
    return dict(url=data.get('url'), viewport=data.get('viewport'), color_scheme=data.get('color_scheme'),
                canvas=_hex(_premultiplied(canvas)), skipped_hidden=data.get('skipped', {}), counts=counts, items=rows,
                limitation='Composites DOM ancestors only. Overlapping non-ancestor layers, images, filters, '
                           'shadows and anti-aliasing need a pixel check of a screenshot; one state per sweep.')


NON_FIELD_INPUTS = ('button', 'submit', 'reset', 'image', 'checkbox', 'radio', 'range', 'color', 'file', 'hidden')
NATIVE_HINT = 'native control: the platform draws its boundary; check a screenshot'


def nontext(path):
    """Evaluate output of scripts/nontext_sweep.js against WCAG 1.4.11 (3:1 for control boundaries).

    A control passes when its fill or a visible border differs from the adjacent background by
    at least 3:1. Without such an indicator, a text field fails (its boundary is what identifies
    it); a control that shows its text label needs judgement (text-only buttons can conform),
    so it is reported as `review`, never as pass."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    canvas = data.get('canvas') or [255, 255, 255, 1]
    rows, counts = [], {'fail': 0, 'review': 0, 'pass': 0, 'uncertain': 0, 'exempt-candidate': 0}
    for item in data['items']:
        control = item['control']
        group = item['chain'] + [{**control, 'borders': None}]
        adjacent = composite(item['chain'], canvas)
        fill = composite(group, canvas)
        indicators = [dict(part='fill', color=fill, ratio=round(contrast(fill, adjacent)['ratio'], 2))]
        for border in control['borders']:
            if border['width_px'] >= 1 and border['style'] not in ('none', 'hidden') and border['color'][3] > 0:
                color = composite(group, canvas, border['color'])
                indicators.append(dict(part='border-' + border['side'], color=color, width_px=border['width_px'],
                                       ratio=round(contrast(color, adjacent)['ratio'], 2)))
        best = max(indicators, key=lambda i: i['ratio'])
        reasons = [name for name, flag in (
            ('background image or gradient', any(l.get('background_image') for l in group)),
            ('filter or backdrop filter', any(l.get('filter') for l in group)),
            ('blend mode', any(l.get('blend') for l in group)),
            ('box shadow may form the boundary', item.get('box_shadow')),
            (NATIVE_HINT, item.get('native_appearance'))) if flag]
        # Fields identified by their boundary: every input that takes a value, selects drawn by the
        # author (appearance none) and editable regions, whatever text they already contain.
        textual = (item.get('editable') or item['role'] in ('textarea', 'select', 'textbox', 'searchbox', 'combobox', 'spinbutton')
                   or item['role'].startswith('input:') and item['role'][6:] not in NON_FIELD_INPUTS)
        if item.get('disabled'):
            status = 'exempt-candidate'  # inactive components are exempt from 1.4.11; verify they are truly inactive
        elif item.get('native_appearance'):
            status = 'uncertain'  # computed borders of a platform-drawn control are not what is painted
        elif best['ratio'] >= 3:
            status = 'pass'
        elif reasons:
            status = 'uncertain'
        elif item.get('has_text') and not textual:
            status = 'review'
        else:
            status = 'fail'
        counts[status] += 1
        rows.append(dict(element=item['element'], role=item['role'], label=item.get('label', ''), adjacent=adjacent,
                         best=best, indicators=indicators, status=status, uncertain=reasons,
                         in_viewport=item.get('in_viewport', True)))
    order = {'fail': 0, 'uncertain': 1, 'review': 2, 'exempt-candidate': 3, 'pass': 4}
    rows.sort(key=lambda r: (order[r['status']], r['best']['ratio']))
    return dict(url=data.get('url'), viewport=data.get('viewport'), counts=counts, items=rows,
                limitation='Default state only and DOM ancestors only: focus indicators (2.4.7/2.4.11), hover, checked '
                           'and error states, icons, graphics and native controls need their own capture or a '
                           'screenshot pixel check.')


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements=[]
        self.stack=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag in ('a','button','input','select','textarea','dialog','form','iframe','canvas','video','audio') or any(k in attrs for k in ('role','tabindex','contenteditable')) or any(k.startswith('on') for k in attrs):
            self.elements.append(dict(tag=tag,line=self.getpos()[0],attributes=attrs))
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag,attrs)


def html(path):
    parser=Inventory()
    parser.feed(Path(path).read_text(encoding='utf-8'))
    return dict(elements=parser.elements,
                limitation='Discovery candidates only. Static HTML omits runtime routes, CSS visibility, shadow DOM, native controls and computed accessible names; no pass verdicts.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('contrast'); c.add_argument('foreground'); c.add_argument('background')
    h=sub.add_parser('html'); h.add_argument('path')
    w=sub.add_parser('sweep', help='evaluate JSON captured with scripts/contrast_sweep.js'); w.add_argument('path')
    n=sub.add_parser('nontext', help='evaluate JSON captured with scripts/nontext_sweep.js (WCAG 1.4.11)'); n.add_argument('path')
    a=p.parse_args()
    try:
        result=(contrast(a.foreground,a.background) if a.command=='contrast' else html(a.path) if a.command=='html'
                else sweep(a.path) if a.command=='sweep' else nontext(a.path))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(2,str(exc)+'\n')

if __name__=='__main__':
    main()
