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



def _true_size(pdf, size):
    """Chromium rounds the page to whole CSS px (A4 comes out 209.9 mm wide): set the exact paper size in points."""
    import pypdf
    w, h = {'letter': (612, 792), 'a4': (595.2756, 841.8898)}[size]
    r = pypdf.PdfReader(pdf); wr = pypdf.PdfWriter(clone_from=r)
    for pg in wr.pages:
        pg.mediabox = pypdf.generic.RectangleObject([0, 0, w, h]); pg.cropbox = pypdf.generic.RectangleObject([0, 0, w, h])
    wr.write(pdf)


def build_print(brief, pdir, files_dir, shots_dir, max_mb, pf):
    """print_format: one PDF per paper size ('<Title>-Letter.pdf', '<Title>-A4.pdf'), same pages in the same order.
    Shots (and product.html, which photo crops read) come from the first size."""
    spec = dict(brief['spec']); files, over_all, first = [], [], None
    base = re.sub(r'[^A-Za-z0-9]+', '-', spec['title']).strip('-')
    for k, size in enumerate(pf.get('sizes') or ['letter']):
        spec['paper'] = size
        res = gen.build(spec)
        if res['broken_links'] or res['duplicate_pages'] or res['orphan_pages'] or res.get('print_problems'):
            return None, {"ok": False, "blocked": "broken links, unreachable pages or print layout problems", "paper": size, "broken": res['broken_links'][:20],
                          "duplicates": res['duplicate_pages'][:20], "unreachable": res['orphan_pages'][:20], "print_problems": res.get('print_problems', [])[:20]}
        html_path = os.path.join(pdir, 'product.html' if k == 0 else f'product-{size}.html'); open(html_path, 'w').write(res['html'])
        raw = os.path.join(files_dir, 'raw.pdf')
        anchors = []
        if k == 0:  # print: also each shot's facing page (anchor + 'b'), the last page of every module and the first and last week
            ids = [a for a, _ in res['page_modules']]
            anchors = shot_anchors(res, brief)
            last = {m: a for a, m in res['page_modules']}
            wk = [a for a in ids if re.fullmatch(r'w\d{2}', a)]
            anchors += [a + 'b' for a in anchors if a + 'b' in ids] + list(last.values()) + wk[:1] + wk[-1:] + [a + 'b' for a in wk[:1] + wk[-1:]]
            anchors = [a for a in dict.fromkeys(anchors) if a in ids]
        over = _render(html_path, raw, shots_dir, anchors, res['size'])
        if k == 0:  # paper photos: the same pages with on-screen-only links hidden (class pfnav)
            php = os.path.join(pdir, 'product-photo.html')
            open(php, 'w').write(res['html'].replace('</style>', '.pfnav{visibility:hidden!important}</style>', 1))
            sp = os.path.join(pdir, 'shots-paper'); import shutil; shutil.rmtree(sp, ignore_errors=True)
            _render(php, '-', sp, anchors, res['size'])
        over_all += [[f'{size}:{o[0]}'] + list(o[1:]) for o in over] if k else over
        name = f"{base}-{gen.PAPER[size][4]}.pdf"
        _true_size(raw, size)
        mb = _compress(raw, os.path.join(files_dir, name))
        files.append({"name": name, "mb": round(mb, 2), "pages": res['pages'], "paper": size})
        first = first or res
    if len({f['pages'] for f in files}) > 1:
        return None, {"ok": False, "blocked": "paper sizes differ in page count", "files": files}
    rec = {"files": files, "links": first['links'], "overflow": over_all, "lean": False, "attempts": [{"lean": False, "mb": f['mb'], "pages": f['pages'], "paper": f['paper']} for f in files],
           "page_modules": first['page_modules'], "shots": sorted(os.listdir(shots_dir)), "size_px": first['size'], "print": True}
    ok = all(f['mb'] <= max_mb for f in files) and not over_all
    return rec, {"ok": ok, "pages": first['pages'], "files": files, "overflow": over_all[:5], "shots": len(rec['shots'])}


def build(brief, pdir, files_dir, shots_dir, max_mb):
    spec = dict(brief['spec'])
    pf = next((x for x in spec.get('sections', []) if x.get('module') == 'print_format'), None)
    if pf:
        return build_print(brief, pdir, files_dir, shots_dir, max_mb, pf)
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
