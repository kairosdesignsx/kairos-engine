"""Smoke test: every planner module builds, links resolve, pages render without overflow."""
import json, os, subprocess, sys, time
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
  {"module": "lined", "label": "Notes", "pages": 3}
 ]}

def run(spec, name):
    t = time.time()
    r = gen.build(spec)
    assert not r['broken_links'], r['broken_links'][:10]
    assert not r['duplicate_pages'], r['duplicate_pages'][:10]
    html = os.path.abspath(f'tests/out/{name}.html'); open(html, 'w').write(r['html'])
    pdf = os.path.abspath(f'tests/out/{name}.pdf')
    W, H = r['size']
    out = subprocess.run(['node', 'lines/planner/render.js', html, pdf, os.path.abspath('tests/out'), 'd0115,w03,start,linktest', str(W), str(H)], capture_output=True, text=True)
    over = json.loads(out.stdout.split('overflow', 1)[1].strip().splitlines()[0]) if 'overflow' in out.stdout else None
    print(name, r['pages'], 'pages', r['links'], 'links', f"{os.path.getsize(pdf)/1e6:.1f} MB raw", 'overflow:', over, f'{time.time()-t:.0f}s', out.stderr[:200])
    return r, over

if __name__ == '__main__':
    r, over = run(SPEC, 'dated')
    und = dict(SPEC, dating={"mode": "undated"}, theme="sage", orientation="portrait")
    r2, over2 = run(und, 'undated')
    assert not over and not over2
    print('ok')
