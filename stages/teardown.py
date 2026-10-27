"""Stage 2: Teardown. Who sells this product type best, and what do their buyers say?

Agent stage in two rounds. The script decides exactly which EverBee calls to make,
the session (or its subagents) makes them, and the script harvests the results
verbatim from the session transcripts. Nothing is retyped by the model.

  plan-a     -> calls-a.json : market check, top listings by revenue and by all-time sales (2 pages each), tag patterns
  collect-a  -> candidates.json + relevance.json (rules pre-mark; the session confirms or overrides)
  plan-b     -> calls-b.json : worst-first and newest reviews for the top shops, shop teardowns
  collect-b  -> data/types/<type>/evidence.json (schema-checked) + laptop photo job
"""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import harvest, parse, store

CFG = store.CONFIG['teardown']
TYPES = store.read(os.path.join(store.ROOT, 'config', 'types.json'))
COLUMNS = ["Product", "Shop Name", "Price", "Sales", "Revenue", "Total Sales", "Total Reviews", "Listing Age",
           "Total Favorites", "Total Views", "Conversion Rate", "Shop Age", "Total Shop Sales", "Tags", "URL", "Category"]
MAX_AGE_DAYS = 7  # harvested results older than this are not trusted


CACHE_DIR = os.path.join(store.DATA, 'everbee-cache')   # results saved across nights (sessions don't share transcripts)
CACHE_DAYS = {'mcp__EverBee__view_shop_reviews': 30, 'mcp__EverBee__analyze_shop': 30}  # others: MAX_AGE_DAYS


def _cache_key(name, inp):
    import hashlib
    return hashlib.sha1((name + json.dumps(inp, sort_keys=True)).encode()).hexdigest()[:16]


def _calls(since):
    """Transcript results from this session, plus saved results from earlier nights that are still fresh."""
    got = list(harvest.calls(since=since))
    if os.path.isdir(CACHE_DIR):
        now = time.time()
        for f in os.listdir(CACHE_DIR):
            r = store.read(os.path.join(CACHE_DIR, f)) or {}
            age_ok = now - r.get('saved', 0) <= CACHE_DAYS.get(r.get('tool'), MAX_AGE_DAYS) * 86400
            if r.get('tool') and age_ok:
                got.append((r['tool'], r['input'], r['text'], r.get('ts') or ''))
    return got


def _save(found):
    os.makedirs(CACHE_DIR, exist_ok=True)
    for c, m in found:
        if m and m[0]:
            name, inp = c['tool'], c['input']
            path = os.path.join(CACHE_DIR, _cache_key(name, inp) + '.json')
            if not os.path.exists(path):
                store.write(path, {"tool": name, "input": inp, "text": m[0], "ts": m[1], "saved": time.time()})


def tdir(type_id):
    return os.path.join(store.type_dir(type_id), 'teardown')


def _listings_call(query, order_by, page):
    params = {"search_term": query, "listing_type": "download", "order_by": order_by, "order_direction": "desc"}
    if page > 1:
        params["page"] = page
    return {"tool": "mcp__EverBee__view_listings", "input": {"params": params, "columns": COLUMNS}}


def plan_a(type_id):
    t = TYPES[type_id]
    q = t['query']
    calls = [{"tool": "mcp__EverBee__validate_product_idea", "input": {"product_idea": q}}]
    for order in ("est_mo_revenue", "est_total_sales"):
        for page in (1, 2):
            calls.append(_listings_call(q, order, page))
    calls.append({"tool": "mcp__EverBee__view_tag_patterns",
                  "input": {"params": {"search_term": q, "listing_type": "download", "order_by": "est_total_sales",
                                       "order_direction": "desc", "per_page": 20}}})
    path = store.write(os.path.join(tdir(type_id), 'calls-a.json'), {"type_id": type_id, "made": store.now(), "calls": calls})
    return path, calls


def _subset(want, have):
    """True if every key in want is in have with an equal value (recursing into dicts)."""
    if isinstance(want, dict):
        return isinstance(have, dict) and all(k in have and _subset(v, have[k]) for k, v in want.items())
    return want == have


def _find(calls_wanted, max_age_days=MAX_AGE_DAYS):
    """Newest harvested result for each wanted call. Returns list of (call, text|None)."""
    since = time.time() - max_age_days * 86400
    got = _calls(since)
    got.sort(key=lambda x: x[3] or '')
    out = []
    for c in calls_wanted:
        match = None
        for name, inp, txt, ts in got:
            if name == c['tool'] and _subset(c['input'], inp) and _strip_page_default(c['input']) == _strip_page_default(inp):
                match = (txt, ts)
        out.append((c, match))
    _save(out)
    return out


def _strip_page_default(inp):
    """Calls differ only by page; treat a missing page as page 1 so page 1 and page 2 never collide."""
    p = (inp or {}).get('params') or {}
    return p.get('page', 1)


def _missing(found):
    return [c for c, m in found if m is None]


def relevance(type_id, title):
    t = TYPES[type_id]
    s = ' ' + title.lower() + ' '
    inc = [w for w in t['include_any'] if w in s]
    exc = [w for w in t['exclude_any'] if w in s]
    foc = [w for w in t['focus_any'] if w in s]
    if exc:
        return False, f"excluded: {', '.join(exc)}", bool(foc)
    if not inc:
        return False, "no format match in title", bool(foc)
    return True, f"format: {', '.join(inc[:3])}", bool(foc)


def collect_a(type_id):
    plan = store.read(os.path.join(tdir(type_id), 'calls-a.json'))
    found = _find(plan['calls'])
    miss = _missing(found)
    if miss:
        return {"ok": False, "missing": miss}
    market, listings, tags, sources = {}, {}, [], []
    for c, (txt, ts) in found:
        st, met, texts = harvest.widget(txt)
        sources.append({"tool": c['tool'], "input": c['input'], "at": ts})
        if c['tool'].endswith('validate_product_idea'):
            market = {
                "opportunity_score": parse.num((met.get('Opportunity Score') or '').split('/')[0]),
                "monthly_searches": parse.num(met.get('Monthly Searches')),
                "competing_listings": parse.num(met.get('Competing Listings')),
                "top_seller_revenue": parse.num(met.get('Top Seller Revenue')),
                "new_sellers_in_top_pct": parse.num(met.get('New Sellers in Top')),
                "summary": next((x for x in texts if len(x) > 80), ''),
                "best_price_band": next((x.replace('Best price band ', '') for x in texts if x.startswith('Best price band')), ''),
            }
        elif c['tool'].endswith('view_listings'):
            order = c['input']['params']['order_by']
            page = c['input']['params'].get('page', 1)
            for i, r in enumerate(st.get('rows', [])):
                lid = parse.listing_id(r.get('url') or r.get('title_href'))
                if not lid:
                    continue
                rank = (page - 1) * 20 + i + 1
                L = listings.setdefault(lid, {
                    "listing_id": lid, "title": r.get('title', ''), "shop": r.get('shop_name', ''),
                    "price": parse.num(r.get('price')), "mo_sales": parse.num(r.get('est_mo_sales')),
                    "mo_revenue": parse.num(r.get('est_mo_revenue')), "total_sales": parse.num(r.get('est_total_sales')),
                    "reviews": parse.num(r.get('est_reviews')), "favorites": parse.num(r.get('num_favorers')),
                    "views": parse.num(r.get('views')), "age_months": parse.num(r.get('listing_age_in_months')),
                    "conversion": parse.num(r.get('conversion_rate')), "shop_age_months": parse.num(r.get('shop_age_month')),
                    "shop_sales": parse.num(r.get('transaction_sold_count')),
                    "tags": [x.strip() for x in (r.get('tags') or '').split(',') if x.strip()],
                    "url": r.get('url') or r.get('title_href') or '', "image": r.get('title_image_preview') or '',
                    "ranks": {}})
                L['ranks'][order] = rank
        elif c['tool'].endswith('view_tag_patterns'):
            for r in st.get('rows', []):
                tags.append({"tag": r.get('keyword'), "used_by": parse.num(r.get('listing_count')),
                             "their_sales": parse.num(r.get('listing_sales')), "volume": parse.num(r.get('new_volume')),
                             "competition": parse.num(r.get('competition')), "score": parse.num(r.get('score'))})
    rel = {}
    for L in listings.values():
        ok, note, focus = relevance(type_id, L['title'])
        L['relevant'], L['relevance_note'], L['focus'] = ok, note, focus
        rel[L['listing_id']] = {"relevant": ok, "note": note, "title": L['title'][:110], "shop": L['shop'],
                                "mo_revenue": L['mo_revenue'], "total_sales": L['total_sales']}
    cand = {"type_id": type_id, "collected": store.now(), "market": market, "listings": list(listings.values()),
            "tags": tags, "sources": sources}
    store.write(os.path.join(tdir(type_id), 'candidates.json'), cand)
    rpath = os.path.join(tdir(type_id), 'relevance.json')
    old = store.read(rpath, {})
    for k, v in old.items():  # keep any decision the session already made
        if k in rel and v.get('by') == 'session':
            rel[k].update(relevant=v['relevant'], note=v['note'], by='session')
    store.write(rpath, rel)
    n_rel = sum(1 for v in rel.values() if v['relevant'])
    return {"ok": True, "listings": len(listings), "relevant": n_rel, "relevance_file": rpath}


def top_relevant(type_id):
    cand = store.read(os.path.join(tdir(type_id), 'candidates.json'))
    rel = store.read(os.path.join(tdir(type_id), 'relevance.json'))
    keep = [dict(L, relevant=rel[L['listing_id']]['relevant'], relevance_note=rel[L['listing_id']]['note'])
            for L in cand['listings'] if rel.get(L['listing_id'], {}).get('relevant')]
    # Winners now (monthly revenue) and proven winners (all-time sales), alternating so both are represented.
    by_rev = sorted(keep, key=lambda L: -(L['mo_revenue'] or 0))
    by_tot = sorted(keep, key=lambda L: -(L['total_sales'] or 0))
    out, seen = [], set()
    for a, b in zip(by_rev, by_tot):
        for L in (a, b):
            if L['listing_id'] not in seen:
                seen.add(L['listing_id']); out.append(L)
    for L in by_rev + by_tot:
        if L['listing_id'] not in seen:
            seen.add(L['listing_id']); out.append(L)
    out = out[:CFG['top_n']]
    for i, L in enumerate(out):
        L['rank'] = i + 1
    return cand, out


def plan_b(type_id):
    cand, top = top_relevant(type_id)
    shops = []
    for L in top:
        if L['shop'] not in shops:
            shops.append(L['shop'])
    shops = shops[:CFG['review_shops']]
    calls = []
    for s in shops:
        calls.append({"tool": "mcp__EverBee__view_shop_reviews", "input": {"shop_name": s, "sort_by": "rating", "sort_order": "asc"}})
        calls.append({"tool": "mcp__EverBee__view_shop_reviews", "input": {"shop_name": s, "sort_by": "rating", "sort_order": "asc", "page": 2}})
        calls.append({"tool": "mcp__EverBee__view_shop_reviews", "input": {"shop_name": s, "sort_by": "created_at", "sort_order": "desc"}})
    for s in shops[:CFG['shop_teardowns']]:
        calls.append({"tool": "mcp__EverBee__analyze_shop", "input": {"shop_name": s}, "optional": True})
    path = store.write(os.path.join(tdir(type_id), 'calls-b.json'), {"type_id": type_id, "made": store.now(), "shops": shops, "calls": calls})
    return path, calls


def _review_page(inp):
    return inp.get('page', 1)


def collect_b(type_id):
    plan = store.read(os.path.join(tdir(type_id), 'calls-b.json'))
    since = time.time() - MAX_AGE_DAYS * 86400
    got = sorted(_calls(since), key=lambda x: x[3] or '')
    found, missing = [], []
    for c in plan['calls']:
        m = None
        for name, inp, txt, ts in got:
            if name == c['tool'] and _subset(c['input'], inp) and _review_page(c['input']) == _review_page(inp):
                m = (txt, ts)
        if m:
            found.append((c, m))
        elif not c.get('optional'):
            missing.append(c)
    _save(found)
    if missing:
        return {"ok": False, "missing": missing}
    skipped = [c['input'] for c in plan['calls'] if c.get('optional') and not any(c is f for f, _ in found)]
    cand, top = top_relevant(type_id)
    top_ids = {L['listing_id'] for L in top}
    shops, reviews, seen = {}, [], set()
    sources = list(cand['sources'])
    for c, (txt, ts) in found:
        sources.append({"tool": c['tool'], "input": c['input'], "at": ts})
        st, met, texts = harvest.widget(txt)
        shop = c['input']['shop_name']
        S = shops.setdefault(shop, {"shop": shop})
        if c['tool'].endswith('view_shop_reviews'):
            summary = next((x for x in texts if 'average' in x and 'reviews' in x), '')
            if summary:
                S['rating_summary'] = summary
                S['rating_avg'] = parse.num(summary.split('average')[0])
                S['review_count'] = parse.num(summary.split('·')[1]) if '·' in summary else None
            for r in st.get('rows', []):
                text = (r.get('review') or '').strip()
                key = (shop, r.get('listing_id'), text[:80], r.get('created_at'))
                if key in seen:
                    continue
                seen.add(key)
                s = parse.stars(r.get('stars'))
                if not s:
                    continue
                reviews.append({"id": f"r{len(reviews) + 1}", "shop": shop, "stars": s,
                                "text": '' if text in ('—', '-') else text,
                                "listing_id": str(r.get('listing_id') or '') or None, "date": r.get('created_at') or '',
                                "on_top_listing": str(r.get('listing_id')) in top_ids})
        elif c['tool'].endswith('analyze_shop'):
            S['teardown'] = {"summary": [x for x in texts if len(x) > 60][:8], "metrics": met, "state": st}
    ev = {"type_id": type_id, "query": TYPES[type_id]['query'], "refreshed_at": store.now(),
          "market": cand['market'], "listings": top, "shops": list(shops.values()), "reviews": reviews,
          "tags": cand['tags'], "sources": sources,
          "photo_status": "pending"}
    store.validate(ev, 'evidence')
    path = store.write(os.path.join(store.type_dir(type_id), 'evidence.json'), ev)
    job = {"job": "competitor_photos", "type_id": type_id, "made": store.now(),
           "listings": [{"listing_id": L['listing_id'], "rank": L['rank']} for L in top]}
    store.write(os.path.join(store.DATA, 'jobs', 'outbox', f"photos-{type_id}.json"), job)
    with_text = [r for r in reviews if r['text']]
    return {"ok": True, "evidence": path, "optional_skipped": skipped, "listings": len(top), "shops": len(shops), "reviews": len(reviews),
            "reviews_with_text": len(with_text), "negative_with_text": sum(1 for r in with_text if r['stars'] <= 3)}


if __name__ == '__main__':
    cmd, type_id = sys.argv[1], sys.argv[2]
    if cmd == 'plan-a':
        path, calls = plan_a(type_id); print(json.dumps({"calls_file": path, "calls": calls}, indent=1))
    elif cmd == 'collect-a':
        print(json.dumps(collect_a(type_id), indent=1))
    elif cmd == 'plan-b':
        path, calls = plan_b(type_id); print(json.dumps({"calls_file": path, "n": len(calls)}, indent=1))
    elif cmd == 'collect-b':
        print(json.dumps(collect_b(type_id), indent=1))
