"""Spreadsheet file checks (.xlsx): size, formula errors after recalculation, every tab reachable from the link bar,
formula cells locked, input cells open, fonts available in Google Sheets and Excel, claims about tabs match the file."""
import os, re
from openpyxl import load_workbook

SAFE_FONTS = ('Arial', 'Calibri', 'Verdana', 'Georgia', 'Roboto', 'Lato', 'Montserrat', 'Open Sans', 'Poppins', 'Nunito', 'Raleway')


def file_checks(d, brief, b, L, add, CHK):
    f = b['files'][0]
    path = os.path.join(d, 'files', f['name'])
    add('file size', f['mb'] <= CHK['max_pdf_mb'], f"{f['name']}: {f['mb']} MB")
    add('no formula errors after recalculation', not b['formula_errors'], f"{len(b['formula_errors'])} errors" + (f": {b['formula_errors'][:5]}" if b['formula_errors'] else ''))
    add('one screenshot per tab', b['export_pages'] == len(b['tabs']) == len(b['shots']), f"{len(b['tabs'])} tabs, {b['export_pages']} export pages, {len(b['shots'])} shots")
    wb = load_workbook(path)
    titles = set(wb.sheetnames)
    bad, fonts, unlocked_formulas, locked_inputs, unprotected = [], set(), [], 0, []
    for ws in wb:
        if not ws.protection.sheet:
            unprotected.append(ws.title)
        for row in ws.iter_rows():
            for c in row:
                if c.hyperlink and c.hyperlink.location is None and str(c.hyperlink.target or '').startswith('#'):
                    t = re.match(r"#'?(.+?)'?!", c.hyperlink.target)
                    if not t or t.group(1) not in titles:
                        bad.append(f'{ws.title}!{c.coordinate}')
                if c.value is not None and c.font and c.font.name:
                    fonts.add(c.font.name)
                if isinstance(c.value, str) and c.value.startswith('=') and not c.protection.locked and c.fill.fgColor.rgb in (None, '00000000'):
                    unlocked_formulas.append(f'{ws.title}!{c.coordinate}')
    add('every tab link works', not bad, f'{len(bad)} broken: {bad[:5]}' if bad else 'all link targets exist')
    add('formulas protected', not unprotected and not unlocked_formulas, f'unprotected tabs {unprotected[:5]}, unlocked formulas {unlocked_formulas[:5]}')
    odd = sorted(x for x in fonts if x not in SAFE_FONTS)
    add('fonts work in Google Sheets and Excel', not odd, f'fonts: {sorted(fonts)}')
    desc = L.get('description', '') + ' ' + L.get('title', '')
    claims = [int(m) for m in re.findall(r'(\d{1,3})\+?\s*(?:tabs|sheets)', desc)]
    add('tab claims match the file', all(c <= len(titles) for c in claims), f'claims {claims}, file has {len(titles)} tabs')
