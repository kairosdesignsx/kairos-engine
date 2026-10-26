"""Planner line: a hyperlinked PDF planner built from a list of modules.

spec = {
  "title", "subtitle", "kicker", "brand",
  "orientation": "landscape" | "portrait",
  "dating": {"mode": "dated", "year": 2027} | {"mode": "undated"},
  "theme": "sage" | {"base": "sage", ...token overrides, "display": font, "body": font, "motif": name},
  "type_scale": 1.0,                 # >1 for larger text (readability)
  "tap_targets": "large",            # optional: top bar, trail and page-number buttons at least 30 pt tall (r-tap)
  "nav_max": 5,                      # optional: how many top-bar buttons (default 7 landscape, 4 portrait)
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
        self.nav_max = int(spec.get('nav_max', 7 if self.W > self.HT else 4))  # top-bar buttons (spec nav_max)
        self.taps = spec.get('tap_targets') == 'large'  # spec tap_targets 'large': nav, trail and page buttons >= 30 pt
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
        # print_format section: true paper sizes, safe margins and spreads for home printing (applies to the whole file)
        self.pf = next((x for x in spec.get('sections', []) if x.get('module') == 'print_format'), None) or {}
        if self.pf:
            self.paper = spec.get('paper') or (self.pf.get('sizes') or ['letter'])[0]
            self.W, self.HT = PAPER[self.paper][2], PAPER[self.paper][3]
            self.pf_groups, self.pf_spreads, self.pf_wdates = [], [], []

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
.k>a:has(>svg){{display:inline-flex;align-items:center;justify-content:center;width:46px;height:38px;margin-left:8px;border-radius:10px;background:{th['soft']};vertical-align:middle}}.k>a>svg{{width:20px;height:20px}}
""" + self.label_css() + (self.eink_css() if self.eink else '') + (self.tap_css() if self.taps else '') + (_pf_css(self) if self.pf else '') + ('*{font-variant-numeric:lining-nums}' if th.get('nums') == 'lining' else '')  # theme 'nums': 'lining' (Cormorant's old-style 1 reads as I)

    def tap_css(self):
        """spec tap_targets 'large': every small button at least 40 css px (30 pt) tall: top bar, Month / Week trail links,
        notes page numbers and prev/next arrows. The bar sits a little higher and the body starts 6px lower."""
        th = self.th
        return (f".nav{{top:8px}}.nav a{{display:inline-flex;align-items:center;height:40px;padding:0 14px}}"
                f".nav .crumb a{{display:inline-flex;align-items:center;height:40px;padding:0 12px;border-radius:{self.rpill}px;background:{th['soft']}}}"
                f".body{{top:62px}}a.pgn{{min-width:40px!important;height:40px;padding:0 10px!important}}"
                f".k>a:has(>svg){{width:48px;height:42px}}")

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
        return ''.join(f'<a href="#{a}" class="{"on" if a == active else ""}">{esc(l)}</a>' for l, a in self.nav_items[:self.nav_max])

    def rail(self, month=None, rail_map=None, rail_labels=None):
        if self.pf:
            return ''  # print_format: no edge rail (a home printer cuts it off)
        out = []
        for i in range(12):
            c = self.tabs[i]; on = month == i + 1
            target = (rail_map or {}).get(i + 1, f'm{i + 1:02d}')
            out.append(f'<a href="#{target}" class="{"on" if on else ""}" style="background:{c}{"" if (on or self.gray) else "cc"}">{(rail_labels or {}).get(i + 1, MONTHS[i][:3] if self.th.get('labels') == 'italic' else MONTHS[i][:3].upper())}</a>')
        return f'<div class="rail">{"".join(out)}</div>'

    def page(self, anchor, inner, active=None, month=None, crumb='', deco=False, raw=False, style='', rail_map=None, rail_labels=None):
        if self.pf:
            return _pf_page(self, anchor, inner, crumb=crumb, raw=raw, style=style)
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
            for i in range(42):  # 6 rows: a 31-day month that starts on a Saturday or Sunday still fits
                cells += '<span class="d"></span>'
            return cells, 6
        cal = calendar.Calendar(0).monthdatescalendar(self.year, m)
        for wk in cal:
            for d in wk:
                if d.month != m:
                    cells += '<span class="d x"></span>' if small else f'<span class="d x">{d.day}</span>'
                else:
                    cells += f'<a class="d" href="#{_pf_week_anchor(self, d) if self.pf else self.did(d)}">{d.day}</a>' if link_days else f'<span class="d">{d.day}</span>'
        return cells, len(cal)

    def html(self):
        body = re.sub(r'%%NAV:([^%]*)%%', lambda m: self.nav_links(m.group(1) or None), ''.join(self.pages))
        if self.eink.get('vector_rules') or self.pf.get('vector_rules'):
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
    if k == 'habits':
        return _habits(P, b)
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
    'habits': 'Weekly habit strip: day initials M to S over seven circles per row, a write-in habit name per row. label, rows',
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
      <p class="k" style="font-size:13px">{esc(s.get("kicker", "Digital planner"))}</p><p class="h" style="font-size:{sec.get("size", 92)}px;line-height:1.04">{esc(s["title"])}</p>
      <p style="font-size:20px;color:{th["muted"]};max-width:560px;line-height:1.4">{esc(s.get("subtitle", ""))}</p>
      <div style="display:flex;gap:10px;margin-top:14px"><a href="#{sec.get("start", "index")}" style="padding:10px 22px;border-radius:99px;background:{P.btn};color:{th["paper"]};font:600 13px '{th["body"]}';letter-spacing:.14em;text-transform:uppercase">{esc(button)}</a></div></div>'''
    if P.pf:  # printed cover: facts row and an owner line at the foot of the page (print_format cover params: facts, owner)
        facts = ''.join(f'<div style="flex:1;border-top:1.3px solid {th["line"]};padding-top:10px;font-size:{P.fs(12.5)};line-height:1.4;color:{th["muted"]}">{esc(f)}</div>' for f in sec.get('facts', []))
        owner = f'<div style="display:flex;align-items:flex-end;gap:14px"><span class="k" style="font-size:{P.fs(15)}">{esc(sec["owner"])}</span><span style="flex:1;border-bottom:1.3px solid {th["ink"]};height:30px"></span></div>' if sec.get('owner') else ''
        inner += f'<div style="position:absolute;left:90px;right:120px;bottom:96px;display:flex;flex-direction:column;gap:46px"><div style="display:flex;gap:22px">{facts}</div>{owner}</div>'
        inner = inner.replace('justify-content:center;padding:0 120px 0 90px', 'justify-content:flex-start;padding:2.3in 120px 0 90px').replace(f'background:{P.btn};color:{th["paper"]}', f'box-shadow:inset 0 0 0 1.5px {th["ink"]};color:{th["ink"]}')
    P.page('cover', motif(th, 'tr', 5, 260) + motif(th, 'bl', 9, 220) + inner + P.rail(), raw=True, style=f'background:{th.get("cover_bg") or (th["paper"] if (P.gray or P.pf) else th["soft"])}')  # theme 'cover_bg' overrides  # e-ink: pure white, a tint dithers; print: no tint


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
    months += ''.join(f'<a href="#m{i + 1:02d}" style="padding:8px 0;text-align:center;border-radius:8px;background:{P.tint(i, th.get("tile_alpha", "55"))};font:600 12px \'{th["body"]}\'">{MONTHS[i]}{"" if P.undated or not getattr(P, "head_start_links", None) else " " + str(P.year)}</a>' for i in range(12))
    tip = P.s.get('index_tip', 'Tap a month tab on the right, any section above, or any date to jump there. Home on the top bar brings you back here, and calendar pages show where you are at the top right. Follow links in read mode (Goodnotes: turn the pen off).')
    if P.HT > P.W:  # portrait: wider cards, and a months grid that fills the page with big tap targets
        cards = cards.replace('min-height:76px', 'min-height:96px')
        months = months.replace('padding:8px 0;text-align:center', 'display:flex;align-items:center;justify-content:center;text-align:center').replace("font:600 12px", f"font:600 {P.fs(14)}")
        grid = f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">{cards}</div><p class="k" style="margin-top:6px">Months</p><div style="flex:1;display:grid;grid-template-columns:repeat(3,1fr);grid-auto-rows:1fr;gap:8px">{months}</div>'
    else:  # landscape: the months grid also grows into the free space (no blank band above the tip, style rule r006)
        months = months.replace('padding:8px 0;text-align:center', 'display:flex;align-items:center;justify-content:center;text-align:center').replace("font:600 12px", f"font:600 {P.fs(13)}")
        grid = f'<div style="display:grid;grid-template-columns:repeat({int(P.s.get("index_cols", 4))},1fr);gap:10px">{cards}</div>\n      <p class="k" style="margin-top:6px">Months</p><div style="flex:1;max-height:330px;display:grid;grid-template-columns:repeat(6,1fr);grid-auto-rows:1fr;gap:8px">{months}</div>'
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
    items = ''.join(f'<a href="#{an}" style="display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid {th["line"]}"><b style="min-width:84px;font:700 {P.fs(11.5)} \'{th["body"]}\';text-transform:uppercase;letter-spacing:.08em">{esc(l)}</b><span style="font-size:{P.fs(13)};color:{th["muted"]}">{esc("Contents" if an == "index" else kick.get(an, ""))}</span></a>' for l, an in P.nav_items[:P.nav_max])
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
            items = ''.join(f'<a href="#{an}" style="display:flex;gap:10px;align-items:baseline;padding:5px 0;border-bottom:1px solid {th["line"]}"><b style="min-width:110px;font:700 12px \'{th["body"]}\';text-transform:uppercase;letter-spacing:.08em">{esc(l)}</b><span style="font-size:{P.fs(13.5)};color:{th["muted"]}">{esc(next((k for (l2, a2, k) in P.index_items if a2 == an), ""))}</span></a>' for l, an in P.nav_items[:P.nav_max] if next((k for (l2, a2, k) in P.index_items if a2 == an), ""))
            extra += f'<div class="box" style="flex:none"><span class="k">{esc(sec.get("map_label", "The top bar, on every page"))}</span><div style="display:grid;grid-template-columns:1fr 1fr;gap:0 28px">{items}</div></div>'
        if sec.get('months'):
            hs_style = f'background:{th["paper"]};color:{th["ink"]};box-shadow:inset 0 0 0 2px {th["ink"]}' if P.gray else f'background:{th["ink"]};color:{th["paper"]}'
            ms = ''.join(f'<a href="#{an}" style="display:flex;align-items:center;justify-content:center;border-radius:12px;{hs_style};font:600 15px \'{th["body"]}\'">{esc(lb)}</a>' for lb, an in getattr(P, 'head_start_links', []))
            ms += ''.join(f'<a href="#m{i + 1:02d}" style="display:flex;align-items:center;justify-content:center;border-radius:12px;background:{P.tint(i, th.get("tile_alpha", "55"))};font:600 15px \'{th["body"]}\'">{MONTHS[i]}{"" if P.undated else " " + str(P.year)}</a>' for i in range(12))
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
        if P.undated:  # blank boxes to write the dates in, instead of an empty page
            cells = cells.replace('border:0;text-align:center" class="d"', f'border:1px solid {th["line"]};min-height:22px;text-align:center" class="d"')
        if P.pf:  # printed: three columns, larger dates
            cells = cells.replace('font-size:9.5px', f'font-size:{P.fs(11)}')
            cells = cells.replace('<span class="d x"></span>', '<span class="d x" style="padding:2px 3px;border:0">&#8203;</span>')  # empty rows keep their height: the 12 grids line up
        if P.undated:  # no date links inside, so the whole month block (name and grid) is one link: "Tap a month"
            blocks += f'<a href="#m{m:02d}" style="display:flex;flex-direction:column;gap:4px"><span class="k" style="color:{th["ink"]};font-size:11px">{MONTHS[m - 1]}</span><div class="cal" style="font-size:9px;grid-template-rows:auto;grid-auto-rows:1fr">{cells}</div></a>'
        else:
            blocks += f'<div style="display:flex;flex-direction:column;gap:4px"><a href="#m{m:02d}" class="k" style="color:{th["ink"]};font-size:11px">{MONTHS[m - 1]}</a><div class="cal" style="font-size:9px">{cells}</div></div>'
    if P.pf:
        blocks = blocks.replace('font-size:11px">', f'font-size:{P.fs(15)}">')
    title = 'Year at a glance' if P.undated else f'{P.year} at a glance'
    _register(P, sec, 'Year', 'year', 'Calendar')
    chips = ''.join(f'<a href="#{a_}" style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:{P.rpill}px;{(f'background:{th["paper"]};color:{th["ink"]};box-shadow:inset 0 0 0 1.5px {th["ink"]}') if P.gray else (f'background:{th["ink"]};color:{th["paper"]}')};font:600 11px \'{th["body"]}\';letter-spacing:.06em;text-transform:uppercase">{esc(l_)} {arrow("r", 12)}</a>' for l_, a_ in sec.get('links', []))
    hint = f'<div style="display:flex;gap:12px;align-items:center">{chips}<span class="k">{"Tap a month" if P.undated else "On screen, a date opens its week" if P.pf else "Tap any date"}</span></div>'
    if P.pf:  # paper: an outlined chip, not a solid ink block
        hint = hint.replace(f'background:{th["ink"]};color:{th["paper"]}', f'box-shadow:inset 0 0 0 1.5px {th["ink"]};color:{th["ink"]}')
    if P.HT > P.W and chips:  # portrait: the chips and hint get their own row under the title, so neither wraps
        hint = hint.replace('text-transform:uppercase">', 'text-transform:uppercase;white-space:nowrap">').replace('<span class="k">', '<span class="k" style="white-space:nowrap">')
        head = P.head('Overview', title) + f'<div style="display:flex;justify-content:space-between;align-items:center">{hint}</div>'
    else:
        head = P.head('Overview', title, right=hint)
    P.page('year', head + f'<div style="display:grid;grid-template-columns:repeat({3 if P.pf else 4},1fr);gap:14px 22px;flex:1">{blocks}</div>', active='year')


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
        strip = '' if n == 1 else ''.join(f'<a href="#{a if j == 1 else f"{a}{j}"}" class="pgn" style="display:inline-flex;align-items:center;justify-content:center;min-width:30px;padding:5px 9px;border-radius:{P.rpill}px;font:600 11px \'{th["body"]}\';{"background:" + th["ink"] + ";color:" + th["paper"] if j == i else "background:" + th["soft"]}">{j}</a>' for j in range(1, n + 1))
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
    if P.pf:  # printed: the button names the page to turn to (filled in at the end of the build)
        steps = re.sub(r'href="#([^"]+)"([^>]*)>Go there ', lambda mm: f'href="#{mm.group(1)}"{mm.group(2)}>Page %%PG:{mm.group(1)}%% ', steps)
        steps = steps.replace(f'background:{P.btn};color:{P.th["paper"]}', f'box-shadow:inset 0 0 0 1.5px {P.th["ink"]};color:{P.th["ink"]}')
    tip = f'<div class="box fill" style="margin-top:auto"><span class="k">Tip</span><span style="font-size:13px;line-height:1.45">{esc(sec["tip"])}</span></div>' if sec.get('tip') else ''
    _register(P, sec, sec['label'], a, sec.get('kicker', 'Start here'))
    P.page(a, P.head(sec.get('kicker', 'Start here'), sec['label']) + f'<div style="display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:1fr;gap:14px;flex:1">{steps}</div>%%GUIDE_EXTRA:{a}%%{tip}', active=a, deco=True)
    P.guide_extras = getattr(P, 'guide_extras', {})
    P.guide_extras[a] = sec


@module('link_test', 'Setup check page: buttons that jump to a test page and back, so buyers confirm links work before planning. label, anchor, targets ([[button label, anchor]] x3, default month, year, Contents), fixes (4 str: the fix list)',
        params={'label': 'str', 'anchor': 'str', 'targets': 'list of [label, anchor], 3 items', 'fixes': 'list of 4 str'})
def m_link_test(P, sec):
    th = P.th; a = sec.get('anchor', 'linktest')
    targets = [tuple(t) for t in sec['targets']] if sec.get('targets') else [('A month page', 'm01'), ('The year', 'year'), ('Contents', 'index')]
    btns = ''.join(f'<a href="#{t}" style="padding:16px 22px;border-radius:14px;background:{th["soft"]};font:600 17px \'{th["body"]}\';display:flex;justify-content:space-between;align-items:center"><span>{esc(l)}</span><span>{arrow('r')}</span></a>' for l, t in targets)
    fixes = _chk(4, sec.get('fixes') or P.eink.get('link_test_fixes') or ["Turn the pen off (read or view mode)", f"Open the file in a {'note' if P.noun == 'journal' else 'PDF planner'} app, not Files or Photos", "Re-import the PDF, do not convert it", "Still stuck? Send the shop an Etsy message"])
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
        params={'month': 'dict', 'habits': 'bool', 'week': 'dict', 'day': 'dict', 'days': 'bool', 'iso_weeks': 'bool: ISO 8601 week numbers (Week 1 holds January 4); needs a head_start covering the days before it.',
                'free_weeks': 'bool (undated only): weeks 1 to 52 run in order from the week the buyer starts, not filed under months; adds a Weeks page (anchor weeks) with all 52, month pages link to it'})
def m_calendar(P, sec):
    if P.pf:
        return _pf_calendar(P, sec)
    th = P.th
    msec = sec.get('month', {}); wsec = sec.get('week', {}); dsec = sec.get('day', {})
    side_labels = msec.get('side', ['Goals', 'Notes'])
    wside = wsec.get('side') or WEEK_PRESETS[wsec.get('preset', 'default')]
    dlay = dsec if dsec.get('left') else DAY_PRESETS[dsec.get('preset', 'default')]
    if sec.get('habits'):
        _register(P, {'nav': False}, 'Habit trackers', 'm01h', 'Monthly', nav=False)
    free = P.undated and sec.get('free_weeks')  # undated: weeks 1 to 52 run from the buyer's first week, not filed under months
    if free:
        _free_weeks_index(P, sec)
    for m in range(1, 13):
        cells, rows = P.cal_grid(m)
        if free:
            weeks = []
        elif P.undated:
            n0 = sum((4, 4, 5)[i % 3] for i in range(m - 1))  # weeks in order: Jan 1-4, Feb 5-8, Mar 9-13 ... Dec 48-52
            weeks = list(range(n0 + 1, n0 + 1 + (4, 4, 5)[(m - 1) % 3]))
        else:
            weeks = sorted({P.week_of(d) for d in calendar.Calendar(0).itermonthdates(P.year, m) if d.month == m})
        w0 = [w for w in weeks if w < 1]; weeks = [w for w in weeks if w >= 1]  # iso_weeks: week 0 belongs to the year before
        wl = ''.join(f'<a href="#w{w:02d}" style="display:inline-flex;align-items:center;line-height:1;padding:6px 9px;border-radius:{P.rpill}px;background:{th["soft"]};font:600 10.5px \'{th["body"]}\'">Week {w}</a>' for w in weeks)
        if free:
            wl = f'<a href="#weeks" style="display:inline-flex;align-items:center;line-height:1;padding:6px 12px;border-radius:{P.rpill}px;background:{th["soft"]};font:600 10.5px \'{th["body"]}\'">All weeks</a>'
        side =''.join(f'<div class="box" style="flex:1"><span class="k">{esc(x)}</span><div class="lines"></div></div>' for x in side_labels)
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
    if free:
        for n in range(1, 53):
            _week(P, n, None, wside, dlay, sec.get('days', True))


def _free_weeks_index(P, sec):
    """Undated free_weeks: one page linking all 52 weeks, each with a line to write the week's first date."""
    th = P.th; cols = 4 if P.HT > P.W else 6
    cells = ''.join(f'<a href="#w{n:02d}" class="box" style="padding:6px 10px;gap:2px;justify-content:center"><span style="font:700 {P.fs(13)} \'{th["body"]}\'">Week {n}</span>'
                    f'<span style="font-size:{P.fs(11)};color:{th["muted"]};border-bottom:1px solid {th["line"]};padding-bottom:1px">starts</span></a>' for n in range(1, 53))
    _register(P, sec.get('weeks_index', {}), 'Weeks', 'weeks', 'All 52 weeks')
    P.page('weeks', P.head('Write each week\'s first date once', 'Weeks') +
           f'<div style="flex:1;display:grid;grid-template-columns:repeat({cols},1fr);grid-auto-rows:1fr;gap:6px">{cells}</div>', active='weeks', crumb='Weeks')


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
        elif getattr(P, 'head_start_range', None) and P.head_start_range[0] <= d <= P.head_start_range[1]:
            head = f'<div style="display:flex;justify-content:space-between;align-items:baseline"><span class="k">{DOW[d.weekday()]}</span><span class="h" style="font-size:22px">{d.day}</span></div>'  # a head-start day: real planner day, not faded
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
    P.page(f'w{n:02d}', inner, month=m, crumb=(f'<a href="#m{m:02d}">{MONTHS[m - 1]}</a>' if m else '<a href="#weeks">Weeks</a>') + f' / Week {n}')
    if not with_days:
        return
    for i, d in enumerate(days):
        if d is not None and d.year != P.year:
            continue
        _day(P, d, n, m, i, day_layout)


def _day(P, d, n, m, i, lay):
    if d is None:
        anchor = f'u{n:02d}{i}'
        prev_a = f'u{n:02d}{i - 1}' if i > 0 else (f'u{n - 1:02d}6' if n > 1 else None)  # across week edges too
        next_a = f'u{n:02d}{i + 1}' if i < 6 else (f'u{n + 1:02d}0' if n < 52 else None)
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
    P.page(anchor, inner, month=mm, crumb=(f'<a href="#m{mm:02d}">{MONTHS[mm - 1]}</a>' if mm else '<a href="#weeks">Weeks</a>') + f' / {wk}')


@module('head_start', 'Lead-in months before the main dated year (for example Nov and Dec 2026 in a 2027 planner): month pages whose dates link to lead-in week pages, Monday-start week pages titled by date range, optional lead-in day pages. Anchors use their own prefix. The last week links days that fall in the main year to their day pages and offers Continue to the main year. label, kicker, anchor (prefix, default hs), from YYYY-MM, to YYYY-MM, days bool, month {side}, week {preset|side}, day {preset|left,right}, continue_to (default m01)',
        params={'label': 'str', 'kicker': 'str', 'anchor': 'str', 'from': 'YYYY-MM', 'to': 'YYYY-MM', 'days': 'bool', 'month': 'dict', 'week': 'dict', 'day': 'dict', 'continue_to': 'str', 'main_links': 'bool: on head-start pages the head-start month tabs say their year (NOV 2026) so one label has one target, the last head-start week arrow opens main Week 1 and Week 1 gets a back arrow'})
def m_head_start(P, sec):
    if P.pf:
        return _pf_head_start(P, sec)
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
    P.head_start_range = (lead_from, last)  # days the planner covers before the main year (Week 1 prints them unfaded)
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


# ---------- trackers (fitness, meals, self-care): undated weeks, workouts, meals, body, charts, months ----------
def _circle(P, r=6.3, color=None):
    """An empty circle to tick or fill (SVG, so no glyph is needed)."""
    s = round(r * 2 + 3)
    return f'<svg width="{s}" height="{s}" viewBox="0 0 {s} {s}" style="flex:none;display:block"><circle cx="{s / 2}" cy="{s / 2}" r="{r}" fill="none" stroke="{color or P.th["muted"]}" stroke-width="1.3"/></svg>'


def _tick_box(P, size=15):
    return f'<i style="width:{size}px;height:{size}px;border:1.4px solid {P.th["muted"]};border-radius:3px;display:block;margin:auto;flex:none"></i>'


def _chip(P, label, anchor, primary=False, back=False):
    """A button to another page: filled (primary) or outlined."""
    th = P.th
    look = f'background:{P.btn};color:{th["paper"]}' if primary else f'background:{th["paper"]};color:{th["ink"]};box-shadow:inset 0 0 0 1.4px {th["line"]}'
    return f'<a href="#{anchor}" style="display:inline-flex;align-items:center;gap:6px;white-space:nowrap;padding:7px 13px;border-radius:{P.rpill}px;{look};font:600 {P.fs(12)} \'{th["body"]}\'">{(arrow("l", 12) + " " + esc(label)) if back else (esc(label) + " " + arrow("r", 12))}</a>'


def _wline(P, label, width=None, after=''):
    """Inline write-in: label then a rule (dates, units)."""
    th = P.th
    w = f'width:{width}px;flex:none' if width else 'flex:1'
    return f'<div style="display:flex;align-items:flex-end;gap:8px;{w}"><span class="k" style="flex:none">{esc(label)}</span><span style="flex:1;min-width:30px;border-bottom:1.2px solid {th["line"]};height:{22 * P.scale:.0f}px"></span>{after}</div>'


def _linked(n, links):
    """Pages that belong to numbered week n. links: [{label, anchor (prefix), per}]. per 1: prefix + 2 digits (meal05);
    per k > 1: k pages numbered across all weeks, prefix + 3 digits (week 2 of per 4: wo005 to wo008), labelled 'label 1' to 'label k'."""
    out = []
    for L in links:
        per = int(L.get('per', 1))
        if per == 1:
            out.append((L['label'], f'{L["anchor"]}{n:02d}'))
        else:
            out += [(f'{L["label"]} {j}', f'{L["anchor"]}{(n - 1) * per + j:03d}') for j in range(1, per + 1)]
    return out


def _grid_rows(P, cols, labels, cells, row_style='flex:1;min-height:0'):
    """Rows of a ruled table: a label cell then one cell per column (cells(j) gives cell content)."""
    th = P.th
    return ''.join(f'<div style="display:grid;grid-template-columns:{cols};border-bottom:1px solid {th["line"]};{row_style};align-items:stretch">'
                   f'<span style="display:flex;align-items:center;padding:0 6px;font:600 {P.fs(12.5)} \'{th["body"]}\'">{lab}</span>' +
                   ''.join(f'<span style="border-left:1px solid {th["line"]};display:flex;align-items:center;justify-content:center;position:relative">{cells(j)}</span>' for j in range(cells.n)) +
                   '</div>' for lab in labels)


class _Cells:
    def __init__(self, n, fn):
        self.n, self.fn = n, fn

    def __call__(self, j):
        return self.fn(j)


def _table_box(P, title, cols, headers, rows_html, style='flex:1', hint='', center=()):
    th = P.th
    hdr = ''.join(f'<span class="k" style="padding:4px 8px;{"text-align:center" if i in center else ""}">{esc(h)}</span>' for i, h in enumerate(headers))
    top = (f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding-bottom:6px"><span class="k" style="flex:none">{esc(title)}</span>'
           f'<span style="font-size:{P.fs(11.5)};color:{th["muted"]};text-align:right;line-height:1.3">{esc(hint)}</span></div>') if title else ''
    return (f'<div class="box" style="{style};gap:0">{top}<div style="display:grid;grid-template-columns:{cols};border-bottom:1.5px solid {th["ink"]}">{hdr}</div>'
            f'<div style="flex:1;display:flex;flex-direction:column">{rows_html}</div></div>')


@module('log_week', "Undated numbered week pages (anchor prefix + 2 digits: w01 to w52) plus an overview page (overview_anchor) with a card per week: tap to open it, write its start date. Each week page: a dates line, buttons to the pages that belong to that week (links, for example its meal plan and workout logs; mark_every adds a button to mark_anchor every few weeks, for example a measuring check-in), a day table (days x columns; check columns draw tick boxes), a habit grid (habits plus blank rows x 7 days of circles), a box of one-line stats (for example Weigh-in) and lined boxes (fields). Previous and next arrows, trail back to the overview. One Contents card and one top-bar item, both opening the overview. label, kicker, anchor, overview_anchor, overview_title, count, days, columns, habits, habits_label, blank_habits, stats, fields, links, mark_every, mark_anchor, mark_label",
        params={'label': 'str (Weeks)', 'kicker': 'str', 'anchor': "str prefix, default 'w'", 'overview_anchor': "str, default 'weeks'", 'overview_title': 'str', 'count': 'int (52)',
                'days': 'list of 7 str (Mon to Sun)', 'columns': 'list of {label, check: bool, width: fr number}', 'habits': 'list of str', 'habits_label': 'str', 'blank_habits': 'int (2)',
                'stats': 'list of str: one-line fields', 'fields': 'list of str: lined boxes', 'links': 'list of {label, anchor: prefix, per: int}',
                'mark_every': 'int', 'mark_anchor': 'str', 'mark_label': 'str'})
def m_log_week(P, sec):
    th = P.th
    pre = sec.get('anchor', 'w'); ov = sec.get('overview_anchor', 'weeks'); N = int(sec.get('count', 52))
    label = sec.get('label', 'Weeks'); kicker = sec.get('kicker', 'Plan')
    days = sec.get('days') or DOW
    cols = sec.get('columns') or [{'label': 'Plan'}, {'label': 'Done', 'check': True}]
    habits = list(sec.get('habits') or []) + [''] * int(sec.get('blank_habits', 2))
    stats = sec.get('stats') or []; fields = sec.get('fields') or ['Notes']
    links = sec.get('links') or []
    mark = int(sec.get('mark_every') or 0); mark_a = sec.get('mark_anchor'); mark_l = sec.get('mark_label', 'Check-in')
    wid = lambda n: f'{pre}{n:02d}'
    _register(P, sec, label, ov, kicker)
    portrait = P.HT > P.W
    # overview: one card per week, tinted in blocks of four weeks
    ncol = 4 if portrait else 8
    cards = ''
    for n in range(1, N + 1):
        tag = f'<span style="font:600 {P.fs(10.5)} \'{th["body"]}\';color:{th["accent"]}">{esc(mark_l)}</span>' if (mark > 1 and n % mark == 0) else ''  # every-week buttons are not marked on the overview
        bg = f'background:{th["paper"]};border-color:{th["line"]}' if P.gray else f'background:{P.tint(((n - 1) // 4) % 12, "30")};border-color:transparent'
        cards += (f'<a href="#{wid(n)}" class="box" style="padding:6px 10px;gap:2px;justify-content:space-between;{bg}">'
                  f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:4px"><b style="font:700 {P.fs(13.5)} \'{th["body"]}\'">Week {n}</b>{tag}</span>'
                  f'<span style="display:flex;align-items:flex-end;gap:6px"><span style="font-size:{P.fs(10.5)};color:{th["muted"]}">from</span><span style="flex:1;border-bottom:1.2px solid {th["line"] if P.gray else mix(th["muted"], th["paper"], .55)};height:14px"></span></span></a>')
    hint = f'<span style="font-size:{P.fs(12)};color:{th["muted"]}">Tap a week to open it</span>'
    P.page(ov, P.head(kicker, sec.get('overview_title', f'{N} weeks'), right=hint) +
           f'<div style="flex:1;display:grid;grid-template-columns:repeat({ncol},1fr);grid-auto-rows:1fr;gap:6px">{cards}</div>', active=ov)
    # week pages
    tcols = f'{58 * P.scale:.0f}px ' + ' '.join(f'{68 * P.scale:.0f}px' if c.get('check') else f'{c.get("width", 1)}fr' for c in cols)
    trows = _grid_rows(P, tcols, [esc(d) for d in days], _Cells(len(cols), lambda j: _tick_box(P) if cols[j].get('check') else ''))
    table = _table_box(P, '', tcols, ['Day'] + [c['label'] for c in cols], trows, style='flex:1.35',
                       center={i + 1 for i, c in enumerate(cols) if c.get('check')})
    hab = ''
    if habits:
        hcols = f'minmax(0,1fr) repeat({len(days)},{(40 if portrait else 33) * P.scale:.0f}px)'
        hh = f'<span class="k">{esc(sec.get("habits_label", "Habits"))}</span>' + ''.join(f'<span style="text-align:center;font:600 {P.fs(11)} \'{th["body"]}\';color:{th["muted"]}">{esc(d)}</span>' for d in days)
        hr = ''.join(f'<div style="display:grid;grid-template-columns:{hcols};align-items:center;border-bottom:1px solid {th["line"]};flex:1;min-height:{24 * P.scale:.0f}px">'
                     f'<span style="font-size:{P.fs(12.5)};padding-right:6px">{esc(h)}</span>' + ''.join(f'<span style="display:flex;justify-content:center">{_circle(P)}</span>' for _ in days) + '</div>' for h in habits)
        hab = (f'<div class="box" style="flex:1;gap:0"><div style="display:grid;grid-template-columns:{hcols};align-items:end;padding-bottom:4px;border-bottom:1.5px solid {th["ink"]}">{hh}</div>'
               f'<div style="flex:1;display:flex;flex-direction:column">{hr}</div></div>')
    st = (f'<div class="box fill" style="flex:1;justify-content:space-evenly">' + ''.join(field(P, s, 'flex:none') for s in stats) + '</div>') if stats else ''
    bottom = f'<div class="row" style="flex:.8">{st}{"".join(lines_box(P, f) for f in fields)}</div>'
    for n in range(1, N + 1):
        chips = ''.join(_chip(P, l, a_, primary=(i == 0)) for i, (l, a_) in enumerate(_linked(n, links)))
        if mark and mark_a and n % mark == 0:
            chips += _chip(P, mark_l, mark_a)
        dates = f'<div style="display:flex;align-items:flex-end;gap:10px">{_wline(P, "Dates")}{_wline(P, "to")}</div>'
        chiprow = f'<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">{chips}</div>' if chips else ''
        inner = (P.head(f'{kicker} · week {n} of {N}', f'Week {n}', right=_arrows(wid(n - 1) if n > 1 else None, wid(n + 1) if n < N else None)) +
                 dates + chiprow + (table + hab + bottom if portrait else  # landscape: day table and notes left, habits and stats right
                 f'<div class="row" style="flex:1"><div class="col" style="flex:1.35">{table}<div class="row" style="flex:.75">{"".join(lines_box(P, f) for f in fields)}</div></div>'
                 f'<div class="col" style="flex:1">{hab}{st.replace("flex:1;justify-content", "flex:none;justify-content", 1)}</div></div>'))
        P.page(wid(n), inner, active=ov, crumb=f'<a href="#{ov}">{esc(label)}</a> / Week {n}')


@module('meal_week', "Weekly meal plan pages (anchor prefix + 2 digits: meal01 to meal52), one per numbered week: a grid of days x meals with a small circle in each cell to tick when you ate what you planned, a grocery list in groups with tick boxes, and lined boxes (fields) beside the groups. With week_anchor (pair with log_week), a button back to that week's page and a trail Week n / Meals. Previous and next arrows. One Contents card. label, kicker, anchor, count, meals, days, grocery, grocery_rows, fields, week_anchor, tick",
        params={'label': 'str (Meal plans)', 'kicker': 'str', 'anchor': "str prefix, default 'meal'", 'count': 'int (52)', 'meals': 'list of str (Breakfast, Lunch, Dinner, Snacks)',
                'days': 'list of 7 str', 'grocery': 'list of str: group names', 'grocery_rows': 'int (5)', 'fields': 'list of str', 'week_anchor': 'str: log_week prefix', 'tick': 'bool (true)'})
def m_meal_week(P, sec):
    th = P.th; pre = sec.get('anchor', 'meal'); N = int(sec.get('count', 52))
    label = sec.get('label', 'Meal plans'); kicker = sec.get('kicker', 'Meals')
    meals = sec.get('meals') or ['Breakfast', 'Lunch', 'Dinner', 'Snacks']
    days = sec.get('days') or DOW
    groups = sec.get('grocery') or ['Produce', 'Protein', 'Dairy and eggs', 'Pantry', 'Other']
    grows = int(sec.get('grocery_rows', 5)); fields = sec.get('fields') or ['Prep ahead']
    wk = sec.get('week_anchor'); tick = sec.get('tick', True)
    mid = lambda n: f'{pre}{n:02d}'
    _register(P, sec, label, mid(1), kicker)
    portrait = P.HT > P.W
    tcols = f'{58 * P.scale:.0f}px repeat({len(meals)},minmax(0,1fr))'
    circ = (lambda j: f'<span style="position:absolute;right:5px;top:5px">{_circle(P, 5.5)}</span>') if tick else (lambda j: '')
    rows = _grid_rows(P, tcols, [esc(d) for d in days], _Cells(len(meals), circ))
    grid = _table_box(P, "This week's meals", tcols, [''] + meals, rows, style='flex:1.5',
                      hint='Tick the circle when you ate what you planned' if tick else '')
    gl = ''.join(f'<div style="display:flex;flex-direction:column;min-width:0"><span style="font:700 {P.fs(12.5)} \'{th["body"]}\';padding-bottom:2px">{esc(g)}</span>{_chk(grows)}</div>' for g in groups)
    fl = ''.join(f'<div style="display:flex;flex-direction:column;min-width:0"><span style="font:700 {P.fs(12.5)} \'{th["body"]}\';padding-bottom:2px">{esc(f)}</span><div class="lines"></div></div>' for f in fields)
    ncol = 3 if portrait else 2
    grocery = f'<div class="box" style="flex:1"><span class="k">Grocery list</span><div style="flex:1;display:grid;grid-template-columns:repeat({ncol},minmax(0,1fr));gap:10px 18px">{gl}{fl}</div></div>'
    for n in range(1, N + 1):
        back = _chip(P, f'Week {n}', f'{wk}{n:02d}', primary=True, back=True) if wk else ''
        right = f'<div style="display:flex;gap:12px;align-items:center">{back}{_arrows(mid(n - 1) if n > 1 else None, mid(n + 1) if n < N else None)}</div>'
        body = f'{grid}{grocery}' if portrait else f'<div class="row" style="flex:1">{grid.replace("flex:1.5", "flex:1.7", 1)}{grocery}</div>'
        P.page(mid(n), P.head(f'{kicker} · week {n}', 'Meal plan', right=right) + body, active=mid(1),
               crumb=(f'<a href="#{wk}{n:02d}">Week {n}</a> / Meals' if wk else f'{esc(label)} · week {n}'))


@module('workout_log', "Workout log: count session pages (anchor prefix + 3 digits: wo001...) and log list pages (log_anchor, then log2, log3...) with a line and a button for every session. With per_week, sessions belong to numbered weeks (week n holds sessions (n-1)*per_week+1 to n*per_week, titled Workout 1 to per_week) and get a button back to the week page (week_anchor; pair with log_week links {anchor: this prefix, per: per_week}). Session page: date, focus, minutes, effort 1 to 5; an exercise table (Exercise, Last time, Set 1 to sets, each set weight x reps) so every session can beat the last; an optional cardio table; lined boxes (fields). Previous and next arrows. One Contents card and one top-bar item, both opening the log list. label, kicker, anchor, log_anchor, count, per_week, week_anchor, exercises, sets, cardio, fields, per_log_page",
        params={'label': 'str (Training log)', 'kicker': 'str', 'anchor': "str prefix, default 'wo'", 'log_anchor': "str, default 'log'", 'count': 'int (156)', 'per_week': 'int',
                'week_anchor': 'str: log_week prefix', 'exercises': 'int rows (8)', 'sets': 'int (4)', 'cardio': 'bool (true)', 'fields': 'list of str (2)', 'per_log_page': 'int'})
def m_workout_log(P, sec):
    th = P.th; pre = sec.get('anchor', 'wo'); la = sec.get('log_anchor', 'log'); N = int(sec.get('count', 156))
    label = sec.get('label', 'Training log'); kicker = sec.get('kicker', 'Workouts')
    per = int(sec.get('per_week') or 0); wk = sec.get('week_anchor')
    ex = int(sec.get('exercises', 8)); sets = int(sec.get('sets', 4)); cardio = sec.get('cardio', True)
    fields = sec.get('fields') or ['How it felt', 'Next time']
    sid = lambda i: f'{pre}{i:03d}'
    rpp = int(sec.get('per_log_page') or (per * 7 if per else 26)); npg = math.ceil(N / rpp)
    lpg = lambda p: la if p == 1 else f'{la}{p}'
    week_of = lambda i: (i - 1) // per + 1 if per else None
    k_of = lambda i: (i - 1) % per + 1 if per else i
    _register(P, sec, label, la, kicker)
    pill = lambda txt, a_: f'<a href="#{a_}" style="display:inline-flex;align-items:center;justify-content:center;min-width:{34 * P.scale:.0f}px;padding:3px 9px;border-radius:{P.rpill}px;background:{th["soft"]};font:700 {P.fs(11.5)} \'{th["body"]}\'">{esc(txt)}</a>'
    # log list pages
    heads = (['Week', 'Workout'] if per else ['No.']) + ['Date', 'Focus', 'Minutes', 'Effort']
    lcols = (f'{82 * P.scale:.0f}px {76 * P.scale:.0f}px' if per else f'{58 * P.scale:.0f}px') + ' 1fr 1.6fr 0.8fr 0.8fr'
    for p in range(1, npg + 1):
        lo, hi = (p - 1) * rpp + 1, min(p * rpp, N)
        strip = ''.join(f'<a href="#{lpg(q)}" style="padding:5px 11px;border-radius:{P.rpill}px;font:600 {P.fs(11)} \'{th["body"]}\';{"background:" + th["ink"] + ";color:" + th["paper"] if q == p else "background:" + th["soft"]}">'
                        f'{week_of((q - 1) * rpp + 1) if per else (q - 1) * rpp + 1} to {week_of(min(q * rpp, N)) if per else min(q * rpp, N)}</a>' for q in range(1, npg + 1))
        rows = ''
        for i in range(lo, hi + 1):
            first = (not per) or k_of(i) == 1
            sep = f'border-top:1.3px solid {mix(th["muted"], th["paper"], .45)};' if (per and k_of(i) == 1 and i != lo) else ''
            wcell = (f'<span style="display:flex;align-items:center">{pill(f"Week {week_of(i)}", f"{wk}{week_of(i):02d}") if (first and wk) else (esc(f"Week {week_of(i)}") if first else "")}</span>' if per else '')
            rows += (f'<div style="display:grid;grid-template-columns:{lcols};align-items:stretch;border-bottom:1px solid {th["line"]};{sep}flex:1;min-height:0">{wcell}'
                     f'<span style="display:flex;align-items:center">{pill(str(k_of(i)), sid(i))}</span>' +
                     ''.join(f'<span style="border-left:1px solid {th["line"]}"></span>' for _ in range(4)) + '</div>')
        inner = (P.head(f'{kicker} · ' + (f'weeks {week_of(lo)} to {week_of(hi)}' if per else f'{lo} to {hi}'), label, right=_arrows(lpg(p - 1) if p > 1 else None, lpg(p + 1) if p < npg else None)) +
                 f'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap"><span class="k" style="margin-right:4px">{"Weeks" if per else "Workouts"}</span>{strip}<span style="margin-left:auto;font-size:{P.fs(12)};color:{th["muted"]}">Tap a number to open that workout</span></div>' +
                 _table_box(P, '', lcols, heads, rows))
        P.page(lpg(p), inner, active=la, crumb=f'{esc(label)} · page {p} of {npg}')
    # session pages
    effort = ''.join(f'<circle cx="{12 + j * 28}" cy="12" r="10.5" fill="none" stroke="{th["muted"]}" stroke-width="1.3"/><text x="{12 + j * 28}" y="16" text-anchor="middle" font-size="11.5" font-family="{th["body"]}" fill="{th["ink"]}">{j + 1}</text>' for j in range(5))
    effort = f'<div style="display:flex;align-items:center;gap:10px;flex:none"><span class="k">Effort</span><svg width="{5 * 28}" height="24" viewBox="0 0 {5 * 28} 24">{effort}</svg></div>'
    details = (f'<div class="box" style="gap:12px;padding:12px 14px;flex:none"><div class="row" style="gap:22px">{field(P, "Date")}{field(P, "Focus", "flex:1.6")}</div>'
               f'<div class="row" style="gap:22px;align-items:flex-end">{field(P, "Minutes", "flex:.8")}{effort}</div></div>')
    ecols = f'1.8fr 1fr repeat({sets},1fr)'
    erows = ''.join(f'<div style="display:grid;grid-template-columns:{ecols};border-bottom:1px solid {th["line"]};flex:1;min-height:0">' +
                    ''.join(f'<span style="{"border-left:1px solid " + th["line"] if j else ""}{";border-right:1.3px solid " + mix(th["muted"], th["paper"], .45) if j == 1 else ""}"></span>' for j in range(sets + 2)) + '</div>' for _ in range(ex))
    extable = _table_box(P, 'Exercises', ecols, ['Exercise', 'Last time'] + [f'Set {j}' for j in range(1, sets + 1)], erows, style='flex:2.3',
                         hint='Write weight x reps, for example 20 x 10. Copy your best set from last time, then try to beat it.')
    ctable = ''
    if cardio:
        ccols = '1.8fr 1fr 1fr 2fr'
        crows = ''.join(f'<div style="display:grid;grid-template-columns:{ccols};border-bottom:1px solid {th["line"]};height:{32 * P.scale:.0f}px">' + ''.join(f'<span style="{"border-left:1px solid " + th["line"] if j else ""}"></span>' for j in range(4)) + '</div>' for _ in range(2))
        ctable = _table_box(P, 'Cardio', ccols, ['Activity', 'Minutes', 'Distance', 'Notes'], crows, style='flex:none')
    bottom = f'<div class="row" style="flex:1">{"".join(lines_box(P, f) for f in fields)}</div>'
    for i in range(1, N + 1):
        w, k = week_of(i), k_of(i)
        back = _chip(P, f'Week {w}', f'{wk}{w:02d}', primary=True, back=True) if (per and wk) else ''
        right = f'<div style="display:flex;gap:12px;align-items:center">{back}{_arrows(sid(i - 1) if i > 1 else None, sid(i + 1) if i < N else None)}</div>'
        kick = f'{kicker} · week {w}, {k} of {per}' if per else f'{kicker} · {i} of {N}'
        trail = f'<a href="#{lpg((i - 1) // rpp + 1)}">{esc(label)}</a> / ' + (f'<a href="#{wk}{w:02d}">Week {w}</a> / Workout {k}' if (per and wk) else f'Workout {i}')
        P.page(sid(i), P.head(kick, f'Workout {k}', right=right) + details + extable + ctable + bottom, active=la, crumb=trail)


@module('body_measure', "Body measurements page: a table of check-ins (rows: Start, then every few weeks) by Date and parts (columns), a Change since start row, a units line, and a How to measure box (tips: one per part). With week_anchor (pair with log_week), each Week n check-in opens that week's page. One Contents card. label, kicker, anchor, parts, every, weeks, week_anchor, tips",
        params={'label': 'str (Measurements)', 'kicker': 'str', 'anchor': "str, default 'measure'", 'parts': 'list of str (columns, 5 to 7)', 'every': 'int (4)', 'weeks': 'int (52)',
                'week_anchor': 'str', 'tips': 'list of [part, how]'})
def m_body_measure(P, sec):
    th = P.th; a = sec.get('anchor', 'measure'); label = sec.get('label', 'Measurements'); kicker = sec.get('kicker', 'Every 4 weeks')
    parts = sec.get('parts') or ['Weight', 'Chest', 'Waist', 'Hips', 'Thigh', 'Arm']
    every = int(sec.get('every', 4)); weeks = int(sec.get('weeks', 52)); wk = sec.get('week_anchor')
    checks = [('Start', 1)] + [(f'Week {w}', w) for w in range(every, weeks + 1, every)]
    tips = sec.get('tips') or []
    _register(P, sec, label, a, kicker)
    cols = f'{92 * P.scale:.0f}px repeat({len(parts) + 1},minmax(0,1fr))'
    lab = lambda t, w: (f'<a href="#{wk}{w:02d}" style="padding:3px 9px;border-radius:{P.rpill}px;background:{th["soft"]};font:700 {P.fs(11.5)} \'{th["body"]}\'">{esc(t)}</a>' if wk else esc(t))
    rows = _grid_rows(P, cols, [lab(t, w) for t, w in checks], _Cells(len(parts) + 1, lambda j: ''))
    rows += _grid_rows(P, cols, [f'<b>Change</b>'], _Cells(len(parts) + 1, lambda j: ''), row_style=f'flex:1.1;min-height:0;border-top:1.5px solid {th["ink"]}')
    table = _table_box(P, 'Check-ins', cols, ['', 'Date'] + parts, rows, style='flex:1', hint='Measure in the morning, before eating. Change is your latest row minus Start.')
    tipbox = (f'<div class="box fill" style="flex:none"><span class="k">How to measure</span><div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 24px">' +
              ''.join(f'<p style="font-size:{P.fs(12)};line-height:1.4"><b>{esc(t)}</b> {esc(x)}</p>' for t, x in tips) + '</div></div>') if tips else ''
    units = f'<div style="display:flex;gap:22px;align-items:flex-end">{_wline(P, "Length unit, cm or in")}{_wline(P, "Weight unit, kg or lb")}</div>'
    P.page(a, P.head(kicker, label) + units + table + tipbox, active=a)


@module('progress_chart', "A chart page to plot one number over time (weight, sleep hours, mood...): points (columns, labelled every few points) by rows, with room for your own scale on the left, a box of one-line fields above (for example Start, Goal) and blocks under the chart (any block kinds: checklist, lines...). links: buttons in the title row. label, kicker, anchor, points, point_label, every, rows, y_label, hint, fields, blocks, links",
        params={'label': 'str (Progress)', 'kicker': 'str', 'anchor': "str, default 'progress'", 'points': 'int (52)', 'point_label': 'str (Week)', 'every': 'int (4)', 'rows': 'int (20)',
                'y_label': 'str', 'hint': 'str', 'fields': 'list of str', 'blocks': 'list of blocks', 'links': 'list of [label, anchor]'})
def m_progress_chart(P, sec):
    th = P.th; a = sec.get('anchor', 'progress'); label = sec.get('label', 'Progress'); kicker = sec.get('kicker', 'Track')
    pts = int(sec.get('points', 52)); every = int(sec.get('every', 4)); rows = int(sec.get('rows', 20))
    plab = sec.get('point_label', 'Week'); ylab = sec.get('y_label', 'Your scale')
    fields = sec.get('fields') or []; blocks = sec.get('blocks') or []; links = sec.get('links') or []
    _register(P, sec, label, a, kicker)
    yw = 44
    strong = mix(th['muted'], th['paper'], .5)
    vl = ''.join(f'<i style="position:absolute;top:0;bottom:0;left:{100 * (j - .5) / pts:.3f}%;border-left:1px solid {strong if (j % every == 0 or j == 1) else th["line"]}"></i>' for j in range(1, pts + 1))
    hl = ''.join(f'<i style="position:absolute;left:-{yw}px;right:0;top:{100 * r / rows:.3f}%;border-top:1px solid {th["line"]}"></i>' for r in range(1, rows))
    xl = ''.join(f'<span style="position:absolute;left:{100 * (j - .5) / pts:.3f}%;transform:translateX(-50%);font:600 {P.fs(10.5)} \'{th["body"]}\';color:{th["muted"]}">{j}</span>' for j in range(1, pts + 1) if (j == 1 or j % every == 0))
    chart = (f'<div class="box" style="flex:1;gap:8px"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px"><span class="k">{esc(ylab)}</span>'
             f'<span style="font-size:{P.fs(11.5)};color:{th["muted"]}">{esc(sec.get("hint", f"Write your scale on the left. One dot per {plab.lower()}, then join the dots."))}</span></div>'
             f'<div style="flex:1;display:flex;flex-direction:column;padding-left:{yw}px;min-height:0"><div style="flex:1;position:relative;border:1.3px solid {strong}">{hl}{vl}</div>'
             f'<div style="position:relative;height:20px;margin-top:4px">{xl}</div><span style="align-self:center;font:600 {P.fs(11)} \'{th["body"]}\';color:{th["muted"]}">{esc(plab)}</span></div></div>')
    fbox = (f'<div class="box fill" style="flex-direction:row;gap:22px;align-items:flex-end;flex:none;padding:14px 16px">' + ''.join(field(P, f) for f in fields) + '</div>') if fields else ''
    brow = (f'<div class="row" style="flex:.42 0 auto">' + ''.join(f'<div style="flex:1;display:flex;flex-direction:column">{block(P, dict(b, grow=True))}</div>' for b in blocks) + '</div>') if blocks else ''
    right = f'<div style="display:flex;gap:6px">{"".join(_chip(P, l, an) for l, an in links)}</div>'
    P.page(a, P.head(kicker, label, right=right) + fbox + chart + brow, active=a)


@module('habit_month', "Twelve undated month pages, anchors m01 to m12 (the month rail and the Contents month grid open them): month name with a year line, a goal box and a box of one-line stats, a habit grid (habits plus blank rows by days 1 to 31, a circle per day; days a month never has are faded), an optional mood row (a square per day to color, with a color key), and lined boxes (fields). Previous and next month arrows. One Contents card (Months) unless index is false; no top-bar item unless nav is true. label, kicker, habits, habits_label, blank_habits, goal, stats, mood, fields, index, nav",
        params={'label': 'str (Months)', 'kicker': 'str', 'habits': 'list of str', 'habits_label': 'str', 'blank_habits': 'int (3)', 'goal': 'str (box label)', 'stats': 'list of str',
                'mood': '{label, keys: [[name, hex]]} or true', 'fields': 'list of str', 'index': 'bool', 'nav': 'bool (false)',
                'extra_months': 'int: extra undated month pages after December (m13...), for runs that start mid-month', 'extra_label': 'str', 'home': 'str: trail link target (default index)'})
def m_habit_month(P, sec):
    th = P.th; label = sec.get('label', 'Months'); kicker = sec.get('kicker', 'Monthly')
    habits = list(sec.get('habits') or []) + [''] * int(sec.get('blank_habits', 3))
    stats = sec.get('stats') or []; goal = sec.get('goal', "This month's goal")
    mood = sec.get('mood'); fields = sec.get('fields') or ['Notes']
    _register(P, dict(sec, nav=sec.get('nav', False)), label, 'm01', kicker)
    last = {2: 29, 4: 30, 6: 30, 9: 30, 11: 30}
    ncol = f'{118 * P.scale:.0f}px repeat(31,minmax(0,1fr))'
    keys = []
    if mood:
        mk = mood.get('keys') if isinstance(mood, dict) else None
        keys = mk or list(zip(['Great', 'Good', 'Okay', 'Low', 'Hard'], [th['accent'], P.tabs[0], th['warm'], P.tabs[-1], th['muted']]))
    extra = int(sec.get('extra_months', 0)); M = 12 + extra  # extra undated months (m13...) for a 52-week run that starts mid-month
    home = sec.get('home', 'index' if any(x.get('module') == 'index' for x in P.s.get('sections', [])) else 'm01')
    for m in range(1, M + 1):
        fade = lambda d: 'opacity:.25;' if d > last.get(m, 31) else ''
        hh = f'<span class="k">{esc(sec.get("habits_label", "Habits"))}</span>' + ''.join(f'<span style="text-align:center;font:600 {P.fs(9.5)} \'{th["body"]}\';color:{th["muted"]};{fade(d)}">{d}</span>' for d in range(1, 32))
        hr = ''.join(f'<div style="display:grid;grid-template-columns:{ncol};align-items:center;border-bottom:1px solid {th["line"]};flex:1;min-height:{28 * P.scale:.0f}px">'
                     f'<span style="font-size:{P.fs(12)};padding-right:6px;overflow:hidden;white-space:nowrap">{esc(h)}</span>' +
                     ''.join(f'<span style="display:flex;justify-content:center;{fade(d)}">{_circle(P, 5.2)}</span>' for d in range(1, 32)) + '</div>' for h in habits)
        grid = (f'<div class="box" style="{"flex:1.6" if len(habits) > 5 else "flex:none"};gap:0"><div style="display:grid;grid-template-columns:{ncol};align-items:end;padding-bottom:4px;border-bottom:1.5px solid {th["ink"]}">{hh}</div>'
                f'<div style="flex:1;display:flex;flex-direction:column">{hr}</div></div>')
        md = ''
        if mood:
            sq = ''.join(f'<span style="display:flex;justify-content:center;{fade(d)}"><i style="width:13px;height:13px;border:1.3px solid {th["muted"]};border-radius:3px;display:block"></i></span>' for d in range(1, 32))
            kk = ''.join(f'<span style="display:inline-flex;align-items:center;gap:6px;font-size:{P.fs(11.5)}"><i style="width:13px;height:13px;border-radius:3px;background:{c};display:block"></i>{esc(k)}</span>' for k, c in keys)
            md = (f'<div class="box" style="flex:none;gap:8px"><div style="display:grid;grid-template-columns:{ncol};align-items:center"><span class="k">{esc((mood.get("label") if isinstance(mood, dict) else None) or "Mood")}</span>{sq}</div>'
                  f'<div style="display:flex;gap:16px;flex-wrap:wrap;padding-left:{118 * P.scale:.0f}px">{kk}</div></div>')
        top = f'<div class="row" style="flex:none">{lines_box(P, goal, rows=2, style="flex:1.4")}' + (f'<div class="box fill" style="flex:1;justify-content:space-evenly">{"".join(field(P, s, "flex:none") for s in stats)}</div>' if stats else '') + '</div>'
        bottom = f'<div class="row" style="flex:1">{"".join(lines_box(P, f) for f in fields)}</div>'
        name = MONTHS[m - 1] if m <= 12 else sec.get('extra_label', 'One more month')
        P.page(f'm{m:02d}', P.head('Month · year ____' if m <= 12 else 'Month ____ · year ____', name, right=_arrows(f'm{m - 1:02d}' if m > 1 else None, f'm{m + 1:02d}' if m < M else None)) + top + grid + md + bottom,
               month=m if m <= 12 else None, crumb=f'<a href="#{home}">{"Contents" if home == "index" else esc(label)}</a> / {esc(name)}')


@module('prompt_week', "Weekly journal pages (anchor prefix + 2 digits: jr01 to jr52), one per numbered week, each with its own printed prompt (prompts, in order, repeating if fewer than count) and lined space to answer, plus boxes (numbered: lines numbered 1 to n, for example Three good things; lines: plain lined boxes). With week_anchor (pair with log_week links {anchor: this prefix}), a button back to the week page and a trail Week n / label. Previous and next arrows. One Contents card. label, kicker, anchor, count, prompts, numbered, boxes, week_anchor",
        params={'label': 'str (Journal)', 'kicker': 'str', 'anchor': "str prefix, default 'jr'", 'count': 'int (52)', 'prompts': 'list of str', 'numbered': '[label, n] or null',
                'boxes': 'list of str: lined boxes', 'week_anchor': 'str: log_week prefix', 'overview_anchor': 'str: adds a journal index page (every prompt, one tap each); Contents card and top-bar item open it', 'overview_title': 'str'})
def m_prompt_week(P, sec):
    th = P.th; pre = sec.get('anchor', 'jr'); N = int(sec.get('count', 52))
    label = sec.get('label', 'Journal'); kicker = sec.get('kicker', 'Reflect')
    prompts = sec.get('prompts') or ['What do I want more of this week?']
    num = sec.get('numbered'); boxes = sec.get('boxes') or []
    wk = sec.get('week_anchor')
    jid = lambda n: f'{pre}{n:02d}'
    ov = sec.get('overview_anchor')
    _register(P, sec, label, ov or jid(1), kicker)
    portrait = P.HT > P.W
    if ov:  # journal index: every week's prompt with a button to its page (the top-bar item opens this, not week 1)
        half = math.ceil(N / 2)
        row = lambda n: (f'<a href="#{jid(n)}" style="display:flex;align-items:center;gap:10px;border-bottom:1px solid {th["line"]};flex:1;min-height:0">'
                         f'<span style="flex:none;min-width:{64 * P.scale:.0f}px;text-align:center;padding:2px 8px;border-radius:{P.rpill}px;background:{th["soft"]};font:700 {P.fs(11)} \'{th["body"]}\'">Week {n}</span>'
                         f'<span style="font-size:{P.fs(11.5)};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{esc(prompts[(n - 1) % len(prompts)])}</span></a>')
        cols = ''.join(f'<div class="box" style="flex:1;gap:0">{"".join(row(n) for n in range(lo, min(lo + half, N + 1)))}</div>' for lo in (1, half + 1))
        P.page(ov, P.head(kicker, sec.get('overview_title', f'{N} prompts'), right=f'<span style="font-size:{P.fs(12)};color:{th["muted"]}">Tap a week to open its page</span>') +
               f'<div class="row" style="flex:1">{cols}</div>', active=ov)
    numbered = ''
    if num:
        rows = ''.join(f'<div style="display:flex;align-items:flex-end;gap:10px;border-bottom:1px solid {th["line"]};flex:1;min-height:{30 * P.scale:.0f}px;padding-bottom:4px"><span style="font:700 {P.fs(13)} \'{th["body"]}\';color:{th["muted"]};width:16px">{k}</span></div>' for k in range(1, int(num[1]) + 1))
        numbered = f'<div class="box" style="flex:1"><span class="k">{esc(num[0])}</span><div style="flex:1;display:flex;flex-direction:column">{rows}</div></div>'
    side = numbered + ''.join(lines_box(P, b) for b in boxes)
    for n in range(1, N + 1):
        q = prompts[(n - 1) % len(prompts)]
        card = (f'<div class="box fill" style="flex:none;padding:18px 20px;gap:8px"><span class="k">This week\'s prompt</span>'
                f'<p class="h" style="font-size:{26 * P.scale:.0f}px;line-height:1.25">{esc(q)}</p></div>')
        main = f'<div class="col" style="flex:1.5">{card}{lines_box(P, "My answer")}</div>'
        body = f'<div class="row" style="flex:1">{main}<div class="col" style="flex:1">{side}</div></div>' if not portrait else f'{card}{lines_box(P, "My answer")}<div class="row" style="flex:.7">{side}</div>'
        back = _chip(P, f'Week {n}', f'{wk}{n:02d}', primary=True, back=True) if wk else ''
        right = f'<div style="display:flex;gap:12px;align-items:center">{back}{_arrows(jid(n - 1) if n > 1 else None, jid(n + 1) if n < N else None)}</div>'
        P.page(jid(n), P.head(f'{kicker} · week {n}', label, right=right) + body, active=ov or jid(1),
               crumb=(f'<a href="#{wk}{n:02d}">Week {n}</a> / {esc(label)}' if wk else f'{esc(label)} · week {n}'))


@module('mood_year', "Undated year-in-moods page (anchor, default 'moods'): one square per day for each month (3-letter month heads, impossible days faded), a Year to ____ line for a year that starts mid-way, a color key, how-to-color notes and a lined box that fills the column. One Contents card and one top-bar item. label, kicker, anchor, nav_label, keys [[name, hex]], how, notes_label",
        params={'label': 'str (Year in moods)', 'kicker': 'str', 'anchor': "str, default 'moods'", 'keys': 'list of [name, hex] (5)', 'how': 'str: how to color', 'notes_label': 'str'})
def m_mood_year(P, sec):
    th = P.th; a = sec.get('anchor', 'moods'); label = sec.get('label', 'Year in moods')
    keys = sec.get('keys') or list(zip(['Great', 'Good', 'Okay', 'Low', 'Hard'], [th['accent'], P.tabs[0], th['warm'], P.tabs[-1], th['muted']]))
    _register(P, sec, label, a, sec.get('kicker', 'Track'))
    last = {2: 29, 4: 30, 6: 30, 9: 30, 11: 30}
    cols = f'{26 * P.scale:.0f}px repeat(12,minmax(0,1fr))'
    head = '<span></span>' + ''.join(f'<span style="text-align:center;font:700 {P.fs(11.5)} \'{th["body"]}\';color:{th["ink"]}">{MONTHS[m][:3]}</span>' for m in range(12))
    rows = ''.join(f'<span style="font:600 {P.fs(10)} \'{th["body"]}\';color:{th["muted"]};text-align:right;padding-right:5px;align-self:center">{d}</span>' +
                   ''.join(f'<i style="border:1px solid {th["line"]};border-radius:3px;{"opacity:.2;" if d > last.get(m, 31) else ""}"></i>' for m in range(1, 13)) for d in range(1, 32))
    grid = f'<div style="flex:2.4;display:grid;grid-template-columns:{cols};grid-template-rows:auto repeat(31,1fr);gap:2px 3px">{head}{rows}</div>'
    kk = ''.join(f'<div style="display:flex;gap:10px;align-items:center;font-size:{P.fs(12.5)}"><i style="width:18px;height:18px;border-radius:4px;background:{c};display:block;flex:none"></i>{esc(k)}</div>' for k, c in keys)
    how = sec.get('how', 'Each evening, color today\'s square in the color of your mood. Starting mid-year? Write the year at the top, begin on today\'s square and carry on into January.')
    side = (f'<div class="col" style="flex:1"><div class="box"><span class="k">Color key</span>{kk}</div>'
            f'<div class="box fill"><span class="k">How to color</span><span style="font-size:{P.fs(12)};line-height:1.45">{esc(how)}</span></div>'
            f'{lines_box(P, sec.get("notes_label", "Moments to remember"))}</div>')
    right = f'<div style="display:flex;gap:14px;align-items:flex-end;width:{300 * P.scale:.0f}px">{_wline(P, "Year")}{_wline(P, "to")}</div>'
    P.page(a, P.head(sec.get('kicker', 'Track'), label, right=right) + f'<div class="row" style="flex:1">{grid}{side}</div>', active=a)


def _lining_labels(html):
    """Digits in italic labels set upright: the italic display face has only old-style figures (1 reads as i)."""
    up = lambda t: re.sub(r'(?<!&#)(?<!&#x)(?<![\dA-Fa-f])(\d+)', r'<span style="font-style:normal">\1</span>', t)  # not inside &#x27; entities
    return re.sub(r'(class="k"[^>]*>)([^<]*)', lambda m: m.group(1) + up(m.group(2)), html)


@module('page_trails', "Prints no page. Put it last in sections. Every page gets a trail and arrows: an empty trail becomes 'Contents / page title', a trail with no link gets its first part linked to Contents, and a page with no previous and next arrows gets arrows (in the trail) to the pages before and after it in the file. With theme nums 'lining' and labels 'italic', digits in italic labels are set upright. home, home_label",
        params={'home': "str, default 'index'", 'home_label': "str, default 'Contents'"})
def m_page_trails(P, sec):
    home = sec.get('home', 'index'); hl = sec.get('home_label', 'Contents')
    ids = [a for a, _ in P.page_modules]
    has_home = home in ids
    for i, pg in enumerate(P.pages):
        m = re.search(r'<span class="crumb">(.*?)</span>', pg, re.S)
        if not m:
            continue  # raw pages (cover)
        a, crumb = ids[i], m.group(1)
        t = re.search(r'<p class="h"[^>]*>(.*?)</p>', pg, re.S); title = t.group(1) if t else ''
        if a == home:
            new = esc(hl)
        elif not crumb.strip():
            new = f'<a href="#{home}">{esc(hl)}</a> / {title}' if has_home else title
        elif '<a' not in crumb and has_home:  # plain text trail: 'Months / May' links its first part; 'Workouts · page 1 of 9' gets Contents in front
            first, _, rest = crumb.partition(' / ')
            new = (f'<a href="#{home}">{first}</a> / {rest}') if rest else f'<a href="#{home}">{esc(hl)}</a> / {crumb}'
        else:
            new = crumb
        if not re.search(r'class="?k"? style="?font-size:16px"?>\s*<a', pg):  # no previous / next arrows on this page
            prv = ids[i - 1] if i > 0 else None; nxt = ids[i + 1] if i + 1 < len(ids) else None
            new += ' <span style="margin-left:10px">' + (f'<a href="#{prv}">{arrow("l")}</a>' if prv else '') + (f' <a href="#{nxt}">{arrow("r")}</a>' if nxt else '') + '</span>'
        P.pages[i] = pg[:m.start(1)] + new + pg[m.end(1):]
    if P.th.get('nums') == 'lining' and P.th.get('labels') == 'italic':
        orig = P.html
        P.html = lambda: _lining_labels(orig())  # after Contents and guide panels are filled in


@module('group_weeks', "Prints no page. Put it last in sections, after log_week and the modules its links name (meal_week, workout_log). Moves each week's linked pages right after that week's page (Week 1, its workouts, its meal plan, then Week 2...), so a buyer who swipes meets one week at a time and can print a week as one page range. Links and anchors do not change.",
        params={})
def m_group_weeks(P, sec):
    lw = next((x for x in P.s.get('sections', []) if x.get('module') == 'log_week'), None)
    if not lw:
        return
    pre = lw.get('anchor', 'w'); N = int(lw.get('count', 52))
    seq = []
    for n in range(1, N + 1):
        seq += [f'{pre}{n:02d}'] + [a for _, a in _linked(n, lw.get('links') or [])]
    pos = {a: i for i, (a, _) in enumerate(P.page_modules)}
    seq = [a for a in seq if a in pos]
    if not seq:
        return
    moved = set(seq); first = min(pos[a] for a in seq)
    order = [i for i in range(len(P.pages)) if i < first and P.page_modules[i][0] not in moved] + [pos[a] for a in seq] + \
            [i for i in range(first, len(P.pages)) if P.page_modules[i][0] not in moved]
    P.pages = [P.pages[i] for i in order]
    P.page_modules = [P.page_modules[i] for i in order]


# ---------- print format (home-printed planners: true Letter and A4, safe margins, two-page spreads) ----------
PAPER = {'letter': ('8.5in', '11in', 816.0, 1056.0, 'Letter'), 'a4': ('210mm', '297mm', 793.7, 1122.5, 'A4')}
FULL_DOW = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def _pf_css(P):
    th = P.th; w, h = PAPER[P.paper][:2]
    m = 96 * float(P.pf.get('margin_in', .5)); b = m + 96 * float(P.pf.get('binding_in', .375))
    ln, mu, ink = th['line'], th['muted'], th['ink']
    out = (f"@page{{size:{w} {h};margin:0}}.pg{{width:{w};height:{h}}}"
           f".pfh{{position:absolute;top:{m:.0f}px;height:16px;display:flex;align-items:center;gap:5px;font:400 {P.fs(10)} '{th['body']}';color:{mu};white-space:nowrap}}"
           f".pfh a{{color:inherit}}.pfh b{{font-weight:600;color:{ink}}}"
           f".body{{top:{m + 26:.0f}px;bottom:{m + 24:.0f}px}}"
           f".pno,.foot{{position:absolute;bottom:{m:.0f}px;font:500 10px '{th['body']}';color:{mu};line-height:1;letter-spacing:0}}")
    for side, L, R in (('odd', b, m), ('even', m, b)):
        out += f".pg[data-side={side}] .body,.pg[data-side={side}] .pfh{{left:{L:.0f}px;right:{R:.0f}px}}"
    out += (f".pg[data-side=odd] .pfh{{justify-content:flex-end}}.pg[data-side=odd] .pno{{right:{m:.0f}px}}.pg[data-side=odd] .foot{{left:{b:.0f}px}}"
            f".pg[data-side=even] .pno{{left:{m:.0f}px}}.pg[data-side=even] .foot{{right:{b:.0f}px;left:auto}}"
            f".pg[data-mk] .pfh{{padding:0 34px}}.pg[data-mk][data-side=odd] .pno{{right:{m + 34:.0f}px}}.pg[data-mk][data-side=even] .pno{{left:{m + 34:.0f}px}}"
            f".pg[data-mk][data-side=odd] .foot{{left:{b + 34:.0f}px}}.pg[data-mk][data-side=even] .foot{{right:{b + 34:.0f}px}}"
            # month grid
            f".pfgh,.pfg{{display:grid;grid-template-columns:{40 * P.scale:.0f}px repeat(7,1fr)}}"
            f".pfgh span{{font:700 {P.fs(10.5)} '{th['body']}';color:{mu};padding:0 6px 5px}}"
            f".pfg{{flex:1;min-height:0;border-right:1px solid {ln};border-bottom:1px solid {ln}}}"
            f".pfg>*{{border-top:1px solid {ln};border-left:1px solid {ln};padding:5px 7px;font:600 {P.fs(12.5)} '{th['body']}';color:{th['accent']};display:block}}"
            f".pfg .x{{color:{mix(mu, th['paper'], .5)};font-weight:500}}"
            f".pfg .wk{{background:{th['soft']};color:{mu};font:600 {P.fs(10)} '{th['body']}';padding:6px 0;text-align:center;line-height:1.25}}"
            # week spreads
            f".pfday{{flex:1 1 0;min-width:0;gap:4px}}.pfdh{{display:flex;justify-content:space-between;align-items:baseline;gap:6px;padding-bottom:2px}}"
            f".pfdh .k{{font-size:{P.fs(15)}}}.pfnum{{font:600 26px '{th['display']}',serif;color:{th['accent']};line-height:1;font-variant-numeric:lining-nums}}.h{{font-variant-numeric:lining-nums}}"
            f".pfnum small{{font:500 {P.fs(10)} '{th['body']}';color:{mu};margin-right:5px}}"
            f".pfblank{{display:inline-block;width:46px;border-bottom:1.3px solid {ln};height:20px}}"
            f".pflink{{display:inline-flex;align-items:center;gap:5px;font:600 {P.fs(11)} '{th['body']}';color:{mu};white-space:nowrap}}"
            f".pfmark{{position:absolute;width:24px;height:24px;border:0 solid {ink}}}")
    if P.pf.get('vector_rules'):
        out += '.lines,.dots{background:none!important;position:relative;overflow:hidden}.lines>svg,.dots>svg{position:absolute;left:0;top:0}'
    return out


def _pf_page(P, anchor, inner, crumb='', raw=False, style='', marks=False, over=''):
    """One printed page: safe margins on every edge, the binding margin on the inner edge (mirrored when duplex),
    the trail as small text in the header row, page number at the outer bottom corner, brand at the inner one."""
    n = len(P.pages) + 1
    side = 'odd' if (n % 2 == 1 or not P.pf.get('duplex', True)) else 'even'
    if not crumb and not raw and len(P.pf_groups) == 1:
        crumb = f'%%PFTRAIL:{anchor}%%'  # front pages: a trail linking every front page
    pno = f'<p class="pno">{n}</p>' if (P.pf.get('page_numbers') and not raw) else ''
    mk = ' data-mk="1"' if marks else ''
    if raw:
        body = inner
    else:
        body = over + (f'<div class="pfh">{crumb}</div>' if crumb else '') + f'<div class="body">{inner}</div>{pno}<p class="foot">{esc(P.s.get("brand", ""))}</p>'
    P.pages.append(f'<section class="pg" id="{anchor}" data-side="{side}"{mk} style="{style}">{body}</section>')
    P.page_modules.append((anchor, P.current))


def _pf_group(P, label, sub=''):
    """A Print map row starts at the next page. Every row must be whole sheets (starts on a sheet front)."""
    P.pf_groups.append([label, sub, len(P.pages) + 1])


def _pf_hs(P):
    return next((x for x in P.s.get('sections', []) if x.get('module') == 'head_start'), None)


def _pf_lead_from(P):
    hs = _pf_hs(P)
    if not hs:
        return None
    y0, m0 = map(int, hs['from'].split('-')); first = datetime.date(y0, m0, 1)
    return first - datetime.timedelta(days=first.weekday())


def _pf_week_anchor(P, d):
    """Left page of the week holding d (no day pages in a printed planner), or None outside the dated range."""
    if P.undated:
        return None
    w1 = P.week_start(1); last = P.week_start(P.nweeks()) + datetime.timedelta(days=6)
    if w1 <= d <= last:
        return f'w{P.week_of(d):02d}'
    lf = _pf_lead_from(P)
    if lf and lf <= d < w1:
        return f'{_pf_hs(P).get("anchor", "hs")}w{(d - lf).days // 7 + 1:02d}'
    return None


def _pf_in_range(P, d):
    return _pf_week_anchor(P, d) is not None


def _pf_grid(P, yy, mm, hs=False):
    """Monday-start month grid filling its space; a week column opens each week, every date opens its week."""
    cal = calendar.Calendar(0).monthdatescalendar(yy, mm)
    head = f'<div class="pfgh"><span style="padding:0;text-align:center">{"From" if (hs and not P.iso) else "Week"}</span>' + ''.join(f'<span>{x}</span>' for x in DOW) + '</div>'
    cells = ''
    for wk in cal:
        wa = _pf_week_anchor(P, wk[0]) or _pf_week_anchor(P, wk[6])
        lab = str(wk[0].isocalendar()[1]) if P.iso else f'{MONTHS[wk[0].month - 1][:3]}<br>{wk[0].day}' if hs else (str(P.week_of(wk[0])) if wa and wa.startswith('w') else '')
        cells += f'<a class="wk" href="#{wa}">{lab}</a>' if wa else '<span class="wk"></span>'
        for d in wk:
            a = _pf_week_anchor(P, d)
            cls = '' if d.month == mm else ' x'
            cells += f'<a class="d{cls}" href="#{a}">{d.day}</a>' if a else f'<span class="d{cls}">{d.day}</span>'
    return head + f'<div class="pfg" style="grid-template-rows:repeat({len(cal)},1fr)">{cells}</div>'


def _pf_link(href, text, d='r'):
    a = arrow(d, 12)
    return f'<a class="pflink" href="#{href}">{a + " " if d == "l" else ""}{esc(text)}{" " + a if d == "r" else ""}</a>'


def _pf_month(P, yy, mm, anchor, kicker, trail, prev_l, next_l, hs=False):
    """Month opener (a sheet front, right-hand page) and month review (the last page of the month's sheets, left-hand,
    facing the next month's opener). Weeks print between them as two-page spreads, so each month is whole sheets."""
    ms = P.pf.get('month_spread') or {}
    page_blocks = ms.get('page') or [{'kind': 'checklist', 'label': 'Goals this month', 'rows': 3, 'fill': True}]
    review_blocks = ms.get('review') or [{'kind': 'lines', 'label': 'Notes'}]
    nav = '<div class="pfnav" style="display:flex;gap:14px;align-items:center">' + (_pf_link(*prev_l, d='l') if prev_l else '') + _pf_link(anchor + 'b', 'Month review') + (_pf_link(*next_l) if next_l else '') + '</div>'
    inner = P.head(kicker, MONTHS[mm - 1], size=52, right=nav) + f'<div class="col" style="flex:1;gap:0">{_pf_grid(P, yy, mm, hs)}</div>' + ''.join(block(P, b) for b in page_blocks)
    _pf_page(P, anchor, inner, crumb=trail)
    return review_blocks


def _pf_review(P, yy, mm, anchor, trail, blocks, next_l):
    right = '<div class="pfnav" style="display:flex;gap:14px;align-items:center">' + _pf_link(anchor[:-1], f'{MONTHS[mm - 1]} page', d='l') + (_pf_link(*next_l) if next_l else '') + '</div>'
    inner = P.head(f'{MONTHS[mm - 1]} {yy}', 'Month review', size=44, right=right) + ''.join(block(P, b) for b in blocks)
    _pf_page(P, anchor, inner, crumb=trail)


def _pf_daycol(P, i, d, style=''):
    rows = int((P.pf.get('week_spread') or {}).get('day_rows', 3))
    if d is None:
        num = '<span class="pfblank"></span>'
    else:
        mon = f'<small>{MONTHS[d.month - 1][:3]}</small>' if d.day == 1 else ''
        num = f'<span class="pfnum">{mon}{d.day}</span>'
    fade = ';opacity:.4' if (d is not None and not _pf_in_range(P, d)) else ''
    return f'<div class="box pfday" style="{style}{fade}"><div class="pfdh"><span class="k">{FULL_DOW[i]}</span>{num}</div>{_chk(rows)}<div class="lines"></div></div>'


def _pf_week(P, a, days, kicker, title, trail, prev_a=None, next_a=None, spare=False):
    """Two-page week spread: left page (even, sheet back) Mon to Wed under the left_top blocks; right page (odd, next
    sheet front) Thu, Fri and Sat over Sun, with the right_bottom blocks underneath."""
    ws = P.pf.get('week_spread') or {}
    days = days or [None] * 7
    P.pf_spreads.append(a)
    if days[0] is not None:
        P.pf_wdates.append((len(P.pages) + 1, days[0], days[6]))  # Print map: the weeks each row holds
    rng = '' if spare else f'{MONTHS[days[0].month - 1][:3]} {days[0].day} to {MONTHS[days[6].month - 1][:3]} {days[6].day}'
    lnav = '<div class="pfnav" style="display:flex;gap:14px;align-items:center">' + (_pf_link(prev_a, 'Notes' if spare else 'Previous week', d='l') if prev_a else '') + _pf_link(a + 'b', 'Thursday to Sunday') + '</div>'
    head = P.head(kicker, title, size=40, right=lnav)
    if spare:
        head = head.replace(f'>{esc(title)}</p>', f'>{esc(title)} <span style="display:inline-block;width:230px;border-bottom:1.3px solid {P.th["line"]};height:30px;vertical-align:baseline"></span></p>', 1)
    left = head + ''.join(block(P, b) for b in ws.get('left_top', [])) + '<div class="row" style="flex:1">' + ''.join(_pf_daycol(P, i, days[i]) for i in range(3)) + '</div>'
    _pf_page(P, a, left, crumb=trail)
    rnav = '<div class="pfnav" style="display:flex;gap:14px;align-items:center">' + _pf_link(a, 'Monday to Wednesday', d='l') + (_pf_link(next_a, 'Notes' if spare else 'Next week') if next_a else '') + '</div>'
    rk = kicker if spare else f'{kicker} · {rng}'
    right = (P.head(rk, 'Thursday to Sunday', size=40, right=rnav) +
             '<div class="row" style="flex:1">' + _pf_daycol(P, 3, days[3]) + _pf_daycol(P, 4, days[4]) +
             f'<div class="col" style="flex:1 1 0;min-width:0">{_pf_daycol(P, 5, days[5])}{_pf_daycol(P, 6, days[6])}</div></div>' +
             ''.join(block(P, b) for b in ws.get('right_bottom', [])))
    _pf_page(P, a + 'b', right, crumb=trail)


def _habits(P, b):
    """Weekly habit strip: a write-in name and seven circles (SVG, r004) per row, day initials on top."""
    th = P.th; rh = round(26 * P.scale)
    letters = '<span></span>' + ''.join(f'<span style="text-align:center;font:700 {P.fs(10.5)} \'{th["body"]}\';color:{th["muted"]}">{x}</span>' for x in 'MTWTFSS')
    circ = f'<svg width="17" height="17" viewBox="0 0 17 17"><circle cx="8.5" cy="8.5" r="7" fill="none" stroke="{th["muted"]}" stroke-width="1.2"/></svg>'
    cell = f'<span style="display:flex;align-items:center;justify-content:center;height:{rh}px;border-bottom:1px solid {th["line"]}">{circ}</span>'
    rows = ''.join(f'<span style="height:{rh}px;border-bottom:1px solid {th["line"]};margin-right:8px"></span>' + cell * 7 for _ in range(int(b.get('rows', 5))))
    return f'<div class="box" style="flex:1"><span class="k">{esc(b.get("label", "Habits"))}</span><div style="display:grid;grid-template-columns:4.7fr repeat(7,1fr);align-items:end">{letters}{rows}</div></div>'


@module('print_format', "Format switch for home-printed planners: prints no page. Put it first. One PDF per paper size (sizes: letter 8.5 x 11 in, a4 210 x 297 mm, portrait, same page order and count), nothing within margin_in of any edge, binding_in extra on the binding edge (mirrored with duplex: odd pages bind left, even pages bind right), white paper only, no top bar or month rail (hide_nav; the trail stays as small text with its links), printed page numbers (page_numbers), vector writing lines (vector_rules). No day pages: dates open their week. Each month prints as whole sheets: a month page (sheet front: grid with a week column, then month_spread.page blocks) and a month review page (month_spread.review blocks, the left page facing the next month), with every week between them as a two-page spread (week_spread: left_top blocks over Mon to Wed; Thu, Fri and Sat over Sun with right_bottom blocks under). The build fails when a spread starts on a sheet front or a Print map row is not whole sheets.",
        params={'sizes': "list of 'letter' | 'a4'", 'margin_in': 'number (0.5)', 'binding_in': 'number (0.375)', 'duplex': 'bool', 'hide_nav': 'bool', 'page_numbers': 'bool', 'vector_rules': 'bool',
                'month_spread': 'dict {page: [blocks under the month grid], review: [blocks on the month review page]}',
                'week_spread': "dict {left_top: [blocks], day_rows: int, weekend: 'stacked', right_bottom: [blocks]}"})
def m_print_format(P, sec):
    _pf_group(P, 'Front pages')  # read by Planner.__init__ (P.pf); here it only opens the first Print map row


def _pf_head_start(P, sec):
    pre = sec.get('anchor', 'hs')
    y0, m0 = map(int, sec['from'].split('-')); y1, m1 = map(int, sec['to'].split('-'))
    months = []; y, m = y0, m0
    while (y, m) <= (y1, m1):
        months.append((y, m)); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    lead = _pf_lead_from(P); w1 = P.week_start(1)
    weeks = []; d = lead
    while d < w1:
        weeks.append([d + datetime.timedelta(days=i) for i in range(7)]); d += datetime.timedelta(days=7)
    first = datetime.date(y0, m0, 1)
    home = lambda w: (w[3].year, w[3].month) if (w[3].year, w[3].month) in months else (months[0] if w[3] < first else months[-1])
    _register(P, sec, sec.get('label', 'Head start'), f'{pre}{m0:02d}', sec.get('kicker', 'Start now'), nav=False)
    P.head_start_links = [(f'{MONTHS[m2 - 1]} {y2}', f'{pre}{m2:02d}') for y2, m2 in months]
    N = len(weeks)
    for k, (yy, mm) in enumerate(months):
        _pf_group(P, f'{MONTHS[mm - 1]} {yy}', 'Head start')
        ma = f'{pre}{mm:02d}'
        trail = f'<a href="#printmap">Print map</a> / Head start / {MONTHS[mm - 1]} {yy}'
        prev_l = (f'{pre}{months[k - 1][1]:02d}', MONTHS[months[k - 1][1] - 1]) if k > 0 else None
        nxt = (f'{pre}{months[k + 1][1]:02d}', MONTHS[months[k + 1][1] - 1]) if k + 1 < len(months) else ('m01', f'January {P.year}')
        rev = _pf_month(P, yy, mm, ma, f'Head start · {yy}', trail, prev_l, nxt, hs=True)
        for i, w in enumerate(weeks):
            if home(w) != (yy, mm):
                continue
            wt = f'<a href="#printmap">Print map</a> / <a href="#{ma}">{MONTHS[mm - 1]} {yy}</a> / Head start week {i + 1} of {N}'
            rng = f'{MONTHS[w[0].month - 1][:3]} {w[0].day} to {MONTHS[w[6].month - 1][:3]} {w[6].day}'
            _pf_week(P, f'{pre}w{i + 1:02d}', w, f'Head start, week {i + 1} of {N}' + (f' · Week {w[0].isocalendar()[1]}' if P.iso else ''), rng, wt,
                     prev_a=f'{pre}w{i:02d}' if i > 0 else None, next_a=f'{pre}w{i + 2:02d}' if i + 1 < N else 'w01')
        _pf_review(P, yy, mm, ma + 'b', trail, rev, nxt)


def _pf_calendar(P, sec):
    ny = P.nweeks()
    owner = {}
    for n in range(1, ny + 1):
        thu = P.week_start(n) + datetime.timedelta(days=3)
        owner[n] = thu.month if thu.year == P.year else (1 if thu.year < P.year else 12)  # r008: built under the month holding its Thursday
    hs = _pf_hs(P)
    last_hs = None
    if hs:
        lf = _pf_lead_from(P); last_hs = f'{hs.get("anchor", "hs")}w{(P.week_start(1) - lf).days // 7:02d}'
    spare = next((x for x in P.s.get('sections', []) if x.get('module') == 'spare_week'), None)
    for m in range(1, 13):
        _pf_group(P, f'{MONTHS[m - 1]} {P.year}')
        ma = f'm{m:02d}'
        trail = f'<a href="#printmap">Print map</a> / <a href="#year">{P.year}</a> / {MONTHS[m - 1]}'
        if m > 1:
            prev_l = (f'm{m - 1:02d}', MONTHS[m - 2])
        elif hs:
            prev_l = (f'{hs.get("anchor", "hs")}{int(hs["to"].split("-")[1]):02d}', MONTHS[int(hs['to'].split('-')[1]) - 1])
        else:
            prev_l = None
        nxt = (f'm{m + 1:02d}', MONTHS[m]) if m < 12 else ((spare.get('anchor', 'spare') + 'n1', 'Spare week') if spare else None)
        rev = _pf_month(P, P.year, m, ma, str(P.year), trail, prev_l, nxt)
        for n in [n for n in range(1, ny + 1) if owner[n] == m]:
            days = [P.week_start(n) + datetime.timedelta(days=i) for i in range(7)]
            wt = f'<a href="#printmap">Print map</a> / <a href="#year">{P.year}</a> / <a href="#{ma}">{MONTHS[m - 1]}</a> / Week {n}'
            rng = f'{MONTHS[days[0].month - 1][:3]} {days[0].day} to {MONTHS[days[6].month - 1][:3]} {days[6].day}'
            _pf_week(P, f'w{n:02d}', days, f'Week {n} · {P.year}', rng, wt,
                     prev_a=f'w{n - 1:02d}' if n > 1 else last_hs, next_a=f'w{n + 1:02d}' if n < ny else None)
        _pf_review(P, P.year, m, ma + 'b', trail, rev, nxt)


@module('print_check', "One-sheet print test (needs print_format): front (anchor, a sheet front) with true-size inch and centimetre rulers, four corner marks at the 0.5 in safe area, binding-edge hole guides (Letter 3 holes 4.25 in apart, A4 2 holes 80 mm apart), a line, dot and tone sample and a pen test box; back (anchor + 'b') with the alignment check, the fixes checklist, a Settings that work table, a box to write your own printer settings, and links to Start here and the Print map. label, anchor, fixes (up to 6)",
        params={'label': 'str (Print check)', 'anchor': "str, default 'printcheck'", 'fixes': 'list of up to 6 str'})
def m_print_check(P, sec):
    th = P.th; a = sec.get('anchor', 'printcheck'); label = sec.get('label', 'Print check')
    _register(P, sec, label, a, 'Before you print', nav=False)
    m = 96 * float(P.pf.get('margin_in', .5)); b = 96 * float(P.pf.get('binding_in', .375))
    ink = th['ink']

    def marks():
        return ''.join(f'<i class="pfmark" style="{v}:{m:.0f}px;{hz}:{m:.0f}px;border-{v}-width:1.6px;border-{hz}-width:1.6px"></i>'
                       for v in ('top', 'bottom') for hz in ('left', 'right'))
    # rulers at true physical size: CSS in and mm units print at real size when Scale is Actual size
    ticks = ''.join(f'<line x1="{12.5 + i * 12.5}" y1="0" x2="{12.5 + i * 12.5}" y2="{30 if i % 8 == 0 else 21 if i % 4 == 0 else 15 if i % 2 == 0 else 9}" stroke="{ink}" stroke-width="{1.4 if i % 8 == 0 else .9}"/>' for i in range(49))
    nums = ''.join(f'<text x="{12.5 + i * 100}" y="48" text-anchor="middle" font-family="{th["body"]}" font-size="15" font-weight="600" fill="{ink}">{i}</text>' for i in range(7))
    inch = f'<svg style="width:6.25in;height:.55in;display:block" viewBox="0 0 625 55"><line x1="12.5" y1=".5" x2="612.5" y2=".5" stroke="{ink}" stroke-width="1.2"/>{ticks}{nums}</svg>'
    cticks = ''.join(f'<line x1="{5 + i}" y1="0" x2="{5 + i}" y2="{7 if i % 10 == 0 else 5 if i % 5 == 0 else 3}" stroke="{ink}" stroke-width="{.32 if i % 10 == 0 else .2}"/>' for i in range(151))
    cnums = ''.join(f'<text x="{5 + i * 10}" y="12.2" text-anchor="middle" font-family="{th["body"]}" font-size="3.6" font-weight="600" fill="{ink}">{i}</text>' for i in range(16))
    cm = f'<svg style="width:160mm;height:14mm;display:block" viewBox="0 0 160 14"><line x1="5" y1=".15" x2="155" y2=".15" stroke="{ink}" stroke-width=".3"/>{cticks}{cnums}</svg>'
    holes_at = ['1.25in', '5.5in', '9.75in'] if P.paper == 'letter' else ['108.5mm', '188.5mm']
    holes = ''.join(f'<i style="position:absolute;left:{m + b / 2 - 11:.1f}px;top:calc({t} - 11px);width:22px;height:22px;border-radius:50%;border:1.4px dashed {th["muted"]}"></i>' for t in holes_at)
    strip = (holes + f'<div style="position:absolute;left:{m:.0f}px;width:{b:.0f}px;top:calc({holes_at[0]} + 26px);height:2.6in;display:flex;align-items:center;justify-content:center">'
             f'<span style="writing-mode:vertical-rl;transform:rotate(180deg);font:600 {P.fs(10)} \'{th["body"]}\';color:{th["muted"]};white-space:nowrap">Binding edge: punch here</span></div>')
    rulers = (f'<div class="box" style="gap:10px"><span class="k">Scale check: true-size rulers</span>{inch}{cm}'
              f'<span style="font-size:{P.fs(12.5)};line-height:1.45">Hold a real ruler to the 5 inch and 12 cm marks. If they match, the scale is right.</span></div>')
    corners = (f'<div class="box fill" style="flex-direction:row;align-items:center;gap:14px"><svg width="34" height="34" viewBox="0 0 34 34" style="flex:none"><path d="M2,32 V2 H32" fill="none" stroke="{ink}" stroke-width="2"/></svg>'
               f'<span style="font-size:{P.fs(12.5)};line-height:1.45"><b>Corner marks.</b> All four corners showing means nothing is cut off. They sit half an inch from each edge of the paper.</span></div>')
    tone = (f'<div class="box"><span class="k">Lines should be light but clear</span><div class="row" style="gap:14px">'
            f'<div style="flex:1;display:flex;flex-direction:column;gap:4px"><span style="font-size:{P.fs(11)};color:{th["muted"]}">Writing lines</span><div class="lines" style="flex:none;height:{3 * P.rule_period()}px"></div></div>'
            f'<div style="flex:1;display:flex;flex-direction:column;gap:4px"><span style="font-size:{P.fs(11)};color:{th["muted"]}">Dot grid</span><div class="dots" style="flex:none;height:{3 * P.rule_period()}px"></div></div>'
            f'<div style="flex:1;display:flex;flex-direction:column;gap:4px"><span style="font-size:{P.fs(11)};color:{th["muted"]}">Filled box</span><div style="height:{3 * P.rule_period()}px;background:{th["soft"]};border-radius:{P.rbox}px"></div></div></div></div>')
    pen = f'<div class="box" style="flex:1"><span class="k">Pen test: write here to check your pen does not bleed</span><div class="lines"></div></div>'
    turn = '<span class="pfnav">' + _pf_link(a + 'b', 'Turn over') + '</span>'
    _pf_page(P, a, P.head('Front of the sheet', label, right=turn) + rulers + corners + tone + pen, marks=True, over=marks() + strip)
    fixes = sec.get('fixes') or []
    settings = [('Paper size', 'Same as the file: Letter or A4'), ('Scale', 'Actual size or 100%'), ('Double-sided', 'Flip on long edge'), ('Color', 'Color or grayscale, both work')]
    rows = ''.join(f'<div style="display:grid;grid-template-columns:1fr 2fr;border-bottom:1px solid {th["line"]};padding:7px 0;font-size:{P.fs(12.5)}"><b style="font-weight:600">{esc(k)}</b><span>{esc(v)}</span></div>' for k, v in settings)
    back = (P.head('Back of the sheet', label, right='<div class="pfnav" style="display:flex;gap:14px">' + _pf_link('start', 'Start here', d='l') + _pf_link('printmap', 'Print map') + '</div>') +
            f'<div class="box fill"><span class="k">Same way up?</span><span style="font-size:{P.fs(12.5)};line-height:1.45">This side should read the same way up as the front. Hold the sheet to the light: the corner marks should sit on top of the front ones.</span></div>'
            f'<div class="box"><span class="k">Something looks wrong?</span>{_chk(len(fixes), fixes)}</div>'
            f'<div class="box" style="gap:0"><span class="k" style="padding-bottom:4px">Settings that work</span>{rows}</div>'
            f'<div class="box" style="flex:1"><span class="k">Your printer and the settings that worked</span><div class="lines"></div></div>')
    _pf_page(P, a + 'b', back, marks=True, over=marks())


@module('print_map', "Print map page (needs print_format): one row per run of whole sheets in file order (front pages, each head-start month, each month, spare week) with its page range, sheet count and a Printed tick box, filled at the end of the build; under it 'Starting before <year>' and 'Starting later in <year>' boxes. label, kicker, anchor",
        params={'label': 'str (Print map)', 'kicker': 'str', 'anchor': "str, default 'printmap'"})
def m_print_map(P, sec):
    a = sec.get('anchor', 'printmap')
    _register(P, sec, sec.get('label', 'Print map'), a, sec.get('kicker', 'Pages by month'), nav=False)
    P.pf_map = (a, sec)
    _pf_page(P, a, '%%PRINTMAP%%')


def _pf_fill(P):
    """End of build: the Print map table, the front-page trail and printed page numbers; parity problems."""
    th = P.th; total = len(P.pages)
    idx = {a: i + 1 for i, (a, _) in enumerate(P.page_modules)}
    groups = []
    for i, (label, sub, start) in enumerate(P.pf_groups):
        end = P.pf_groups[i + 1][2] - 1 if i + 1 < len(P.pf_groups) else total
        if end >= start:
            groups.append((label, sub, start, end, P.page_modules[start - 1][0]))
    names = {a: l for (l, a, k) in P.index_items}
    front = [a for a, _ in P.page_modules[:groups[0][3]]] if groups else []
    seen = {}; trail_items = []
    for a in front:
        if a in names:
            seen[names[a]] = seen.get(names[a], 0) + 1
            trail_items.append((a, names[a] if seen[names[a]] == 1 else f'{names[a]}, page {seen[names[a]]}'))
    lastfront = groups[0][3] if groups else 0
    if groups and not groups[0][1]:
        groups[0] = (groups[0][0], ', '.join(['Cover'] + list(dict.fromkeys(names[a] for a in front if a in names))), *groups[0][2:])
    box = f'<i style="width:15px;height:15px;border:1.4px solid {th["muted"]};border-radius:3px;display:block;margin:auto"></i>'
    cols = f'2.1fr 1.55fr .95fr .6fr {60 * P.scale:.0f}px'
    hdr = ''.join(f'<span class="k" style="padding:4px 6px{";text-align:center" if j == 4 else ""}">{h}</span>' for j, h in enumerate(['What', 'Weeks', 'Pages', 'Sheets', 'Printed']))
    sub = lambda s: f'<span style="font-size:{P.fs(10)};color:{th["muted"]}">{esc(s)}</span>' if s else ''
    md = lambda d: f'{MONTHS[d.month - 1][:3]} {d.day}'

    def weeks(s0, s1):  # the weeks a row holds (a week is filed under the month holding its Thursday, r008)
        ws = [(m0, s_) for pg_, m0, s_ in P.pf_wdates if s0 <= pg_ <= s1]
        return f'{md(ws[0][0])} to {md(ws[-1][1])}' if ws else ('Undated' if s0 > 1 else '')
    cell = lambda t: f'<span style="padding:0 6px;font-size:{P.fs(12)}">{t}</span>'
    rows = ''.join(f'<div style="display:grid;grid-template-columns:{cols};align-items:center;border-bottom:1px solid {th["line"]};flex:1 0 auto;padding:2px 0">'
                   f'<a href="#{a}" style="padding:0 6px;display:flex;flex-wrap:wrap;align-items:baseline;gap:0 10px"><b style="font:600 {P.fs(12.5)} \'{th["body"]}\'">{esc(l)}</b>{sub(s)}</a>'
                   f'{cell(weeks(s0, s1))}{cell(f"{s0} to {s1}")}{cell(math.ceil((s1 - s0 + 1) / 2))}{box}</div>'
                   for l, s, s0, s1, a in groups)
    rows += (f'<div style="display:grid;grid-template-columns:{cols};align-items:center;border-top:1.5px solid {th["ink"]};padding:8px 0">'
             f'<b style="padding:0 6px;font:600 {P.fs(12.5)} \'{th["body"]}\'">Whole planner</b><span></span>{cell(f"1 to {total}")}{cell(math.ceil(total / 2))}<span></span></div>')
    yr = P.year
    pc = next((idx[x] for x, mod in P.page_modules if mod == 'print_check'), None)
    front_pages = f'1 to {pc - 1} and {pc + 2} to {lastfront}' if (pc and 1 < pc and pc + 2 <= lastfront) else f'1 to {lastfront}'
    lf = _pf_lead_from(P)
    first = (f'Print pages {front_pages}' + (f' (you already have the check sheet, pages {pc} to {pc + 1})' if pc else '') +
             '. Then find today in the Weeks column, print that row and start with this week.' +
             (f' The first week begins Monday, {MONTHS[lf.month - 1]} {lf.day}, {lf.year}.' if lf else ''))
    later = 'Print each next row before its first week begins: the Weeks column shows the date. Missed a week? Skip it and start with this one.'
    a, sec = P.pf_map
    intro = (f'<div class="box fill"><span class="k">How to print</span><span style="font-size:{P.fs(12.5)};line-height:1.45">Each row is whole sheets. Print one row at a time, double-sided (flip on long edge), at Actual size, '
             f'and it drops into your binder in order with every week open as a two-page spread. Page numbers are printed at the bottom corner of every page after the cover and match in the Letter and A4 files.</span></div>')
    table = f'<div class="box" style="flex:1;gap:0"><div style="display:grid;grid-template-columns:{cols};border-bottom:1.5px solid {th["ink"]}">{hdr}</div><div style="flex:1;display:flex;flex-direction:column">{rows}</div></div>'
    starts = (f'<div class="row"><div class="box fill" style="flex:1"><span class="k">Your first print, any date</span><span style="font-size:{P.fs(12)};line-height:1.45">{esc(first)}</span></div>'
              f'<div class="box fill" style="flex:1"><span class="k">After that</span><span style="font-size:{P.fs(12)};line-height:1.45">{esc(later)}</span></div></div>')
    inner = P.head(sec.get('kicker', 'Pages by month'), sec.get('label', 'Print map')) + intro + table + starts
    out = []
    for i, pg in enumerate(P.pages):
        pg = pg.replace('%%PRINTMAP%%', inner)
        if '%%PFTRAIL:' in pg:
            pg = re.sub(r'%%PFTRAIL:([^%]+)%%', lambda mm: ' · '.join(f'<b>{esc(t)}</b>' if x == mm.group(1) else f'<a href="#{x}">{esc(t)}</a>' for x, t in trail_items), pg)
        pg = re.sub(r'%%PG:([^%]+)%%', lambda mm: str(idx.get(mm.group(1), '?')), pg)
        out.append(pg)
    P.pages = out
    probs = []
    if P.pf.get('duplex', True):
        probs += [f'spread {x} starts on page {idx[x]}, a sheet front' for x in P.pf_spreads if idx[x] % 2]
        probs += [f'Print map row {g[0]} starts on page {g[2]}, a sheet back (rows must be whole sheets)' for g in groups if g[2] % 2 == 0]
        if total % 2:
            probs.append(f'{total} pages: the last sheet is half blank')
        pc = next((x for x, mod in P.page_modules if mod == 'print_check'), None)
        if pc and idx[pc] % 2 == 0:
            probs.append(f'print check {pc} is on page {idx[pc]}: front and back are not one sheet')
    P.pf_problems = probs


@module('spare_week', "Undated week spreads for print_format (count of them), each printed as two whole sheets: a Notes page (sheet front), the week spread (Week of ____, a blank date rule per day) and a Notes page (sheet back), so a copy drops into the binder anywhere. Anchors: anchor+'n1', anchor, anchor+'b', anchor+'n2' (then anchor2..). label, kicker, anchor, count",
        params={'label': 'str (Spare week)', 'kicker': 'str', 'anchor': "str, default 'spare'", 'count': 'int (1)'})
def m_spare_week(P, sec):
    th = P.th; a0 = sec.get('anchor', 'spare'); n = int(sec.get('count', 1))
    _register(P, sec, sec.get('label', 'Spare week'), f'{a0}n1', sec.get('kicker', 'Undated'), nav=False)
    for i in range(1, n + 1):
        a = a0 if i == 1 else f'{a0}{i}'
        _pf_group(P, sec.get('label', 'Spare week') + ('' if n == 1 else f' {i}'), 'A notes page, the week spread, a notes page')
        trail = f'<a href="#printmap">Print map</a> / {esc(sec.get("label", "Spare week"))}'
        _pf_page(P, f'{a}n1', P.head('Spare week', 'Notes', right='<span class="pfnav">' + _pf_link(a, 'Spare week') + '</span>') + '<div class="box" style="flex:1"><div class="lines"></div></div>', crumb=trail)
        _pf_week(P, a, None, sec.get('kicker', 'Spare week, print as many as you need'), 'Week of', trail, prev_a=f'{a}n1', next_a=f'{a}n2', spare=True)
        _pf_page(P, f'{a}n2', P.head('Spare week', 'Notes', right='<span class="pfnav">' + _pf_link(a + 'b', 'Spare week', d='l') + '</span>') + '<div class="box" style="flex:1"><div class="lines"></div></div>', crumb=trail)


def _pf_problems(spec, th):
    pf = next((x for x in spec.get('sections', []) if x.get('module') == 'print_format'), None)
    if not pf:
        return []
    out = []
    if str(th.get('paper', '')).upper() != '#FFFFFF':
        out.append(f"print_format: paper must be #FFFFFF (a tinted page prints with a white frame), not {th.get('paper')}")
    bad = [s for s in pf.get('sizes', ['letter']) if s not in PAPER]
    if bad or not pf.get('sizes'):
        out.append(f"print_format: sizes must be letter and/or a4, not {pf.get('sizes')}")
    if spec.get('orientation', 'portrait') != 'portrait':
        out.append('print_format: portrait only')
    if (pf.get('week_spread') or {}).get('weekend', 'stacked') != 'stacked':
        out.append("print_format: week_spread weekend must be 'stacked'")
    if any(x.get('module') == 'calendar' and x.get('days') is not False for x in spec.get('sections', [])):
        out.append('print_format: calendar days must be false (no day pages in a printed weekly planner)')
    return out


# ---------- build ----------
def capabilities():
    return {'modules': {k: {'desc': v['desc'], 'params': v['params']} for k, v in MODULES.items()},
            'blocks': BLOCK_KINDS, 'day_presets': list(DAY_PRESETS), 'week_presets': list(WEEK_PRESETS),
            'themes': list(THEMES), 'orientations': list(SIZES), 'dating': ['dated (year)', 'undated'],
            'fonts': ['Corm', 'Jost', 'Fraunces', 'Manrope', 'Quicksand', 'Nunito', 'DMSerif', 'Outfit', 'Baskerville', 'Script'],
            'type_scale': 'number, 1.0 default; 1.15 for larger text',
            'tap_targets': "'large': top bar, trail, page-number and arrow buttons at least 30 pt tall", 'nav_max': 'int, top-bar buttons (default 7 landscape, 4 portrait)'}


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
        problems += _pf_problems(spec, th)
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
    if P.pf:
        _pf_fill(P)
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
            'size': (round(P.W), round(P.HT)), 'print_problems': getattr(P, 'pf_problems', []), 'paper': getattr(P, 'paper', None), 'links': len(re.findall(r'href="#', html))}


if __name__ == '__main__':
    import sys
    print(json.dumps(capabilities(), indent=1))
