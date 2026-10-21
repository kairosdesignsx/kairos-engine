"""Listing photos for planners: 2700x2025 HTML scenes built from the brief's photo plan and the listing's photo copy,
screenshotted by shoot.js. Scenes: hero, grid (what's inside), page (one page with headline and points), how (3 steps)."""
import os
from fonts import faces
from gen import resolve_theme, motif, esc


def page_names(brief):
    names = {'cover': 'Cover', 'index': 'Contents', 'year': 'Year at a glance'}
    for sec in brief['spec'].get('sections', []):
        if sec.get('anchor') and sec.get('label'):
            names[sec['anchor']] = sec['label']
    return names


def page_name(a, names):
    import re as _re
    if a in names:
        return names[a]
    if _re.fullmatch(r'd\d{4}|u\d{3}', a): return 'Day page'
    if _re.fullmatch(r'm\d{2}h', a): return 'Habit tracker'
    if _re.fullmatch(r'm\d{2}', a): return 'Month'
    if _re.fullmatch(r'w\d{2}', a): return 'Week'
    if _re.fullmatch(r'hs\d{2}', a): return 'Head start month'
    if _re.fullmatch(r'hsw\d{2}', a): return 'Head start week'
    return a


def tablet(src, w, x, y, ratio, rot=0, z=1, caption=''):
    pad = w * .032
    cap = f'<div style="position:absolute;left:50%;bottom:-74px;transform:translateX(-50%);white-space:nowrap;font:600 36px var(--b);letter-spacing:.06em;text-transform:uppercase;opacity:.75">{caption}</div>' if caption else ''
    return (f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;transform:rotate({rot}deg);z-index:{z};'
            f'background:#1c1c21;border-radius:{w * .045:.0f}px;padding:{pad:.0f}px;box-shadow:0 40px 80px rgba(30,25,40,.28),0 8px 18px rgba(30,25,40,.18)">'
            f'<img src="{src}" style="width:100%;display:block;border-radius:{w * .01:.0f}px;aspect-ratio:{ratio}">{cap}</div>')


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
    S = {}
    for i, ph in enumerate(brief['photos']):
        c = copy.get(ph['id'], {})
        pg = [a for a in ph.get('pages', []) if a in have]
        head = esc(c.get('headline', ph['shows'][:40]))
        pts = ''.join(f'<p class="pt"><b>&#9679;</b><span>{esc(x)}</span></p>' for x in c.get('points', [])[:3])
        label = f'<p class="k">{esc(c["label"])}</p>' if c.get('label') else ''
        key = f'{i + 1:02d}-{ph["id"]}'
        if i == 0:
            tw = 1050 if portrait else 1350
            t1 = tablet(P(pg[1]), tw, 1300 if portrait else 1250, 160, ratio, 4, 1) if len(pg) > 1 else ''
            t2 = tablet(P(pg[0]), tw, 1180 if portrait else 1180, 480 if not portrait else 300, ratio, -3, 2, N(pg[0])) if pg else ''
            S[key] = base(th, motif(th, 'tr', 3, 520) + f'''<div style="position:absolute;left:150px;top:0;bottom:0;width:1000px;display:flex;flex-direction:column;justify-content:center;gap:40px">
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
                  <div style="position:absolute;left:1000px;right:120px;top:120px;bottom:100px;display:grid;grid-template-columns:1fr 1fr;gap:40px 50px;align-content:center">{cells}</div>''')
                continue
            S[key] = base(th, f'''<div style="position:absolute;inset:0;padding:110px 150px;display:flex;flex-direction:column;align-items:center;gap:60px">
              <div style="text-align:center">{label or '<p class="k">What\'s inside</p>'}<p class="h" style="font-size:130px;margin-top:20px">{head}</p></div>
              <div style="display:grid;grid-template-columns:repeat({cols},1fr);gap:50px;width:100%">{cells}</div></div>''')
        elif 2 <= len(pg) <= 3:
            n = len(pg)
            tw = (1180 if n == 2 else 790) if not portrait else (900 if n == 2 else 640)
            gap = 2700 - 300 - tw * n
            tabs = ''.join(tablet(P(a), tw, 150 + k * (tw + gap // max(1, n - 1)), 660 if not portrait else 560, ratio, 0, 1, N(a)) for k, a in enumerate(pg))
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
            tab = tablet(P(pg[0]), tw, tx, 160 if portrait else 300, ratio, 0, 1, N(pg[0])) if pg else ''
            if c.get('steps'):
                pts = ''.join(f'<div style="display:flex;gap:26px;align-items:flex-start"><span style="flex:none;width:74px;height:74px;border-radius:50%;background:{th["ink"]};color:{th["paper"]};display:flex;align-items:center;justify-content:center;font:700 40px var(--b)">{n + 1}</span><div><p class="h" style="font-size:58px">{esc(a)}</p><p style="font-size:42px;color:{th["muted"]};line-height:1.3;margin-top:8px">{esc(b)}</p></div></div>' for n, (a, b) in enumerate(c['steps'][:3]))
            text_x = f'right:150px' if left else 'left:150px'
            S[key] = base(th, tab + f'''<div style="position:absolute;{text_x};top:0;bottom:0;width:{720 if not portrait else 1100}px;display:flex;flex-direction:column;justify-content:center;gap:34px">
              {label}<p class="h" style="font-size:120px">{head}</p>{pts}</div>''')
    os.makedirs(out_dir, exist_ok=True)
    for k, v in S.items():
        open(os.path.join(out_dir, f'mock-{k}.html'), 'w').write(v)
    return list(S)
