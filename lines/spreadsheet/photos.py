"""Listing photos for spreadsheets: 2700x2025 scenes with real tab screenshots shown on a laptop or as cards.
Scenes follow the brief's photo plan ('pages' are tab anchors: start, setup, dashboard, m01..m12, bills, debt, savings)
and the listing's photo copy. The first photo is the hero; a photo whose id starts with 'how' is the 3-step how-to."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'planner'))
from fonts import faces
from gen import resolve_theme, esc, MONTHS

NAMES = {'start': 'Start here', 'setup': 'Setup', 'dashboard': 'Dashboard', 'bills': 'Bill tracker', 'debt': 'Debt payoff', 'savings': 'Savings goals'}


def tab_name(a):
    if a.startswith('m') and a[1:].isdigit():
        return MONTHS[int(a[1:]) - 1]
    return NAMES.get(a, a)


def laptop(src, w, x, y, caption='', z=1):
    h = w * 0.625
    cap = f'<div style="position:absolute;left:50%;bottom:-80px;transform:translateX(-50%);white-space:nowrap;font:600 36px var(--b);letter-spacing:.06em;text-transform:uppercase;opacity:.75">{caption}</div>' if caption else ''
    return (f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;z-index:{z}">'
            f'<div style="background:#1b1c20;border-radius:{w * .025:.0f}px {w * .025:.0f}px 0 0;padding:{w * .022:.0f}px {w * .022:.0f}px {w * .03:.0f}px">'
            f'<div style="height:{h:.0f}px;background:#fff;overflow:hidden;border-radius:4px"><div style="height:{w * .028:.0f}px;background:#f1f3f4;border-bottom:1px solid #dadce0"></div>'
            f'<img src="{src}" style="width:100%;display:block;object-fit:cover;object-position:left top;height:calc(100% - {w * .028:.0f}px)"></div></div>'
            f'<div style="height:{w * .028:.0f}px;margin:0 -{w * .06:.0f}px;background:linear-gradient(#d9dade,#a9abb1);border-radius:0 0 {w * .03:.0f}px {w * .03:.0f}px;box-shadow:0 40px 70px rgba(20,25,35,.28)"></div>{cap}</div>')


def card(src, caption):
    return (f'<div style="display:flex;flex-direction:column;gap:16px;align-items:center"><div style="width:100%;aspect-ratio:16/10;background:#fff;border-radius:18px;overflow:hidden;box-shadow:0 18px 36px rgba(20,25,35,.16)">'
            f'<img src="{src}" style="width:100%;height:100%;object-fit:cover;object-position:left top"></div><p style="font:600 36px var(--b);letter-spacing:.06em;text-transform:uppercase;opacity:.75">{caption}</p></div>')


def base(th, body):
    D, Bf = th.get('photo_display', 'Outfit'), th.get('photo_body', 'Manrope')
    paper = th['paper'] if th['paper'].upper() != '#FFFFFF' else '#FBFBF9'
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{faces(D, Bf)}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{--b:'{Bf}';width:2700px;height:2025px;overflow:hidden;position:relative;font-family:'{Bf}';color:{th['ink']};background:radial-gradient(ellipse at 25% 15%,{paper} 0%,{th['soft']} 70%)}}
.h{{font-family:'{D}';font-weight:600;line-height:1.04}}
.k{{font:600 40px '{Bf}';letter-spacing:.2em;text-transform:uppercase;color:{th['muted']}}}
.pill{{display:inline-block;font:600 40px '{Bf}';padding:18px 40px;border-radius:999px;background:{th['accent']};color:#fff}}
.pill.o{{background:transparent;color:{th['ink']};border:4px solid {th['ink']}}}
.pt{{font-size:52px;line-height:1.3;display:flex;gap:22px}} .pt b{{color:{th['accent']}}}
</style></head><body>{body}</body></html>"""


def scenes(brief, listing, build, shots_dir, out_dir):
    th = resolve_theme(brief['spec'].get('theme', 'slate'))
    P = lambda a: 'file://' + os.path.join(shots_dir, a + '.png')
    have = {f[:-4] for f in os.listdir(shots_dir) if f.endswith('.png')}
    copy = listing.get('photo_copy', {})
    tabs = len(build['tabs'])
    S = {}
    for i, ph in enumerate(brief['photos']):
        c = copy.get(ph['id'], {})
        pg = [a for a in ph.get('pages', []) if a in have]
        head = esc(c.get('headline', ph['shows'][:40]))
        pts = ''.join(f'<p class="pt"><b>&#9679;</b><span>{esc(x)}</span></p>' for x in c.get('points', [])[:3])
        label = f'<p class="k">{esc(c["label"])}</p>' if c.get('label') else ''
        key = f'{i + 1:02d}-{ph["id"]}'
        if i == 0:
            lap = laptop(P(pg[0]), 1420, 1180, 380, tab_name(pg[0])) if pg else ''
            S[key] = base(th, f'''<div style="position:absolute;left:150px;top:0;bottom:0;width:960px;display:flex;flex-direction:column;justify-content:center;gap:40px">
              {label or '<p class="k">Google Sheets and Excel</p>'}<p class="h" style="font-size:150px">{esc(listing.get("hero_title") or brief["spec"]["title"])}</p>
              <p style="font-size:58px;color:{th["muted"]};line-height:1.25">{head}</p>{pts}
              <div style="display:flex;gap:20px;flex-wrap:wrap"><span class="pill">Instant download</span><span class="pill o">{tabs} tabs</span></div></div>''' + lap)
        elif ph['id'].startswith('how'):
            steps = c.get('steps') or listing.get('how_steps') or []
            S[key] = base(th, f'''<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:90px">
              <div style="text-align:center">{label or '<p class="k">How it works</p>'}<p class="h" style="font-size:140px;margin-top:24px">{head}</p></div>
              <div style="display:grid;grid-template-columns:repeat(3,700px);gap:70px">{''.join(f'<div style="background:#fff;border-radius:40px;padding:70px 60px;box-shadow:0 20px 40px rgba(20,25,35,.1);text-align:center"><p style="font:600 46px var(--b);color:{th["muted"]};letter-spacing:.2em">{n + 1}</p><p class="h" style="font-size:88px;margin:16px 0 26px">{esc(a)}</p><p style="font-size:46px;color:{th["muted"]};line-height:1.35">{esc(b)}</p></div>' for n, (a, b) in enumerate(steps[:3]))}</div></div>''')
        elif len(pg) >= 3:
            cells = ''.join(card(P(a), esc(tab_name(a))) for a in pg[:4])
            S[key] = base(th, f'''<div style="position:absolute;left:150px;top:0;bottom:0;width:780px;display:flex;flex-direction:column;justify-content:center;gap:34px">
              {label or '<p class="k">What\'s inside</p>'}<p class="h" style="font-size:118px">{head}</p>{pts}</div>
              <div style="position:absolute;left:1020px;right:120px;top:0;bottom:0;display:grid;grid-template-columns:1fr 1fr;gap:60px 50px;align-content:center">{cells}</div>''')
        else:
            left = i % 2 == 1
            w = 1560
            lx = 130 if left else 2700 - 130 - w
            lap = laptop(P(pg[0]), w, lx, 330, tab_name(pg[0])) if pg else ''
            if c.get('steps'):
                pts = ''.join(f'<div style="display:flex;gap:26px;align-items:flex-start"><span style="flex:none;width:74px;height:74px;border-radius:50%;background:{th["accent"]};color:#fff;display:flex;align-items:center;justify-content:center;font:700 40px var(--b)">{n + 1}</span><div><p class="h" style="font-size:56px">{esc(a)}</p><p style="font-size:42px;color:{th["muted"]};line-height:1.3;margin-top:8px">{esc(b)}</p></div></div>' for n, (a, b) in enumerate(c['steps'][:3]))
            tx = 'right:130px' if left else 'left:150px'
            S[key] = base(th, lap + f'''<div style="position:absolute;{tx};top:0;bottom:0;width:820px;display:flex;flex-direction:column;justify-content:center;gap:34px">
              {label}<p class="h" style="font-size:112px">{head}</p>{pts}</div>''')
    os.makedirs(out_dir, exist_ok=True)
    for k, v in S.items():
        open(os.path.join(out_dir, f'mock-{k}.html'), 'w').write(v)
    return list(S)
