"""Spreadsheet line build: spec -> .xlsx (opens in Google Sheets and Excel), a recalculated copy for checks,
one screenshot per tab (LibreOffice export, so the shots are the real file) and a build record."""
import json, os, re, shutil, subprocess
from openpyxl import load_workbook
import gen

ERRORS = ('#REF!', '#VALUE!', '#NAME?', '#DIV/0!', '#N/A', '#NUM!', '#NULL!', 'Err:', '#ERR')


def soffice(args, timeout=240):
    r = subprocess.run(['soffice', '--headless', '--norestore'] + args, capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0


def recalc(xlsx, work):
    """LibreOffice opens the file, recalculates every formula, saves a copy with values (what a buyer sees)."""
    os.makedirs(work, exist_ok=True)
    soffice(['--calc', '--convert-to', 'xlsx', '--outdir', work, xlsx])
    out = os.path.join(work, os.path.basename(xlsx))
    if not os.path.exists(out):
        raise RuntimeError('LibreOffice recalculation failed')
    return out


def scan(calc_path):
    """Formula errors and the values every tab shows after recalculation."""
    wb = load_workbook(calc_path, data_only=True)
    errs = []
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith(ERRORS):
                    errs.append(f'{ws.title}!{c.coordinate} {c.value}')
    return errs, wb.sheetnames


def trim(src, dst, pad=40):
    """Cut the empty page margins so a shot is just the tab's content."""
    from PIL import Image, ImageChops
    im = Image.open(src).convert('RGB')
    bg = Image.new('RGB', im.size, im.getpixel((2, 2)))
    box = ImageChops.difference(im, bg).getbbox()
    if box:
        box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
        im = im.crop(box)
    im.save(dst)


def shots(calc_path, tabs, anchors, shots_dir, work):
    """Export the recalculated copy to PDF (one page per tab) and save each page as <anchor>.png."""
    soffice(['--convert-to', 'pdf', '--outdir', work, calc_path])
    pdf = os.path.splitext(os.path.join(work, os.path.basename(calc_path)))[0] + '.pdf'
    import pypdf
    n = len(pypdf.PdfReader(pdf).pages)
    os.makedirs(shots_dir, exist_ok=True)
    for f in os.listdir(shots_dir):
        os.remove(os.path.join(shots_dir, f))
    subprocess.run(['pdftoppm', '-r', '150', '-png', pdf, os.path.join(work, 'pg')], capture_output=True, timeout=300)
    pages = sorted(f for f in os.listdir(work) if f.startswith('pg') and f.endswith('.png'))
    names = []
    for tab, page in zip(tabs, pages):
        a = anchors.get(tab, re.sub(r'\W+', '-', tab).lower())
        trim(os.path.join(work, page), os.path.join(shots_dir, a + '.png'))
        names.append(a + '.png')
    return n, names


def build(brief, pdir, files_dir, shots_dir, max_mb):
    spec = dict(brief['spec'])
    problems, needs = gen.validate_spec(spec)
    if needs:
        return None, {"ok": False, "blocked": "needs_module", "needs_module": needs}
    if problems:
        return None, {"ok": False, "blocked": "spec problems", "problems": problems}
    name = re.sub(r'[^A-Za-z0-9]+', '-', spec['title']).strip('-') + '.xlsx'
    os.makedirs(files_dir, exist_ok=True)
    for f in os.listdir(files_dir):
        if f.endswith('.xlsx'):
            os.remove(os.path.join(files_dir, f))
    path = os.path.join(files_dir, name)
    res = gen.build(spec, path)
    work = os.path.join(pdir, 'work'); shutil.rmtree(work, ignore_errors=True)
    calc = recalc(path, work)
    errs, tabs = scan(calc)
    anchors = {t: a for a, t, m in res['sheets']}
    n_pages, shot_files = shots(calc, tabs, anchors, shots_dir, work)
    mb = os.path.getsize(path) / 1e6
    rec = {"files": [{"name": name, "mb": round(mb, 2), "tabs": len(tabs)}], "tabs": tabs,
           "page_modules": [[a, m] for a, t, m in res['sheets']], "nav": res['nav'], "formula_errors": errs[:50],
           "export_pages": n_pages, "shots": shot_files, "overflow": [], "links": len(res['nav']) * len(tabs),
           "size_px": [1650, 1275]}
    ok = mb <= max_mb and not errs and n_pages == len(tabs)
    return rec, {"ok": ok, "tabs": len(tabs), "mb": round(mb, 2), "formula_errors": len(errs), "export_pages": n_pages, "shots": len(shot_files)}
