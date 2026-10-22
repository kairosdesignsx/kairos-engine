"""Stage 5: Build. Brief spec -> product files, shots and a build record, using the product line's own builder.

  run <product_id>   -> data/products/<pid>/files/*, shots/*.png, build.json
Each line provides lines/<line>/gen.py (validate_spec, capabilities) and lines/<line>/make.py (build).
Blocks, saying exactly what is missing, when the brief needs a module the line cannot build yet:
the session then writes the module into lines/<line>/gen.py, adds it to the line test, and runs again.
"""
import importlib, json, os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

CHK = store.CONFIG['check']


def line_dir(line):
    return os.path.join(store.ROOT, 'lines', line)


def line_mod(line, name):
    d = line_dir(line)
    if d not in sys.path:
        sys.path.insert(0, d)
    for m in ('gen', 'make', 'checks', 'photos'):  # the lines share module names: load fresh per line
        if m in sys.modules and not (getattr(sys.modules[m], '__file__', '') or '').startswith(d):
            del sys.modules[m]
    return importlib.import_module(name)


def gen_for(line):
    return line_mod(line, 'gen')


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
    files_dir = os.path.join(pdir, 'files'); shots_dir = os.path.join(pdir, 'shots')
    shutil.rmtree(files_dir, ignore_errors=True); shutil.rmtree(shots_dir, ignore_errors=True)
    os.makedirs(files_dir); os.makedirs(shots_dir)
    make = line_mod(brief['line'], 'make')
    rec, result = make.build(brief, pdir, files_dir, shots_dir, CHK['max_pdf_mb'])
    if rec is None:
        return result
    rec.update({"product_id": pid, "brief_id": brief['brief_id'], "built_at": store.now(), "line": brief['line']})
    store.write(os.path.join(pdir, 'build.json'), rec)
    return result


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[2] if sys.argv[1] == 'run' else sys.argv[1]), indent=1))
