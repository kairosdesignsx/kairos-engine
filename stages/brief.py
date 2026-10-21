"""Stage 4: Brief. Turn insights into a design brief where every decision cites evidence.

  prepare <type_id> [--line planner]  -> data/types/<type>/brief-in.json  (digest for the brief writer)
  check   <brief.json>                -> pass/fail with every problem listed; needs_module list for Build

The gate (check) enforces Darren's rule: the brief must account for everything the market says.
  - every significant complaint is fixed or explicitly waived with a reason
  - every standard feature (most top sellers have it) is included or waived with a reason
  - at least N unique features, each tied to a gap (complaint, wish, or a feature few or none show)
  - every evidence reference points at something real in insights
  - SEO and price rules; the spec must be buildable by the product line
"""
import importlib, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

CFG = store.CONFIG['brief']


def threshold(ins):
    return max(5, round(0.02 * ins['basis']['reviews']))


def line_module(line):
    sys.path.insert(0, os.path.join(store.ROOT, 'lines', line))
    return importlib.import_module('gen')


def prepare(type_id):
    types = store.read(os.path.join(store.ROOT, 'config', 'types.json'))
    t = types[type_id]
    ins = store.read(os.path.join(store.type_dir(type_id), 'insights.json'))
    ev = store.read(os.path.join(store.type_dir(type_id), 'evidence.json'))
    th = threshold(ins)
    q = lambda xs: [{"text": x['text'][:200], "stars": x['stars']} for x in xs[:3]]
    digest = {
        "type_id": type_id, "product_type": t['name'], "format": t['format'], "line": t['line'],
        "rules": {"significant_complaint_count": th, "min_unique": CFG['min_unique_features'],
                  "evidence_ref_kinds": ["complaint:<id>", "praise:<id>", "wish:<id>", "feature:<id>", "price:<field>",
                                         "keyword:<tag>", "listing:<listing_id>", "market:<field>", "look:<style>"]},
        "basis": ins['basis'],
        "market": ev['market'],
        "must_address": [{"ref": f"complaint:{c['id']}", "theme": c['theme'], "count": c['count'], "quotes": q(c['quotes'])}
                         for c in ins['complaints'] if c['count'] >= th],
        "other_complaints": [{"ref": f"complaint:{c['id']}", "theme": c['theme'], "count": c['count']} for c in ins['complaints'] if c['count'] < th],
        "praise": [{"ref": f"praise:{c['id']}", "theme": c['theme'], "count": c['count'], "quotes": q(c['quotes'])} for c in ins['praise']],
        "wishes": [{"ref": f"wish:{c['id']}", "theme": c['theme'], "count": c['count']} for c in ins['wishes']],
        "features": [{"ref": f"feature:{f['id']}", "name": f['name'], "tier": f['tier'], "share": f['share'], "revenue_share": f['revenue_share']} for f in ins['features']],
        "standard_features": [f"feature:{f['id']}" for f in ins['features'] if f['tier'] == 'standard'],
        "price": ins['price'],
        "keywords": ins['keywords'][:30],
        "looks": [{"ref": f"look:{l['style']}", "share": l['share']} for l in ins['looks']],
        "top_listings": [{"ref": f"listing:{L['listing_id']}", "title": L['title'][:120], "shop": L['shop'], "price": L['price'],
                          "mo_revenue": L['mo_revenue'], "total_sales": L['total_sales']} for L in ev['listings'][:15]],
        "capabilities": line_module(t['line']).capabilities(),
        "style_rules": store.read(os.path.join(store.DATA, 'learn', 'style-rules.json'), []),
        "past_briefs": [b for b in (store.read(os.path.join(store.DATA, 'learn', 'briefs-index.json'), []) or []) if b.get('type_id') == type_id],
    }
    path = store.write(os.path.join(store.type_dir(type_id), 'brief-in.json'), digest)
    return {"brief_in": path, "must_address": len(digest['must_address']), "standard_features": digest['standard_features'], "threshold": th}


def _refs_ok(refs, ins, ev):
    ids = {
        'complaint': {c['id'] for c in ins['complaints']}, 'praise': {c['id'] for c in ins['praise']},
        'wish': {c['id'] for c in ins['wishes']}, 'feature': {f['id'] for f in ins['features']},
        'price': set(ins['price']), 'keyword': {k['tag'] for k in ins['keywords']} | {t['tag'] for t in ev['tags']},
        'listing': {L['listing_id'] for L in ev['listings']}, 'market': set(ev['market']), 'look': {l['style'] for l in ins['looks']},
    }
    bad = []
    for r in refs:
        kind, _, val = r.partition(':')
        if val not in ids.get(kind, set()):
            bad.append(r)
    return bad


def check(brief_path):
    b = store.read(brief_path)
    problems = []
    try:
        store.validate(b, 'brief')
    except ValueError as e:
        return {"pass": False, "problems": [str(e)], "needs_module": []}
    ins = store.read(os.path.join(store.type_dir(b['type_id']), 'insights.json'))
    ev = store.read(os.path.join(store.type_dir(b['type_id']), 'evidence.json'))

    # 1. every evidence reference must exist
    sections = [('must_haves', b['must_haves']), ('fixes', b['fixes']), ('unique', b['unique'])]
    for name, items in sections:
        for it in items:
            bad = _refs_ok(it['evidence'], ins, ev)
            if bad:
                problems.append(f"{name}/{it['id']}: unknown evidence {bad}")
    for name in ('look', 'price'):
        bad = _refs_ok(b[name].get('evidence', []), ins, ev)
        if bad:
            problems.append(f"{name}: unknown evidence {bad}")

    # 2. coverage: significant complaints and standard features handled or waived
    waived = {w['ref']: w['reason'] for w in b.get('waived', [])}
    fixed = {f['complaint'] for f in b['fixes']} | {r for f in b['fixes'] for r in f['evidence']}
    th = threshold(ins)
    coverage = []
    for c in ins['complaints']:
        if c['count'] < th:
            continue
        ref = f"complaint:{c['id']}"
        state = 'fixed' if (ref in fixed or c['id'] in fixed) else 'waived' if ref in waived else 'MISSING'
        coverage.append({"ref": ref, "theme": c['theme'], "count": c['count'], "state": state})
        if state == 'MISSING':
            problems.append(f"complaint {c['id']} ({c['count']} reviews: {c['theme']}) is neither fixed nor waived")
    included = {r for m in b['must_haves'] for r in m['evidence']} | {r for u in b['unique'] for r in u['evidence']}
    for f in ins['features']:
        if f['tier'] != 'standard':
            continue
        ref = f"feature:{f['id']}"
        state = 'included' if ref in included else 'waived' if ref in waived else 'MISSING'
        coverage.append({"ref": ref, "theme": f['name'], "share": f['share'], "state": state})
        if state == 'MISSING':
            problems.append(f"standard feature {f['id']} ({f['share']:.0%} of top sellers) is neither included nor waived")

    # 3. unique features must answer a gap
    gap_kinds = {'complaint', 'wish'}
    open_feats = {f['id'] for f in ins['features'] if f['tier'] in ('rare', 'nobody', 'not_seen')}
    for u in b['unique']:
        ok = any(r.split(':')[0] in gap_kinds or (r.startswith('feature:') and r.split(':', 1)[1] in open_feats) for r in u['evidence'])
        if not ok:
            problems.append(f"unique/{u['id']}: evidence must point at a complaint, a wish, or a feature few or no top sellers show")
    if len(b['unique']) < CFG['min_unique_features']:
        problems.append(f"needs at least {CFG['min_unique_features']} unique features")

    # 4. SEO and price
    tags = b['seo']['tags']
    if len({t.lower() for t in tags}) != 13:
        problems.append('13 different tags required')
    for t in tags:
        if len(t) > 20 or re.search(r'[^a-zA-Z0-9 \'&-]', t):
            problems.append(f'tag not allowed by Etsy: "{t}"')
    if len(b['seo']['title']) > 140:
        problems.append('title over 140 characters')
    pr = ins['price']
    if not (pr['p25'] * 0.5 <= b['price']['amount'] <= pr['p75'] * 1.5):
        problems.append(f"price {b['price']['amount']} far outside the market ({pr['p25']} to {pr['p75']}); justify or change")

    # 5. buildable?
    gen = line_module(b['line'])
    spec_problems, needs = gen.validate_spec(b['spec'])
    problems += [f'spec: {x}' for x in spec_problems]
    unique_modules = {m for u in b['unique'] for m in u.get('modules', [])} | {m for f in b['fixes'] for m in f.get('modules', [])}
    used = {s['module'] for s in b['spec'].get('sections', [])}
    for m in unique_modules - used:
        problems.append(f'module {m} is named in fixes or unique but not used in spec.sections')

    out = {"pass": not problems, "problems": problems, "needs_module": needs, "coverage": coverage,
           "summary": {"fixed": sum(1 for c in coverage if c['state'] == 'fixed'), "included": sum(1 for c in coverage if c['state'] == 'included'),
                       "waived": sum(1 for c in coverage if c['state'] == 'waived'), "missing": sum(1 for c in coverage if c['state'] == 'MISSING'),
                       "unique": len(b['unique'])}}
    store.write(brief_path.replace('.json', '.check.json'), out)
    return out


if __name__ == '__main__':
    cmd, arg = sys.argv[1], sys.argv[2]
    print(json.dumps(prepare(arg) if cmd == 'prepare' else check(arg), indent=1))
