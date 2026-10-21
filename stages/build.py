"""Stage 5: Build. Brief spec -> product files, page shots and a build record.

  run <product_id>   -> data/products/<pid>/files/*.pdf, shots/*.png, build.json
Blocks (and says exactly what is missing) when the brief needs a module the line cannot build yet:
the session then writes the module into lines/<line>/gen.py, adds it to the line test, and runs again.
"""
import importlib, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

CHK = store.CONFIG['check']


def line_dir(line):
    return os.path.join(store.ROOT, 'lines', line)


def gen_for(line):
    sys.path.insert(0, line_dir(line))
    return importlib.import_module('gen')


def _render(line, html_path, pdf_path, shots_dir, anchors, size):
    os.makedirs(shots_dir, exist_ok=True)
    r = subprocess.run(['node', os.path.join(line_dir(line), 'render.js'), html_path, pdf_path, shots_dir, ','.join(anchors), str(size[0]), str(size[1])],
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


def run(pid):
    pdir = store.product_dir(pid)
    brief = store.read(os.path.join(pdir, 'brief.json'))
    chk = store.read(os.path.join(pdir, 'brief.check.json'))
    if not chk or not chk.get('pass'):
        return {"ok": False, "blocked": "brief has not passed its check", "problems": (chk or {}).get('problems')}
    gen = gen_for(brief['line'])
    problems, needs = gen.validate_spec(brief['spec'])
    if problems or needs:
        return {"ok": False, "blocked": "needs_module" if needs else "spec problems", "needs_module": needs,
                "new_modules": [m for m in brief.get('new_modules', []) if m['name'] in needs], "problems": problems}
    spec = dict(brief['spec'])
    files_dir = os.path.join(pdir, 'files'); shots_dir = os.path.join(pdir, 'shots')
    shutil.rmtree(files_dir, ignore_errors=True); shutil.rmtree(shots_dir, ignore_errors=True)
    os.makedirs(files_dir); os.makedirs(shots_dir)
    attempts = []
    for lean in (False, True):
        spec['lean'] = lean
        res = gen.build(spec)
        if res['broken_links'] or res['duplicate_pages'] or res['orphan_pages']:
            return {"ok": False, "blocked": "broken links, duplicate or unreachable pages", "broken": res['broken_links'][:20],
                    "duplicates": res['duplicate_pages'][:20], "unreachable": res['orphan_pages'][:20]}
        html_path = os.path.join(pdir, 'product.html'); open(html_path, 'w').write(res['html'])
        anchors = shot_anchors(res, brief)
        raw = os.path.join(files_dir, 'raw.pdf')
        over = _render(brief['line'], html_path, raw, shots_dir, anchors, res['size'])
        name = re.sub(r'[^A-Za-z0-9]+', '-', spec['title']).strip('-') + '.pdf'
        mb = _compress(raw, os.path.join(files_dir, name))
        attempts.append({"lean": lean, "mb": round(mb, 2), "pages": res['pages']})
        if mb <= CHK['max_pdf_mb']:
            break
    rec = {"product_id": pid, "brief_id": brief['brief_id'], "built_at": store.now(), "line": brief['line'],
           "files": [{"name": name, "mb": round(mb, 2), "pages": res['pages']}], "links": res['links'],
           "overflow": over, "lean": spec['lean'], "attempts": attempts, "page_modules": res['page_modules'],
           "shots": sorted(os.listdir(shots_dir)), "size_px": res['size']}
    store.write(os.path.join(pdir, 'build.json'), rec)
    ok = mb <= CHK['max_pdf_mb'] and not over
    return {"ok": ok, "pages": res['pages'], "mb": round(mb, 2), "lean": spec['lean'], "overflow": over[:5], "shots": len(rec['shots'])}


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[2] if sys.argv[1] == 'run' else sys.argv[1]), indent=1))
