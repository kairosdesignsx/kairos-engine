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


def arrow(d='r', size=14):
    """Arrow drawn as SVG: the planner fonts have no arrow glyphs, and a fallback font would be embedded (licensing check)."""
    path = 'M2,7 H12 M8,3 L12,7 L8,11' if d == 'r' else 'M12,7 H2 M6,3 L2,7 L6,11'
    return f'<svg width="{size}" height="{size}" viewBox="0 0 14 14" style="vertical-align:-2px"><path d="{path}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'


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
        # e-ink format (eink_format section): applies to the whole file, wherever the section sits in the list
        self.eink = next((x for x in spec.get('sections', []) if x.get('module') == 'eink_format'), None) or {}
        self.gutter = int(self.eink.get('left_gutter', 40)) if self.eink else 40
        self.gray = bool(self.eink.get('grayscale'))
        self.btn = self.th.get('button', self.th['ink'])  # buttons (Open, Go there): theme token 'button', default ink
        # iso_weeks (calendar option): Week 1 is the week holding January 4 (ISO 8601), so days before it sit in week 0
        self.iso = any(x.get('module') == 'calendar' and x.get('iso_weeks') for x in spec.get('sections', []))
        self.noun = 'planner'   # what the file calls itself in printed help ('journal' when the cover button says so)

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
.nav{{position:absolute;left:{self.gutter}px;right:70px;top:16px;display:flex;gap:6px;align-items:center;z-index:3}}
.nav a{{font:600 10.5px '{th['body']}';letter-spacing:.12em;text-transform:uppercase;padding:5px 10px;border-radius:{self.rpill}px;background:{th['soft']};color:{th['ink']}}}
.nav a.on{{background:{th['ink']};color:{th['paper']}}}
.nav .crumb{{margin-left:auto;font:500 11px '{th['body']}';color:{th['muted']};letter-spacing:.06em}}
.nav .crumb a{{background:none;padding:0 4px;text-transform:none;letter-spacing:.04em}}
.body{{position:absolute;left:{self.gutter}px;right:70px;top:56px;bottom:26px;display:flex;flex-direction:column;gap:12px}}
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
.foot{{position:absolute;left:{self.gutter}px;bottom:8px;font:500 9.5px '{th['body']}';color:{th['muted']};letter-spacing:.08em}}
.step{{display:flex;gap:12px;align-items:flex-start}}
.step b{{flex:none;width:28px;height:28px;border-radius:50%;background:{th['ink']};color:{th['paper']};display:flex;align-items:center;justify-content:center;font:700 13px '{th['body']}'}}
""" + self.label_css() + (self.eink_css() if self.eink else '')

    def label_css(self):
        """theme 'labels': 'italic' = two-font hierarchy by weight and italic instead of tracked all-caps labels
        (Colynne, p-rjd-001: tracked caps read as a third font and tire the eyes). Labels set in the display face's
        italic, pills and calendar heads in the body face's bold, normal case."""
        th = self.th
        if th.get('labels') != 'italic':
            return ''
        return (f".k{{font:italic 400 {self.fs(13)} '{th['display']}',serif;letter-spacing:0;text-transform:none;color:{th['muted']}}}"
                f".nav a{{font:700 11.5px '{th['body']}';letter-spacing:.02em;text-transform:none}}"
                f".cal .hd{{font:700 11px '{th['body']}';letter-spacing:.02em;text-transform:none}}"
                f".rail a{{letter-spacing:.02em}}.foot{{letter-spacing:0}}"
                f"[style*='text-transform:uppercase']{{text-transform:none!important;letter-spacing:.02em!important}}")

    # ---------- e-ink: writing lines and dots as plain vector strokes ----------
    def rule_period(self):
        return round(28 * self.scale)

    def eink_css(self):
        out = '.wkside>*{flex:1 1 0;min-width:0}'  # week side blocks laid in a row (week_layout rows)
        if self.eink.get('vector_rules'):
            out += '.lines,.dots{background:none!important;position:relative;overflow:hidden}.lines>svg,.dots>svg{position:absolute;left:0;top:0}'
        return out

    def vector_script(self):
        """Lines and dots drawn as SVG strokes (vector paths in the PDF, no gradient pattern), each sized to its own box
        when the page is laid out, so nothing clipped is drawn. Same rhythm as the gradient version: a 1px rule at the
        bottom of every line, a dot every 18px (zero-length round-capped strokes: one tiny path each)."""
        p, c = self.rule_period(), self.th['line']
        return ("<script>(function(){var P=%d,C='%s';document.querySelectorAll('.lines,.dots').forEach(function(e){"
                "var w=e.clientWidth,h=e.clientHeight,d='',x,y,ln=e.classList.contains('lines');"
                "if(ln){for(y=P-1;y<h;y+=P)d+='M0,'+(y+.5)+'H'+w;}else{for(y=13;y<h-1;y+=18)for(x=13;x<w-1;x+=18)d+='M'+x+','+y+'h0';}"
                "e.innerHTML='<svg width=\"'+w+'\" height=\"'+h+'\" viewBox=\"0 0 '+w+' '+h+'\"><path d=\"'+d+'\" fill=\"none\" stroke=\"'+C+'\" '+"
                "(ln?'stroke-width=\"1\" shape-rendering=\"crispEdges\"':'stroke-width=\"2.4\" stroke-linecap=\"round\"')+'/></svg>';});})();</script>") % (p, c)

    def tint(self, i, alpha):
        """Background for a month or card tint; flat gray on a grayscale (e-ink) file."""
        return self.th['soft'] if self.gray else f'{self.tabs[i]}{alpha}'

    def nav(self, active=None, crumb=''):
        # placeholder, filled in html() once every section has registered, so early pages get the full bar
        return f'<div class="nav">%%NAV:{active or ""}%%<span class="crumb">{crumb}</span></div>'

    def nav_links(self, active):
        return ''.join(f'<a href="#{a}" class="{"on" if a == active else ""}">{esc(l)}</a>' for l, a in self.nav_items[:7 if self.W > self.HT else 4])

    def rail(self, month=None, rail_map=None, rail_labels=None):
        out = []
        for i in range(12):
            c = self.tabs[i]; on = month == i + 1
            target = (rail_map or {}).get(i + 1, f'm{i + 1:02d}')
            out.append(f'<a href="#{target}" class="{"on" if on else ""}" style="background:{c}{"" if (on or self.gray) else "cc"}">{(rail_labels or {}).get(i + 1, MONTHS[i][:3] if self.th.get('labels') == 'italic' else MONTHS[i][:3].upper())}</a>')
        return f'<div class="rail">{"".join(out)}</div>'

    def page(self, anchor, inner, active=None, month=None, crumb='', deco=False, raw=False, style='', rail_map=None, rail_labels=None):
        self.seed += 3
        m = (motif(self.th, 'tr', self.seed) + motif(self.th, 'bl', self.seed + 1)) if deco else ''
        if raw:
            self.pages.append(f'<section class="pg" id="{anchor}" style="{style}">{inner}</section>')
        else:
            self.pages.append(f'<section class="pg" id="{anchor}" style="{style}">{m}{self.nav(active, crumb)}{self.rail(month, rail_map, rail_labels)}<div class="body">{inner}</div><p class="foot">{esc(self.s.get("brand", ""))}</p></section>')
        self.page_modules.append((anchor, self.current))

    def head(self, kicker, title, size=44, right=''):
        return f'<div class="row" style="align-items:flex-end;justify-content:space-between"><div><p class="k">{esc(kicker)}</p><p class="h" style="font-size:{size}px">{esc(title)}</p></div>{right}</div>'

    # ---------- dates ----------
    @staticmethod
    def did(d):
        return f'd{d.month:02d}{d.day:02d}'

    def _week1(self):
        first = datetime.date(self.year, 1, 4 if self.iso else 1)
        return first - datetime.timedelta(days=first.weekday())

    def week_of(self, d):
        return (d - self._week1()).days // 7 + 1

    def week_start(self, n):
        return self._week1() + datetime.timedelta(days=7 * (n - 1))

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
        body = re.sub(r'%%NAV:([^%]*)%%', lambda m: self.nav_links(m.group(1) or None), ''.join(self.pages))
        if self.eink.get('vector_rules'):
            body += self.vector_script()
        return f'<!doctype html><html><head><meta charset="utf-8"><style>{self.css()}</style></head><body>{body}</body></html>'


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
        keep = ';flex:none' if P.eink else ''  # e-ink: hour rows keep their height (writing room); the box after them gives way
        hfs = P.fs(11.5) if P.eink else '10.5px'
        hrs = ''.join(f'<div style="display:flex;gap:8px;border-bottom:1px solid {th["line"]};height:{b.get("row", 26)}px;align-items:center{keep}"><span style="width:38px;font:600 {hfs} \'{th["body"]}\';color:{th["muted"]}">{(h - 1) % 12 + 1}{"am" if h < 12 else "pm"}</span></div>' for h in range(a, z + 1))
        return f'<div class="box" style="flex:{"none" if P.eink else "1"}"><span class="k">{label or "Schedule"}</span>{hrs}</div>'
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



def _mm(P):
    """The money_month section of this spec, if any (month pages built earlier link forward to it)."""
    return next((x for x in P.s.get('sections', []) if x.get('module') == 'money_month'), None)


def _mm_chip(P, anchor):
    th = P.th
    return f'<a href="#{anchor}" class="k" style="color:{th["ink"]};padding:6px 10px;border-radius:99px;border:1.3px solid {th["line"]}">{esc((_mm(P) or {}).get("label", "Money month"))}</a>'

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


@module('cover', 'Cover page with title, subtitle and an Open button. start (anchor the button opens, default index), button (default Open planner; "Open journal" also makes printed help say journal), size (title px)',
        params={'start': 'str', 'button': 'str, default "Open planner"', 'size': 'int'})
def m_cover(P, sec):
    th = P.th; s = P.s
    button = sec.get('button', 'Open planner')
    if sec.get('button'):
        P.noun = button.split()[-1].lower()
    inner = f'''<div style="position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 120px 0 90px;gap:18px">
      <p class="k" style="font-size:13px">{esc(s.get("kicker", "Digital planner"))}</p><p class="h" style="font-size:{sec.get("size", 92)}px;line-height:.95">{esc(s["title"])}</p>
      <p style="font-size:20px;color:{th["muted"]};max-width:560px;line-height:1.4">{esc(s.get("subtitle", ""))}</p>
      <div style="display:flex;gap:10px;margin-top:14px"><a href="#{sec.get("start", "index")}" style="padding:10px 22px;border-radius:99px;background:{P.btn};color:{th["paper"]};font:600 13px '{th["body"]}';letter-spacing:.14em;text-transform:uppercase">{esc(button)}</a></div></div>'''
    P.page('cover', motif(th, 'tr', 5, 260) + motif(th, 'bl', 9, 220) + inner + P.rail(), raw=True, style=f'background:{th["paper"] if P.gray else th["soft"]}')  # e-ink: pure white, a tint dithers


@module('index', 'Contents page: a card for every section plus all months', nav='Home')
def m_index(P, sec):
    th = P.th
    P.nav_items.insert(0, ('Home', 'index'))
    P._index_pending = True  # filled in at the end, once all sections are known
    P.page('index', '%%INDEX%%', active='index', deco=True)


def _fill_index(P):
    th = P.th
    cards = ''.join(f'<a href="#{a}" class="box" style="justify-content:space-between;min-height:76px;background:{th["paper"] if P.gray else c + "22"};border-color:{th["line"] if P.gray else c}"><span class="k">{esc(k)}</span><span class="h" style="font-size:22px">{esc(l)}</span></a>'
                    for (l, a, k), c in zip(P.index_items[:12], P.tabs * 3))
    hs_style = f'background:{th["paper"]};color:{th["ink"]};box-shadow:inset 0 0 0 2px {th["ink"]}' if P.gray else f'background:{th["ink"]};color:{th["paper"]}'  # e-ink: no large dark blocks (they ghost)
    months = ''.join(f'<a href="#{an}" style="padding:8px 0;text-align:center;border-radius:8px;{hs_style};font:600 12px \'{th["body"]}\'">{esc(lb)}</a>' for lb, an in getattr(P, 'head_start_links', []))
    months += ''.join(f'<a href="#m{i + 1:02d}" style="padding:8px 0;text-align:center;border-radius:8px;background:{P.tint(i, "55")};font:600 12px \'{th["body"]}\'">{MONTHS[i]}{"" if P.undated or not getattr(P, "head_start_links", None) else " " + str(P.year)}</a>' for i in range(12))
    tip = P.s.get('index_tip', 'Tap a month tab on the right, any section above, or any date to jump there. Home on the top bar brings you back here, and calendar pages show where you are at the top right. Follow links in read mode (Goodnotes: turn the pen off).')
    if P.HT > P.W:  # portrait: wider cards, and a months grid that fills the page with big tap targets
        cards = cards.replace('min-height:76px', 'min-height:96px')
        months = months.replace('padding:8px 0;text-align:center', 'display:flex;align-items:center;justify-content:center;text-align:center').replace("font:600 12px", f"font:600 {P.fs(14)}")
        grid = f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">{cards}</div><p class="k" style="margin-top:6px">Months</p><div style="flex:1;display:grid;grid-template-columns:repeat(3,1fr);grid-auto-rows:1fr;gap:8px">{months}</div>'
    else:
        grid = f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">{cards}</div>\n      <p class="k" style="margin-top:6px">Months</p><div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px">{months}</div>'
    inner = f'''<p class="h" style="font-size:44px">Contents</p>
      {grid}
      <div class="box fill" style="margin-top:auto{";flex:none" if P.HT > P.W else ""}"><span class="k">How the links work</span><span style="font-size:13px;line-height:1.5">{esc(tip)}</span></div>'''
    for i, pg in enumerate(P.pages):
        if '%%INDEX%%' in pg:
            P.pages[i] = pg.replace('%%INDEX%%', inner)


def _fill_link_test_map(P):
    """'Where things are': the top bar's buttons and what each opens (portrait Setup check, under the fix list)."""
    th = P.th
    kick = {a: k for (l, a, k) in P.index_items}
    items = ''.join(f'<a href="#{an}" style="display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid {th["line"]}"><b style="min-width:84px;font:700 {P.fs(11.5)} \'{th["body"]}\';text-transform:uppercase;letter-spacing:.08em">{esc(l)}</b><span style="font-size:{P.fs(13)};color:{th["muted"]}">{esc("Contents" if an == "index" else kick.get(an, ""))}</span></a>' for l, an in P.nav_items[:7 if P.W > P.HT else 4])
    box = f'<div class="box" style="flex:1"><span class="k">Where things are: the top bar</span><div style="flex:1;display:flex;flex-direction:column;justify-content:space-evenly">{items}</div></div>'
    for i, pg in enumerate(P.pages):
        if '%%LT_MAP%%' in pg:
            P.pages[i] = pg.replace('%%LT_MAP%%', box)


def _fill_guides(P):
    """Guide pages get their extra panels at the end, once every section is known."""
    th = P.th
    for a, sec in getattr(P, 'guide_extras', {}).items():
        extra = ''
        if sec.get('map'):
            items = ''.join(f'<a href="#{an}" style="display:flex;gap:10px;align-items:baseline;padding:5px 0;border-bottom:1px solid {th["line"]}"><b style="min-width:110px;font:700 12px \'{th["body"]}\';text-transform:uppercase;letter-spacing:.08em">{esc(l)}</b><span style="font-size:{P.fs(13.5)};color:{th["muted"]}">{esc(next((k for (l2, a2, k) in P.index_items if a2 == an), ""))}</span></a>' for l, an in P.nav_items[:7 if P.W > P.HT else 4] if next((k for (l2, a2, k) in P.index_items if a2 == an), ""))
            extra += f'<div class="box" style="flex:none"><span class="k">{esc(sec.get("map_label", "The top bar, on every page"))}</span><div style="display:grid;grid-template-columns:1fr 1fr;gap:0 28px">{items}</div></div>'
        if sec.get('months'):
            hs_style = f'background:{th["paper"]};color:{th["ink"]};box-shadow:inset 0 0 0 2px {th["ink"]}' if P.gray else f'background:{th["ink"]};color:{th["paper"]}'
            ms = ''.join(f'<a href="#{an}" style="display:flex;align-items:center;justify-content:center;border-radius:12px;{hs_style};font:600 15px \'{th["body"]}\'">{esc(lb)}</a>' for lb, an in getattr(P, 'head_start_links', []))
            ms += ''.join(f'<a href="#m{i + 1:02d}" style="display:flex;align-items:center;justify-content:center;border-radius:12px;background:{P.tint(i, "55")};font:600 15px \'{th["body"]}\'">{MONTHS[i]}{"" if P.undated else " " + str(P.year)}</a>' for i in range(12))
            extra += f'<div class="box" style="flex:1"><span class="k">{esc(sec.get("months_label", "Jump back in: tap this month"))}</span><div style="flex:1;display:grid;grid-template-columns:repeat(6,1fr);grid-auto-rows:1fr;gap:10px">{ms}</div></div>'
        if not extra:
            extra = '<div style="flex:1"></div>'
        for i, pg in enumerate(P.pages):
            if f'%%GUIDE_EXTRA:{a}%%' in pg:
                P.pages[i] = pg.replace(f'%%GUIDE_EXTRA:{a}%%', extra)


@module('year', 'Year at a glance: 12 mini calendars, every date links to its day (dated) or month (undated)', nav='Year')
def m_year(P, sec):
    th = P.th; blocks = ''
    for m in range(1, 13):
        cells, nrows = P.cal_grid(m, small=True, link_days=not P.undated)
        cells += '<span class="d x"></span>' * (7 * (6 - nrows))
        cells = cells.replace('class="d', 'style="padding:2px 3px;font-size:9.5px;border:0;text-align:center" class="d')
        blocks += f'<div style="display:flex;flex-direction:column;gap:4px"><a href="#m{m:02d}" class="k" style="color:{th["ink"]};font-size:11px">{MONTHS[m - 1]}</a><div class="cal" style="font-size:9px">{cells}</div></div>'
    title = 'Year at a glance' if P.undated else f'{P.year} at a glance'
    _register(P, sec, 'Year', 'year', 'Calendar')
    chips = ''.join(f'<a href="#{a_}" style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:{P.rpill}px;{(f'background:{th["paper"]};color:{th["ink"]};box-shadow:inset 0 0 0 1.5px {th["ink"]}') if P.gray else (f'background:{th["ink"]};color:{th["paper"]}')};font:600 11px \'{th["body"]}\';letter-spacing:.06em;text-transform:uppercase">{esc(l_)} {arrow("r", 12)}</a>' for l_, a_ in sec.get('links', []))
    hint = f'<div style="display:flex;gap:12px;align-items:center">{chips}<span class="k">{"Tap a month" if P.undated else "Tap any date"}</span></div>'
    if P.HT > P.W and chips:  # portrait: the chips and hint get their own row under the title, so neither wraps
        hint = hint.replace('text-transform:uppercase">', 'text-transform:uppercase;white-space:nowrap">').replace('<span class="k">', '<span class="k" style="white-space:nowrap">')
        head = P.head('Overview', title) + f'<div style="display:flex;justify-content:space-between;align-items:center">{hint}</div>'
    else:
        head = P.head('Overview', title, right=hint)
    P.page('year', head + f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px 22px;flex:1">{blocks}</div>', active='year')


@module('lined', 'Lined or dot-grid writing pages (notes, goals, brain dump). label, kicker, pages, dots, anchor',
        params={'label': 'str', 'kicker': 'str', 'pages': 'int', 'dots': 'bool', 'anchor': 'str'})
def m_lined(P, sec):
    a = sec.get('anchor') or re.sub(r'[^a-z0-9]', '', sec['label'].lower())[:12]
    n = sec.get('pages', 1)
    _register(P, sec, sec['label'], a, sec.get('kicker', 'Pages'))
    for i in range(1, n + 1):
        anchor = a if i == 1 else f'{a}{i}'
        nxt = f' <a href="#{a}{i + 1}">{arrow('r')}</a>' if i < n else ''
        prv = f'<a href="#{a if i == 2 else f"{a}{i - 1}"}">{arrow("l")}</a> ' if i > 1 else ''
        th = P.th  # with several pages, a numbered strip opens any of them directly (every page two taps from Contents)
        strip = '' if n == 1 else ''.join(f'<a href="#{a if j == 1 else f"{a}{j}"}" style="display:inline-flex;align-items:center;justify-content:center;min-width:30px;padding:5px 9px;border-radius:{P.rpill}px;font:600 11px \'{th["body"]}\';{"background:" + th["ink"] + ";color:" + th["paper"] if j == i else "background:" + th["soft"]}">{j}</a>' for j in range(1, n + 1))
        right = f'<div style="display:flex;gap:6px;align-items:center">{strip}<span class="k" style="font-size:16px;margin-left:8px">{prv}{nxt}</span></div>'
        P.page(anchor, P.head(sec.get('kicker', '') if n == 1 else f'{sec.get("kicker", "")} · page {i} of {n}', sec['label'], right=right) +
               f'<div class="box" style="flex:1"><div class="{"dots" if sec.get("dots") else "lines"}"></div></div>', active=a)


@module('checklist', 'Checklist page in columns. label, kicker, groups: [[title, [items]]], anchor',
        params={'label': 'str', 'kicker': 'str', 'groups': 'list', 'anchor': 'str'})
def m_checklist(P, sec):
    a = sec.get('anchor') or re.sub(r'[^a-z0-9]', '', sec['label'].lower())[:12]
    rows = sec.get('rows', 14 if P.W > P.HT else 20)
    cols = ''.join(f'<div class="box" style="flex:1"><span class="k">{esc(g)}</span>{_chk(max(rows, len(items)), items)}</div>' for g, items in sec['groups'])
    _register(P, sec, sec['label'], a, sec.get('kicker', 'List'))
    P.page(a, P.head(sec.get('kicker', ''), sec['label']) + f'<div class="row" style="flex:1">{cols}</div>', active=a)


@module('table', 'Table page. label, kicker, headers, rows, first_column (pre-filled), anchor, check_columns (headers drawn as a narrow column of tick boxes), dividers (column rules)',
        params={'label': 'str', 'headers': 'list', 'rows': 'int', 'first_column': 'list', 'anchor': 'str', 'check_columns': 'list of header names', 'dividers': 'bool'})
def m_table(P, sec):
    th = P.th; a = sec.get('anchor') or re.sub(r'[^a-z0-9]', '', sec['label'].lower())[:12]
    hd = sec['headers']; n = len(hd); first = sec.get('first_column')
    checks = set(sec.get('check_columns') or []); div = sec.get('dividers', False)
    cols = ' '.join(f'{68 * P.scale:.0f}px' if h in checks else '1fr' for h in hd) if (checks or div) else f'repeat({n},1fr)'
    sep = lambda j: f'border-left:1px solid {th["line"]};' if (div and j > 0) else ''
    box = f'<i style="width:15px;height:15px;border:1.4px solid {th["muted"]};border-radius:3px;display:block;margin:auto"></i>'
    head = ''.join(f'<span class="k" style="padding:6px 8px;{"text-align:center;" if h in checks else ""}">{esc(h)}</span>' for h in hd)
    cell = lambda r, j: (box if hd[j] in checks else (esc(first[r]) if (first and j == 0 and r < len(first)) else ''))
    body = ''.join(f'<div style="display:grid;grid-template-columns:{cols};border-bottom:1px solid {th["line"]};height:30px;align-items:{"stretch" if div else "center"}">' +
                   ''.join(f'<span style="padding:0 8px;font-size:12px;font-weight:600;{sep(j)}{"display:flex;align-items:center" if div else ""}">{cell(r, j)}</span>' for j in range(n)) + '</div>' for r in range(sec.get('rows', 15)))
    _register(P, sec, sec['label'], a, sec.get('kicker', 'Tracker'))
    P.page(a, P.head(sec.get('kicker', ''), sec['label']) + f'<div class="box" style="flex:1;gap:0"><div style="display:grid;grid-template-columns:{cols};border-bottom:1.5px solid {th["ink"]}">{head}</div>{body}</div>', active=a)


@module('year_pixels', 'Year in pixels: color one square per day for mood or energy. label, keys', params={'label': 'str', 'keys': 'list'})
def m_pixels(P, sec):
    th = P.th; a = sec.get('anchor', 'pixels')
    head = '<span></span>' + ''.join(f'<span class="k" style="text-align:center;font-size:9px">{m[:1]}</span>' for m in MONTHS)
    rows = ''.join(f'<span style="font:600 9px \'{th["body"]}\';color:{th["muted"]};text-align:right;padding-right:4px">{d}</span>' +
                   ''.join(f'<i style="border:1px solid {th["line"]};border-radius:3px;{"opacity:.25;" if (not P.undated and d > calendar.monthrange(P.year, m)[1]) else ""}"></i>' for m in range(1, 13)) for d in range(1, 32))
    keys = ''.join(f'<div style="display:flex;gap:8px;align-items:center;font-size:12px"><i style="width:16px;height:16px;border-radius:4px;background:{c}"></i>{esc(k)}</div>' for k, c in zip(sec.get('keys', ['Great', 'Good', 'Okay', 'Low', 'Hard']), [P.th['accent'], P.tabs[0], P.th['warm'], P.tabs[-1], P.th['muted']]))
    _register(P, sec, sec.get('label', 'Year in pixels'), a, 'Track')
    P.page(a, P.head('' if P.undated else str(P.year), sec.get('label', 'Year in pixels')) + f'<div class="row" style="flex:1"><div style="flex:3;display:grid;grid-template-columns:22px repeat(12,1fr);grid-template-rows:auto repeat(31,1fr);gap:2px">{head}{rows}</div><div class="box" style="flex:1;align-self:flex-start"><span class="k">Color key</span>{keys}</div></div>', active=a)


@module('guide', 'Printed guide page with numbered steps (how to start, how to import, how links work). label, kicker, steps: [[title, text]], tip, anchor',
        params={'label': 'str', 'kicker': 'str', 'steps': 'list', 'tip': 'str', 'anchor': 'str'})
def m_guide(P, sec):
    a = sec.get('anchor') or re.sub(r'[^a-z0-9]', '', sec['label'].lower())[:12]
    steps = ''.join(f'<div class="box step" style="padding:18px 20px;gap:14px;flex-direction:row"><b style="width:36px;height:36px;font-size:16px">{i}</b><div style="display:flex;flex-direction:column;gap:8px;flex:1"><p class="h" style="font-size:24px">{esc(st[0])}</p><p style="font-size:{P.fs(14.5)};line-height:1.5;color:{P.th["muted"]}">{esc(st[1])}</p>{(f'<a href="#{st[2]}" style="align-self:flex-start;margin-top:auto;padding:8px 16px;border-radius:{P.rpill}px;background:{P.btn};color:{P.th["paper"]};font:600 12px \'{P.th["body"]}\';letter-spacing:.08em;text-transform:uppercase">Go there {arrow("r")}</a>') if len(st) > 2 and st[2] else ''}</div></div>' for i, st in enumerate(sec['steps'], 1))
    tip = f'<div class="box fill" style="margin-top:auto"><span class="k">Tip</span><span style="font-size:13px;line-height:1.45">{esc(sec["tip"])}</span></div>' if sec.get('tip') else ''
    _register(P, sec, sec['label'], a, sec.get('kicker', 'Start here'))
    P.page(a, P.head(sec.get('kicker', 'Start here'), sec['label']) + f'<div style="display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:1fr;gap:14px;flex:1">{steps}</div>%%GUIDE_EXTRA:{a}%%{tip}', active=a, deco=True)
    P.guide_extras = getattr(P, 'guide_extras', {})
    P.guide_extras[a] = sec


@module('link_test', 'Setup check page: buttons that jump to a test page and back, so buyers confirm links work before planning. label, anchor')
def m_link_test(P, sec):
    th = P.th; a = sec.get('anchor', 'linktest')
    targets = [('A month page', 'm01'), ('The year', 'year'), ('Contents', 'index')]
    btns = ''.join(f'<a href="#{t}" style="padding:16px 22px;border-radius:14px;background:{th["soft"]};font:600 17px \'{th["body"]}\';display:flex;justify-content:space-between;align-items:center"><span>{esc(l)}</span><span>{arrow('r')}</span></a>' for l, t in targets)
    fixes = _chk(4, P.eink.get('link_test_fixes') or ["Turn the pen off (read or view mode)", f"Open the file in a {'note' if P.noun == 'journal' else 'PDF planner'} app, not Files or Photos", "Re-import the PDF, do not convert it", "Still stuck? Send the shop an Etsy message" if P.noun == 'journal' else "Still stuck? Message us on Etsy and we will help"])
    pen = P.eink.get('pen_label', 'Test the pen: turn it on and write your name here')
    ltmap = '%%LT_MAP%%' if P.HT > P.W else ''  # portrait: the tall left column gets a map of the top bar (no half-empty page)
    inner = P.head('Setup check', sec.get('label', 'Do your links work?')) + f'''
      <div class="row" style="flex:1">
        <div class="col" style="flex:1"><div class="box fill"><span class="k">Try it now</span><span style="font-size:{P.fs(14)};line-height:1.5">Tap each button. If it jumps, your {P.noun} is set up. To come back here, tap Home, then Setup check.</span></div>{btns}
          <div class="box"><span class="k">Nothing happened?</span>{fixes}</div>{ltmap}</div>
        <div class="col" style="flex:1"><div class="box" style="flex:1"><span class="k">{esc(pen)}</span><div class="lines"></div></div></div>
      </div>'''
    _register(P, sec, sec.get('label', 'Setup check'), a, sec.get('kicker', 'Check links'))
    P.page(a, inner, active=a)


@module('calendar', 'The dated or undated calendar: month pages, optional habit page per month, week pages and day pages, all cross-linked. month: {side: [labels]}, habits: bool, week: {preset | side: [blocks]}, day: {preset | left: [blocks], right: [blocks]}, days: bool',
        params={'month': 'dict', 'habits': 'bool', 'week': 'dict', 'day': 'dict', 'days': 'bool', 'iso_weeks': 'bool: ISO 8601 week numbers (Week 1 holds January 4); needs a head_start covering the days before it'})
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
        w0 = [w for w in weeks if w < 1]; weeks = [w for w in weeks if w >= 1]  # iso_weeks: week 0 belongs to the year before
        wl = ''.join(f'<a href="#w{w:02d}" style="display:inline-flex;align-items:center;line-height:1;padding:6px 9px;border-radius:{P.rpill}px;background:{th["soft"]};font:600 10.5px \'{th["body"]}\'">Week {w}</a>' for w in weeks)
        side = ''.join(f'<div class="box" style="flex:1"><span class="k">{esc(x)}</span><div class="lines"></div></div>' for x in side_labels)
        habit = f'<a href="#m{m:02d}h" class="k" style="color:{th["ink"]};padding:6px 10px;border-radius:99px;border:1.3px solid {th["line"]}">Habit tracker</a>' if sec.get('habits') else ''
        mm_sec = _mm(P)
        if mm_sec:
            habit += _mm_chip(P, f'{mm_sec.get("anchor", "mm")}{m:02d}')
        title_k = 'Month' if P.undated else str(P.year)
        inner = f'''<div class="row" style="align-items:flex-end;justify-content:space-between"><div><p class="k">{title_k}</p><p class="h" style="font-size:52px">{MONTHS[m - 1]}</p></div><div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;max-width:520px">{habit}{wl}</div></div>
          <div class="row" style="flex:1"><div class="cal" style="flex:3;grid-template-rows:auto repeat({rows},1fr);border-bottom:1px solid {th["line"]}">{cells}</div><div class="col" style="flex:1.1">{side}</div></div>'''
        P.page(f'm{m:02d}', inner, month=m, crumb=f'<a href="#year">Year</a> / {MONTHS[m - 1]}')
        if sec.get('habits'):
            days = 31 if P.undated else calendar.monthrange(P.year, m)[1]
            head = ''.join(f'<span style="text-align:center;font:600 9.5px \'{th["body"]}\';color:{th["muted"]}">{d}</span>' for d in range(1, days + 1))
            gw = P.W - (P.gutter + 70) - 150  # grid width for the day columns
            cw = gw / days
            circ = ''.join(f'<circle cx="{cw * (i + .5):.1f}" cy="15" r="{min(6.3, round(cw * .4, 1))}" fill="none" stroke="{mix(th["muted"], th["paper"], .3)}" stroke-width="1.3"/>' for i in range(days))
            hrows = ''.join(f'<div style="display:flex;align-items:center;border-bottom:1px solid {th["line"]};flex:1"><span style="width:150px;flex:none;border-right:1px solid {th["line"]};height:100%"></span><svg width="{gw}" height="30" viewBox="0 0 {gw} 30">{circ}</svg></div>' for _ in range(14))
            P.page(f'm{m:02d}h', P.head(MONTHS[m - 1], 'Habit tracker', right='<span class="k">One habit per line, fill a dot each day</span>') +
                   f'<div style="display:grid;grid-template-columns:150px repeat({days},1fr);padding-bottom:4px"><span class="k">Habit</span>{head}</div><div style="flex:1;display:flex;flex-direction:column">{hrows}</div>', month=m, crumb=f'<a href="#m{m:02d}">{MONTHS[m - 1]}</a> / Habits')
        for n in w0:  # its days in this year (e.g. Jan 1 to 3) still get day pages; their trail opens the head-start week
            for i, d in enumerate(P.week_start(n) + datetime.timedelta(days=k) for k in range(7)):
                if d.year == P.year and sec.get('days', True):
                    _day(P, d, n, m, i, dlay)
        for n in weeks:
            if not P.undated:
                thu = P.week_start(n) + datetime.timedelta(days=3)
                owner = thu.month if thu.year == P.year else (1 if thu.year < P.year else 12)
                if owner != m:
                    continue  # a week that spans two months is built once, under the month holding its Thursday
            _week(P, n, m, wside, dlay, sec.get('days', True))


def _week_grid(P, cols, side):
    """Week page body: seven day boxes plus Notes, and the side blocks.
    grid (default): 4 x 2 day boxes beside a side column. rows (eink_format week_layout, portrait): two columns of day boxes
    (Mon to Thu left, Fri to Sun and Notes right), side blocks in a row underneath."""
    notes = '<div class="box fill"><span class="k">Notes</span><div class="dots"></div></div>'
    if P.eink.get('week_layout') == 'rows' and P.HT > P.W:
        return (f'<div class="col" style="flex:1"><div style="flex:3.2;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:repeat(4,1fr);grid-auto-flow:column;gap:10px">{cols}{notes}</div>'
                f'<div class="row wkside" style="flex:1">{side}</div></div>')
    return f'<div class="row" style="flex:1"><div style="flex:3;display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:1fr 1fr;gap:10px">{cols}{notes}</div><div class="col" style="flex:1.05">{side}</div></div>'


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
        elif d in getattr(P, 'extra_day_anchors', {}):
            head = f'<a href="#{P.extra_day_anchors[d]}" style="display:flex;justify-content:space-between;align-items:baseline"><span class="k">{DOW[d.weekday()]}</span><span class="h" style="font-size:22px">{d.day}</span></a>'
        else:
            head = f'<div style="display:flex;justify-content:space-between;opacity:.4"><span class="k">{DOW[d.weekday()]}</span><span class="h" style="font-size:22px">{d.day}</span></div>'
        cols += f'<div class="box" style="flex:1">{head}<div class="lines"></div></div>'
    side = ''.join(block(P, b) for b in side_blocks)
    back1 = getattr(P, 'hs_last_week', None) if (n == 1 and not P.undated) else None  # Week 1 back to the last head-start week
    nav_w = (f'<a href="#w{n - 1:02d}">{arrow("l")}</a>' if n > 1 else (f'<a href="#{back1}">{arrow("l")}</a>' if back1 else '')) + (f' <a href="#w{n + 1:02d}">{arrow("r")}</a>' if n < (52 if P.undated else P.nweeks()) else '')
    rng = 'Write the dates' if P.undated else f'{MONTHS[days[0].month - 1][:3]} {days[0].day} to {MONTHS[days[6].month - 1][:3]} {days[6].day}'
    inner = f'''{P.head(rng, f"Week {n}")}
      {_week_grid(P, cols, side)}'''
    inner = inner.replace(P.head(rng, f"Week {n}"), P.head(rng, f"Week {n}", right=f'<span class="k" style="font-size:16px">{nav_w}</span>'), 1)
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
        prev_a = P.did(pd) if pd.year == P.year else getattr(P, 'extra_day_anchors', {}).get(pd)
        next_a = P.did(nd) if nd.year == P.year else None
        title = f'{MONTHS[d.month - 1]} {d.day}'
        kicker = d.strftime('%A')
    arrows = (f'<a href="#{prev_a}">{arrow('l')}</a>' if prev_a else '') + (f' <a href="#{next_a}">{arrow('r')}</a>' if next_a else '')
    left = ''.join(block(P, b) for b in lay['left'])
    right = ''.join(block(P, b) for b in lay['right'])
    inner = f'{P.head(kicker, title, right=f"<span class=k style=font-size:16px>{arrows}</span>")}<div class="row" style="flex:1"><div class="col" style="flex:1">{left}</div><div class="col" style="flex:1.15">{right}</div></div>'
    mm = d.month if d else m
    wk = (f'<a href="#{P.w0[0]}">{esc(P.w0[1])}</a>' if getattr(P, 'w0', None) else f'Week {n}') if (n < 1 and d) else f'<a href="#w{n:02d}">Week {n}</a>'
    P.page(anchor, inner, month=mm, crumb=f'<a href="#m{mm:02d}">{MONTHS[mm - 1]}</a> / {wk}')


@module('head_start', 'Lead-in months before the main dated year (for example Nov and Dec 2026 in a 2027 planner): month pages whose dates link to lead-in week pages, Monday-start week pages titled by date range, optional lead-in day pages. Anchors use their own prefix. The last week links days that fall in the main year to their day pages and offers Continue to the main year. label, kicker, anchor (prefix, default hs), from YYYY-MM, to YYYY-MM, days bool, month {side}, week {preset|side}, day {preset|left,right}, continue_to (default m01)',
        params={'label': 'str', 'kicker': 'str', 'anchor': 'str', 'from': 'YYYY-MM', 'to': 'YYYY-MM', 'days': 'bool', 'month': 'dict', 'week': 'dict', 'day': 'dict', 'continue_to': 'str', 'main_links': 'bool: on head-start pages the head-start month tabs say their year (NOV 2026) so one label has one target, the last head-start week arrow opens main Week 1 and Week 1 gets a back arrow'})
def m_head_start(P, sec):
    th = P.th; pre = sec.get('anchor', 'hs'); cont = sec.get('continue_to', 'm01')
    mainl = bool(sec.get('main_links'))  # one meaning per month tab: tabs always open the main year's months
    y0, m0 = map(int, sec['from'].split('-')); y1, m1 = map(int, sec['to'].split('-'))
    months = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        months.append((y, m)); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    first = datetime.date(y0, m0, 1)
    last = datetime.date(y1, m1, calendar.monthrange(y1, m1)[1])
    start = first - datetime.timedelta(days=first.weekday())
    weeks = []
    d = start
    while d <= last:
        weeks.append([d + datetime.timedelta(days=i) for i in range(7)]); d += datetime.timedelta(days=7)
    wk_anchor = lambda n: f'{pre}w{n:02d}'
    day_anchor = lambda d: f'{pre}{d.month:02d}{d.day:02d}'
    lead_from = first - datetime.timedelta(days=first.weekday())  # e.g. Mon Oct 26 for a November head start
    in_lead = lambda d: lead_from <= d <= last
    in_main = lambda d: (not P.undated) and d.year == P.year
    def week_of(d):
        return next(i + 1 for i, w in enumerate(weeks) if w[0] <= d <= w[6])
    with_days = sec.get('days', False)
    # a lead-in week that reaches into the main year IS the main year's week 1: link there instead of printing it twice
    overlaps = lambda w: (not P.undated) and any(d.year == P.year for d in w) and not (P.iso and P.week_of(w[0]) < 1)
    main_week = lambda d: f'w{P.week_of(d):02d}'
    wside = (sec.get('week') or {}).get('side') or WEEK_PRESETS[(sec.get('week') or {}).get('preset', 'default')]
    dsec = sec.get('day') or {}
    dlay = dsec if dsec.get('left') else DAY_PRESETS[dsec.get('preset', 'default')]
    side_labels = (sec.get('month') or {}).get('side', ['Goals', 'Notes'])
    _register(P, sec, sec.get('label', 'Head start'), f'{pre}{m0:02d}', sec.get('kicker', 'Start now'), nav=False)
    P.extra_day_anchors = getattr(P, 'extra_day_anchors', {})
    contlink = f'<a href="#{cont}" style="padding:6px 12px;border-radius:{P.rpill}px;background:{th["ink"]};color:{th["paper"]};font:600 11px \'{th["body"]}\';letter-spacing:.08em;text-transform:uppercase">Continue to {MONTHS[0] if cont == "m01" else "the year"} {P.year if not P.undated else ""} {arrow('r')}</a>'
    def lead_day(d, week_anchor, week_title):
        P.extra_day_anchors[d] = day_anchor(d)
        pd, nd = d - datetime.timedelta(days=1), d + datetime.timedelta(days=1)
        nxt = day_anchor(nd) if in_lead(nd) else (P.did(nd) if in_main(nd) else None)
        arrows = (f'<a href="#{day_anchor(pd)}">{arrow("l")}</a>' if in_lead(pd) else '') + (f' <a href="#{nxt}">{arrow("r")}</a>' if nxt else '')
        left = ''.join(block(P, b) for b in dlay['left']); rightb = ''.join(block(P, b) for b in dlay['right'])
        P.page(day_anchor(d), month=d.month if (d.year, d.month) in months else None, rail_map=rail_map, rail_labels=rail_labels, inner=f'{P.head(d.strftime("%A") + f" · {d.year}", f"{MONTHS[d.month - 1]} {d.day}", right=f"<span class=k style=font-size:16px>{arrows}</span>")}<div class="row" style="flex:1"><div class="col" style="flex:1">{left}</div><div class="col" style="flex:1.15">{rightb}</div></div>',
               crumb=f'<a href="#{pre}{(d.month if (d.year, d.month) in months else m0):02d}">{MONTHS[d.month - 1]} {d.year}</a> / <a href="#{week_anchor}">{week_title}</a>')

    rail_map = {m2: f'{pre}{m2:02d}' for y2, m2 in months}
    up = (lambda x: x) if th.get('labels') == 'italic' else str.upper
    rail_labels = {m2: f'{up(MONTHS[m2 - 1][:3])} {y2}' for y2, m2 in months} if mainl else None  # one label, one target
    P.head_start_links = [(f'{MONTHS[m2 - 1]} {y2}', f'{pre}{m2:02d}') for y2, m2 in months]
    done = set()
    for (yy, mm) in months:
        cells = ''.join(f'<span class="d hd">{x}</span>' for x in DOW)
        cal = calendar.Calendar(0).monthdatescalendar(yy, mm)
        for wk in cal:
            for d in wk:
                if d.month != mm and not (with_days and in_lead(d) and d < first):
                    cells += f'<span class="d x">{d.day}</span>'
                elif d.month != mm:
                    cells += f'<a class="d" href="#{day_anchor(d)}">{d.day}</a>'  # lead-in days before the first month (e.g. Oct 26 to 31)
                else:
                    w_ = weeks[week_of(d) - 1]
                    target = day_anchor(d) if with_days else (main_week(w_[6]) if overlaps(w_) else wk_anchor(week_of(d)))
                    cells += f'<a class="d" href="#{target}">{d.day}</a>'
        ws_all = sorted({week_of(d) for d in calendar.Calendar(0).itermonthdates(yy, mm) if d.month == mm})
        ws = [w for w in ws_all if not overlaps(weeks[w - 1])]
        wl = ''.join(f'<a href="#{wk_anchor(w)}" style="padding:4px 8px;border-radius:{P.rpill}px;background:{th["soft"]};font:600 10.5px \'{th["body"]}\'">{MONTHS[weeks[w - 1][0].month - 1][:3]} {weeks[w - 1][0].day}</a>' for w in ws) + ''.join(f'<a href="#{main_week(weeks[w - 1][6])}" style="padding:4px 8px;border-radius:{P.rpill}px;background:{th["soft"]};font:600 10.5px \'{th["body"]}\'">{MONTHS[weeks[w - 1][0].month - 1][:3]} {weeks[w - 1][0].day}</a>' for w in ws_all if overlaps(weeks[w - 1]))
        side = ''.join(f'<div class="box" style="flex:1"><span class="k">{esc(x)}</span><div class="lines"></div></div>' for x in side_labels)
        k_ = months.index((yy, mm))
        prevm = f'<a href="#{pre}{months[k_ - 1][1]:02d}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;border-radius:{P.rpill}px;border:1.3px solid {th["line"]};font:600 10.5px \'{th["body"]}\'">{arrow("l", 12)} {MONTHS[months[k_ - 1][1] - 1]}</a>' if k_ > 0 else ''
        nextm = f'<a href="#{pre}{months[k_ + 1][1]:02d}" style="display:inline-flex;align-items:center;gap:4px;padding:6px 10px;border-radius:{P.rpill}px;background:{th["ink"]};color:{th["paper"]};font:600 10.5px \'{th["body"]}\'">{MONTHS[months[k_ + 1][1] - 1]} {arrow("r", 12)}</a>' if k_ + 1 < len(months) else contlink
        extra = prevm + nextm
        mm_sec = _mm(P)
        if mm_sec and mm_sec.get('head_start'):
            wl = _mm_chip(P, f'{mm_sec.get("anchor", "mm")}{pre}{mm:02d}') + wl
        inner = f'''<div class="row" style="align-items:flex-end;justify-content:space-between"><div><p class="k">{esc(sec.get("kicker", "Head start"))} · {yy}</p><p class="h" style="font-size:52px">{MONTHS[mm - 1]}</p></div><div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;max-width:560px">{wl}{extra}</div></div>
          <div class="row" style="flex:1"><div class="cal" style="flex:3;grid-template-rows:auto repeat({len(cal)},1fr);border-bottom:1px solid {th["line"]}">{cells}</div><div class="col" style="flex:1.1">{side}</div></div>'''
        trail = ' · '.join(f'<a href="#{pre}{m2:02d}">{MONTHS[m2 - 1][:3]} {y2}</a>' for y2, m2 in months)
        P.page(f'{pre}{mm:02d}', inner, crumb=f'Head start: {trail}', month=mm, rail_map=rail_map, rail_labels=rail_labels)
        for w in ws:
            thu = weeks[w - 1][3]
            home = (thu.year, thu.month) if (thu.year, thu.month) in months else (months[0] if thu < first else months[-1])
            if w in done or home != (yy, mm):
                continue
            done.add(w)
            days = weeks[w - 1]
            cols = ''
            for d in days:
                lab = f'<span class="k">{DOW[d.weekday()]}</span><span class="h" style="font-size:22px">{d.day}</span>'
                if in_lead(d) and with_days:
                    head = f'<a href="#{day_anchor(d)}" style="display:flex;justify-content:space-between;align-items:baseline">{lab}</a>'
                elif in_main(d):
                    head = f'<a href="#{P.did(d)}" style="display:flex;justify-content:space-between;align-items:baseline">{lab}</a>'
                elif in_lead(d):
                    head = f'<div style="display:flex;justify-content:space-between;align-items:baseline">{lab}</div>'
                else:
                    head = f'<div style="display:flex;justify-content:space-between;opacity:.4">{lab}</div>'
                cols += f'<div class="box" style="flex:1">{head}<div class="lines"></div></div>'
            sideb = ''.join(block(P, b) for b in wside)
            title = f'{MONTHS[days[0].month - 1][:3]} {days[0].day} to {MONTHS[days[6].month - 1][:3]} {days[6].day}'
            lead_weeks = [x for x in range(1, len(weeks) + 1) if not overlaps(weeks[x - 1])]
            pos = lead_weeks.index(w)
            prev_w = f'<a href="#{wk_anchor(lead_weeks[pos - 1])}">{arrow("l")}</a>' if pos > 0 else ''
            next_w = f' <a href="#{wk_anchor(lead_weeks[pos + 1])}">{arrow("r")}</a>' if pos + 1 < len(lead_weeks) else ''
            if mainl and not next_w and not P.undated:  # last head-start week: arrow to main Week 1
                nxt = main_week(weeks[w][6]) if (w < len(weeks) and overlaps(weeks[w])) else 'w01'
                next_w = f' <a href="#{nxt}">{arrow("r")}</a>'
                P.hs_last_week = wk_anchor(w)
            if any(in_main(d) for d in days):
                P.w0 = (wk_anchor(w), title)  # iso_weeks: Jan 1 to 3 day pages trail back to this head-start week
            right = f'<span class="k" style="font-size:16px">{prev_w}{next_w}</span>' + (contlink if pos + 1 == len(lead_weeks) else '')
            inner = f'''{P.head(f"Head start · week {pos + 1} of {len(lead_weeks)}", title, right=right)}
              {_week_grid(P, cols, sideb)}'''
            P.page(wk_anchor(w), inner, crumb=f'<a href="#{pre}{mm:02d}">{MONTHS[mm - 1]} {yy}</a> / {title}', month=mm, rail_map=rail_map, rail_labels=rail_labels)
            if with_days:
                for d in days:
                    if in_lead(d):
                        lead_day(d, wk_anchor(w), title)
    # lead-in days inside the main year's week 1 (for example Dec 28 to 31): their own day pages, linked from Week 1
    if with_days:
        for w in range(1, len(weeks) + 1):
            if overlaps(weeks[w - 1]):
                for d in weeks[w - 1]:
                    if in_lead(d):
                        lead_day(d, main_week(weeks[w - 1][6]), f'Week {P.week_of(weeks[w - 1][6])}')


@module('money_month', 'One month-end money page per month (anchors mm01 to mm12; with head_start also mmhs11, mmhs12 for the head-start months), each linked from its month page by a chip. Two tables (Money in, Money out: Category, Planned, Actual, Total row), a This month box (Money in, Money out, Profit), lined boxes for fields (the last fills the page) and a strip of pills to every Money month. One Contents card and one top-bar item. label, kicker, anchor, nav_label, head_start, income, expenses, fields',
        params={'label': 'str (Money month)', 'kicker': 'str (Month end)', 'anchor': "str prefix, default 'mm'", 'nav_label': 'str (Money)',
                'head_start': 'bool: also pages for the head_start months', 'income': 'list of str (3 to 5)', 'expenses': 'list of str (4 to 8)',
                'fields': 'list of str: lined boxes, the last grows', 'index': 'bool', 'nav': 'bool'})
def m_money_month(P, sec):
    th = P.th; pre = sec.get('anchor', 'mm'); label = sec.get('label', 'Money month')
    income = sec.get('income') or ['Sales', 'Other income']; expenses = sec.get('expenses') or ['Stock', 'Fees', 'Marketing', 'Other']
    fields = sec.get('fields') or ['What worked', 'One change for next month']
    hs = []  # (anchor, month, year, month page anchor, rail_map, rail_labels)
    hs_sec = next((x for x in P.s.get('sections', []) if x.get('module') == 'head_start'), None)
    if sec.get('head_start') and hs_sec:
        hpre = hs_sec.get('anchor', 'hs')
        for name, a in getattr(P, 'head_start_links', []):
            mon = int(a[len(hpre):]); yr = int(name.split()[-1])
            hs.append((f'{pre}{hpre}{mon:02d}', mon, yr, a))
    main = [(f'{pre}{m:02d}', m, None if P.undated else P.year, f'm{m:02d}') for m in range(1, 13)]
    allp = hs + main
    _register(P, sec, label, f'{pre}01', sec.get('kicker', 'Month end'))
    row_h = max(30, round(30 * P.scale))

    def table(title, rows, grow=False):
        head = ''.join(f'<span class="k" style="padding:6px 8px{";text-align:right" if i else ""}">{h}</span>' for i, h in enumerate(['Category', 'Planned', 'Actual']))
        body = ''.join(f'<div style="display:grid;grid-template-columns:2fr 1fr 1fr;border-bottom:1px solid {th["line"]};height:{row_h}px;align-items:center"><span style="padding:0 8px;font-size:{P.fs(12)};font-weight:600">{esc(r)}</span><span></span><span></span></div>' for r in rows + [''])
        total = f'<div style="display:grid;grid-template-columns:2fr 1fr 1fr;border-top:1.5px solid {th["ink"]};height:{row_h}px;align-items:center"><span style="padding:0 8px;font-size:{P.fs(12)};font-weight:700">Total</span><span></span><span></span></div>'
        fill = '<div class="lines" style="flex:1;min-height:0"></div>' if grow else ''  # extra write-in rows fill the column (r006)
        return f'<div class="box" style="gap:0{";flex:1" if grow else ""}"><span class="k" style="padding-bottom:6px">{esc(title)}</span><div style="display:grid;grid-template-columns:2fr 1fr 1fr;border-bottom:1.5px solid {th["ink"]}">{head}</div>{body}{fill}{total}</div>'

    for i, (a, mon, yr, mpage) in enumerate(allp):
        strip = ''.join(f'<a href="#{a2}" style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:{P.rpill}px;{"background:" + th["ink"] + ";color:" + th["paper"] if a2 == a else "background:" + th["soft"]};font:600 10px \'{th["body"]}\'">{MONTHS[m2 - 1][:3]}{" " + str(y2)[2:] if (y2 and y2 != P.year) else ""}</a>' for a2, m2, y2, _ in allp)
        this = (f'<div class="box fill"><span class="k">This month</span>' + field(P, 'Money in', 'flex:none') + field(P, 'Money out', 'flex:none') + field(P, 'Profit', 'flex:none') +
                f'<span style="font-size:{P.fs(10.5)};color:{th["muted"]}">Profit is money in minus money out.</span></div>')
        short = 1 if P.W > P.HT else 2  # landscape: one writing line per box so the last box still has room
        boxes = ''.join(lines_box(P, f, rows=None if j == len(fields) - 1 else short) for j, f in enumerate(fields))
        right = f'<div class="col" style="flex:1;gap:10px">{this}{boxes}<div style="display:flex;flex-wrap:wrap;gap:4px">{strip}</div></div>'
        left = f'<div class="col" style="flex:1.9;gap:10px">{table("Money in", income)}{table("Money out", expenses, grow=True)}</div>'
        kick = f'{label} · {yr}' if yr else label
        prev_a = allp[i - 1][0] if i > 0 else None; next_a = allp[i + 1][0] if i + 1 < len(allp) else None
        inner = P.head(kick, MONTHS[mon - 1], size=44, right=_arrows(prev_a, next_a)) + f'<div class="row" style="flex:1">{left}{right}</div>'
        is_hs = i < len(hs)
        if is_hs:
            hmonths = [(x[2], x[1]) for x in hs]
            rail_map = {m2: f'{hs_sec.get("anchor", "hs")}{m2:02d}' for y2, m2 in hmonths}
            up = (lambda x: x) if th.get('labels') == 'italic' else str.upper
            rail_labels = {m2: f'{up(MONTHS[m2 - 1][:3])} {y2}' for y2, m2 in hmonths} if hs_sec.get('main_links') else None
            P.page(a, inner, active=f'{pre}01', month=mon, rail_map=rail_map, rail_labels=rail_labels,
                   crumb=f'<a href="#{mpage}">{MONTHS[mon - 1]} {yr}</a> / Money')
        else:
            P.page(a, inner, active=f'{pre}01', month=mon, crumb=f'<a href="#year">Year</a> / <a href="#{mpage}">{MONTHS[mon - 1]}</a> / Money')


# ---------- e-ink format ----------
@module('eink_format', 'Format switch for e-ink tablets (reMarkable): prints no page. Put it first in sections. Widens the left gutter to left_gutter px (clears the toolbar), draws writing lines and dot grids as vector strokes instead of gradient patterns (vector_rules), refuses a theme with any color when grayscale is true and drops the month and card tints, lays portrait week pages (calendar and head start) out as two columns of day boxes with the side blocks underneath (week_layout rows), and replaces the Setup check fix list and pen test label (link_test_fixes, pen_label). In portrait the Setup check also gets a map of the top bar under the pen test.',
        params={'left_gutter': 'int px, default 40', 'vector_rules': 'bool', 'grayscale': 'bool', 'week_layout': "'grid' (default) | 'rows'", 'link_test_fixes': 'list of 4 str', 'pen_label': 'str'})
def m_eink_format(P, sec):
    pass  # read by Planner.__init__ (P.eink), so it applies to every page wherever the section sits


def _gray_problems(th):
    bad = []
    for k in ('paper', 'ink', 'muted', 'line', 'accent', 'soft', 'warm', 'tabs', 'rainbow'):
        for c in ([th[k]] if isinstance(th.get(k), str) else list(th.get(k) or [])):
            r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
            if max(r, g, b) - min(r, g, b) > 2:
                bad.append(f'{k} {c}')
    return bad


# ---------- reading journal ----------
def star_row(P, n=5, size=15, gap=4):
    """Five star outlines drawn as SVG (no star glyph in the fonts, style rule r004)."""
    pts = []
    for j in range(10):
        r = 7 if j % 2 == 0 else 2.9
        ang = math.radians(-90 + 36 * j)
        pts.append(f'{7.5 + r * math.cos(ang):.2f},{7.8 + r * math.sin(ang):.2f}')
    star = ' '.join(pts)
    w = n * size + (n - 1) * gap
    body = ''.join(f'<polygon transform="translate({i * (size + gap)} 0) scale({size / 15:.3f})" points="{star}" fill="none" stroke="{P.th["accent"]}" stroke-width="1.2" stroke-linejoin="round"/>' for i in range(n))
    return f'<svg width="{w}" height="{size}" viewBox="0 0 {w} {size}" style="flex:none">{body}</svg>'


def tick_options(P, labels):
    """Write-in choices: an empty circle before each word (tick or fill one)."""
    th = P.th
    return ''.join(f'<span style="display:inline-flex;align-items:center;gap:6px;font-size:{P.fs(12.5)}"><svg width="15" height="15" viewBox="0 0 15 15"><circle cx="7.5" cy="7.5" r="6.3" fill="none" stroke="{th["muted"]}" stroke-width="1.3"/></svg>{esc(l)}</span>' for l in labels)


def field(P, label, style='flex:1', after=''):
    """A label followed by a write-in rule."""
    return f'<div style="display:flex;align-items:flex-end;gap:10px;{style}"><span class="k" style="flex:none">{esc(label)}</span><span style="flex:1;min-width:24px;border-bottom:1.2px solid {P.th["line"]};height:{24 * P.scale:.0f}px"></span>{after}</div>'


def lines_box(P, label, rows=None, right='', style=''):
    """Lined box: a fixed number of writing lines, or growing to fill (rows None)."""
    hd = f'<div style="display:flex;justify-content:space-between;align-items:flex-end;gap:10px"><span class="k">{esc(label)}</span>{right}</div>'
    ln = '<div class="lines"></div>' if rows is None else f'<div class="lines" style="flex:none;height:{rows * P.rule_period()}px"></div>'
    return f'<div class="box" style="{"flex:1;" if rows is None else ""}{style}">{hd}{ln}</div>'


def _arrows(prev_a, next_a):
    return f'<span class="k" style="font-size:16px">' + (f'<a href="#{prev_a}">{arrow("l")}</a>' if prev_a else '') + (f' <a href="#{next_a}">{arrow("r")}</a>' if next_a else '') + '</span>'


@module('books', 'Book log (Library) plus one review page per book, cross-linked both ways. Library pages (anchor, then anchor2, anchor3...): per_log_page numbered lines (No., Title, Author, Finished, Stars, Shelf); each number opens that book; a strip links all Library pages. Book pages (book_anchor + 001...): title, author, genre, format, dates, pages, stars, reread, why I picked it up, thoughts (fills the page), favorite quote with page, favorite character, one-line review; previous and next book arrows; trail back to the Library page holding its line. One Contents card and one top-bar item. label, kicker, anchor, book_anchor, count, per_log_page',
        params={'label': 'str (Library)', 'kicker': 'str', 'anchor': "str, default 'library'", 'book_anchor': "str, default 'b' (b001)", 'count': 'int (100)', 'per_log_page': 'int (25)'})
def m_books(P, sec):
    th = P.th
    a = sec.get('anchor', 'library'); pre = sec.get('book_anchor', 'b')
    n = int(sec.get('count', 100)); per = int(sec.get('per_log_page', 25)); npg = math.ceil(n / per)
    label = sec.get('label', 'Library'); kicker = sec.get('kicker', 'Book log')
    lib = lambda p: a if p == 1 else f'{a}{p}'
    bid = lambda i: f'{pre}{i:03d}'
    page_of = lambda i: (i - 1) // per + 1
    _register(P, sec, label, a, kicker)
    cols = f'{40 * P.scale:.0f}px 2.3fr 1.6fr 1fr {5 * 15 + 16 + 8}px 1fr'
    for p in range(1, npg + 1):
        lo, hi = (p - 1) * per + 1, min(p * per, n)
        strip = ''.join(f'<a href="#{lib(q)}" style="padding:6px 12px;border-radius:{P.rpill}px;font:600 {P.fs(11)} \'{th["body"]}\';{"background:" + th["ink"] + ";color:" + th["paper"] if q == p else "background:" + th["soft"]}">{(q - 1) * per + 1} to {min(q * per, n)}</a>' for q in range(1, npg + 1))
        hdr = ''.join(f'<span class="k" style="padding:6px 6px">{h}</span>' for h in ('No.', 'Title', 'Author', 'Finished', 'Stars', 'Shelf'))
        rows = ''.join(f'<div style="display:grid;grid-template-columns:{cols};align-items:center;border-bottom:1px solid {th["line"]};flex:1;min-height:0">'
                       f'<a href="#{bid(i)}" style="justify-self:start;margin-left:2px;min-width:{32 * P.scale:.0f}px;text-align:center;padding:3px 6px;border-radius:{P.rpill}px;background:{th["soft"]};font:700 {P.fs(11.5)} \'{th["body"]}\'">{i}</a>'
                       f'<span></span><span style="border-left:1px solid {th["line"]};align-self:stretch"></span><span style="border-left:1px solid {th["line"]};align-self:stretch"></span>'
                       f'<span style="padding-left:6px">{star_row(P, size=14, gap=4)}</span><span style="border-left:1px solid {th["line"]};align-self:stretch"></span></div>'
                       for i in range(lo, hi + 1))
        inner = (P.head(f'{kicker} · books {lo} to {hi}', label, right=_arrows(lib(p - 1) if p > 1 else None, lib(p + 1) if p < npg else None)) +
                 f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">{strip}<span style="margin-left:auto;font-size:{P.fs(12)};color:{th["muted"]}">Tap a number to open that book</span></div>'
                 f'<div class="box" style="flex:1;gap:0"><div style="display:grid;grid-template-columns:{cols};border-bottom:1.5px solid {th["ink"]}">{hdr}</div><div style="flex:1;display:flex;flex-direction:column">{rows}</div></div>')
        P.page(lib(p), inner, active=a, crumb=f'{label} · page {p} of {npg}')
    for i in range(1, n + 1):
        details = (f'<div class="box" style="gap:12px;padding:12px 14px">'
                   f'{field(P, "Title")}{field(P, "Author")}'
                   f'<div class="row" style="align-items:flex-end;gap:22px">{field(P, "Genre")}<div style="display:flex;gap:12px;align-items:center;flex:none"><span class="k">Format</span>{tick_options(P, ["Print", "Ebook", "Audio"])}{tick_options(P, [""])}<span style="width:{56 * P.scale:.0f}px;margin-left:-6px;border-bottom:1.2px solid {th["line"]};height:{18 * P.scale:.0f}px"></span></div></div>'
                   f'<div class="row" style="gap:22px">{field(P, "Started")}{field(P, "Finished")}{field(P, "Pages", "flex:.7")}</div>'
                   f'<div class="row" style="align-items:center;justify-content:space-between;gap:22px"><div style="display:flex;gap:12px;align-items:center"><span class="k">Stars</span>{star_row(P, size=20, gap=6)}</div>'
                   f'<div style="display:flex;gap:12px;align-items:center"><span class="k">Would I reread?</span>{tick_options(P, ["Yes", "Maybe", "No"])}</div></div></div>')
        quote_pg = f'<span style="display:flex;gap:6px;align-items:flex-end"><span class="k">Page</span><span style="width:54px;border-bottom:1.2px solid {th["line"]};height:16px"></span></span>'
        inner = (P.head(f'{kicker} · book {i} of {n}', f'Book {i}', right=_arrows(bid(i - 1) if i > 1 else None, bid(i + 1) if i < n else None)) +
                 details + lines_box(P, 'Why I picked it up', 2) + lines_box(P, 'My thoughts') + lines_box(P, 'Favorite quote', 3, right=quote_pg) +
                 f'<div class="row">{lines_box(P, "Favorite character", 2, style="flex:1")}{lines_box(P, "One-line review", 2, style="flex:1.4")}</div>')
        P.page(bid(i), inner, active=a, crumb=f'<a href="#{lib(page_of(i))}">{esc(label)}</a> / Book {i}')


@module('reading_month', 'Twelve undated monthly reading pages, anchors m01 to m12 (the month rail and Contents month grid link to them): books finished this month with stars, 31 reading-day circles, pages or hours read, book of the month, up next, notes. Trail Reading year / Month. Registers nothing unless index or nav is true. label, index, nav',
        params={'label': 'str (not shown)', 'index': 'bool, default false', 'nav': 'bool, default false'})
def m_reading_month(P, sec):
    th = P.th
    if sec.get('index', False) or sec.get('nav', False):
        _register(P, dict(sec, index=sec.get('index', False), nav=sec.get('nav', False)), sec.get('label', 'Reading months'), 'm01', sec.get('kicker', 'Monthly'))
    per = 16; gap = 38; r = 14
    circ = ''.join(f'<circle cx="{r + 2 + (d % per) * gap}" cy="{r + 2 + (d // per) * (2 * r + 12)}" r="{r}" fill="none" stroke="{th["muted"]}" stroke-width="1.3"/>'
                   f'<text x="{r + 2 + (d % per) * gap}" y="{r + 6.5 + (d // per) * (2 * r + 12)}" text-anchor="middle" font-size="11.5" font-family="{th["body"]}" font-weight="600" fill="{th["ink"]}">{d + 1}</text>' for d in range(31))
    vw, vh = (per - 1) * gap + 2 * r + 4, 2 * (2 * r) + 12 + 4
    days = f'<svg viewBox="0 0 {vw} {vh}" width="100%" style="max-height:{vh + 6}px">{circ}</svg>'
    finished = ''.join(f'<div style="display:flex;align-items:flex-end;gap:10px;border-bottom:1px solid {th["line"]};flex:1;min-height:{26 * P.scale:.0f}px;padding-bottom:4px"><span style="font:700 {P.fs(11.5)} \'{th["body"]}\';color:{th["muted"]};width:16px">{k}</span><span style="flex:1"></span>{star_row(P, size=13, gap=3)}</div>' for k in range(1, 9))
    for m in range(1, 13):
        inner = (P.head('Month · year ____', MONTHS[m - 1], right=_arrows(f'm{m - 1:02d}' if m > 1 else None, f'm{m + 1:02d}' if m < 12 else None)) +
                 f'''<div class="row" style="flex:1.4">
                   <div class="box" style="flex:1.45"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px"><span class="k">Books finished this month</span><span style="font-size:{P.fs(11)};color:{th["muted"]}">More than 8? Add them in Notes</span></div><div style="flex:1;display:flex;flex-direction:column">{finished}</div></div>
                   <div class="col" style="flex:1">
                     <div class="box" style="gap:10px"><span class="k">Book of the month</span><span style="border-bottom:1.2px solid {th["line"]};height:{26 * P.scale:.0f}px"></span><span style="border-bottom:1.2px solid {th["line"]};height:{26 * P.scale:.0f}px"></span></div>
                     <div class="box" style="gap:10px"><span class="k">Pages or hours read</span><span style="border-bottom:1.2px solid {th["line"]};height:{26 * P.scale:.0f}px"></span></div>
                     <div class="box" style="flex:1"><span class="k">Up next</span><div style="flex:1;display:flex;flex-direction:column;justify-content:space-evenly">{_chk(3)}</div></div>
                   </div></div>
                 <div class="box" style="gap:10px"><div style="display:flex;justify-content:space-between"><span class="k">Reading days</span><span style="font-size:{P.fs(12)};color:{th["muted"]}">Color a circle on each day you read</span></div>{days}</div>
                 {lines_box(P, "Notes")}''')
        P.page(f'm{m:02d}', inner, month=m, crumb=f'<a href="#year">Reading year</a> / {MONTHS[m - 1]}')


@module('reading_year', "One undated reading-year page (anchor 'year'): yearly book goal with a year field, month by month rows (each month links to m01 to m12) with 10 squares to color per finished book, tallies (Fiction, Nonfiction, Print, Ebook, Audio), top 5 of the year, best quote of the year. Registers a Contents card and, unless nav is false, a top-bar item. label, kicker, anchor, nav",
        params={'label': 'str (Reading year)', 'kicker': 'str', 'anchor': "str, must be 'year'", 'nav': 'bool'})
def m_reading_year(P, sec):
    th = P.th; a = sec.get('anchor', 'year'); label = sec.get('label', 'Reading year')
    _register(P, sec, label, a, sec.get('kicker', 'Goal'))
    sq = 17; g = 5
    squares = f'<svg width="{10 * sq + 9 * g}" height="{sq}" viewBox="0 0 {10 * sq + 9 * g} {sq}" style="flex:none">' + ''.join(f'<rect x="{i * (sq + g) + .65}" y=".65" width="{sq - 1.3}" height="{sq - 1.3}" rx="3" fill="none" stroke="{th["muted"]}" stroke-width="1.3"/>' for i in range(10)) + '</svg>'
    months = ''.join(f'<div style="display:flex;align-items:center;gap:10px;border-bottom:1px solid {th["line"]};flex:1;min-height:0"><a href="#m{m:02d}" style="flex:1;display:flex;align-items:center;gap:6px;font:600 {P.fs(12.5)} \'{th["body"]}\'">{MONTHS[m - 1]} {arrow("r", 11)}</a>{squares}</div>' for m in range(1, 13))
    tallies = ''.join(f'<div style="border:1.3px solid {th["line"]};border-radius:{min(P.rbox, 8)}px;padding:6px 8px;display:flex;flex-direction:column;min-height:{50 * P.scale:.0f}px"><span class="k" style="font-size:{P.fs(10)}">{t}</span></div>' for t in ('Fiction', 'Nonfiction', 'Print', 'Ebook', 'Audio'))
    top5 = ''.join(f'<div style="display:flex;align-items:flex-end;gap:10px;border-bottom:1px solid {th["line"]};flex:1;min-height:{26 * P.scale:.0f}px;padding-bottom:4px"><span style="font:700 {P.fs(12)} \'{th["body"]}\';color:{th["muted"]};width:14px">{k}</span></div>' for k in range(1, 6))
    goal = (f'<div class="box fill" style="flex-direction:row;align-items:flex-end;gap:12px;padding:16px 18px;flex-wrap:wrap">'
            f'<span class="k" style="align-self:center;margin-right:4px">My goal</span><span class="h" style="font-size:{21 * P.scale:.0f}px">I want to read</span>'
            f'<span style="width:70px;border-bottom:1.5px solid {th["ink"]};height:24px"></span><span class="h" style="font-size:{21 * P.scale:.0f}px">books this year</span></div>')
    inner = (P.head(sec.get('kicker', 'Goal'), label, right=f'<div style="display:flex;align-items:flex-end;gap:8px;width:170px"><span class="k">Year</span><span style="flex:1;border-bottom:1.5px solid {th["ink"]};height:24px"></span></div>') + goal +
             f'''<div class="row" style="flex:1.6">
               <div class="box" style="flex:1.25"><div style="display:flex;justify-content:space-between"><span class="k">Month by month</span><span style="font-size:{P.fs(11)};color:{th["muted"]}">One square per book (tally past 10)</span></div><div style="flex:1;display:flex;flex-direction:column">{months}</div></div>
               <div class="col" style="flex:1">
                 <div class="box"><div style="display:flex;justify-content:space-between"><span class="k">Tallies</span><span style="font-size:{P.fs(11)};color:{th["muted"]}">One mark per book</span></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">{tallies}<span style="display:flex;align-items:center;justify-content:center;text-align:center;font-size:{P.fs(11)};color:{th["muted"]};line-height:1.35">Five marks,<br>then a line across</span></div></div>
                 <div class="box" style="flex:1"><span class="k">Top 5 of the year</span><div style="flex:1;display:flex;flex-direction:column">{top5}</div></div>
               </div></div>
             {lines_box(P, "Best quote of the year")}''')
    P.page(a, inner, active=a)


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
        th = resolve_theme(spec.get('theme', 'neutral'))
        ek = next((x for x in spec.get('sections', []) if x.get('module') == 'eink_format'), None)
        if ek and ek.get('grayscale'):
            bad = _gray_problems(th)
            if bad:
                problems.append('grayscale: theme colors are not gray: ' + ', '.join(bad))
        if ek and ek.get('week_layout', 'grid') not in ('grid', 'rows'):
            problems.append(f"eink_format week_layout must be 'grid' or 'rows', not {ek.get('week_layout')!r}")
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
    _fill_guides(P)
    _fill_link_test_map(P)
    html = P.html()
    all_ids = re.findall(r'<section class="pg" id="([^"]+)"', html)
    ids = set(re.findall(r'id="([^"]+)"', html))
    dup = sorted({a for a in all_ids if all_ids.count(a) > 1})
    broken = sorted(set(h for h in re.findall(r'href="#([^"]+)"', html) if h not in ids))
    # every page must be reachable from the first page by following links (a group of pages that only link to each other fails)
    graph = {src: set(re.findall(r'href="#([^"]+)"', body)) for src, body in re.findall(r'<section class="pg" id="([^"]+)"(.*?)</section>', html, flags=re.S)}
    seen, stack = set(), [all_ids[0]] if all_ids else []
    while stack:
        a = stack.pop()
        if a in seen or a not in graph:
            continue
        seen.add(a); stack.extend(graph[a] - seen)
    orphans = [a for a in all_ids if a not in seen]
    return {'html': html, 'pages': len(P.pages), 'page_modules': P.page_modules, 'broken_links': broken, 'duplicate_pages': dup, 'orphan_pages': orphans,
            'size': (P.W, P.HT), 'links': len(re.findall(r'href="#', html))}


if __name__ == '__main__':
    import sys
    print(json.dumps(capabilities(), indent=1))
