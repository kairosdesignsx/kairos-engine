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
