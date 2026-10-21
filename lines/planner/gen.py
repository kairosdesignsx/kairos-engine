"""Planner line: a hyperlinked PDF planner built from a list of modules.

spec = {
  "title", "subtitle", "kicker", "brand",
  "orientation": "landscape" | "portrait",
  "dating": {"mode": "dated", "year": 2027} | {"mode": "undated"},
  "theme": "sage" | {"base": "sage", ...token overrides, "display": font, "body": font, "motif": name},
  "type_scale": 1.0,                 # >1 for larger text (readability)
  "sections": [ {"module": "cover"}, {"module": "calendar", ...}, ... ]
}
Every module registers itself in MODULES with a description and its parameters, so the brief
writer can see exactly what the line can build (capabilities()). A module a brief asks for that
does not exist yet is reported by validate_spec() as needs_module.
"""
import calendar, datetime, html as H, json, math, random, re
from fonts import faces

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
SIZES = {'landscape': (1024, 768), 'portrait': (768, 1024)}

THEMES = {
    'sage':    dict(paper='#FBFAF6', ink='#2F3A2C', muted='#7E8A75', line='#DCE0D4', accent='#8A9A7B', soft='#EEF1E8', warm='#D8B4A0', tabs=('#9AAA8B', '#C9B79C'), display='Corm', body='Jost', motif='sprig'),
    'neutral': dict(paper='#FAF7F2', ink='#2B2622', muted='#8A7F74', line='#E4DCD1', accent='#A7836A', soft='#F2EBE2', warm='#C9A38A', tabs=('#B89C86', '#7E8C88'), display='Fraunces', body='Manrope', motif='arch'),
    'pastel':  dict(paper='#FFFDF9', ink='#3B3550', muted='#8C86A3', line='#E7E3F0', accent='#8C7BD8', soft='#F2EFFC', warm='#FFB8A3', tabs=('#B7A8F0', '#9FD9C9'), display='Quicksand', body='Nunito', motif='dots', rainbow=['#F8B4B4', '#FBC9A6', '#F9DE9C', '#C9E7A7', '#A8DCCB', '#A9D3EF', '#B9C4F4', '#CDB8F2', '#E9B6E3', '#F4B3C8', '#F7C5A8', '#D6D1C4']),
    'navy':    dict(paper='#FBFAF7', ink='#1D2A44', muted='#6E7891', line='#DDE1EA', accent='#1D2A44', soft='#EEF1F6', warm='#C2A15F', tabs=('#2D3E62', '#C2A15F'), display='DMSerif', body='Outfit', motif='lines'),
    'blush':   dict(paper='#FFFBF9', ink='#4A3036', muted='#9A7F84', line='#F0E1E1', accent='#C98D94', soft='#FBEDEC', warm='#E8B4A8', tabs=('#D9A3A9', '#B9A7C9'), display='Baskerville', body='Nunito', motif='arch'),
    'night':   dict(paper='#1E2230', ink='#ECE8F5', muted='#A3A0B8', line='#3A3F55', accent='#B7A8F0', soft='#2A2F42', warm='#F3B79B', tabs=('#6F7FD6', '#D08AB8'), display='Outfit', body='Nunito', motif='dots', rainbow=['#E58C8C', '#E9A47E', '#E5C46E', '#9FCB84', '#72C2AE', '#6FB2DE', '#8C9BEA', '#AE92E6', '#D48ACD', '#E48AAE', '#E8A08A', '#B5AFA0']),
}


def mix(a, b, t):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * t):02x}' for x, y in zip(a, b))


def esc(s):
    return H.escape(str(s))


def resolve_theme(t):
    if isinstance(t, str):
        return dict(THEMES[t])
    th = dict(THEMES[t.get('base', 'neutral')])
    th.update({k: v for k, v in t.items() if k != 'base'})
    if isinstance(th.get('tabs'), list):
        th['tabs'] = tuple(th['tabs'])
    return th


# ---------- decoration ----------
def sprig(th, seed=1, w=220, h=220):
    rnd = random.Random(seed); parts = []

    def branch(x0, y0, x1, y1, cx, cy, n, size):
        parts.append(f'<path d="M{x0},{y0} Q{cx},{cy} {x1},{y1}" fill="none" stroke="{th["accent"]}" stroke-width="2" stroke-linecap="round"/>')
        for i in range(1, n + 1):
            t = i / (n + 1)
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1; y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1
            dx = 2 * (1 - t) * (cx - x0) + 2 * t * (x1 - cx); dy = 2 * (1 - t) * (cy - y0) + 2 * t * (y1 - cy)
            ang = math.degrees(math.atan2(dy, dx)); side = 1 if i % 2 else -1
            r = size * (1 - .35 * t) * (.9 + .2 * rnd.random()); L = math.hypot(dx, dy) or 1
            lx, ly = x + side * r * .95 * -dy / L, y + side * r * .95 * dx / L
            parts.append(f'<ellipse cx="{lx:.1f}" cy="{ly:.1f}" rx="{r:.1f}" ry="{r * .82:.1f}" transform="rotate({ang + side * 20:.1f} {lx:.1f} {ly:.1f})" fill="{th["accent"] if (i + seed) % 3 == 0 else mix(th["accent"], th["paper"], .45)}" fill-opacity=".9"/>')
    branch(18, h - 18, w - 36, 28, w * .3, h * .35, 9, 15)
    branch(w * .3, h * .62, w * .82, h * .62, w * .55, h * .45, 5, 11)
    for _ in range(4):
        parts.append(f'<circle cx="{rnd.uniform(w * .35, w * .7):.1f}" cy="{rnd.uniform(h * .25, h * .55):.1f}" r="{rnd.uniform(3, 5.5):.1f}" fill="{th["warm"]}"/>')
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="100%">{"".join(parts)}</svg>'


def motif(th, where, seed=1, size=150):
    m = th.get('motif')
    if m == 'sprig':
        pos = 'right:44px;top:-26px' if where == 'tr' else 'left:-30px;bottom:-30px;transform:rotate(180deg)'
        return f'<div style="position:absolute;{pos};width:{size}px;height:{size}px;opacity:.9;pointer-events:none">{sprig(th, seed)}</div>'
    if m == 'dots':
        rnd = random.Random(seed); cs = th.get('rainbow') or [th['accent'], th['warm']]
        dots = ''.join(f'<circle cx="{rnd.uniform(0, size):.0f}" cy="{rnd.uniform(0, size):.0f}" r="{rnd.uniform(3, 9):.1f}" fill="{rnd.choice(cs)}" fill-opacity=".8"/>' for _ in range(16))
        pos = 'right:60px;top:-30px' if where == 'tr' else 'left:-30px;bottom:-30px'
        return f'<div style="position:absolute;{pos};width:{size}px;height:{size}px;pointer-events:none"><svg viewBox="0 0 {size} {size}" width="100%" height="100%">{dots}</svg></div>'
    if m == 'arch' and where == 'tr':
        return f'<div style="position:absolute;right:80px;top:-70px;width:150px;height:150px;border-radius:50%;border:2px solid {th["warm"]};opacity:.5;pointer-events:none"></div><div style="position:absolute;right:120px;top:-40px;width:110px;height:110px;border-radius:50%;background:{th["soft"]};pointer-events:none"></div>'
    if m == 'lines' and where == 'tr':
        return f'<div style="position:absolute;right:54px;top:0;width:160px;height:6px;background:{th["warm"]}"></div>'
    return ''


# ---------- the planner shell ----------
class Planner:
    def __init__(self, spec):
        self.s = spec
        self.th = resolve_theme(spec.get('theme', 'neutral'))
        self.W, self.HT = SIZES[spec.get('orientation', 'landscape')]
        dating = spec.get('dating', {'mode': 'dated', 'year': 2027})
        self.undated = dating.get('mode') == 'undated'
        self.year = dating.get('year', 2027)
        self.tabs = self.th['rainbow'] if self.th.get('rainbow') else [mix(self.th['tabs'][0], self.th['tabs'][1], i / 11) for i in range(12)]
        self.scale = float(spec.get('type_scale', 1.0))
        lean = spec.get('lean', False)  # set by the build stage when a file is over the size budget
        self.rbox, self.rpill = (5, 6) if lean else (12, 99)
        self.pages, self.page_modules, self.seed = [], [], 1
        self.nav_items = []     # (label, anchor) shown on every page's top bar
        self.index_items = []   # (label, anchor, kicker) for the contents page
        self.current = None

    def fs(self, px):
        return f'{px * self.scale:.1f}px'

    def css(self):
        th, W, HT = self.th, self.W, self.HT
        return f"""
{faces(th['display'], th['body'])}
@page{{size:{W}px {HT}px;margin:0}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:{th['paper']}}}
body{{font-family:'{th['body']}',sans-serif;color:{th['ink']};font-size:{self.fs(12.5)};-webkit-print-color-adjust:exact;print-color-adjust:exact}}
a{{color:inherit;text-decoration:none}}
.pg{{width:{W}px;height:{HT}px;position:relative;overflow:hidden;background:{th['paper']};break-after:page}}
.pg:last-child{{break-after:auto}}
.rail{{position:absolute;right:0;top:0;bottom:0;width:46px;display:flex;flex-direction:column;z-index:3}}
.rail a{{flex:1;display:flex;align-items:center;justify-content:center;font:600 11px '{th['body']}';letter-spacing:.06em;color:{th['ink'] if th['paper'] > '#888888' else '#1E2230'};border-bottom:1px solid {th['paper']};writing-mode:vertical-rl;transform:rotate(180deg)}}
.rail a.on{{margin-left:-8px;box-shadow:-3px 0 0 {th['ink']} inset}}
.nav{{position:absolute;left:40px;right:70px;top:16px;display:flex;gap:6px;align-items:center;z-index:3}}
.nav a{{font:600 10.5px '{th['body']}';letter-spacing:.12em;text-transform:uppercase;padding:5px 10px;border-radius:{self.rpill}px;background:{th['soft']};color:{th['ink']}}}
.nav a.on{{background:{th['ink']};color:{th['paper']}}}
.nav .crumb{{margin-left:auto;font:500 11px '{th['body']}';color:{th['muted']};letter-spacing:.06em}}
.nav .crumb a{{background:none;padding:0 4px;text-transform:none;letter-spacing:.04em}}
.body{{position:absolute;left:40px;right:70px;top:56px;bottom:26px;display:flex;flex-direction:column;gap:12px}}
.h{{font-family:'{th['display']}',serif;font-weight:{600 if th['display'] in ('Corm', 'Fraunces', 'Outfit') else 400 if th['display'] == 'DMSerif' else 700};color:{th['ink']};line-height:1}}
.k{{font:600 {self.fs(10.5)} '{th['body']}';letter-spacing:.18em;text-transform:uppercase;color:{th['muted']}}}
.box{{border:1.3px solid {th['line']};border-radius:{self.rbox}px;padding:10px 12px;display:flex;flex-direction:column;gap:6px;min-height:0}}
.box.fill{{background:{th['soft']};border-color:transparent}}
.lines{{flex:1;background-image:repeating-linear-gradient(to bottom,transparent 0,transparent {27 * self.scale:.0f}px,{th['line']} {27 * self.scale:.0f}px,{th['line']} {28 * self.scale:.0f}px);min-height:28px}}
.dots{{flex:1;background-image:radial-gradient({th['line']} 1.2px,transparent 1.3px);background-size:18px 18px;background-position:4px 4px;min-height:20px}}
.row{{display:flex;gap:12px;min-height:0}}
.col{{display:flex;flex-direction:column;gap:12px;min-height:0}}
.chk{{display:flex;align-items:center;gap:8px;font-size:{self.fs(12.5)};border-bottom:1px solid {th['line']};padding:5px 0;min-height:{26 * self.scale:.0f}px}}
.chk i{{width:12px;height:12px;border:1.4px solid {th['muted']};border-radius:3px;flex:none}}
.cal{{display:grid;grid-template-columns:repeat(7,1fr);gap:0;flex:1}}
.cal .d{{border-top:1px solid {th['line']};border-left:1px solid {th['line']};padding:5px 7px;font:600 {self.fs(12)} '{th['body']}';position:relative;display:block}}
.cal .d:nth-child(7n){{border-right:1px solid {th['line']}}}
.cal .hd{{font:600 10px '{th['body']}';letter-spacing:.14em;text-transform:uppercase;color:{th['muted']};padding:0 7px 6px;border:0}}
.cal .x{{color:{mix(th['muted'], th['paper'], .5)}}}
.foot{{position:absolute;left:40px;bottom:8px;font:500 9px '{th['body']}';color:{mix(th['muted'], th['paper'], .3)};letter-spacing:.08em}}
.step{{display:flex;gap:12px;align-items:flex-start}}
.step b{{flex:none;width:28px;height:28px;border-radius:50%;background:{th['ink']};color:{th['paper']};display:flex;align-items:center;justify-content:center;font:700 13px '{th['body']}'}}
"""

    def nav(self, active=None, crumb=''):
        links = ''.join(f'<a href="#{a}" class="{"on" if a == active else ""}">{esc(l)}</a>' for l, a in self.nav_items[:7 if self.W > self.HT else 4])
        return f'<div class="nav">{links}<span class="crumb">{crumb}</span></div>'

    def rail(self, month=None):
        out = []
        for i in range(12):
            c = self.tabs[i]; on = month == i + 1
            out.append(f'<a href="#m{i + 1:02d}" class="{"on" if on else ""}" style="background:{c}{"" if on else "cc"}">{MONTHS[i][:3].upper()}</a>')
        return f'<div class="rail">{"".join(out)}</div>'

    def page(self, anchor, inner, active=None, month=None, crumb='', deco=False, raw=False, style=''):
        self.seed += 3
        m = (motif(self.th, 'tr', self.seed) + motif(self.th, 'bl', self.seed + 1)) if deco else ''
        if raw:
            self.pages.append(f'<section class="pg" id="{anchor}" style="{style}">{inner}</section>')
        else:
            self.pages.append(f'<section class="pg" id="{anchor}" style="{style}">{m}{self.nav(active, crumb)}{self.rail(month)}<div class="body">{inner}</div><p class="foot">{esc(self.s.get("brand", ""))}</p></section>')
        self.page_modules.append((anchor, self.current))

    def head(self, kicker, title, size=44, right=''):
        return f'<div class="row" style="align-items:flex-end;justify-content:space-between"><div><p class="k">{esc(kicker)}</p><p class="h" style="font-size:{size}px">{esc(title)}</p></div>{right}</div>'

    # ---------- dates ----------
    @staticmethod
    def did(d):
        return f'd{d.month:02d}{d.day:02d}'

    def week_of(self, d):
        first = datetime.date(self.year, 1, 1); start = first - datetime.timedelta(days=first.weekday())
        return (d - start).days // 7 + 1

    def week_start(self, n):
        first = datetime.date(self.year, 1, 1); start = first - datetime.timedelta(days=first.weekday())
        return start + datetime.timedelta(days=7 * (n - 1))

    def nweeks(self):
        return self.week_of(datetime.date(self.year, 12, 31))

    def cal_grid(self, m, link_days=True, small=False):
        cells = ''.join(f'<span class="d hd">{x[0] if small else x}</span>' for x in DOW)
        if self.undated:
            for i in range(35):
                cells += '<span class="d"></span>'
            return cells, 5
        cal = calendar.Calendar(0).monthdatescalendar(self.year, m)
        for wk in cal:
            for d in wk:
                if d.month != m:
                    cells += '<span class="d x"></span>' if small else f'<span class="d x">{d.day}</span>'
                else:
                    cells += f'<a class="d" href="#{self.did(d)}">{d.day}</a>' if link_days else f'<span class="d">{d.day}</span>'
        return cells, len(cal)

    def html(self):
        return f'<!doctype html><html><head><meta charset="utf-8"><style>{self.css()}</style></head><body>{"".join(self.pages)}</body></html>'


# ---------- day and week blocks ----------
def _chk(n, items=()):
    items = list(items) + [''] * max(0, n - len(items))
    return ''.join(f'<div class="chk"><i></i>{esc(t)}</div>' for t in items[:n])


def block(P, b):
    """One block on a day or week page. b = {"kind": ..., "label": ..., ...}."""
    th = P.th; k = b['kind']; label = esc(b.get('label', ''))
    if k == 'checklist':
        return f'<div class="box{" fill" if b.get("fill") else ""}" style="{"flex:1" if b.get("grow") else ""}"><span class="k">{label}</span>{_chk(b.get("rows", 3), b.get("items", ()))}</div>'
    if k in ('lines', 'dots'):
        h = '' if b.get('grow', True) else f'flex:none;height:{b.get("height", 28)}px'
        return f'<div class="box" style="{"flex:1" if b.get("grow", True) else ""}"><span class="k">{label}</span><div class="{k}" style="{h}"></div></div>'
    if k == 'water':
        n = b.get('count', 8)
        drops = ''.join(f'<path d="M{8 + i * 22},2 C{8 + i * 22},2 {1 + i * 22},11 {1 + i * 22},15 a7,7 0 0,0 14,0 C{15 + i * 22},11 {8 + i * 22},2 {8 + i * 22},2 Z" fill="none" stroke="{th["accent"]}" stroke-width="1.4"/>' for i in range(n))
        return f'<div class="box" style="flex:1"><span class="k">{label or "Water"}</span><svg width="{n * 22}" height="24" viewBox="0 0 {n * 22} 24">{drops}</svg></div>'
    if k == 'scale':
        n = b.get('max', 5)
        dots = ''.join(f'<circle cx="{12 + i * 28}" cy="12" r="10.5" fill="none" stroke="{th["muted"]}" stroke-width="1.4"/><text x="{12 + i * 28}" y="16" text-anchor="middle" font-size="11.5" font-family="{th["body"]}" fill="{th["ink"]}">{i + 1}</text>' for i in range(n))
        return f'<div class="box" style="flex:1"><span class="k">{label}</span><svg width="{n * 28}" height="24" viewBox="0 0 {n * 28} 24">{dots}</svg></div>'
    if k == 'hours':
        a, z = b.get('from', 7), b.get('to', 21)
        hrs = ''.join(f'<div style="display:flex;gap:8px;border-bottom:1px solid {th["line"]};height:{b.get("row", 26)}px;align-items:center"><span style="width:38px;font:600 10.5px \'{th["body"]}\';color:{th["muted"]}">{(h - 1) % 12 + 1}{"am" if h < 12 else "pm"}</span></div>' for h in range(a, z + 1))
        return f'<div class="box" style="flex:1"><span class="k">{label or "Schedule"}</span>{hrs}</div>'
    if k == 'pair':
        return '<div class="row">' + ''.join(f'<div style="flex:1;display:flex;flex-direction:column">{block(P, x)}</div>' for x in b['items']) + '</div>'
    if k == 'text':
        return f'<div class="box fill"><span class="k">{label}</span><span style="font-size:{P.fs(12.5)};line-height:1.45">{esc(b.get("text", ""))}</span></div>'
    raise ValueError(f'unknown block kind {k}')


BLOCK_KINDS = {
    'checklist': 'Checkbox list. label, rows, items (pre-filled), fill, grow',
    'lines': 'Lined writing box. label, grow (default true) or height',
    'dots': 'Dot-grid box. label, grow or height',
    'water': 'Water tracker drops. label, count',
    'scale': 'Circles 1 to max to rate energy, mood or focus. label, max',
    'hours': 'Hourly schedule. label, from, to, row (px)',
    'pair': 'Two blocks side by side. items: [block, block]',
    'text': 'Short printed tip or instruction. label, text',
}

DAY_PRESETS = {
    'default': {'left': [{'kind': 'checklist', 'label': 'Priorities', 'rows': 3, 'fill': True}, {'kind': 'checklist', 'label': 'To do', 'rows': 8, 'grow': True}],
                'right': [{'kind': 'hours', 'label': 'Schedule'}, {'kind': 'lines', 'label': 'Notes', 'grow': False, 'height': 60}]},
    'adhd': {'left': [{'kind': 'checklist', 'label': "Today's top 3", 'rows': 3, 'fill': True}, {'kind': 'dots', 'label': 'Brain dump'},
                      {'kind': 'pair', 'items': [{'kind': 'water'}, {'kind': 'scale', 'label': 'Energy 1 to 5'}]}],
             'right': [{'kind': 'hours', 'label': 'Time blocks'},
                       {'kind': 'pair', 'items': [{'kind': 'lines', 'label': 'One win today', 'grow': False}, {'kind': 'lines', 'label': 'Dopamine break', 'grow': False}]}]},
}
WEEK_PRESETS = {
    'default': [{'kind': 'lines', 'label': 'Priorities'}, {'kind': 'lines', 'label': 'Notes'}],
    'adhd': [{'kind': 'lines', 'label': 'This week I want to'},
             {'kind': 'checklist', 'label': 'Weekly reset', 'rows': 5, 'items': ['Empty inbox', 'Plan meals', 'Laundry done', 'Check budget', 'Rest one evening']},
             {'kind': 'dots', 'label': 'Brain dump'}],
}


# ---------- modules ----------
MODULES = {}


def module(name, desc, params=None, nav=None):
    def deco(fn):
        MODULES[name] = {'fn': fn, 'desc': desc, 'params': params or {}, 'nav': nav}
        return fn
    return deco


def _register(P, sec, label, anchor, kicker, nav=True):
    if sec.get('index', True):
        P.index_items.append((sec.get('label', label), anchor, sec.get('kicker', kicker)))
    if nav and sec.get('nav', True):
        P.nav_items.append((sec.get('nav_label', sec.get('label', label)), anchor))


@module('cover', 'Cover page with title, subtitle and an Open planner button')
def m_cover(P, sec):
    th = P.th; s = P.s
    inner = f'''<div style="position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 120px 0 90px;gap:18px">
      <p class="k" style="font-size:13px">{esc(s.get("kicker", "Digital planner"))}</p><p class="h" style="font-size:{sec.get("size", 92)}px;line-height:.95">{esc(s["title"])}</p>
      <p style="font-size:20px;color:{th["muted"]};max-width:560px;line-height:1.4">{esc(s.get("subtitle", ""))}</p>
      <div style="display:flex;gap:10px;margin-top:14px"><a href="#{sec.get("start", "index")}" style="padding:10px 22px;border-radius:99px;background:{th["ink"]};color:{th["paper"]};font:600 13px '{th["body"]}';letter-spacing:.14em;text-transform:uppercase">Open planner</a></div></div>'''
    P.page('cover', motif(th, 'tr', 5, 260) + motif(th, 'bl', 9, 220) + inner + P.rail(), raw=True, style=f'background:{th["soft"]}')


@module('index', 'Contents page: a card for every section plus all months', nav='Home')
def m_index(P, sec):
    th = P.th
    P.nav_items.insert(0, ('Home', 'index'))
    P._index_pending = True  # filled in at the end, once all sections are known
    P.page('index', '%%INDEX%%', active='index', deco=True)


def _fill_index(P):
    th = P.th
    cards = ''.join(f'<a href="#{a}" class="box" style="justify-content:space-between;min-height:76px;background:{c}22;border-color:{c}"><span class="k">{esc(k)}</span><span class="h" style="font-size:22px">{esc(l)}</span></a>'
                    for (l, a, k), c in zip(P.index_items[:12], P.tabs * 3))
    months = ''.join(f'<a href="#m{i + 1:02d}" style="padding:8px 0;text-align:center;border-radius:8px;background:{P.tabs[i]}55;font:600 12px \'{th["body"]}\'">{MONTHS[i]}</a>' for i in range(12))
    tip = P.s.get('index_tip', 'Tap a month tab on the right, any section above, or any date to jump there. Every page links back here with Home. Follow links in read mode (Goodnotes: turn the pen off).')
    inner = f'''<p class="h" style="font-size:44px">Contents</p>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">{cards}</div>
      <p class="k" style="margin-top:6px">Months</p><div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px">{months}</div>
      <div class="box fill" style="margin-top:auto"><span class="k">How the links work</span><span style="font-size:13px;line-height:1.5">{esc(tip)}</span></div>'''
    for i, pg in enumerate(P.pages):
        if '%%INDEX%%' in pg:
            P.pages[i] = pg.replace('%%INDEX%%', inner)


@module('year', 'Year at a glance: 12 mini calendars, every date links to its day (dated) or month (undated)', nav='Year')
def m_year(P, sec):
    th = P.th; blocks = ''
    for m in range(1, 13):
        cells, _ = P.cal_grid(m, small=True, link_days=not P.undated)
        cells = cells.replace('class="d', 'style="padding:2px 3px;font-size:9.5px;border:0;text-align:center" class="d')
        blocks += f'<div style="display:flex;flex-direction:column;gap:4px"><a href="#m{m:02d}" class="k" style="color:{th["ink"]};font-size:11px">{MONTHS[m - 1]}</a><div class="cal" style="font-size:9px">{cells}</div></div>'
    title = 'Year at a glance' if P.undated else f'{P.year} at a glance'
    _register(P, sec, 'Year', 'year', 'Calendar')
    P.page('year', P.head('Overview', title, right=f'<span class="k">{"Tap a month" if P.undated else "Tap any date"}</span>') + f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px 22px;flex:1">{blocks}</div>', active='year')


@module('lined', 'Lined or dot-grid writing pages (notes, goals, brain dump). label, kicker, pages, dots, anchor',
        params={'label': 'str', 'kicker': 'str', 'pages': 'int', 'dots': 'bool', 'anchor': 'str'})
def m_lined(P, sec):
    a = sec.get('anchor') or re.sub(r'[^a-z0-9]', '', sec['label'].lower())[:12]
    n = sec.get('pages', 1)
    _register(P, sec, sec['label'], a, sec.get('kicker', 'Pages'))
    for i in range(1, n + 1):
        anchor = a if i == 1 else f'{a}{i}'
        nxt = f' <a href="#{a}{i + 1}">&rarr;</a>' if i < n else ''
        P.page(anchor, P.head(sec.get('kicker', '') if n == 1 else f'{sec.get("kicker", "")} · page {i} of {n}', sec['label'], right=f'<span class="k" style="font-size:16px">{nxt}</span>') +
               f'<div class="box" style="flex:1"><div class="{"dots" if sec.get("dots") else "lines"}"></div></div>', active=a)


@module('checklist', 'Checklist page in columns. label, kicker, groups: [[title, [items]]], anchor',
        params={'label': 'str', 'kicker': 'str', 'groups': 'list', 'anchor': 'str'})
def m_checklist(P, sec):
    a = sec.get('anchor') or re.sub(r'[^a-z0-9]', '', sec['label'].lower())[:12]
    cols = ''.join(f'<div class="box" style="flex:1"><span class="k">{esc(g)}</span>{_chk(max(10, len(items)), items)}</div>' for g, items in sec['groups'])
    _register(P, sec, sec['label'], a, sec.get('kicker', 'List'))
    P.page(a, P.head(sec.get('kicker', ''), sec['label']) + f'<div class="row" style="flex:1">{cols}</div>', active=a)


@module('table', 'Table page. label, kicker, headers, rows, first_column (pre-filled), anchor',
        params={'label': 'str', 'headers': 'list', 'rows': 'int', 'first_column': 'list', 'anchor': 'str'})
def m_table(P, sec):
    th = P.th; a = sec.get('anchor') or re.sub(r'[^a-z0-9]', '', sec['label'].lower())[:12]
    hd = sec['headers']; n = len(hd); first = sec.get('first_column')
    head = ''.join(f'<span class="k" style="padding:6px 8px">{esc(h)}</span>' for h in hd)
    body = ''.join(f'<div style="display:grid;grid-template-columns:repeat({n},1fr);border-bottom:1px solid {th["line"]};height:30px;align-items:center">' +
                   ''.join(f'<span style="padding:0 8px;font-size:12px;font-weight:600">{esc(first[r]) if (first and j == 0 and r < len(first)) else ""}</span>' for j in range(n)) + '</div>' for r in range(sec.get('rows', 15)))
    _register(P, sec, sec['label'], a, sec.get('kicker', 'Tracker'))
    P.page(a, P.head(sec.get('kicker', ''), sec['label']) + f'<div class="box" style="flex:1;gap:0"><div style="display:grid;grid-template-columns:repeat({n},1fr);border-bottom:1.5px solid {th["ink"]}">{head}</div>{body}</div>', active=a)


@module('year_pixels', 'Year in pixels: color one square per day for mood or energy. label, keys', params={'label': 'str', 'keys': 'list'})
def m_pixels(P, sec):
    th = P.th; a = sec.get('anchor', 'pixels')
    head = '<span></span>' + ''.join(f'<span class="k" style="text-align:center;font-size:9px">{m[:1]}</span>' for m in MONTHS)
    rows = ''.join(f'<span style="font:600 9px \'{th["body"]}\';color:{th["muted"]};text-align:right;padding-right:4px">{d}</span>' +
                   ''.join(f'<i style="border:1px solid {th["line"]};border-radius:3px;{"opacity:.25;" if (not P.undated and d > calendar.monthrange(P.year, m)[1]) else ""}"></i>' for m in range(1, 13)) for d in range(1, 32))
    keys = ''.join(f'<div style="display:flex;gap:8px;align-items:center;font-size:12px"><i style="width:16px;height:16px;border-radius:4px;background:{c}"></i>{esc(k)}</div>' for k, c in zip(sec.get('keys', ['Great', 'Good', 'Okay', 'Low', 'Hard']), P.tabs[::2]))
    _register(P, sec, sec.get('label', 'Year in pixels'), a, 'Track')
    P.page(a, P.head('' if P.undated else str(P.year), sec.get('label', 'Year in pixels')) + f'<div class="row" style="flex:1"><div style="flex:3;display:grid;grid-template-columns:22px repeat(12,1fr);grid-template-rows:auto repeat(31,1fr);gap:2px">{head}{rows}</div><div class="box" style="flex:1;align-self:flex-start"><span class="k">Color key</span>{keys}</div></div>', active=a)


@module('guide', 'Printed guide page with numbered steps (how to start, how to import, how links work). label, kicker, steps: [[title, text]], tip, anchor',
        params={'label': 'str', 'kicker': 'str', 'steps': 'list', 'tip': 'str', 'anchor': 'str'})
def m_guide(P, sec):
    a = sec.get('anchor') or re.sub(r'[^a-z0-9]', '', sec['label'].lower())[:12]
    steps = ''.join(f'<div class="step"><b>{i}</b><div><p class="h" style="font-size:20px;margin-bottom:4px">{esc(t)}</p><p style="font-size:{P.fs(13)};line-height:1.45;color:{P.th["muted"]}">{esc(x)}</p></div></div>' for i, (t, x) in enumerate(sec['steps'], 1))
    tip = f'<div class="box fill" style="margin-top:auto"><span class="k">Tip</span><span style="font-size:13px;line-height:1.45">{esc(sec["tip"])}</span></div>' if sec.get('tip') else ''
    _register(P, sec, sec['label'], a, sec.get('kicker', 'Start here'))
    P.page(a, P.head(sec.get('kicker', 'Start here'), sec['label']) + f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px 28px">{steps}</div>{tip}', active=a, deco=True)


@module('link_test', 'Setup check page: buttons that jump to a test page and back, so buyers confirm links work before planning. label, anchor')
def m_link_test(P, sec):
    th = P.th; a = sec.get('anchor', 'linktest')
    targets = [('A month page', 'm01'), ('The year', 'year'), ('Contents', 'index')]
    btns = ''.join(f'<a href="#{t}" style="padding:14px 18px;border-radius:14px;background:{th["soft"]};font:600 15px \'{th["body"]}\';display:flex;justify-content:space-between"><span>{esc(l)}</span><span>&rarr;</span></a>' for l, t in targets)
    inner = P.head('Setup check', sec.get('label', 'Do your links work?')) + f'''
      <div class="row" style="flex:1"><div class="col" style="flex:1"><div class="box fill"><span class="k">Try it now</span><span style="font-size:{P.fs(14)};line-height:1.5">Tap each button. If it jumps, your planner is set up. Use the Home tab at the top to come back.</span></div>{btns}</div>
      <div class="col" style="flex:1"><div class="box" style="flex:1"><span class="k">Nothing happened?</span>{_chk(4, ["Turn the pen off (read or view mode)", "Open the file in a PDF planner app, not Files or Photos", "Re-import the PDF, do not convert it", "Still stuck? Message us on Etsy, we reply fast"])}</div></div></div>'''
    _register(P, sec, sec.get('label', 'Setup check'), a, 'Start here')
    P.page(a, inner, active=a)


@module('calendar', 'The dated or undated calendar: month pages, optional habit page per month, week pages and day pages, all cross-linked. month: {side: [labels]}, habits: bool, week: {preset | side: [blocks]}, day: {preset | left: [blocks], right: [blocks]}, days: bool',
        params={'month': 'dict', 'habits': 'bool', 'week': 'dict', 'day': 'dict', 'days': 'bool'})
def m_calendar(P, sec):
    th = P.th
    msec = sec.get('month', {}); wsec = sec.get('week', {}); dsec = sec.get('day', {})
    side_labels = msec.get('side', ['Goals', 'Notes'])
    wside = wsec.get('side') or WEEK_PRESETS[wsec.get('preset', 'default')]
    dlay = dsec if dsec.get('left') else DAY_PRESETS[dsec.get('preset', 'default')]
    if sec.get('habits'):
        _register(P, {'nav': False}, 'Habit trackers', 'm01h', 'Monthly', nav=False)
    for m in range(1, 13):
        cells, rows = P.cal_grid(m)
        if P.undated:
            weeks = list(range((m - 1) * 4 + 1, (m - 1) * 4 + 5)) + ([49 + (m - 1) // 3] if m % 3 == 0 else [])
            weeks = [w for w in weeks if w <= 52]
        else:
            weeks = sorted({P.week_of(d) for d in calendar.Calendar(0).itermonthdates(P.year, m) if d.month == m})
        wl = ''.join(f'<a href="#w{w:02d}" style="padding:4px 8px;border-radius:{P.rpill}px;background:{th["soft"]};font:600 10.5px \'{th["body"]}\'">Week {w}</a>' for w in weeks)
        side = ''.join(f'<div class="box" style="flex:1"><span class="k">{esc(x)}</span><div class="lines"></div></div>' for x in side_labels)
        habit = f'<a href="#m{m:02d}h" class="k" style="color:{th["ink"]};padding:6px 10px;border-radius:99px;border:1.3px solid {th["line"]}">Habit tracker</a>' if sec.get('habits') else ''
        title_k = 'Month' if P.undated else str(P.year)
        inner = f'''<div class="row" style="align-items:flex-end;justify-content:space-between"><div><p class="k">{title_k}</p><p class="h" style="font-size:52px">{MONTHS[m - 1]}</p></div><div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;max-width:520px">{habit}{wl}</div></div>
          <div class="row" style="flex:1"><div class="cal" style="flex:3;grid-template-rows:auto repeat({rows},1fr);border-bottom:1px solid {th["line"]}">{cells}</div><div class="col" style="flex:1.1">{side}</div></div>'''
        P.page(f'm{m:02d}', inner, month=m, crumb=f'<a href="#year">Year</a> / {MONTHS[m - 1]}')
        if sec.get('habits'):
            days = 31 if P.undated else calendar.monthrange(P.year, m)[1]
            head = ''.join(f'<span style="text-align:center;font:600 9.5px \'{th["body"]}\';color:{th["muted"]}">{d}</span>' for d in range(1, days + 1))
            gw = P.W - 110 - 150  # grid width for the day columns
            cw = gw / days
            circ = ''.join(f'<circle cx="{cw * (i + .5):.1f}" cy="15" r="6.3" fill="none" stroke="{mix(th["muted"], th["paper"], .3)}" stroke-width="1.3"/>' for i in range(days))
            hrows = ''.join(f'<div style="display:flex;align-items:center;border-bottom:1px solid {th["line"]};height:30px"><span style="width:150px;flex:none;border-right:1px solid {th["line"]};height:100%"></span><svg width="{gw}" height="30" viewBox="0 0 {gw} 30">{circ}</svg></div>' for _ in range(14))
            P.page(f'm{m:02d}h', P.head(MONTHS[m - 1], 'Habit tracker', right='<span class="k">One habit per line, fill a dot each day</span>') +
                   f'<div style="display:grid;grid-template-columns:150px repeat({days},1fr);padding-bottom:4px"><span class="k">Habit</span>{head}</div><div style="flex:1">{hrows}</div>', month=m, crumb=f'<a href="#m{m:02d}">{MONTHS[m - 1]}</a> / Habits')
        for n in weeks:
            _week(P, n, m, wside, dlay, sec.get('days', True))


def _week(P, n, m, side_blocks, day_layout, with_days):
    th = P.th
    if P.undated:
        days = [None] * 7
    else:
        start = P.week_start(n); days = [start + datetime.timedelta(days=i) for i in range(7)]
    cols = ''
    for i, d in enumerate(days):
        if d is None:
            target = f'u{n:02d}{i}'
            head = f'<a href="#{target}" style="display:flex;justify-content:space-between;align-items:baseline"><span class="k">{DOW[i]}</span><span class="h" style="font-size:22px;opacity:.35">__</span></a>' if with_days else f'<span class="k">{DOW[i]}</span>'
        elif d.year == P.year:
            head = f'<a href="#{P.did(d)}" style="display:flex;justify-content:space-between;align-items:baseline"><span class="k">{DOW[d.weekday()]}</span><span class="h" style="font-size:22px">{d.day}</span></a>' if with_days else f'<span class="k">{DOW[d.weekday()]} {d.day}</span>'
        else:
            head = f'<div style="display:flex;justify-content:space-between;opacity:.4"><span class="k">{DOW[d.weekday()]}</span><span class="h" style="font-size:22px">{d.day}</span></div>'
        cols += f'<div class="box" style="flex:1">{head}<div class="lines"></div></div>'
    side = ''.join(block(P, b) for b in side_blocks)
    rng = 'Write the dates' if P.undated else f'{MONTHS[days[0].month - 1][:3]} {days[0].day} to {MONTHS[days[6].month - 1][:3]} {days[6].day}'
    inner = f'''{P.head(rng, f"Week {n}")}
      <div class="row" style="flex:1"><div style="flex:3;display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:1fr 1fr;gap:10px">{cols}<div class="box fill"><span class="k">Notes</span><div class="dots"></div></div></div><div class="col" style="flex:1.05">{side}</div></div>'''
    P.page(f'w{n:02d}', inner, month=m, crumb=f'<a href="#m{m:02d}">{MONTHS[m - 1]}</a> / Week {n}')
    if not with_days:
        return
    for i, d in enumerate(days):
        if d is not None and d.year != P.year:
            continue
        _day(P, d, n, m, i, day_layout)


def _day(P, d, n, m, i, lay):
    if d is None:
        anchor = f'u{n:02d}{i}'
        prev_a = f'u{n:02d}{i - 1}' if i > 0 else None
        next_a = f'u{n:02d}{i + 1}' if i < 6 else None
        title = DOW[i] + 'day' if DOW[i] != 'Wed' else 'Wednesday'
        title = {'Mon': 'Monday', 'Tue': 'Tuesday', 'Wed': 'Wednesday', 'Thu': 'Thursday', 'Fri': 'Friday', 'Sat': 'Saturday', 'Sun': 'Sunday'}[DOW[i]]
        kicker = f'Week {n} · date ____'
    else:
        anchor = P.did(d)
        pd, nd = d - datetime.timedelta(days=1), d + datetime.timedelta(days=1)
        prev_a = P.did(pd) if pd.year == P.year else None
        next_a = P.did(nd) if nd.year == P.year else None
        title = f'{MONTHS[d.month - 1]} {d.day}'
        kicker = d.strftime('%A')
    arrows = (f'<a href="#{prev_a}">&larr;</a>' if prev_a else '') + (f' <a href="#{next_a}">&rarr;</a>' if next_a else '')
    left = ''.join(block(P, b) for b in lay['left'])
    right = ''.join(block(P, b) for b in lay['right'])
    inner = f'{P.head(kicker, title, right=f"<span class=k style=font-size:16px>{arrows}</span>")}<div class="row" style="flex:1"><div class="col" style="flex:1">{left}</div><div class="col" style="flex:1.15">{right}</div></div>'
    P.page(anchor, inner, month=(d.month if d else m), crumb=f'<a href="#m{m:02d}">{MONTHS[m - 1]}</a> / <a href="#w{n:02d}">Week {n}</a>')


# ---------- build ----------
def capabilities():
    return {'modules': {k: {'desc': v['desc'], 'params': v['params']} for k, v in MODULES.items()},
            'blocks': BLOCK_KINDS, 'day_presets': list(DAY_PRESETS), 'week_presets': list(WEEK_PRESETS),
            'themes': list(THEMES), 'orientations': list(SIZES), 'dating': ['dated (year)', 'undated'],
            'fonts': ['Corm', 'Jost', 'Fraunces', 'Manrope', 'Quicksand', 'Nunito', 'DMSerif', 'Outfit', 'Baskerville', 'Script'],
            'type_scale': 'number, 1.0 default; 1.15 for larger text'}


def validate_spec(spec):
    problems, needs = [], []
    for k in ('title', 'sections'):
        if k not in spec:
            problems.append(f'missing {k}')
    for s in spec.get('sections', []):
        if s.get('module') not in MODULES:
            needs.append(s.get('module'))
    try:
        resolve_theme(spec.get('theme', 'neutral'))
    except Exception as e:
        problems.append(f'theme: {e}')
    return problems, needs


def build(spec):
    problems, needs = validate_spec(spec)
    if problems or needs:
        raise ValueError(f'spec problems: {problems}; needs_module: {needs}')
    P = Planner(spec)
    for sec in spec['sections']:
        P.current = sec['module']
        MODULES[sec['module']]['fn'](P, sec)
    if getattr(P, '_index_pending', False):
        _fill_index(P)
    html = P.html()
    ids = set(re.findall(r'id="([^"]+)"', html))
    broken = sorted(set(h for h in re.findall(r'href="#([^"]+)"', html) if h not in ids))
    return {'html': html, 'pages': len(P.pages), 'page_modules': P.page_modules, 'broken_links': broken,
            'size': (P.W, P.HT), 'links': len(re.findall(r'href="#', html))}


if __name__ == '__main__':
    import sys
    print(json.dumps(capabilities(), indent=1))
