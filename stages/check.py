"""Stage 8: Check. Nothing reaches Darren's queue unless it passes.

  tech <pid>              file size, links, overflow, fonts (licensing), photos, listing rules and honesty
  clone <pid>             text similarity to competitor titles; image similarity to competitor photos (when fetched)
  coverage-prep <pid>     task file for the separate coverage checker agent
  finish <pid>            merge everything into check.json with pass/fail
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

CHK = store.CONFIG['check']


def _load(pid):
    d = store.product_dir(pid)
    return d, {k: store.read(os.path.join(d, f'{k}.json')) for k in ('brief', 'build', 'listing', 'photos')}


def tech(pid):
    """Common listing checks here; file checks come from lines/<line>/checks.py (each line knows its own format)."""
    from PIL import Image
    d, x = _load(pid)
    out = []
    add = lambda name, ok, detail: out.append({"name": name, "pass": bool(ok), "detail": detail})
    L = x['listing'] or {}
    sys.path.insert(0, os.path.join(store.ROOT, 'stages'))
    from build import line_mod
    line_mod(x['brief']['line'], 'checks').file_checks(d, x['brief'], x['build'], L, add, CHK)
    ph = x['photos'] or {'photos': []}
    sizes = [Image.open(os.path.join(d, 'photos', f)).size for f in ph['photos']]
    add('listing photos', 5 <= len(sizes) <= 10 and all(s == (2700, 2025) for s in sizes), f'{len(sizes)} photos, sizes {sorted(set(sizes))}')
    tags = L.get('tags', [])
    add('title', 0 < len(L.get('title', '')) <= 140, f"{len(L.get('title', ''))} chars")
    add('13 tags, max 20 chars', len(tags) == 13 and all(len(t) <= 20 for t in tags), f'{len(tags)} tags')
    desc = L.get('description', '')
    add('no em dashes or emojis', not re.search('[\u2014\U0001F300-\U0001FAFF]', desc + L.get('title', '')), 'checked title and description')
    add('says digital download', 'digital' in desc.lower() and 'shipped' in desc.lower(), 'download and nothing-shipped note')
    store.write(os.path.join(d, 'check-tech.json'), out)
    return out


def clone(pid):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    d, x = _load(pid)
    ev = store.read(os.path.join(store.type_dir(x['brief']['type_id']), 'evidence.json'))
    ours = (x['listing'] or {}).get('title', '') or x['brief']['seo']['title']
    theirs = [L['title'] for L in ev['listings']]
    vec = TfidfVectorizer(ngram_range=(1, 3), sublinear_tf=True).fit(theirs + [ours])
    sims = cosine_similarity(vec.transform([ours]), vec.transform(theirs))[0]
    i = int(sims.argmax())
    text = {"max": round(float(sims[i]), 3), "closest": ev['listings'][i]['title'], "closest_shop": ev['listings'][i]['shop']}
    comp_dir = os.path.join(store.type_dir(x['brief']['type_id']), 'photos')
    comp = sorted(glob.glob(os.path.join(comp_dir, '*', '*.jpg')))
    if comp:
        import imagehash
        from PIL import Image
        oh = {f: imagehash.phash(Image.open(os.path.join(d, 'photos', f))) for f in x['photos']['photos']}
        best = (0, None, None)
        for c in comp:
            try:
                ch = imagehash.phash(Image.open(c))
            except Exception:
                continue
            for f, h in oh.items():
                s = 1 - (h - ch) / 64
                if s > best[0]:
                    best = (s, f, c)
        image = {"status": "checked", "max": round(best[0], 3), "ours": best[1], "theirs": os.path.relpath(best[2], comp_dir) if best[2] else None, "compared": len(comp)}
    else:
        image = {"status": "pending", "max": None, "note": "competitor photos not fetched yet (laptop worker)"}
    res = {"max_text_sim": text['max'], "text": text, "max_image_sim": image['max'], "image": image,
           "pass": text['max'] <= CHK['max_text_similarity'] and (image['max'] is None or image['max'] <= CHK['max_image_similarity'])}
    store.write(os.path.join(d, 'check-clone.json'), res)
    return res


def coverage_prep(pid):
    d, x = _load(pid)
    b = x['brief']
    items = [{"key": f"must:{m['id']}", "kind": "must_have", "text": m['what']} for m in b['must_haves']]
    items += [{"key": f"fix:{f['id']}", "kind": "fix", "text": f"{f['complaint']}: {f['how']}"} for f in b['fixes']]
    items += [{"key": f"unique:{u['id']}", "kind": "unique", "text": f"{u['name']}: {u['what']}"} for u in b['unique']]
    items.append({"key": "look", "kind": "look", "text": b['look']['direction']})
    mods = dict(x['build'].get('page_modules') or [])
    shots = [{"path": os.path.join(d, 'shots', s), "anchor": s[:-4], "module": mods.get(s[:-4])} for s in x['build']['shots']]
    task = {"product_id": pid, "items": items, "shots": shots,
            "photos": [os.path.join(d, 'photos', p) for p in x['photos']['photos']],
            "listing": os.path.join(d, 'listing.json'), "page_modules": x['build'].get('page_modules'), "line": b['line'], "files": [os.path.join(d, 'files', f['name']) for f in x['build']['files']]}
    path = store.write(os.path.join(d, 'coverage-in.json'), task)
    return {"coverage_in": path, "coverage_out": os.path.join(d, 'coverage-out.json'), "items": len(items), "shots": len(shots)}


def finish(pid):
    d, x = _load(pid)
    t = store.read(os.path.join(d, 'check-tech.json')) or tech(pid)
    c = store.read(os.path.join(d, 'check-clone.json')) or clone(pid)
    cov = store.read(os.path.join(d, 'coverage-out.json'))
    if cov is None:
        return {"ok": False, "blocked": "coverage checker has not run"}
    items = [{"item": i['key'], "kind": i['key'].split(':')[0], "found": i['found'], "where": i.get('where', ''), "note": i.get('note', '')} for i in cov['items']]
    high = [v for v in cov.get('visual', []) if v.get('severity') == 'high']
    res = {"product_id": pid, "at": store.now(), "tech": t, "coverage": items, "clone": c,
           "visual": cov.get('visual', []),
           "pass": all(x_['pass'] for x_ in t) and c['pass'] and all(i['found'] for i in items) and not high,
           "notes": []}
    if c['image']['status'] == 'pending':
        res['notes'].append('Image clone check pending: competitor photos come from the laptop worker.')
    store.validate(res, 'check')
    store.write(os.path.join(d, 'check.json'), res)
    fails = [x_['name'] for x_ in t if not x_['pass']] + [i['item'] for i in items if not i['found']] + [v['issue'] for v in high]
    if not c['pass']:
        fails.append(f"clone: text {c['max_text_sim']}, image {c['max_image_sim']}")
    return {"pass": res['pass'], "fails": fails, "coverage": f"{sum(i['found'] for i in items)}/{len(items)}", "visual": len(res['visual'])}


if __name__ == '__main__':
    cmd, pid = sys.argv[1], sys.argv[2]
    fn = {'tech': tech, 'clone': clone, 'coverage-prep': coverage_prep, 'finish': finish}[cmd]
    print(json.dumps(fn(pid), indent=1, default=str))
