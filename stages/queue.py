"""Stage 9: Queue. Package a checked product for the Review Queue page.

  python3 stages/queue.py <pid>  -> data/products/<pid>/queue/NN.jpg and queue.json
queue.json = {"doc": product row for the page's database (collection "products", id = pid),
              "files": {published path: local path}}  (published as p/<pid>/NN.jpg)
The session then publishes the files to the Review Queue artifact and writes the row with ArtifactData.
"""
import json, os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

LINE_NAMES = {'planner': 'Digital planners'}


def run(pid):
    from PIL import Image
    d = store.product_dir(pid)
    rd = lambda k: store.read(os.path.join(d, f'{k}.json'))
    brief, build, listing, check, bcheck = rd('brief'), rd('build'), rd('listing'), rd('check'), rd('brief.check')
    if not check:
        return {"ok": False, "blocked": "product has not been checked"}
    ins = store.read(os.path.join(store.type_dir(brief['type_id']), 'insights.json'))
    ev = store.read(os.path.join(store.type_dir(brief['type_id']), 'evidence.json'))
    qd = os.path.join(d, 'queue'); shutil.rmtree(qd, ignore_errors=True); os.makedirs(qd)
    srcs = [os.path.join(d, 'photos', f) for f in sorted(os.listdir(os.path.join(d, 'photos'))) if f.startswith('photo-')]
    srcs += [os.path.join(d, 'shots', f) for f in build['shots']]
    files = {}
    for i, s in enumerate(srcs, 1):
        im = Image.open(s).convert('RGB'); im.thumbnail((1600, 1600))
        out = os.path.join(qd, f'{i:02d}.jpg'); im.save(out, quality=84)
        files[f'p/{pid}/{i:02d}.jpg'] = out

    comp_by_id = {c['id']: c for c in ins['complaints']}
    fixes = {f['complaint'].split(':', 1)[-1]: f for f in brief['fixes']}
    waived = {w['ref']: w['reason'] for w in brief.get('waived', [])}
    complaints = []
    for row in bcheck['coverage']:
        kind, _, cid = row['ref'].partition(':')
        if kind != 'complaint':
            continue
        c = comp_by_id[cid]
        how = fixes[cid]['how'] if cid in fixes else waived.get(row['ref'], '')
        q = c['quotes'][0]['text'] if c['quotes'] else ''
        complaints.append({"theme": c['theme'], "count": c['count'], "state": row['state'], "how": how, "quote": q[:180]})
    must = {r for m in brief['must_haves'] for r in m['evidence']}
    standard = []
    for row in bcheck['coverage']:
        if row['ref'].startswith('feature:'):
            how = next((m['what'] for m in brief['must_haves'] if row['ref'] in m['evidence']), waived.get(row['ref'], ''))
            standard.append({"name": row['theme'], "share": row.get('share'), "state": row['state'], "how": how})
    unique = [{"name": u['name'], "what": u['what'], "why": u['why'], "verified_absent": bool(u.get('verified_absent'))} for u in brief['unique']]
    comps = [{"title": L['title'][:110], "shop": L['shop'], "price": L['price'], "mo_revenue": L['mo_revenue'],
              "total_sales": L['total_sales'], "img": L.get('image', '')} for L in ev['listings'][:8]]
    cov = check['coverage']
    evidence = {
        "positioning": brief['positioning'],
        "basis": {"listings": ins['basis']['listings'], "reviews": ins['basis']['reviews'], "shops": len(ev['shops']),
                  "refreshed": ev['refreshed_at'], "feature_sources": ins['basis']['feature_sources']},
        "market": {k: ev['market'].get(k) for k in ('monthly_searches', 'competing_listings', 'best_price_band')},
        "checks": {"pass": check['pass'], "coverage": f"{sum(i['found'] for i in cov)}/{len(cov)}", "coverage_ok": all(i['found'] for i in cov),
                   "text_sim": check['clone']['max_text_sim'], "closest": check['clone']['text']['closest'],
                   "img_sim": check['clone']['max_image_sim'], "visual": check.get('visual', [])},
        "complaints": complaints, "standard": standard, "unique": unique, "competitors": comps}
    doc = {"title": brief['spec']['title'] if not listing else listing.get('hero_title') or brief['spec']['title'],
           "line": LINE_NAMES.get(brief['line'], brief['line']), "lane": brief['type_id'], "price": listing['price'],
           "images": list(files), "status": "queued" if check['pass'] else "needs_help", "created": int(time.time() * 1000),
           "listing": {"title": listing['title'], "tags": listing['tags'], "description": listing['description']},
           "files": build['files'], "evidence": evidence, "engine": {"brief_id": brief['brief_id'], "product_id": pid}}
    store.write(os.path.join(d, 'queue.json'), {"doc": doc, "files": files})
    return {"ok": True, "images": len(files), "queue": os.path.join(d, 'queue.json')}


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1]), indent=1))
