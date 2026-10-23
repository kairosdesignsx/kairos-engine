"""Stage 3: Insights. Turn raw evidence into what the brief needs.

  prepare  -> review coding batches for subagents (codebook + reviews with text)
  build    -> data/types/<type>/insights.json (schema-checked)

Features come from titles and tags now; descriptions and photos add to them once the
laptop has fetched them (evidence listing.features = {feature_id: true, ...}).
"""
import json, os, re, statistics, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

BATCH = 120
TIER = store.CONFIG['brief']


def line_cfg(line):
    return store.read(os.path.join(store.ROOT, 'config', 'lines', f'{line}.json'))


def codebook(line):
    """Seed codebook from the line config plus themes learned in earlier runs."""
    base = line_cfg(line)['codebook']
    learned = store.read(os.path.join(store.DATA, 'learn', f'codebook-{line}.json'), {})
    out = {k: list(v) for k, v in base.items()}
    for kind, items in learned.items():
        have = {t['id'] for t in out.setdefault(kind, [])}
        out[kind] += [t for t in items if t['id'] not in have]
    return out


def idir(type_id):
    return os.path.join(store.type_dir(type_id), 'insights')


def prepare(type_id):
    types = store.read(os.path.join(store.ROOT, 'config', 'types.json'))
    line = types[type_id]['line']
    ev = store.read(os.path.join(store.type_dir(type_id), 'evidence.json'))
    reviews = [{"id": r['id'], "stars": r['stars'], "text": r['text']} for r in ev['reviews'] if len(r['text']) >= 12]
    cb = codebook(line)
    batches = []
    for i in range(0, len(reviews), BATCH):
        n = i // BATCH + 1
        src = store.write(os.path.join(idir(type_id), f'code-in-{n}.json'),
                          {"product_type": types[type_id]['name'] + ' (' + types[type_id]['format'] + ')', "codebook": cb, "reviews": reviews[i:i + BATCH]})
        batches.append({"in": src, "out": os.path.join(idir(type_id), f'code-out-{n}.json'), "n": len(reviews[i:i + BATCH])})
    store.write(os.path.join(idir(type_id), 'batches.json'), batches)
    return {"reviews_to_code": len(reviews), "batches": batches}


def _feature_hits(L, feats):
    # Titles (and descriptions once fetched). Tags are keyword-stuffed, so they feed keywords, not features.
    text = ' ' + (L['title'] + ' ' + (L.get('description') or '')).lower() + ' '
    extra = L.get('features') or {}
    hits = set(k for k, v in extra.items() if v)
    for f in feats:
        if any(re.search(p, text) for p in f['match']):
            hits.add(f['id'])
    return hits


def _pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 2)


def _quotes(rev_ids, reviews, n=3):
    by_id = {r['id']: r for r in reviews}
    rs = [by_id[i] for i in rev_ids if i in by_id and 25 <= len(by_id[i]['text']) <= 240]
    rs.sort(key=lambda r: (not r.get('on_top_listing'), abs(len(r['text']) - 110)))
    out, shops = [], set()
    for r in rs:  # spread across shops first
        if r['shop'] not in shops:
            out.append(r); shops.add(r['shop'])
        if len(out) == n:
            break
    for r in rs:
        if len(out) == n:
            break
        if r not in out:
            out.append(r)
    return [{"text": r['text'], "shop": r['shop'], "stars": r['stars'], "review_id": r['id']} for r in out]


def build(type_id):
    types = store.read(os.path.join(store.ROOT, 'config', 'types.json'))
    line = types[type_id]['line']
    cfg = line_cfg(line)
    ev = store.read(os.path.join(store.type_dir(type_id), 'evidence.json'))
    batches = store.read(os.path.join(idir(type_id), 'batches.json'), [])
    codes, new_themes, off_type = {}, [], set()
    aliases = store.read(os.path.join(idir(type_id), 'aliases.json'), {})  # duplicate theme id -> canonical id (reconcile step)
    for b in batches:
        out = store.read(b['out'])
        if out is None:  # batches.json written in an older clone path: look next to it
            out = store.read(os.path.join(idir(type_id), os.path.basename(b['out'])))
        if out is None:
            raise SystemExit(f"missing review codes: {b['out']}")
        for c in out.get('codes', []):
            codes[c['id']] = sorted({aliases.get(t, t) for t in c.get('themes', []) if aliases.get(t, t)})
            if c.get('off_type'):
                off_type.add(c['id'])
        new_themes += [t for t in out.get('new_themes', []) if not aliases.get(t['id'])]
    coded = set(codes)
    expected = sum(b['n'] for b in batches)
    if len(coded) < 0.95 * expected:
        raise SystemExit(f'only {len(coded)} of {expected} reviews coded')

    # learned themes persist for the next product type in this line
    cb = codebook(line)
    learned = store.read(os.path.join(store.DATA, 'learn', f'codebook-{line}.json'), {})
    names = {t['id']: t['theme'] for kind in cb.values() for t in kind}
    for t in new_themes:
        kind = t.get('kind') or {'c': 'complaints', 'p': 'praise', 'w': 'wishes'}.get(t['id'][:1], 'complaints')
        if t['id'] not in names:
            learned.setdefault(kind, []).append({"id": t['id'], "theme": t['theme'], "use_for": t.get('use_for', '')})
            names[t['id']] = t['theme']
    store.write(os.path.join(store.DATA, 'learn', f'codebook-{line}.json'), learned)

    reviews = [r for r in ev['reviews'] if r['id'] not in off_type]
    themes = {}
    for rid, ts in codes.items():
        if rid in off_type:
            continue
        for t in set(ts):
            themes.setdefault(t, []).append(rid)

    def theme_list(prefix):
        out = []
        for tid, rids in themes.items():
            if tid.startswith(prefix):
                out.append({"id": tid, "theme": names.get(tid, tid), "count": len(rids),
                            "on_top_listings": sum(1 for r in reviews if r['id'] in rids and r.get('on_top_listing')),
                            "quotes": _quotes(rids, reviews), "review_ids": rids})
        return sorted(out, key=lambda x: -x['count'])

    listings = ev['listings']
    n = len(listings)
    rev_total = sum(L['mo_revenue'] or 0 for L in listings) or 1
    sales_total = sum(L['total_sales'] or 0 for L in listings) or 1
    feats_all = list(cfg['features'])
    known = {f['id'] for f in feats_all}
    for L in listings:  # features the photo readers found that the line's list doesn't have yet
        for nf in L.get('new_features', []):
            if nf['id'] not in known:
                known.add(nf['id']); feats_all.append({"id": nf['id'], "name": nf['name'], "match": [], "discovered": True})
    hits = {L['listing_id']: _feature_hits(L, feats_all) | {nf['id'] for nf in L.get('new_features', [])} for L in listings}
    detailed = any(L.get('features') or L.get('description') for L in listings)
    features = []
    for f in feats_all:
        have = [lid for lid, h in hits.items() if f['id'] in h]
        share = len(have) / n
        tier = 'standard' if share >= TIER['standard_share'] else 'common' if share >= TIER['common_share'] else 'rare' if have else ('nobody' if detailed else 'not_seen')
        features.append({"id": f['id'], "name": f['name'], "have": have, "share": round(share, 3),
                         "revenue_share": round(sum(L['mo_revenue'] or 0 for L in listings if L['listing_id'] in have) / rev_total, 3),
                         "sales_share": round(sum(L['total_sales'] or 0 for L in listings if L['listing_id'] in have) / sales_total, 3),
                         "tier": tier})
    features.sort(key=lambda f: -f['share'])

    prices = [L['price'] for L in listings if L['price']]
    top10 = sorted(listings, key=lambda L: -(L['mo_revenue'] or 0))[:10]
    weighted = []
    for L in listings:
        if L['price'] and L['mo_revenue']:
            weighted += [L['price']] * max(1, int(L['mo_revenue'] // 50))
    price = {"p25": _pct(prices, .25), "median": _pct(prices, .5), "p75": _pct(prices, .75),
             "top10_by_revenue_median": _pct([L['price'] for L in top10], .5),
             "revenue_weighted_median": _pct(weighted, .5) if weighted else None,
             "best_band": ev['market'].get('best_price_band')}

    tagcount = {}
    for L in listings:
        for t in L.get('tags', []):
            tagcount[t.lower()] = tagcount.get(t.lower(), 0) + 1
    tp = {t['tag']: t for t in ev['tags']}
    keywords = [{"tag": t, "used_by_top": c, "volume": (tp.get(t) or {}).get('volume')}
                for t, c in sorted(tagcount.items(), key=lambda kv: -kv[1])[:40]]

    looks = [{"style": f['name'], "share": f['share'], "have": f['have']} for f in features
             if f['id'] in ('minimalist', 'colorful', 'dark_mode', 'landscape', 'portrait')]

    complaints, praise, wishes = theme_list('c_'), theme_list('p_'), theme_list('w_')
    neg = [r for r in reviews if r['id'] in coded and r['stars'] <= 3]
    theme_names = names
    fix_map = cfg.get('fix_map', {})
    gaps = []
    for c in complaints[:8]:
        gaps.append({"kind": "fix", "complaint": c['id'], "theme": c['theme'], "count": c['count'],
                     "features_that_fix": fix_map.get(c['id'], [])})
    for f in features:
        if f['tier'] in ('rare', 'nobody', 'not_seen'):
            gaps.append({"kind": "open_feature", "feature": f['id'], "name": f['name'], "share": f['share']})
    for w in wishes:
        gaps.append({"kind": "wish", "wish": w['id'], "theme": w['theme'], "count": w['count']})

    sources = ['titles', 'tags']
    sources = ['titles'] + (['descriptions_or_photos'] if detailed else [])
    ins = {"type_id": type_id, "built_at": store.now(),
           "basis": {"listings": n, "reviews": len(reviews), "reviews_coded": len(coded) - len(off_type), "off_type_dropped": len(off_type), "negative_reviews": len(neg),
                     "feature_sources": sources, "photos": ev.get('photo_status', 'pending')},
           "features": features, "complaints": complaints, "praise": praise, "wishes": wishes,
           "price": price, "looks": looks, "keywords": keywords, "gaps": gaps}
    store.validate(ins, 'insights')
    path = store.write(os.path.join(store.type_dir(type_id), 'insights.json'), ins)
    return {"ok": True, "insights": path, "features": len(features), "complaints": len(complaints),
            "praise": len(praise), "wishes": len(wishes), "coded": len(coded)}


def reconcile(type_id):
    """List new themes from all batches with counts, so the session can merge duplicates into aliases.json."""
    batches = store.read(os.path.join(idir(type_id), 'batches.json'), [])
    new, cnt = {}, {}
    for b in batches:
        out = store.read(b['out']) or {}
        for t in out.get('new_themes', []):
            new.setdefault(t['id'], t)
        for c in out.get('codes', []):
            for t in c.get('themes', []):
                cnt[t] = cnt.get(t, 0) + 1
    rows = [{"id": k, "theme": v['theme'], "use_for": v.get('use_for', ''), "count": cnt.get(k, 0)} for k, v in new.items()]
    path = store.write(os.path.join(idir(type_id), 'new-themes.json'), sorted(rows, key=lambda r: -r['count']))
    return {"new_themes": len(rows), "file": path, "aliases_file": os.path.join(idir(type_id), 'aliases.json'),
            "how": "Write aliases.json mapping each duplicate new id to an existing or canonical id (or to null to drop it)."}


if __name__ == '__main__':
    cmd, type_id = sys.argv[1], sys.argv[2]
    fn = {'prepare': prepare, 'reconcile': reconcile, 'build': build}[cmd]
    print(json.dumps(fn(type_id), indent=1))
