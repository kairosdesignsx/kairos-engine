"""Stage 9: Queue. Package a checked product for the Review Queue page.

  python3 stages/enqueue.py <pid>  -> data/products/<pid>/queue/NN.jpg and queue.json
queue.json = {"doc": product row for the page's database (collection "products", id = pid),
              "files": {published path: local path}}  (published as p/<pid>/NN.jpg)
The session then publishes the files to the Review Queue artifact and writes the row with ArtifactData.
"""
import json, os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

LINE_NAMES = {'planner': 'Digital planners', 'spreadsheet': 'Spreadsheets'}
DEVICE_TEST = {
    'planner': "Before approving: open the PDF in Goodnotes (or your tablet app), tap a few month tabs and dates, and write on one page. The listing names apps we have not tested on a real device yet.",
    'spreadsheet': "Before approving: upload the .xlsx to Google Drive and open it with Google Sheets, then open it in Excel. Check the charts, the dropdowns, the Ready check, and whether the formulas stay locked in Sheets (the listing only promises locked in Excel).",
}


def _rounds(d):
    """One line per independent check round: promises found and issues by severity."""
    import re as _re
    files = sorted((int(_re.search(r'round(\d+)', f).group(1)), f) for f in os.listdir(d) if _re.fullmatch(r'coverage-out\.round\d+\.json', f))
    files.append((len(files) + 1, 'coverage-out.json'))
    out = []
    for n, f in files:
        c = store.read(os.path.join(d, f)) or {}
        items = c.get('items', []); vis = c.get('visual', [])
        sev = {k: sum(1 for v in vis if v.get('severity') == k) for k in ('high', 'medium', 'low')}
        top = (next((v['issue'] for v in vis if v.get('severity') == 'high'), None) or next((v['issue'] for v in vis if v.get('severity') == 'medium'), None)
               or next((i['note'] for i in items if not i.get('found')), ''))
        out.append({"round": n, "found": sum(1 for i in items if i.get('found')), "of": len(items), **sev, "main": top[:220]})
    return out


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
    # full brief and research, readable on the review page
    sec_names = []
    for sec in brief['spec'].get('sections', []):
        sec_names.append(sec.get('label') or {'cover': 'Cover', 'index': 'Contents', 'year': 'Year at a glance', 'calendar': 'Months, weeks and days'}.get(sec['module'], sec['module']))
    brief_full = {
        "positioning": brief['positioning'],
        "must_haves": [{"what": m['what'], "evidence": m['evidence']} for m in brief['must_haves']],
        "fixes": [{"complaint": comp_by_id.get(f['complaint'].split(':', 1)[-1], {}).get('theme', f['complaint']),
                   "count": comp_by_id.get(f['complaint'].split(':', 1)[-1], {}).get('count'), "how": f['how']} for f in brief['fixes']],
        "unique": [{"name": u['name'], "what": u['what'], "why": u['why'], "evidence": u['evidence']} for u in brief['unique']],
        "waived": brief.get('waived', []),
        "look": {"direction": brief['look']['direction'], "avoid": brief['look'].get('avoid', []),
                 "palette": {k: v for k, v in (brief['look']['theme'] if isinstance(brief['look']['theme'], dict) else {}).items() if isinstance(v, str) and v.startswith('#')},
                 "fonts": [x for x in ((brief['look']['theme'] or {}).get('display') if isinstance(brief['look']['theme'], dict) else None, (brief['look']['theme'] or {}).get('body') if isinstance(brief['look']['theme'], dict) else None) if x]},
        "price": brief['price'], "seo": brief['seo'],
        "photos": [{"shows": ph['shows'], "proves": ph.get('proves', '')} for ph in brief['photos']],
        "sections": sec_names,
        "revisions": brief.get('revisions', []),
        "check_rounds": _rounds(d),
    }
    ev_listings = sorted(ev['listings'], key=lambda L: L.get('rank') or 99)
    research = {
        "query": ev['query'], "refreshed": ev['refreshed_at'], "basis": ins['basis'], "market": ev['market'],
        "listings": [{"rank": L.get('rank'), "title": L['title'][:140], "shop": L['shop'], "price": L['price'], "mo_revenue": L['mo_revenue'],
                      "total_sales": L['total_sales'], "reviews": L.get('reviews'), "age_months": L.get('age_months'), "url": L.get('url', '')} for L in ev_listings],
        "complaints": [{"theme": c['theme'], "count": c['count'], "quotes": [q['text'][:220] for q in c['quotes']]} for c in ins['complaints']],
        "praise": [{"theme": c['theme'], "count": c['count'], "quotes": [q['text'][:220] for q in c['quotes']]} for c in ins['praise']],
        "wishes": [{"theme": c['theme'], "count": c['count']} for c in ins['wishes']],
        "features": [{"name": f['name'], "tier": f['tier'], "share": f['share'], "revenue_share": f.get('revenue_share')} for f in ins['features']],
        "price": ins['price'],
        "keywords": [{"tag": k['tag'], "used_by_top": k['used_by_top']} for k in ins['keywords'][:24]],
        "shops": [{"shop": s_['shop'], "rating": s_.get('rating_avg'), "reviews": s_.get('review_count')} for s_ in ev['shops']],
    }
    doc = {"title": brief['spec']['title'] if not listing else listing.get('hero_title') or brief['spec']['title'],
           "line": LINE_NAMES.get(brief['line'], brief['line']), "lane": brief['type_id'], "price": listing['price'], "launch_sale": listing.get('launch_sale') or brief['price'].get('launch_sale'),
           "images": list(files), "status": "queued" if check['pass'] else "needs_help", "created": int(time.time() * 1000),
           "listing": {"title": listing['title'], "tags": listing['tags'], "description": listing['description']},
           "files": build['files'], "evidence": evidence, "brief": brief_full, "research": research, "engine": {"brief_id": brief['brief_id'], "product_id": pid},
           "claude_note": ' '.join(check.get('notes', []) + [DEVICE_TEST.get(brief['line'], DEVICE_TEST['planner'])])}
    store.write(os.path.join(d, 'queue.json'), {"doc": doc, "files": files})
    _handoff(pid, d, listing, build)
    return {"ok": True, "images": len(files), "queue": os.path.join(d, 'queue.json')}


def _handoff(pid, d, listing, build):
    """Everything the laptop needs to review and list the product, mirroring Kairos\\data\\products\\<pid>\\:
    files/ (what the buyer downloads), photos/ (listing photos in order), listing.json and listing.txt (copy-paste ready)."""
    import shutil
    out = os.path.join(store.DATA, 'handoff', pid)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, 'files')); os.makedirs(os.path.join(out, 'photos'))
    for f in build['files']:
        shutil.copy(os.path.join(d, 'files', f['name']), os.path.join(out, 'files', f['name']))
    photos = sorted(f for f in os.listdir(os.path.join(d, 'photos')) if f.startswith('photo-') and f.endswith('.jpg'))
    for f in photos:
        shutil.copy(os.path.join(d, 'photos', f), os.path.join(out, 'photos', f))
    shutil.copy(os.path.join(d, 'listing.json'), os.path.join(out, 'listing.json'))
    alt = listing.get('alt') or {}
    b = store.read(os.path.join(d, 'brief.json')) or {}
    sale = listing.get('launch_sale') or (b.get('price') or {}).get('launch_sale')  # listing.json carries it; older listings fall back to the brief
    price_lines = ['PRICE', f"${listing['price']}"]
    if sale:
        price_lines += ['', 'LAUNCH SALE (set up by hand: Etsy cannot do this from the API)',
                        f"{sale['percent']}% off for {sale['days']} days, so buyers see ${float(sale.get('sale_price') or 0):.2f} with ${listing['price']} crossed out.",
                        'Shop Manager > Marketing > Sales and discounts > New special offer > Run a sale > percentage off,',
                        f"{sale['percent']}%, {sale['days']} days, select this listing only."]
    lines = ['TITLE', listing['title'], ''] + price_lines + ['', 'TAGS', ', '.join(listing['tags']), '',
             'DESCRIPTION', listing['description'], '', 'PHOTOS (upload in this order, with this alt text)']
    for f in photos:
        lines.append(f"{f}: {alt.get(f[len('photo-00-'):-4], '')}")
    lines += ['', 'DIGITAL FILES', *[f['name'] for f in build['files']]]
    open(os.path.join(out, 'listing.txt'), 'w').write('\n'.join(lines) + '\n')
    return out


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1]), indent=1))
