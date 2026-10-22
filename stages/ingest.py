"""Bring laptop results into the engine.

The session first stages the laptop's results into the cloud workspace:
  device_stage_files  Kairos\\jobs\\results\\*.json  (and, for photos, Kairos\\data\\types\\<type>\\photos\\**)
They arrive under config laptop.mirror. Then:
  python3 stages/ingest.py results           merge every new result (photos+descriptions, publish, stats)
  python3 stages/ingest.py photo-tasks <type> batches for subagents with prompts/photo-reader.md
  python3 stages/ingest.py photo-merge <type> merge their output into evidence.json (then rebuild insights)
"""
import glob, json, os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

MIRROR = store.CONFIG['laptop']['mirror']


def results():
    seen = store.read(os.path.join(store.DATA, 'jobs', 'ingested.json'), [])
    out = []
    for f in sorted(glob.glob(os.path.join(MIRROR, 'jobs', 'results', '*.json'))):
        name = os.path.basename(f)
        if name in seen:
            continue
        r = store.read(f)
        if not r.get('ok'):
            out.append({"job": name, "error": r.get('error')}); seen.append(name); continue
        res = r['result']
        if r['kind'] == 'competitor_photos':
            tid = res['type_id']
            evp = os.path.join(store.type_dir(tid), 'evidence.json'); ev = store.read(evp)
            by = {x['listing_id']: x for x in res['listings']}
            for L in ev['listings']:
                x = by.get(L['listing_id'])
                if not x:
                    continue
                L['description'] = x.get('description', '')
                if x.get('full_price') is not None:  # full price in the seller's currency: with EverBee's USD price it shows who runs a sale
                    L['full_price'] = x['full_price']; L['currency'] = x.get('currency')
                local = []
                for rel in x.get('photos', []):
                    src = os.path.join(MIRROR, rel.replace('\\', '/'))
                    if os.path.exists(src):
                        dst = os.path.join(store.type_dir(tid), 'photos', L['listing_id'], os.path.basename(src))
                        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(src, dst); local.append(dst)
                L['photos'] = local
            ev['photo_status'] = 'fetched'
            store.write(evp, ev)
            out.append({"job": name, "type_id": tid, "listings": len(by), "photos": sum(len(L.get('photos', [])) for L in ev['listings'])})
        elif r['kind'] == 'publish':
            d = store.product_dir(res['product_id'])
            store.write(os.path.join(d, 'published.json'), res)
            out.append({"job": name, "published": res})
        elif r['kind'] in ('inspect', 'fix_listing'):
            store.write(os.path.join(store.DATA, 'etsy', f"{r['kind']}-{store.now()[:10]}.json"), res)
            out.append({"job": name, r['kind']: True})
        elif r['kind'] == 'stats':
            store.write(os.path.join(store.DATA, 'stats', f"{store.now()[:10]}.json"), res)
            out.append({"job": name, "stats_listings": len(res['listings'])})
        seen.append(name)
    store.write(os.path.join(store.DATA, 'jobs', 'ingested.json'), seen)
    return out


def photo_tasks(tid, per=6):
    types = store.read(os.path.join(store.ROOT, 'config', 'types.json'))
    line = store.read(os.path.join(store.ROOT, 'config', 'lines', types[tid]['line'] + '.json'))
    ev = store.read(os.path.join(store.type_dir(tid), 'evidence.json'))
    feats = [{"id": f['id'], "name": f['name']} for f in line['features']]
    Ls = [{"listing_id": L['listing_id'], "title": L['title'], "description": (L.get('description') or '')[:4000], "photos": L.get('photos', [])}
          for L in ev['listings'] if L.get('photos')]
    tasks = []
    for i in range(0, len(Ls), per):
        n = i // per + 1
        src = store.write(os.path.join(store.type_dir(tid), 'photo-read', f'in-{n}.json'), {"features": feats, "listings": Ls[i:i + per]})
        tasks.append({"in": src, "out": src.replace('in-', 'out-')})
    return {"tasks": tasks}


def photo_merge(tid):
    evp = os.path.join(store.type_dir(tid), 'evidence.json'); ev = store.read(evp)
    got = {}
    for f in glob.glob(os.path.join(store.type_dir(tid), 'photo-read', 'out-*.json')):
        for x in store.read(f).get('listings', []):
            got[x['listing_id']] = x
    for L in ev['listings']:
        x = got.get(L['listing_id'])
        if x:
            L['features'] = x.get('features', {})
            L['page_types'] = x.get('page_types', [])
            L['look'] = x.get('look', {})
            L['new_features'] = x.get('new_features', [])
            L['photo_tactics'] = x.get('photo_tactics', [])
    ev['photo_status'] = 'read' if got else ev.get('photo_status')
    store.write(evp, ev)
    return {"listings_read": len(got)}


if __name__ == '__main__':
    cmd = sys.argv[1]
    fn = {'results': lambda: results(), 'photo-tasks': lambda: photo_tasks(sys.argv[2]), 'photo-merge': lambda: photo_merge(sys.argv[2])}[cmd]
    print(json.dumps(fn(), indent=1))
