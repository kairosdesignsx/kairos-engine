"""Planner file checks (PDF): size, overflow, page count, links, fonts, page-count claims. Called by stages/check.py tech."""
import os, re

FONT_FAMILIES = {'Cormorant': 'Corm', 'Jost': 'Jost', 'PinyonScript': 'Script', 'Fraunces': 'Fraunces', 'Manrope': 'Manrope',
                 'Quicksand': 'Quicksand', 'Nunito': 'Nunito', 'DMSerif': 'DMSerif', 'Outfit': 'Outfit', 'LibreBaskerville': 'Baskerville',
                 'Corm': 'Corm', 'Script': 'Script', 'Baskerville': 'Baskerville'}


def file_checks(d, brief, b, L, add, CHK):
    import pypdf
    for f in b['files']:
        add('file size', f['mb'] <= CHK['max_pdf_mb'], f"{f['name']}: {f['mb']} MB (limit {CHK['max_pdf_mb']}, Etsy 20)")
    add('no text overflow', not b['overflow'], f"{len(b['overflow'])} pages overflow" if b['overflow'] else 'none')
    r = pypdf.PdfReader(os.path.join(d, 'files', b['files'][0]['name']))
    n = len(r.pages)
    add('page count', n == b['files'][0]['pages'], f'{n} pages in PDF')
    for f in b['files'][1:]:  # print_format: one file per paper size, same pages
        n2 = len(pypdf.PdfReader(os.path.join(d, 'files', f['name'])).pages)
        add(f"page count {f['name']}", n2 == f['pages'] == n, f'{n2} pages (first file {n})')
    annots = sum(len(p.get('/Annots') or []) for p in r.pages)
    add('links present in PDF', annots >= 0.9 * b['links'], f'{annots} link annotations for {b["links"]} links in the source')
    fonts = set()
    for p in r.pages[:: max(1, n // 40)]:
        for f in ((p.get('/Resources') or {}).get('/Font') or {}).values():
            bf = str(f.get_object().get('/BaseFont', ''))
            fonts.add(re.sub(r'^/?[A-Z]{6}\+', '', bf).lstrip('/'))
    unknown = sorted(f for f in fonts if not any(f.replace('-', '').startswith(k) for k in FONT_FAMILIES))
    add('fonts licensed (OFL list only)', not unknown, f'fonts: {sorted(fonts)}' + (f'; NOT ALLOWED: {unknown}' if unknown else ''))
    desc = L.get('description', '')
    claims = [int(m) for m in re.findall(r'(\d{2,4})\+?\s*(?:hyperlinked\s+|linked\s+)?pages', desc)]
    claims = [c for c in claims if not 2020 <= c <= 2039]  # years ("Nov and Dec 2026 pages") are not page counts
    add('page claims match the file', all(c <= n for c in claims), f'claims {claims}, file has {n}')
    layout_checks(d, b, add)


MIN_ZOOM = 2.4       # photo px per page css px for a close-up: about 0.9x page size at Etsy's zoom (r013; 1.84 read too small, 2.49 fine)
MAX_EMPTY = 0.33     # largest empty band allowed in a photo, as a share of its height (r006, r013)


def link_problems(path):
    """Link boxes outside the page box (past the edge, so they can't be tapped) and overlapping link boxes."""
    import pypdf
    out_box, overlaps = [], []
    for i, p in enumerate(pypdf.PdfReader(path).pages, 1):
        mb = [float(v) for v in p.mediabox]
        rects = []
        for a in p.get('/Annots') or []:
            a = a.get_object()
            if a.get('/Subtype') != '/Link' or '/Rect' not in a:
                continue
            x0, y0, x1, y1 = [float(v) for v in a['/Rect']]
            x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1))
            if x0 < mb[0] - 0.5 or y0 < mb[1] - 0.5 or x1 > mb[2] + 0.5 or y1 > mb[3] + 0.5:
                out_box.append(i)
            dest = str(a.get('/Dest') or (a.get('/A') or {}).get('/D') or (a.get('/A') or {}).get('/URI'))
            rects.append((x0, y0, x1, y1, dest))
        for j in range(len(rects)):
            for k in range(j + 1, len(rects)):
                a, c = rects[j], rects[k]
                w = min(a[2], c[2]) - max(a[0], c[0]); h = min(a[3], c[3]) - max(a[1], c[1])
                if w > 1 and h > 1 and a[4] != c[4]:  # two boxes to the same page are harmless
                    overlaps.append(i)
    return sorted(set(out_box)), sorted(set(overlaps))


def empty_band(path):
    """Largest run of near-blank rows in a photo, as a share of its height."""
    from PIL import Image, ImageStat
    im = Image.open(path).convert('L'); im = im.resize((270, max(1, round(270 * im.height / im.width))))
    run = best = 0
    for y in range(im.height):
        row = im.crop((0, y, im.width, y + 1))
        if ImageStat.Stat(row).stddev[0] < 2.0:
            run += 1; best = max(best, run)
        else:
            run = 0
    return best / im.height


def layout_checks(d, b, add):
    """Code checks that catch what used to cost AI check rounds: links past the page edge, overlapping links,
    close-ups too small to read, and photos with big empty bands."""
    for f in b['files']:
        out_box, overlaps = link_problems(os.path.join(d, 'files', f['name']))
        add(f"links inside the page ({f['name']})", not out_box, f"pages with a link past the edge: {out_box[:12]}" if out_box else 'all inside')
        add(f"links don't overlap ({f['name']})", not overlaps, f"pages with overlapping links: {overlaps[:12]}" if overlaps else 'none')
    import json
    pj = {}
    try:
        pj = json.load(open(os.path.join(d, 'photos.json')))
    except Exception:
        pass
    small = {k: min(v) for k, v in (pj.get('zoom_scale') or {}).items() if v and min(v) < MIN_ZOOM}
    add('close-ups big enough to read (r013)', not small,
        ('too small (photo px per page px, need ' + str(MIN_ZOOM) + '): ' + ', '.join(f'{k} {v}' for k, v in sorted(small.items()))) if small else 'all close-ups at readable size')
    pdir = os.path.join(d, 'photos')
    if os.path.isdir(pdir):
        bands = {f: round(empty_band(os.path.join(pdir, f)), 2) for f in sorted(os.listdir(pdir)) if f.startswith('photo-') and f.endswith('.jpg')}
        big = {k: v for k, v in bands.items() if v > MAX_EMPTY}
        add('no big empty bands in photos (r006)', not big,
            ('empty share of height: ' + ', '.join(f'{k} {v}' for k, v in big.items())) if big else f'largest {max(bands.values()) if bands else 0}')
