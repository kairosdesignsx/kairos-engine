"""Spreadsheet line: build a full workbook, recalculate in LibreOffice, and require zero formula errors,
working tab links, locked formulas, one export page per tab, and sensible numbers on the dashboard."""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'lines', 'spreadsheet'))
import gen, make
from openpyxl import load_workbook

SPEC = {'title': 'Test Budget', 'subtitle': 'test', 'year': 2027, 'theme': 'sage', 'sample_data': True, 'sections': [
    {'module': 'start_here', 'steps': [['Open it', 'x'], ['Fill Setup', 'y']], 'tip': 't'}, {'module': 'setup'}, {'module': 'months', 'log_rows': 40},
    {'module': 'dashboard'}, {'module': 'bills'}, {'module': 'debt'}, {'module': 'savings'}]}


def main():
    work = tempfile.mkdtemp()
    path = os.path.join(work, 'Test-Budget.xlsx')
    res = gen.build(SPEC, path)
    calc = make.recalc(path, os.path.join(work, 'calc'))
    errs, tabs = make.scan(calc)
    assert not errs, errs[:10]
    n, shots = make.shots(calc, tabs, {t: a for a, t, m in res['sheets']}, os.path.join(work, 'shots'), os.path.join(work, 'calc'))
    assert n == len(tabs) == len(shots), (n, len(tabs), len(shots))
    wb = load_workbook(calc, data_only=True)
    d = wb['Dashboard']
    assert d['C7'].value == 3000 and abs(d['D7'].value - 1992.09) < 0.01, (d['C7'].value, d['D7'].value)
    assert d['C8'].value in (None, ''), 'months with nothing logged must stay empty'
    errors = []
    sys.path.insert(0, os.path.join(HERE, '..', 'lines', 'spreadsheet'))
    import checks
    b = {'files': [{'name': 'Test-Budget.xlsx', 'mb': os.path.getsize(path) / 1e6}], 'formula_errors': errs, 'export_pages': n, 'tabs': tabs, 'shots': shots}
    os.makedirs(os.path.join(work, 'p', 'files'), exist_ok=True); os.replace(path, os.path.join(work, 'p', 'files', 'Test-Budget.xlsx'))
    checks.file_checks(os.path.join(work, 'p'), {}, b, {'description': '18 tabs'}, lambda name, ok, det: errors.append((name, det)) if not ok else None, {'max_pdf_mb': 19.5})
    assert not errors, errors
    print('ok', len(tabs), 'tabs', round(b['files'][0]['mb'], 2), 'MB')


if __name__ == '__main__':
    main()
