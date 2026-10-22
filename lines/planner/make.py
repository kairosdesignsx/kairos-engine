"""Planner line build: spec -> hyperlinked PDF, page shots and a build record (called by stages/build.py)."""
import json, os, re, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
import gen

def _render(html_path, pdf_path, shots_dir, anchors, size):
    os.makedirs(shots_dir, exist_ok=True)
    r = subprocess.run(['node', os.path.join(HERE, 'render.js'), html_path, pdf_path, shots_dir, ','.join(anchors), str(size[0]), str(size[1])],
                       capture_output=True, text=True, timeout=900)
    over = []
    m = re.search(r'overflow (\[.*\])', r.stdout)
    if m:
        over = json.loads(m.group(1))
    if r.returncode != 0:
        raise RuntimeError(f'render failed: {r.stderr[:500]}')
    return over


def _compress(raw, out):
    subprocess.run(['qpdf', '--object-streams=generate', '--recompress-flate', '--compression-level=9', raw, out], check=True)
    os.remove(raw)
    return os.path.getsize(out) / 1e6


def shot_anchors(result, brief):
    """Pages to screenshot: every page the photo plan names, plus the first page of each module and a sample of days and weeks."""
    want = []
    for ph in brief.get('photos', []):
        want += ph.get('pages', [])
    seen_mod = set()
    for anchor, mod in result['page_modules']:
        if mod not in seen_mod:
            seen_mod.add(mod); want.append(anchor)
    days = [a for a, m in result['page_modules'] if re.fullmatch(r'd\d{4}|u\d{3}', a)]
    weeks = [a for a, m in result['page_modules'] if re.fullmatch(r'w\d{2}', a)]
    months = [a for a, m in result['page_modules'] if re.fullmatch(r'm\d{2}h?', a)]
    for group, n in ((days, 3), (weeks, 2), (months, 2)):
        if group:
            step = max(1, len(group) // n)
            want += group[::step][:n]
    ids = {a for a, _ in result['page_modules']}
    out = []
    for a in want:
        if a in ids and a not in out:
            out.append(a)
    return out



def build(brief, pdir, files_dir, shots_dir, max_mb):
    spec = dict(brief['spec'])
    attempts = []
    for lean in (False, True):
        spec['lean'] = lean
        res = gen.build(spec)
        if res['broken_links'] or res['duplicate_pages'] or res['orphan_pages']:
            return None, {"ok": False, "blocked": "broken links, duplicate or unreachable pages", "broken": res['broken_links'][:20],
                          "duplicates": res['duplicate_pages'][:20], "unreachable": res['orphan_pages'][:20]}
        html_path = os.path.join(pdir, 'product.html'); open(html_path, 'w').write(res['html'])
        anchors = shot_anchors(res, brief)
        raw = os.path.join(files_dir, 'raw.pdf')
        over = _render(html_path, raw, shots_dir, anchors, res['size'])
        name = re.sub(r'[^A-Za-z0-9]+', '-', spec['title']).strip('-') + '.pdf'
        mb = _compress(raw, os.path.join(files_dir, name))
        attempts.append({"lean": lean, "mb": round(mb, 2), "pages": res['pages']})
        if mb <= max_mb:
            break
    rec = {"files": [{"name": name, "mb": round(mb, 2), "pages": res['pages']}], "links": res['links'],
           "overflow": over, "lean": spec['lean'], "attempts": attempts, "page_modules": res['page_modules'],
           "shots": sorted(os.listdir(shots_dir)), "size_px": res['size']}
    ok = mb <= max_mb and not over
    return rec, {"ok": ok, "pages": res['pages'], "mb": round(mb, 2), "lean": spec['lean'], "overflow": over[:5], "shots": len(rec['shots'])}
