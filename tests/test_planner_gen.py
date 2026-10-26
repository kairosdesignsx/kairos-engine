"""Smoke test: every planner module builds, links resolve, pages render without overflow."""
import json, os, re, subprocess, sys, time
sys.path.insert(0, 'lines/planner')
import gen

SPEC = {
 "title": "Test Planner", "subtitle": "Every module once", "brand": "Kairos test",
 "orientation": "landscape", "dating": {"mode": "dated", "year": 2027}, "theme": "night", "type_scale": 1.0,
 "sections": [
  {"module": "cover"},
  {"module": "guide", "label": "Start here", "anchor": "start", "steps": [["Import", "Open the PDF in your app."], ["Read mode", "Turn the pen off to tap links."], ["Plan", "Write with your stylus."], ["Help", "Message us anytime."]], "tip": "Test tip."},
  {"module": "link_test"},
  {"module": "index"},
  {"module": "year"},
  {"module": "lined", "label": "Brain dump", "pages": 2, "dots": True},
  {"module": "checklist", "label": "Routines", "groups": [["Morning", ["Water"]], ["Evening", ["Phone away"]]]},
  {"module": "table", "label": "Bills", "headers": ["Bill", "Due", "Paid"], "rows": 12},
  {"module": "year_pixels", "label": "Year in moods"},
  {"module": "head_start", "label": "Head start", "from": "2026-11", "to": "2026-12", "days": True, "week": {"preset": "adhd"}, "day": {"preset": "adhd"}},
  {"module": "calendar", "habits": True, "week": {"preset": "adhd"}, "day": {"preset": "adhd"}},
  {"module": "money_month", "head_start": True, "income": ["Product sales", "Services"], "expenses": ["Stock", "Fees", "Ads"], "fields": ["Best seller", "One change"]},
  {"module": "lined", "label": "Notes", "pages": 3}
 ]}

def run(spec, name):
    t = time.time()
    r = gen.build(spec)
    assert not r['broken_links'], r['broken_links'][:10]
    assert not r['duplicate_pages'], r['duplicate_pages'][:10]
    assert not r['orphan_pages'], ('unreachable pages', r['orphan_pages'][:10])
    html = os.path.abspath(f'tests/out/{name}.html'); open(html, 'w').write(r['html'])
    pdf = os.path.abspath(f'tests/out/{name}.pdf')
    W, H = r['size']
    out = subprocess.run(['node', 'lines/planner/render.js', html, pdf, os.path.abspath('tests/out'), 'd0115,w03,start,linktest,mm01,mmhs11', str(W), str(H)], capture_output=True, text=True)
    over = json.loads(out.stdout.split('overflow', 1)[1].strip().splitlines()[0]) if 'overflow' in out.stdout else None
    import pypdf
    rd = pypdf.PdfReader(pdf)
    fonts = {str(f.get_object().get('/BaseFont', '')) for pg in rd.pages[::max(1, len(rd.pages) // 60)] for f in ((pg.get('/Resources') or {}).get('/Font') or {}).values()}
    bad = [f for f in fonts if any(x in f for x in ('Liberation', 'DejaVu', 'Noto', 'Arial', 'Times', 'Helvetica'))]
    assert not bad, f'fallback fonts embedded: {bad}'
    print(name, r['pages'], 'pages', r['links'], 'links', f"{os.path.getsize(pdf)/1e6:.1f} MB raw", 'overflow:', over, f'{time.time()-t:.0f}s', out.stderr[:200])
    return r, over

# Reading journal: books (library + book pages), reading_month, reading_year, cover button
JOURNAL = {
 "title": "Test Journal", "subtitle": "Books", "kicker": "Digital reading journal", "brand": "Kairos test",
 "orientation": "portrait", "dating": {"mode": "undated"}, "theme": {"base": "navy", "display": "Baskerville", "body": "Manrope", "accent": "#8C3B3B", "button": "#8C3B3B"}, "type_scale": 1.1,
 "sections": [
  {"module": "cover", "start": "start", "button": "Open journal"},
  {"module": "index"},
  {"module": "guide", "label": "Start here", "anchor": "start", "nav": False, "steps": [["Import", "Open it.", "linktest"], ["Library", "Write a title.", "library"], ["Year", "Set a goal.", "year"], ["Months", "Tap a tab."]], "map": True},
  {"module": "link_test", "label": "Setup check", "anchor": "linktest", "nav": False},
  {"module": "books", "label": "Library", "kicker": "Book log", "anchor": "library", "book_anchor": "b", "count": 30, "per_log_page": 12},
  {"module": "reading_year", "label": "Reading year", "kicker": "Goal", "anchor": "year", "nav": False},
  {"module": "reading_month", "label": "Reading months", "index": False, "nav": False},
  {"module": "table", "label": "To be read", "anchor": "tbr", "headers": ["Title", "Author", "Got it"], "rows": 10, "check_columns": ["Got it"], "dividers": True},
  {"module": "lined", "label": "Notes", "anchor": "notes", "pages": 1}
 ]}

# E-ink (reMarkable) format: gutter, vector rules, grayscale, week rows, link test wording
GRAY = {"base": "neutral", "paper": "#FFFFFF", "ink": "#111111", "muted": "#4D4D4D", "line": "#9E9E9E", "accent": "#2B2B2B", "soft": "#EBEBEB", "warm": "#6B6B6B", "tabs": ["#DADADA", "#B5B5B5"], "display": "Outfit", "body": "Manrope", "motif": "none"}
EINK = {
 "title": "Test Eink", "subtitle": "Gray", "brand": "Kairos test", "orientation": "portrait", "dating": {"mode": "dated", "year": 2027}, "theme": GRAY, "type_scale": 1.15,
 "sections": [
  {"module": "eink_format", "left_gutter": 64, "vector_rules": True, "grayscale": True, "week_layout": "rows",
   "link_test_fixes": ["Tap with your finger", "Open the uploaded PDF", "Update the tablet", "Send us a message"], "pen_label": "Pen test here"},
  {"module": "cover"}, {"module": "index"},
  {"module": "link_test", "anchor": "linktest"},
  {"module": "year", "links": [["Head start", "hs11"]]},
  {"module": "lined", "label": "Grid", "pages": 1, "dots": True, "anchor": "grid"},
  {"module": "head_start", "label": "Head start", "from": "2026-11", "to": "2026-12", "days": True, "nav": False, "main_links": True,
   "day": {"left": [{"kind": "checklist", "label": "Top 3", "rows": 3}, {"kind": "lines", "label": "Notes"}], "right": [{"kind": "hours", "label": "Time blocks", "from": 6, "to": 22, "row": 30}, {"kind": "lines", "label": "Done today"}]}},
  {"module": "calendar", "habits": True, "days": True, "iso_weeks": True, "week": {"side": [{"kind": "checklist", "label": "Top 3", "rows": 3, "fill": True}, {"kind": "lines", "label": "Notes"}]}}
 ]}


def test_journal():
    r, over = run(JOURNAL, 'journal')
    assert not over, over
    ids = [a for a, _ in r['page_modules']]
    assert ['library', 'library2', 'library3'] == [a for a in ids if a.startswith('library')]
    assert [f'b{i:03d}' for i in range(1, 31)] == [a for a in ids if re.fullmatch(r'b\d{3}', a)]
    assert [f'm{i:02d}' for i in range(1, 13)] == [a for a in ids if re.fullmatch(r'm\d{2}', a)]
    assert ids.count('year') == 1
    pages = dict(re.findall(r'<section class="pg" id="([^"]+)"(.*?)</section>', r['html'], flags=re.S))
    assert 'Open journal' in pages['cover'] and 'Open planner' not in pages['cover']
    assert 'your journal is set up' in pages['linktest']
    # library line 13 opens book 13; book 13 links back to the library page holding it, and to books 12 and 14
    assert 'href="#b013"' in pages['library2'] and 'href="#library2">Library</a> / Book 13' in pages['b013']
    assert 'href="#b012"' in pages['b013'] and 'href="#b014"' in pages['b013'] and 'href="#b031"' not in pages['b030']
    for p in ('library', 'library2', 'library3'):
        assert all(f'href="#{q}"' in pages[p] for q in ('library', 'library2', 'library3'))
    assert all(f'href="#m{i:02d}"' in pages['year'] for i in range(1, 13)) and 'href="#year">Reading year</a> / March' in pages['m03']
    assert 'class="on"' not in pages['b005'].split('class="rail"')[1].split('</div>')[0], 'book pages: no active month'
    assert 'class="on"' in pages['m05'].split('class="rail"')[1].split('</div>')[0]
    # Contents: Library and Reading year cards; reading months register nothing; top bar has Library but not Reading year
    idx = pages['index']
    assert 'href="#library"' in idx and 'href="#year" class="box"' in idx
    assert '>Library</a>' in pages['b001'].split('class="crumb"')[0] and 'Reading year</a>' not in pages['b001'].split('class="crumb"')[0]
    assert '\u2014' not in r['html'], 'no em dashes'
    # theme button token: Go there and cover buttons use it; stars use the accent; check column draws boxes, dividers
    assert 'background:#8C3B3B;color' in pages['start'] and 'background:#8C3B3B;color' in pages['cover']
    assert 'stroke="#8C3B3B"' in pages['b001'] and 'note app, not Files' in pages['linktest']
    assert pages['tbr'].count('<i style="width:15px') == 10 and 'border-left:1px solid' in pages['tbr']


def test_eink():
    assert gen.validate_spec(dict(EINK, theme=dict(GRAY, accent='#8C3B3B')))[0], 'grayscale must refuse a colored theme'
    assert gen.validate_spec(EINK) == ([], [])
    r, over = run(EINK, 'eink')
    assert not over, over
    html = r['html']
    pages = dict(re.findall(r'<section class="pg" id="([^"]+)"(.*?)</section>', html, flags=re.S))
    assert 'eink_format' not in [m for _, m in r['page_modules']], 'eink_format prints no page'
    assert '.nav{position:absolute;left:64px' in html and '.body{position:absolute;left:64px' in html
    css = html.split('</style>')[0]
    assert 'background:none!important' in css and "querySelectorAll('.lines,.dots')" in html and 'repeating-linear-gradient' not in css.split('background:none!important')[1]
    assert 'grid-auto-flow:column' in pages['w10'] and 'wkside' in pages['w10'] and 'wkside' in pages['hsw01']
    assert 'Tap with your finger' in pages['linktest'] and 'Pen test here' in pages['linktest'] and 'Goodnotes' not in pages['linktest']
    assert 'Where things are' in pages['linktest']
    # main_links: head-start tabs open the 2027 months, no tab lit; last head-start week -> Week 1 -> back
    rail = lambda a: pages[a].split('class="rail"')[1].split('</div>')[0]
    last = max(a for a in pages if re.fullmatch(r'hsw\d\d', a))
    assert 'href="#w01"' in pages[last] and f'href="#{last}"' in pages['w01']
    assert 'white-space:nowrap' in pages['year']
    # iso_weeks: Week 1 is Jan 4 to 10 2027, 52 weeks, Dec 28 to Jan 3 is the last head-start week; Jan 1 to 3 trail to it
    assert 'Jan 4 to Jan 10' in pages['w01'] and 'w52' in pages and 'w53' not in pages and 'w00' not in pages
    assert f'href="#{last}">Dec 28 to Jan 3</a>' in pages['d0101'] and 'href="#d0101"' in pages[last]
    assert 'Week 2</a>' in pages['d0111'].split('class="crumb"')[1][:400]
    assert '>NOV 2026<' in rail('hs11') and 'class="on"' in rail('hs11') and '>NOV<' in rail('w10')
    assert 'background:#FFFFFF' in pages['cover'] and 'background:#EBEBEB' not in pages['cover'], 'e-ink cover is pure white'
    assert 'background:#111111;color:#FFFFFF' not in pages['index'], 'e-ink Contents: no solid black month tiles'
    assert not re.search(r'#[0-9A-Fa-f]{6}(22|55|cc)\b', html.split('</style>')[1]), 'no color tints in grayscale'
    # the built PDF draws lines and dots as vector paths: no gradient patterns, shadings or images
    import pypdf
    rd = pypdf.PdfReader(os.path.abspath('tests/out/eink.pdf'))
    for pg in rd.pages:
        res = pg.get('/Resources') or {}
        assert not res.get('/Pattern') and not res.get('/Shading'), 'pattern or shading fill in an e-ink page'
        assert not any(x.get_object().get('/Subtype') == '/Image' for x in (res.get('/XObject') or {}).values()), 'image in an e-ink page'
    grid = rd.pages[[a for a, _ in r['page_modules']].index('grid')].get_contents().get_data()
    assert grid.count(b' l') > 500, 'dot grid page draws its dots as vector strokes'
    # without eink_format nothing changes: gradients, 4 x 2 week grid, default link test wording
    plain = gen.build(dict(EINK, sections=EINK['sections'][1:]))['html']
    assert 'repeating-linear-gradient' in plain and 'wkside' not in plain and 'Turn the pen off' in plain and 'left:40px' in plain


def test_undated_weeks():
    """Undated: weeks run in order through the year (Mar 9-13, Dec 48-52) and month grids have 6 rows (42 boxes)."""
    r = gen.build(dict(SPEC, dating={"mode": "undated"}, sections=[{"module": "cover"}, {"module": "index"}, {"module": "calendar", "days": False}]))
    pages = dict(re.findall(r'<section class="pg" id="([^"]+)"[^>]*>(.*?)</section>', r['html'], re.S))
    for m, ws in ((3, range(9, 14)), (12, range(48, 53))):
        assert all(f'href="#w{w:02d}"' in pages[f'm{m:02d}'] for w in ws), (m, list(ws))
    assert 'href="#w49"' not in pages['m03']
    assert pages['m01'].count('<span class="d"></span>') == 42
    r2 = gen.build(dict(SPEC, dating={"mode": "undated"}, sections=[{"module": "cover"}, {"module": "year"}, {"module": "calendar", "days": False}]))
    yr = dict(re.findall(r'<section class="pg" id="([^"]+)"[^>]*>(.*?)</section>', r2['html'], re.S))['year']
    assert yr.count('border:1px solid') >= 12 * 42, 'undated year page: boxes to write dates in'
    assert all(f'<a href="#m{m:02d}" style="display:flex' in yr for m in range(1, 13)), 'undated year: the whole month block is the link'
    r4 = gen.build(dict(SPEC, tap_targets='large', nav_max=5, dating={"mode": "undated"}, sections=[{"module": "cover"}, {"module": "index"}, {"module": "year"}, {"module": "lined", "label": "Notes", "pages": 3}, {"module": "checklist", "label": "Lists", "groups": [["A", []]]}, {"module": "calendar", "days": False, "free_weeks": True}]))
    assert '.nav a{display:inline-flex;align-items:center;height:40px' in r4['html'] and 'class="pgn"' in r4['html']
    assert re.search(r'<div class="nav">(?:<a [^>]*>[^<]*</a>){5}<span', r4['html']), 'nav_max 5: five top-bar buttons'
    r5 = gen.build(dict(SPEC, tap_targets='large', nav_desc={'weeks': 'All 52 weeks, in order'}, dating={"mode": "undated"}, orientation='portrait',
                        sections=[{"module": "cover"}, {"module": "index"}, {"module": "year"}, {"module": "link_test"}, {"module": "calendar", "free_weeks": True}]))
    pg5 = dict(re.findall(r'<section class="pg" id="([^"]+)"[^>]*>(.*?)</section>', r5['html'], re.S))
    assert pg5['w01'].count('class="dchip"') == 7 and 'href="#u016" class="dchip"' in pg5['w01'], 'large taps: an Open chip on every day box'
    assert not r5['broken_links']
    # free_weeks: weeks 1 to 52 not filed under months, a Weeks page links them all, day arrows cross week edges
    r3 = gen.build(dict(SPEC, dating={"mode": "undated"}, sections=[{"module": "cover"}, {"module": "index"}, {"module": "year"}, {"module": "calendar", "free_weeks": True}]))
    assert not r3['broken_links'] and not r3['orphan_pages'], (r3['broken_links'][:5], r3['orphan_pages'][:5])
    pg3 = dict(re.findall(r'<section class="pg" id="([^"]+)"[^>]*>(.*?)</section>', r3['html'], re.S))
    assert all(f'href="#w{n:02d}"' in pg3['weeks'] for n in range(1, 53)) and 'href="#weeks"' in pg3['m10']
    assert 'href="#w4' not in pg3['m10'] and 'href="#weeks">Weeks</a> / Week 44' in pg3['w44']
    assert 'href="#u020"' in pg3['u016'] and 'href="#u016"' in pg3['u020'] and 'href="#u530"' not in pg3['u526']


# Trackers (fitness, meals, self-care): log_week hub, workout_log, meal_week, progress_chart, body_measure, habit_month, group_weeks
TRACK = {
 "title": "Test Fit", "subtitle": "Trackers", "brand": "Kairos test", "orientation": "portrait", "dating": {"mode": "undated"},
 "theme": {"base": "navy", "display": "Baskerville", "body": "Outfit", "button": "#2D4FC4", "labels": "italic"}, "type_scale": 1.05,
 "sections": [
  {"module": "cover", "start": "start"}, {"module": "index"},
  {"module": "guide", "label": "Start here", "anchor": "start", "nav": False, "steps": [["A", "a", "w01"], ["B", "b", "linktest"], ["C", "c", "progress"], ["D", "d", "m01"]], "map": True},
  {"module": "link_test", "label": "Setup check", "anchor": "linktest", "nav": False, "targets": [["A week page", "w01"], ["A month page", "m01"], ["Contents", "index"]],
   "fixes": ["Pen off", "Note app", "Re-import", "Send the shop an Etsy message"]},
  {"module": "log_week", "label": "Weeks", "count": 6, "columns": [{"label": "Workout plan", "width": 2.2}, {"label": "Minutes"}, {"label": "Done", "check": True}],
   "habits": ["Water", "Steps"], "stats": ["Weigh-in", "Change"], "fields": ["Win of the week", "Next week I will"],
   "links": [{"label": "Meal plan", "anchor": "meal"}, {"label": "Workout", "anchor": "wo", "per": 3}, {"label": "Journal", "anchor": "jr"}], "mark_every": 4, "mark_anchor": "measure", "mark_label": "Measure"},
  {"module": "workout_log", "label": "Workouts", "kicker": "Training log", "count": 18, "per_week": 3, "week_anchor": "w"},
  {"module": "meal_week", "count": 6, "week_anchor": "w", "nav": False, "grocery_rows": 4},
  {"module": "prompt_week", "count": 6, "week_anchor": "w", "prompts": ["First prompt?", "Second prompt?"], "numbered": ["Three good things", 3], "boxes": ["A kind word"]},
  {"module": "progress_chart", "label": "Progress", "anchor": "progress", "points": 6, "every": 2, "fields": ["Start", "Goal"],
   "blocks": [{"kind": "checklist", "label": "Milestones", "rows": 5}, {"kind": "lines", "label": "Wins"}], "links": [["Measurements", "measure"]]},
  {"module": "body_measure", "anchor": "measure", "nav": False, "week_anchor": "w", "every": 2, "weeks": 6, "tips": [["Waist", "At the narrowest point."], ["Hips", "Widest part."]]},
  {"module": "habit_month", "habits": ["Workout day"], "blank_habits": 3, "mood": {"label": "Energy"}, "stats": ["Workouts done"], "fields": ["What went well", "One change"]},
  {"module": "group_weeks"}
 ]}


def test_trackers():
    r, over = run(TRACK, 'trackers')
    assert not over, over
    ids = [a for a, _ in r['page_modules']]
    pages = dict(re.findall(r'<section class="pg" id="([^"]+)"(.*?)</section>', r['html'], flags=re.S))
    # group_weeks: week, its meal plan, its workouts, then the next week; log list pages stay after the weeks
    i = ids.index('w01')
    assert ids[i:i + 12] == ['w01', 'meal01', 'wo001', 'wo002', 'wo003', 'jr01', 'w02', 'meal02', 'wo004', 'wo005', 'wo006', 'jr02'], ids[i:i + 12]
    assert 'First prompt?' in pages['jr03'] and 'Second prompt?' in pages['jr04'] and 'href="#w04"' in pages['jr04'] and 'href="#jr04"' in pages['w04']
    assert ids.index('weeks') < i and ids.index('log') > ids.index('wo018')
    assert len(ids) == len(set(ids)) and 'group_weeks' not in [m for _, m in r['page_modules']]
    # week hub links both ways; measure button every 4th week; overview opens every week
    assert all(f'href="#{a}"' in pages['w02'] for a in ('meal02', 'wo004', 'wo005', 'wo006', 'w01', 'w03', 'weeks'))
    assert 'href="#measure"' in pages['w04'] and 'href="#measure"' not in pages['w03']
    assert 'href="#w02"' in pages['meal02'] and 'href="#w02"' in pages['wo005'] and 'Workout 2' in pages['wo005']
    assert all(f'href="#w{n:02d}"' in pages['weeks'] for n in range(1, 7))
    # log list: each workout one tap, week pills; measure rows open week pages; months m01 to m12 with faded Feb 30, 31
    assert all(f'href="#wo{n:03d}"' in pages['log'] for n in range(1, 19)) and 'href="#w06"' in pages['log']
    assert 'href="#w04"' in pages['measure'] and 'href="#w06"' in pages['measure'] and 'How to measure' in pages['measure']
    assert [f'm{m:02d}' for m in range(1, 13)] == [a for a in ids if re.fullmatch(r'm\d{2}', a)]
    assert 'Energy' in pages['m02'] and pages['m02'].count('opacity:.25') >= 4 and pages['m01'].count('opacity:.25') == 0
    assert 'Last time' in pages['wo001'] and 'Set 4' in pages['wo001'] and 'Grocery list' in pages['meal01']
    assert 'A week page' in pages['linktest'] and 'Send the shop an Etsy message' in pages['linktest'] and 'we will help' not in pages['linktest']
    # landscape builds without overflow too (a meal planner may be landscape)
    r2, over2 = run(dict(TRACK, orientation='landscape'), 'trackers-land')
    assert not over2, over2
    assert '—' not in r['html'], 'no em dashes'


# Print format (home-printed weekly planner): Letter and A4, safe and binding margins, whole-sheet months, spreads
PRINT_TH = {"base": "sage", "paper": "#FFFFFF", "ink": "#1F2A33", "muted": "#55606B", "line": "#C3C9CF", "accent": "#A8492B", "soft": "#F5EFEA", "display": "Corm", "body": "Jost", "motif": "none", "labels": "italic"}
PRINT = {
 "title": "Test Print", "subtitle": "Paper", "kicker": "Printable weekly planner", "brand": "Kairos test", "orientation": "portrait", "dating": {"mode": "dated", "year": 2027}, "theme": PRINT_TH, "type_scale": 1.1,
 "sections": [
  {"module": "print_format", "sizes": ["letter", "a4"], "margin_in": 0.5, "binding_in": 0.375, "duplex": True, "hide_nav": True, "page_numbers": True, "vector_rules": True,
   "week_spread": {"left_top": [{"kind": "checklist", "label": "Focus", "rows": 3, "fill": True}], "day_rows": 3, "weekend": "stacked",
                   "right_bottom": [{"kind": "pair", "items": [{"kind": "habits", "label": "Habits", "rows": 5}, {"kind": "checklist", "label": "To do", "rows": 5}]}]},
   "month_spread": {"page": [{"kind": "checklist", "label": "Goals", "rows": 3, "fill": True}], "review": [{"kind": "lines", "label": "Notes"}]}},
  {"module": "cover", "start": "start", "button": "Start here", "size": 80, "facts": ["Fact one"], "owner": "This planner belongs to"},
  {"module": "guide", "label": "Start here", "anchor": "start", "nav": False, "steps": [["A", "a"], ["B", "b", "printcheck"], ["C", "c", "printmap"], ["D", "d"]]},
  {"module": "print_check", "anchor": "printcheck", "fixes": ["One", "Two"]},
  {"module": "print_map", "anchor": "printmap"},
  {"module": "year", "nav": False, "links": [["Head start", "hs11"]]},
  {"module": "table", "label": "Dates", "anchor": "dates", "headers": ["Date", "Done"], "rows": 20, "check_columns": ["Done"]},
  {"module": "table", "label": "Dates", "anchor": "dates2", "headers": ["Date", "Done"], "rows": 20, "check_columns": ["Done"]},
  {"module": "head_start", "label": "Head start", "anchor": "hs", "from": "2026-11", "to": "2026-12", "days": False, "nav": False},
  {"module": "calendar", "habits": False, "days": False, "iso_weeks": True},
  {"module": "spare_week", "anchor": "spare", "count": 1}
 ]}


def test_print():
    assert gen.validate_spec(dict(PRINT, theme=dict(PRINT_TH, paper="#FBFAF6")))[0], 'print_format must refuse tinted paper'
    assert gen.validate_spec(PRINT) == ([], [])
    a4 = gen.build(dict(PRINT, paper='a4'))
    r, over = run(PRINT, 'print')
    assert not over, over
    assert not r['print_problems'] and not a4['print_problems'], (r['print_problems'], a4['print_problems'])
    assert r['size'] == (816, 1056) and a4['size'] == (794, 1122) and r['pages'] == a4['pages'] and r['pages'] % 2 == 0
    ids = [a for a, _ in r['page_modules']]; idx = {a: i + 1 for i, a in enumerate(ids)}
    assert 'print_format' not in [m for _, m in r['page_modules']]
    assert idx['printcheck'] % 2 == 1 and idx['hs11'] % 2 == 1 and idx['m01'] % 2 == 1 and idx['m01b'] % 2 == 0, 'months are whole sheets'
    assert all(idx[a] % 2 == 0 for a in ids if re.fullmatch(r'(hs)?w\d\d|spare', a)), 'spreads start on a sheet back'
    assert 'w52' in idx and 'w53' not in idx and 'hsw10' in idx and 'hsw11' not in idx and not any(re.fullmatch(r'd\d{4}', a) for a in ids), 'ISO: 52 weeks, 10 head-start weeks, no day pages'
    html = r['html']; pages = dict(re.findall(r'<section class="pg" id="([^"]+)"(.*?)</section>', html, flags=re.S))
    assert 'class="rail"' not in html and '@page{size:8.5in 11in' in html and '@page{size:210mm 297mm' in a4['html']
    assert 'href="#w12"' in pages['year'] and 'href="#hsw10"' in pages['year'] and 'href="#hsw10"' in pages['hs12'] and 'href="#hsw01"' in pages['hs11'], 'dates open their week (Jan 1 to 3 sit in the last head-start week)'
    assert 'href="#w01"' in pages['hsw10b'] and 'href="#hsw10"' in pages['w01'], 'head start runs into Week 1'
    assert 'Jan 4 to Jan 10' in pages['w01'] and 'Mar 22 to Mar 28' in pages['w12'] and 'Dec 27 to Jan 2' in pages['w52'], 'iso_weeks: ISO 8601 week numbers'
    assert 'Weeks' in pages['printmap'] and 'Oct 26 to Nov 29' in pages['printmap'] and '1 to 2 and 5 to 8' in pages['printmap'], 'Print map: weeks per row, first print skips the check sheet'
    assert 'class="pfnav"' in pages['w12'] and 'Previous week' in pages['w12']
    no_iso = gen.build(dict(PRINT, sections=[{k: v for k, v in x.items() if k != 'iso_weeks'} for x in PRINT['sections']]))
    assert 'w53' in [a for a, _ in no_iso['page_modules']] and not no_iso['print_problems'], 'without iso_weeks the old count stays (opt-in only)'
    assert f'1 to {idx["dates2"]}' in pages['printmap'] and '%%' not in html and 'Page 3' in pages['start']
    assert '<circle' in pages['w12b'] and 'Thursday to Sunday' in pages['w12']
    assert re.search(r'id="w12" data-side="even"', html) and re.search(r'id="w12b" data-side="odd"', html)
    assert '\u2014' not in html, 'no em dashes'


if __name__ == '__main__':
    import re
    test_trackers()
    test_undated_weeks()
    print('ok undated weeks')
    test_journal()
    test_eink()
    test_print()
    r, over = run(SPEC, 'dated')
    und = dict(SPEC, dating={"mode": "undated"}, theme="sage", orientation="portrait")
    r2, over2 = run(und, 'undated')
    assert not over and not over2
    print('ok')
