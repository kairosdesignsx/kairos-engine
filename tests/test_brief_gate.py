"""The brief gate must reject a brief that ignores evidence. Uses the real p-adhd-001 brief as a base."""
import copy, json, os, sys, tempfile
sys.path.insert(0, 'stages'); sys.path.insert(0, 'lib')
import brief as B

base = json.load(open('data/products/p-adhd-001/brief.json'))

def run(mutate, expect):
    b = copy.deepcopy(base); mutate(b)
    d = tempfile.mkdtemp(); p = os.path.join(d, 'brief.json'); json.dump(b, open(p, 'w'))
    r = B.check(p)
    hit = [x for x in r['problems'] if expect in x]
    print(('PASS' if (not r['pass'] and hit) else 'FAIL'), '|', expect, '|', (hit or r['problems'] or ['(no problems)'])[0][:110])
    return bool(hit) and not r['pass']

ok = all([
    run(lambda b: b.update(fixes=[f for f in b['fixes'] if f['complaint'] != 'complaint:c_download']), 'c_download'),
    run(lambda b: b.update(must_haves=[m for m in b['must_haves'] if 'feature:goodnotes' not in m['evidence']], unique=[dict(u, evidence=[e for e in u['evidence'] if e != 'feature:goodnotes']) for u in b['unique']]), 'goodnotes'),
    run(lambda b: b['unique'][0].update(evidence=['praise:p_look']), 'unique/'),
    run(lambda b: b['fixes'][0].update(evidence=['complaint:c_made_up']), 'unknown evidence'),
    run(lambda b: b['seo'].update(tags=b['seo']['tags'][:12] + ['this tag is far too long']), 'too long'),
    run(lambda b: b['price'].update(amount=99), 'price'),
])
b = copy.deepcopy(base); b['spec']['sections'].append({'module': 'unicorn_pages'})
d = tempfile.mkdtemp(); p = os.path.join(d, 'brief.json'); json.dump(b, open(p, 'w'))
nm = B.check(p)['needs_module']
print(('PASS' if nm == ['unicorn_pages'] else 'FAIL'), '| unknown page type goes to Build as needs_module |', nm)
ok = ok and nm == ['unicorn_pages']
print('gate ok' if ok else 'gate BROKEN')
