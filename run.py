"""Engine entry point.

  python3 run.py plan      -> runs/<id>/plan.json: what tonight does (teardowns due, new products, fixes)
  python3 run.py status    -> where every product is in the pipeline
  python3 run.py report    -> runs/<id>/report.md: the morning report
"""
import datetime as dt, glob, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import store

STAGES = ['brief', 'brief.check', 'build', 'listing', 'photos', 'check', 'queue']


def product_stage(pid):
    d = store.product_dir(pid)
    have = {s: os.path.exists(os.path.join(d, f'{s}.json')) for s in STAGES}
    chk = store.read(os.path.join(d, 'check.json'))
    bchk = store.read(os.path.join(d, 'brief.check.json'))
    if have['queue']:
        return 'queued'
    if chk:
        return 'checked: ' + ('pass' if chk['pass'] else 'FAIL')
    for s in reversed(STAGES):
        if have[s]:
            if s == 'brief.check' and not bchk.get('pass'):
                return 'brief: check failing'
            return f'after {s}'
    return 'new'


def status():
    rows = []
    for d in sorted(glob.glob(os.path.join(store.DATA, 'products', '*'))):
        pid = os.path.basename(d)
        b = store.read(os.path.join(d, 'brief.json')) or {}
        rows.append({"product_id": pid, "type": b.get('type_id'), "title": (b.get('spec') or {}).get('title'), "stage": product_stage(pid)})
    return rows


def next_pid(type_id):
    short = ''.join(w[0] for w in type_id.split('-'))[:4]
    n = 1
    while os.path.exists(store.product_dir(f'p-{short}-{n:03d}')):
        n += 1
    return f'p-{short}-{n:03d}'


def plan():
    run = store.Run()
    types = store.read(os.path.join(store.ROOT, 'config', 'types.json'))
    cfg = store.CONFIG
    now = dt.datetime.now(dt.timezone.utc)
    # new product types from the picker (market research x what the lines can build x overlap with what we make)
    sys.path.insert(0, os.path.join(store.ROOT, 'stages'))
    import pick
    picked = pick.run()
    added = []
    pending_new = [t for t in types if not store.read(os.path.join(store.type_dir(t), 'evidence.json'))]
    for p in (store.read(os.path.join(store.DATA, 'plan', 'picks.json')) or {}).get('picks', [])[:max(0, cfg['nightly'].get('new_types_per_night', 1) - len(pending_new))]:
        r = pick.add(p['idea'])
        added.append({"type_id": r['type_id'], "idea": p['idea'], "score": p['score'], "why": p['why']})
    types = store.read(os.path.join(store.ROOT, 'config', 'types.json'))
    teardowns = []
    for tid in types:
        ev = store.read(os.path.join(store.type_dir(tid), 'evidence.json'))
        age = None
        if ev:
            age = (now - dt.datetime.fromisoformat(ev['refreshed_at'].replace('Z', '+00:00'))).days
        if ev is None or age >= cfg['teardown']['refresh_days']:
            teardowns.append({"type_id": tid, "reason": "no evidence yet" if ev is None else f"evidence {age} days old"})
    fixes = [f for f in store.read(os.path.join(store.DATA, 'learn', 'fix-queue.json'), []) if f['status'] == 'open'][:cfg['nightly']['max_fixes']]
    in_flight = [r for r in status() if r['stage'] not in ('queued',) and not r['stage'].startswith('checked: pass')]
    budget = max(0, cfg['nightly']['max_new_products'] - len(in_flight))
    ready_types = [t for t in types if store.read(os.path.join(store.type_dir(t), 'insights.json'))]
    rows_ = status()
    made = {r['type'] for r in rows_ if r.get('type')}
    waiting = {r['type'] for r in rows_ if r['stage'] == 'queued'}
    # learn before repeating: no new product of a type while its last one waits for Darren's review
    ready_types = [t for t in ready_types if t not in waiting]
    ready_types.sort(key=lambda t: (t in made, 0))  # types with no product yet first
    # family cap: no first product for a type whose family already has FAMILY_CAP types with products (wait for their sales)
    import pick
    groups = store.read(os.path.join(store.ROOT, 'config', 'groups.json'))
    fam = lambda t: groups.get(types[t]['group'], {}).get('family', types[t]['group'])
    fam_made = {}
    for t in made:
        if t in types:
            fam_made[fam(t)] = fam_made.get(fam(t), 0) + 1
    ready_types = [t for t in ready_types if t in made or fam_made.get(fam(t), 0) < pick.FAMILY_CAP]
    new = []
    for i in range(budget):
        if not ready_types:
            break
        t = ready_types[i % len(ready_types)]
        pid = next_pid(t)
        while any(x['product_id'] == pid for x in new):
            pid = pid[:-3] + f'{int(pid[-3:]) + 1:03d}'
        new.append({"type_id": t, "product_id": pid})
    # nightly shop stats from Etsy (views, favorites, sales per listing): the laptop worker fetches them
    store.write(os.path.join(store.DATA, 'jobs', 'outbox', f"stats-{now.strftime('%Y%m%d')}.json"), {"job": "stats"})
    p = {"run": run.id, "made": store.now(), "new_types": added, "teardowns": teardowns, "fixes": fixes, "continue": in_flight, "new_products": new}
    store.write(os.path.join(run.dir, 'plan.json'), p)
    run.stage('plan', 'done', teardowns=len(teardowns), fixes=len(fixes), new=len(new), continuing=len(in_flight))
    return p


def report():
    run = store.Run.latest()
    rows = status()
    plan_ = store.read(os.path.join(run.dir, 'plan.json'), {})
    lines = [f"# Kairos engine, run {run.id}", ""]
    queued = [r for r in rows if r['stage'] == 'queued']
    failing = [r for r in rows if 'FAIL' in r['stage'] or 'failing' in r['stage']]
    lines.append(f"Waiting for your review: {len(queued)}")
    for r in queued:
        lines.append(f"- {r['title']} ({r['product_id']})")
    if failing:
        lines += ["", "Stuck, needs a look:"] + [f"- {r['product_id']}: {r['stage']}" for r in failing]
    if plan_.get('teardowns'):
        done_ = [t['type_id'] for t in plan_['teardowns'] if store.read(os.path.join(store.type_dir(t['type_id']), 'insights.json'))]
        todo_ = [t['type_id'] for t in plan_['teardowns'] if t['type_id'] not in done_]
        if done_:
            lines += ["", "Research done: " + ', '.join(done_)]
        if todo_:
            lines += ["", "Research not finished: " + ', '.join(todo_)]
    for e in store.read(os.path.join(store.DATA, 'learn', 'experiments.json'), []) or []:
        if not e.get('decided'):
            lines += ["", f"Test {e['id']}: {e['question']} Status: {e['status']}."]
    if plan_.get('new_types'):
        lines += ["", "New product types picked: " + ', '.join(f"{t['idea']} (score {t['score']})" for t in plan_['new_types'])]
    if plan_.get('fixes'):
        lines += ["", f"Fixes worked on: {len(plan_['fixes'])}"]
    log = os.path.join(run.dir, 'log.jsonl')
    errors = [json.loads(l) for l in open(log)] if os.path.exists(log) else []
    errors = [e for e in errors if e.get('event') in ('failed', 'error')]
    if errors:
        lines += ["", "Errors:"] + [f"- {e['stage']}: {e.get('detail', '')}" for e in errors[:10]]
    text = '\n'.join(lines) + '\n'
    open(os.path.join(run.dir, 'report.md'), 'w').write(text)
    return text


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    out = {'plan': plan, 'status': status, 'report': report}[cmd]()
    print(out if isinstance(out, str) else json.dumps(out, indent=1))
