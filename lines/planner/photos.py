"""Listing photos for planners: 2700x2025 HTML scenes built from the brief's photo plan and the listing's photo copy,
screenshotted by shoot.js. Scenes: hero, grid (what's inside), page (one page with headline and points), how (3 steps)."""
import os
from fonts import faces
from gen import resolve_theme, motif, esc, MONTHS


def page_names(brief):
    names = {'cover': 'Cover', 'index': 'Contents', 'year': 'Year at a glance'}
    for sec in brief['spec'].get('sections', []):
        if sec.get('anchor') and sec.get('label'):
            names[sec['anchor']] = sec['label']
        if sec.get('module') == 'reading_month':
            names.update({f'm{i + 1:02d}': m for i, m in enumerate(MONTHS)})
    return names


def page_name(a, names):
    import re as _re
    if a in names:
        return names[a]
    if _re.fullmatch(r'b\d{3}', a): return f'Book {int(a[1:])}'
    if _re.fullmatch(r'[a-z]+\d', a) and a[:-1] in names: return f'{names[a[:-1]]} page {a[-1]}'
    if _re.fullmatch(r'd\d{4}|u\d{3}', a): return 'Day page'
    if _re.fullmatch(r'm\d{2}h', a): return 'Habit tracker'
    if _re.fullmatch(r'm\d{2}', a): return 'Month'
    if _re.fullmatch(r'w\d{2}', a): return 'Week'
    if _re.fullmatch(r'hs\d{2}', a): return 'Head start month'
    if _re.fullmatch(r'hs\d{4}', a): return 'Head start day'
    if _re.fullmatch(r'hsw\d{2}', a): return 'Head start week'
    return a


FRAMES = {  # device frame: 'dark' (generic tablet) or 'eink' (light gray e-ink tablet, for reMarkable files)
    'dark': dict(bg='#1c1c21', pad=.032, shadow='0 40px 80px rgba(30,25,40,.28),0 8px 18px rgba(30,25,40,.18)', edge=''),
    'eink': dict(bg='#d9d9d5', pad=.05, shadow='0 30px 60px rgba(0,0,0,.16),0 6px 14px rgba(0,0,0,.10)', edge='border:2px solid #c4c4bf;'),
}


def tablet(src, w, x, y, ratio, rot=0, z=1, caption='', frame='dark'):
    f = FRAMES[frame]
    pad = w * f['pad']
    cap = f'<div style="position:absolute;left:50%;bottom:-74px;transform:translateX(-50%);white-space:nowrap;font:600 36px var(--b);letter-spacing:.06em;text-transform:uppercase;opacity:.75">{caption}</div>' if caption else ''
    return (f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;transform:rotate({rot}deg);z-index:{z};'
            f'background:{f["bg"]};{f["edge"]}border-radius:{w * .045:.0f}px;padding:{pad:.0f}px;box-shadow:{f["shadow"]}">'
            f'<img src="{src}" style="width:100%;display:block;border-radius:{w * .01:.0f}px;aspect-ratio:{ratio}">{cap}</div>')


def steps_html(th, steps):
    return ''.join(f'<div style="display:flex;gap:26px;align-items:flex-start"><span style="flex:none;width:74px;height:74px;border-radius:50%;background:{th["ink"]};color:{th["paper"]};display:flex;align-items:center;justify-content:center;font:700 40px var(--b)">{n + 1}</span><div><p class="h" style="font-size:58px">{esc(a)}</p><p style="font-size:42px;color:{th["muted"]};line-height:1.3;margin-top:8px">{esc(b)}</p></div></div>' for n, (a, b) in enumerate(steps[:3]))


def crop_scene(th, c, pg, P, N, W, H, frame, head, pts, label):
    """Close-up view (style rule r013): pages shown large in a device that runs off the bottom edge of the photo, so the
    top of each page is readable at Etsy's zoom. One page: device on one side, copy on the other. Two pages: side by side
    under the headline. The caption names the page and sits above its device."""
    f = FRAMES[frame]
    cap = lambda a, x, y, w: f'<p style="position:absolute;left:{x}px;top:{y}px;width:{w}px;text-align:center;font:600 38px var(--b);letter-spacing:.06em;text-transform:uppercase;opacity:.8">{N(a)}</p>'
    if len(pg) == 1:
        tw = int(c.get('width', 1380)); tx = 150 if c.get('side', 'left') == 'left' else 2700 - 150 - tw
        dev = tablet(P(pg[0]), tw, tx, 200, f'{W}/{H}', 0, 1, '', frame)
        text_x = tx + tw + 130 if tx == 150 else 150
        tw_text = 2700 - 150 - text_x if tx == 150 else tx - 130 - 150
        extra = ''
        if c.get('steps'):
            extra = f'<div style="display:flex;flex-direction:column;gap:30px;margin-top:10px">{steps_html(th, c["steps"])}</div>'
        if c.get('panel'):
            extra = f'<div style="border:3px solid {th["line"]};border-radius:30px;padding:34px 40px;display:flex;flex-direction:column;gap:14px;background:{th["paper"]}">' + ''.join(f'<p style="font-size:44px;line-height:1.3"><b>{esc(k)}</b> {esc(v)}</p>' for k, v in c['panel']) + '</div>' + extra
        return (dev + cap(pg[0], tx, 120, tw) +
                f'<div style="position:absolute;left:{text_x}px;top:0;bottom:0;width:{tw_text}px;display:flex;flex-direction:column;justify-content:center;gap:34px">{label}<p class="h" style="font-size:{c.get("size", 110)}px">{head}</p>{pts}{extra}</div>')
    tw = 1150; gap = 2700 - 300 - 2 * tw
    devs = ''.join(tablet(P(a), tw, 150 + k * (tw + gap), 600, f'{W}/{H}', 0, 1, '', frame) + cap(a, 150 + k * (tw + gap), 520, tw) for k, a in enumerate(pg[:2]))
    return (f'<div style="position:absolute;left:150px;right:150px;top:90px;display:flex;flex-direction:column;gap:22px">{label}<p class="h" style="font-size:110px">{head}</p>'
            f'<div style="display:flex;gap:60px;flex-wrap:wrap">{"".join(f"<p class=pt><b>&#9679;</b><span>{esc(x)}</span></p>" for x in c.get("points", [])[:3])}</div></div>' + devs)


def page_blocks(html_path, anchors, W, H):
    """Atomic pieces on each page (boxes, text, svg, calendar cells, tabs): a crop edge may never cross one."""
    import json as _j, subprocess as _sp
    r = _sp.run(['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blocks.js'), html_path, ','.join(sorted(set(anchors))), str(W), str(H)],
                capture_output=True, text=True, timeout=300, check=True)
    return _j.loads(r.stdout)


def crop_region(z, pieces, W, H, max_h):
    """Region in page px for a zoom: x from z['x'] (fractions), top z['y'] (fraction), bottom z['y1'] (fraction) or the lowest
    safe cut that fits max_h. Raises if any edge would slice a piece (style rule r013: whole blocks, never sliced text)."""
    x0, x1 = z['x'][0] * W, z['x'][1] * W; y0 = z.get('y', 0) * H
    # big containers (a table, a lined page, a month grid) may be cut between their rows; cards, text, cells and tabs may not
    pieces = [q for q in pieces if not ((q[4] == 'box' and q[3] - q[1] > .4 * H) or (q[4] == 'svg' and q[3] - q[1] > 200))]
    inx = lambda q: q[2] > x0 + .5 and q[0] < x1 - .5
    cuts_y = lambda y: [q for q in pieces if inx(q) and q[1] < y - .5 and q[3] > y + .5]
    if z.get('y1') is not None:
        y1 = z['y1'] * H
    else:
        cands = [y0 + 2 + k for k in range(int(min(H, y0 + max_h) - y0 - 2))] + ([H] if H <= y0 + max_h else [])
        safe = [c for c in cands if not cuts_y(c)]
        if not safe:
            raise ValueError(f"no safe bottom cut for {z['page']} within {max_h:.0f}px")
        y1 = max(safe)
    iny = lambda q: q[3] > y0 + .5 and q[1] < y1 - .5
    bad = [q for q in pieces if iny(q) and ((q[0] < x0 - .5 and q[2] > x0 + .5) or (q[0] < x1 - .5 and q[2] > x1 + .5))]
    bad += cuts_y(y0) + cuts_y(y1)
    if bad:
        raise ValueError(f"crop of {z['page']} slices: " + '; '.join(f'{q[4]} "{q[5]}"' for q in bad[:6]))
    return x0, y0, x1, y1


def zoom_card(src, reg, x, y, cw, W, H, frame):
    """A whole-block region of one page, shown large on a rounded card (a close-up, not a device)."""
    x0, y0, x1, y1 = reg
    k = cw / (x1 - x0); ch = (y1 - y0) * k
    bd = '#c4c4bf' if frame == 'eink' else '#d8cfc0'
    return (f'<div style="position:absolute;left:{x}px;top:{y:.0f}px;width:{cw}px;height:{ch:.0f}px;overflow:hidden;border-radius:30px;border:3px solid {bd};'
            f'box-shadow:0 30px 60px rgba(30,25,40,.16),0 6px 14px rgba(30,25,40,.10);background:#fff">'
            f'<img src="{src}" style="position:absolute;left:{-x0 * k:.0f}px;top:{-y0 * k:.0f}px;width:{W * k:.0f}px;height:{H * k:.0f}px"></div>'), ch


def zoom_scene(th, c, P, N, W, H, frame, head, pts, label, have, blocks):
    zs = [z for z in c['zoom'] if z['page'] in have]
    cap = lambda txt, x, y, w: f'<p style="position:absolute;left:{x}px;top:{y:.0f}px;width:{w}px;text-align:center;font:600 38px var(--b);letter-spacing:.06em;text-transform:uppercase;opacity:.8">{txt}</p>'
    name = lambda z: esc(z['caption']) if z.get('caption') else N(z['page'])
    if len(zs) == 1:
        z = zs[0]; cw = int(c.get('width', 1500)); left = c.get('side', 'left') == 'left'
        x0, x1 = z['x'][0] * W, z['x'][1] * W
        reg = crop_region(z, blocks[z['page']], W, H, 1720 * (x1 - x0) / cw)
        x = 150 if left else 2700 - 150 - cw
        card, ch = zoom_card(P(z['page']), reg, x, 0, cw, W, H, frame)
        y = (2025 - ch) / 2 + 35
        card = card.replace('top:0px', f'top:{y:.0f}px', 1)
        tx = x + cw + 120 if left else 150; tw = 2700 - 150 - tx if left else x - 120 - 150
        extra = ''
        if c.get('panel'):
            extra += f'<div style="border:3px solid {th["line"]};border-radius:30px;padding:34px 40px;display:flex;flex-direction:column;gap:14px;background:{th["paper"]}">' + ''.join(f'<p style="font-size:44px;line-height:1.3"><b>{esc(k)}</b> {esc(v)}</p>' for k, v in c['panel']) + '</div>'
        if c.get('steps'):
            extra += f'<div style="display:flex;flex-direction:column;gap:30px;margin-top:10px">{steps_html(th, c["steps"])}</div>'
        return (card + cap(name(z), x, y - 70, cw) +
                f'<div style="position:absolute;left:{tx}px;top:0;bottom:0;width:{tw}px;display:flex;flex-direction:column;justify-content:center;gap:34px">{label}<p class="h" style="font-size:{c.get("size", 110)}px">{head}</p>{pts}{extra}</div>')
    ws = [int(z.get('width', c.get('width', 1220))) for z in zs[:2]]
    gap = 2700 - 200 - sum(ws) if not any('width' in z for z in zs) else 100
    xs = [(2700 - sum(ws) - gap) // 2]; xs.append(xs[0] + ws[0] + gap)
    y = 560; out = ''
    for k, z in enumerate(zs[:2]):
        cw = ws[k]; x0, x1 = z['x'][0] * W, z['x'][1] * W
        reg = crop_region(z, blocks[z['page']], W, H, (2025 - y - 50) * (x1 - x0) / cw)
        card, ch = zoom_card(P(z['page']), reg, xs[k], y, cw, W, H, frame)
        out += card + cap(name(z), xs[k], y - 66, cw)
    return (f'<div style="position:absolute;left:150px;right:150px;top:80px;display:flex;flex-direction:column;gap:20px">{label}<p class="h" style="font-size:110px">{head}</p>'
            f'<div style="display:flex;gap:60px;flex-wrap:wrap">{"".join(f"<p class=pt><b>&#9679;</b><span>{esc(x)}</span></p>" for x in c.get("points", [])[:3])}</div></div>' + out)


def base(th, body):
    light = th['paper'] > '#888888'
    bg = f"radial-gradient(ellipse at 25% 15%,{th['paper']} 0%,{th['soft']} 60%,{th['soft']} 100%)"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{faces(th['display'], th['body'])}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{--b:'{th['body']}';width:2700px;height:2025px;overflow:hidden;position:relative;font-family:'{th['body']}';color:{th['ink']};background:{bg}}}
.h{{font-family:'{th['display']}';line-height:1.02;font-weight:{600 if th['display'] in ('Corm', 'Fraunces', 'Outfit') else 400 if th['display'] == 'DMSerif' else 700}}}
.k{{font:600 40px '{th['body']}';letter-spacing:.2em;text-transform:uppercase;color:{th['muted']}}}
.pill{{display:inline-block;font:600 40px '{th['body']}';padding:18px 40px;border-radius:999px;background:{th['ink']};color:{th['paper']}}}
.pill.o{{background:transparent;color:{th['ink']};border:4px solid {th['ink']}}}
.pt{{font-size:52px;line-height:1.3;display:flex;gap:22px}} .pt b{{color:{th['accent']}}}
{f".k{{font:italic 400 50px '{th['display']}',serif;letter-spacing:0;text-transform:none}} [style*='text-transform:uppercase']{{text-transform:none!important;letter-spacing:.01em!important}}" if th.get('labels') == 'italic' else ''}
</style></head><body>{body}</body></html>"""


def scenes(brief, listing, build, shots_dir, out_dir):
    th = resolve_theme(brief['spec'].get('theme', 'neutral'))
    W, H = build['size_px']; ratio = f'{W}/{H}'; portrait = H > W
    P = lambda a: 'file://' + os.path.join(shots_dir, a + '.png')
    have = {f[:-4] for f in os.listdir(shots_dir) if f.endswith('.png')}
    copy = listing.get('photo_copy', {})
    pages = build['files'][0]['pages']
    names = page_names(brief)
    N = lambda a: esc(page_name(a, names))
    frame = 'eink' if any(x.get('module') == 'eink_format' for x in brief['spec'].get('sections', [])) else 'dark'
    T = lambda *a, **k: tablet(*a, frame=frame, **k)
    S = {}; blocks = None
    for i, ph in enumerate(brief['photos']):
        c = copy.get(ph['id'], {})
        pg = [a for a in (c.get('pages') or ph.get('pages', [])) if a in have]
        head = esc(c.get('headline', ph['shows'][:40]))
        pts = ''.join(f'<p class="pt"><b>&#9679;</b><span>{esc(x)}</span></p>' for x in c.get('points', [])[:3])
        label = f'<p class="k">{esc(c["label"])}</p>' if c.get('label') else ''
        key = f'{i + 1:02d}-{ph["id"]}'
        if c.get('zoom') and i > 0:
            Nc = lambda a, _c=c.get('captions', {}): esc(_c[a]) if a in _c else N(a)
            if blocks is None:
                zpages = [z['page'] for ph2 in brief['photos'] for z in copy.get(ph2['id'], {}).get('zoom', []) if z['page'] in have]
                blocks = page_blocks(os.path.join(os.path.dirname(os.path.abspath(shots_dir)), 'product.html'), zpages, W, H)
            S[key] = base(th, zoom_scene(th, c, P, Nc, W, H, frame, head, pts, label, have, blocks))
            continue
        if c.get('view') == 'crop' and pg and i > 0:
            Nc = lambda a, _c=c.get('captions', {}): esc(_c[a]) if a in _c else N(a)  # listing can name a page more exactly
            S[key] = base(th, crop_scene(th, c, pg, P, Nc, W, H, frame, head, pts, label))
            continue
        if i == 0:
            tw = 1050 if portrait else 1350
            t1 = T(P(pg[1]), tw, 1300 if portrait else 1250, 160, ratio, 4, 1) if len(pg) > 1 else ''
            t2 = T(P(pg[0]), tw, 1180 if portrait else 1180, 480 if not portrait else 300, ratio, -3, 2, N(pg[0])) if pg else ''
            S[key] = base(th, (motif(th, 'tr', 3, 520) if th.get('motif') not in ('lines', None) else '') + f'''<div style="position:absolute;left:150px;top:0;bottom:0;width:1000px;display:flex;flex-direction:column;justify-content:center;gap:40px">
              {label or '<p class="k">Digital planner</p>'}<p class="h" style="font-size:170px">{esc(listing.get("hero_title") or brief["spec"]["title"])}</p>
              <p style="font-size:60px;color:{th["muted"]};line-height:1.25">{head}</p>{pts}
              <div style="display:flex;gap:20px;flex-wrap:wrap"><span class="pill">Hyperlinked</span><span class="pill o">{pages} pages</span></div></div>''' + t1 + t2)
        elif len(pg) >= 4:
            few = len(pg) <= 4
            cols = 2 if few else 4
            cells = ''.join(f'<div style="display:flex;flex-direction:column;gap:14px;align-items:center"><img src="{P(a)}" style="width:100%;aspect-ratio:{ratio};border-radius:14px;box-shadow:0 18px 36px rgba(30,25,40,.16)"><p style="font:600 36px var(--b);letter-spacing:.06em;text-transform:uppercase;opacity:.75">{N(a)}</p></div>' for a in pg[:8 if not portrait else 4])
            if few:  # 2x2 beside the headline so pages stay readable
                S[key] = base(th, f'''<div style="position:absolute;left:150px;top:0;bottom:0;width:760px;display:flex;flex-direction:column;justify-content:center;gap:34px">
                  {label or '<p class="k">What\'s inside</p>'}<p class="h" style="font-size:120px">{head}</p>{pts}</div>
                  <div style="position:absolute;left:1000px;right:120px;top:120px;bottom:100px;display:grid;grid-template-columns:{'repeat(2,600px)' if portrait else '1fr 1fr'};justify-content:center;gap:40px 50px;align-content:center">{cells}</div>''')
                continue
            S[key] = base(th, f'''<div style="position:absolute;inset:0;padding:110px 150px;display:flex;flex-direction:column;align-items:center;gap:60px">
              <div style="text-align:center">{label or '<p class="k">What\'s inside</p>'}<p class="h" style="font-size:130px;margin-top:20px">{head}</p></div>
              <div style="display:grid;grid-template-columns:repeat({cols},1fr);gap:50px;width:100%">{cells}</div></div>''')
        elif 2 <= len(pg) <= 3:
            n = len(pg)
            tw = (1180 if n == 2 else 800) if not portrait else (900 if n == 2 else 640)
            gap = 2700 - 300 - tw * n
            th_ = tw * (H / W) + tw * .064  # tablet height incl. frame
            top_ = 560 + max(0, (2025 - 560 - 90 - th_) / 2)  # centred in the space under the headline, room for captions
            tabs = ''.join(T(P(a), tw, 150 + k * (tw + gap // max(1, n - 1)), int(top_), ratio, 0, 1, N(a)) for k, a in enumerate(pg))
            S[key] = base(th, f'''<div style="position:absolute;left:150px;right:150px;top:110px;display:flex;flex-direction:column;gap:26px">
              {label}<p class="h" style="font-size:120px">{head}</p><div style="display:flex;gap:60px;flex-wrap:wrap">{''.join(f'<p class="pt"><b>&#9679;</b><span>{esc(x)}</span></p>' for x in c.get('points', [])[:3])}</div></div>''' + tabs)
        elif ph['id'].startswith('how') or 'how it works' in ph['shows'].lower():
            steps = listing.get('how_steps') or [['Buy', 'Download the PDF from Etsy.'], ['Import', 'Open it in your PDF planner app.'], ['Plan', 'Write with your stylus.']]
            S[key] = base(th, motif(th, 'tr', 11, 480) + f'''<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:90px">
              <div style="text-align:center">{label or '<p class="k">Instant digital download</p>'}<p class="h" style="font-size:150px;margin-top:24px">{head}</p></div>
              <div style="display:grid;grid-template-columns:repeat(3,680px);gap:70px">{''.join(f'<div style="background:{th["paper"]};border-radius:40px;padding:70px 60px;box-shadow:0 20px 40px rgba(30,25,40,.1);text-align:center"><p style="font:600 46px {th["body"]};color:{th["muted"]};letter-spacing:.2em">{n + 1}</p><p class="h" style="font-size:96px;margin:16px 0 26px">{esc(a)}</p><p style="font-size:46px;color:{th["muted"]};line-height:1.35">{esc(b)}</p></div>' for n, (a, b) in enumerate(steps[:3]))}</div></div>''')
        else:
            left = i % 2 == 1
            tw = 1100 if portrait else 1650
            tx = (150 if left else 2700 - 150 - tw) if not portrait else (220 if left else 2700 - 220 - tw)
            tab = T(P(pg[0]), tw, tx, 160 if portrait else 300, ratio, 0, 1, N(pg[0])) if pg else ''
            if c.get('steps'):
                pts = ''.join(f'<div style="display:flex;gap:26px;align-items:flex-start"><span style="flex:none;width:74px;height:74px;border-radius:50%;background:{th["ink"]};color:{th["paper"]};display:flex;align-items:center;justify-content:center;font:700 40px var(--b)">{n + 1}</span><div><p class="h" style="font-size:58px">{esc(a)}</p><p style="font-size:42px;color:{th["muted"]};line-height:1.3;margin-top:8px">{esc(b)}</p></div></div>' for n, (a, b) in enumerate(c['steps'][:3]))
            text_x = f'right:150px' if left else 'left:150px'
            S[key] = base(th, tab + f'''<div style="position:absolute;{text_x};top:0;bottom:0;width:{720 if not portrait else 1100}px;display:flex;flex-direction:column;justify-content:center;gap:34px">
              {label}<p class="h" style="font-size:120px">{head}</p>{pts}</div>''')
    os.makedirs(out_dir, exist_ok=True)
    for k, v in S.items():
        open(os.path.join(out_dir, f'mock-{k}.html'), 'w').write(v)
    return list(S)
