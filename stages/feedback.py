"""Stage 0 of each night: act on Darren's (and Colynne's) reviews from the Review Queue page.

1. The session saves the page's rows to files (no retyping):
     ArtifactData list  collection "reviews"   out_dir data/feedback/raw
     ArtifactData list  collection "products"  out_dir data/feedback/raw
2. python3 stages/feedback.py process
   - owner Approve        -> laptop publish job (jobs/outbox/publish-<pid>.json)
   - any Fix              -> data/learn/fix-queue.json (tonight's plan picks these up)
   - owner Reject         -> data/learn/lessons.jsonl
   - every reason and note -> data/learn/reason-tally.json (the brief writer reads it with style-rules.json)
Only the owner's decision publishes. Other reviewers' decisions are signals.
"""
import glob, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

RAW = os.path.join(store.DATA, 'feedback', 'raw')
LEARN = os.path.join(store.DATA, 'learn')
PUBLISH_AS = store.CONFIG.get('publish_as', 'draft')


def _docs(collection):
    out = {}
    for f in glob.glob(os.path.join(RAW, collection, '*.json')):
        d = store.read(f)
        doc = d.get('data', d) if isinstance(d, dict) else d
        out[os.path.basename(f)[:-5]] = doc
    return out


def process():
    reviews, products = _docs('reviews'), _docs('products')
    state = store.read(os.path.join(LEARN, 'feedback-state.json'), {"seen": {}})
    fixq = store.read(os.path.join(LEARN, 'fix-queue.json'), [])
    tally = store.read(os.path.join(LEARN, 'reason-tally.json'), {"reasons": {}, "notes": []})
    actions = []
    for rid, r in sorted(reviews.items(), key=lambda kv: kv[1].get('at', 0)):
        key = f"{rid}@{r.get('at')}"
        if key in state['seen']:
            continue
        state['seen'][key] = store.now()
        pid = r.get('product')
        p = products.get(pid, {})
        eng = (p.get('engine') or {}).get('product_id', pid)
        owner = r.get('rid') == 'owner'
        for reason in r.get('reasons', []):
            tally['reasons'].setdefault(reason, {"count": 0, "by_decision": {}})
            tally['reasons'][reason]['count'] += 1
            bd = tally['reasons'][reason]['by_decision']
            bd[r.get('decision')] = bd.get(r.get('decision'), 0) + 1
        if r.get('note'):
            tally['notes'].append({"product": pid, "decision": r.get('decision'), "reasons": r.get('reasons', []), "note": r['note'], "owner": owner, "at": r.get('at')})
        if r.get('decision') == 'approve' and owner:
            d = store.product_dir(eng)
            build = store.read(os.path.join(d, 'build.json')) or {}
            listing = store.read(os.path.join(d, 'listing.json')) or p.get('listing', {})
            photos = sorted(f for f in os.listdir(os.path.join(d, 'photos')) if f.startswith('photo-')) if os.path.isdir(os.path.join(d, 'photos')) else []
            job = {"job": "publish", "product_id": eng, "state": PUBLISH_AS,
                   "listing": {"title": listing['title'], "description": listing['description'], "tags": listing['tags'], "price": listing['price']},
                   "files": [f"data/products/{eng}/files/{f['name']}" for f in build.get('files', [])],
                   "photos": [f"data/products/{eng}/photos/{f}" for f in photos],
                   "alt": [(listing.get('alt') or {}).get(f[len('photo-00-'):-4], '') for f in photos],
                   "taxonomy": (store.read(os.path.join(store.ROOT, 'config', 'lines', f"{(store.read(os.path.join(d, 'brief.json')) or {}).get('line', 'planner')}.json")) or {}).get('etsy_taxonomy', ['Calendars & Planners'])}
            store.write(os.path.join(store.DATA, 'jobs', 'outbox', f'publish-{eng}.json'), job)
            actions.append(f'publish job for {eng}')
        elif r.get('decision') == 'fix':
            fixq.append({"product_id": eng, "reasons": r.get('reasons', []), "note": r.get('note', ''), "owner": owner, "at": r.get('at'), "status": "open"})
            actions.append(f'fix queued for {eng}')
        elif r.get('decision') == 'reject' and owner:
            b = store.read(os.path.join(store.product_dir(eng), 'brief.json')) or {}
            with open(os.path.join(LEARN, 'lessons.jsonl'), 'a') as f:
                f.write(json.dumps({"product_id": eng, "type_id": b.get('type_id'), "reasons": r.get('reasons', []), "note": r.get('note', ''),
                                    "look": (b.get('look') or {}).get('direction'), "unique": [u['name'] for u in b.get('unique', [])], "at": r.get('at')}) + '\n')
            actions.append(f'lesson logged for {eng}')
    store.write(os.path.join(LEARN, 'feedback-state.json'), state)
    store.write(os.path.join(LEARN, 'fix-queue.json'), fixq)
    store.write(os.path.join(LEARN, 'reason-tally.json'), tally)
    return {"reviews": len(reviews), "new_actions": actions, "open_fixes": sum(1 for x in fixq if x['status'] == 'open')}


if __name__ == '__main__':
    print(json.dumps(process(), indent=1))
