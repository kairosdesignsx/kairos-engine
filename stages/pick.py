"""Stage 0b: Pick what to make next.

  run                 rank every market idea -> data/plan/picks.json (and picks.md for people)
  add <idea>          turn a picked idea into a product type in config/types.json (teardown runs next)

Score = market score (EverBee research, 0 to 100)
        x line fit       (1.0 the line builds it today; 0.85 it needs new modules; no line = not picked, listed as needs_line)
        x overlap        (0.55 per type already in the same family (config/groups.json), and none at all once a family has FAMILY_CAP types: breadth first while the shop is new;
                          a group whose product is approved or selling gets this lifted later from stats)
        x lessons        (0.7 when Darren rejected a product of this group)
Ideas with call "Skip" are left out; "Test" ideas stay but rank lower because their market score is lower.
"""
import json, os, re, sys

FAMILY_CAP = 2  # no new type in a family that already has this many types, until sales data says the family works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store

GROUPS = os.path.join(store.ROOT, 'config', 'groups.json')
TYPES = os.path.join(store.ROOT, 'config', 'types.json')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def _type_groups(types, ideas):
    by_query = {i['idea']: i['group'] for i in ideas}
    out = {}
    for tid, t in types.items():
        out[tid] = t.get('group') or by_query.get(t.get('query')) or ''
    return out


def run():
    ideas = store.read(os.path.join(store.DATA, 'market', 'opportunities.json'), [])
    groups = store.read(GROUPS)
    types = store.read(TYPES)
    tgroups = _type_groups(types, ideas)
    lessons = []
    lp = os.path.join(store.DATA, 'learn', 'lessons.jsonl')
    if os.path.exists(lp):
        lessons = [json.loads(l) for l in open(lp) if l.strip()]
    rejected_groups = {tgroups.get(l.get('type_id')) for l in lessons}
    have_queries = {t.get('query') for t in types.values()}
    picks, needs_line, held = [], [], []
    for i in ideas:
        if i.get('call') == 'Skip':
            continue
        g = groups.get(i['group'], {})
        if i['idea'] in have_queries:
            continue
        if not g.get('line'):
            needs_line.append({"idea": i['idea'], "group": i['group'], "market": i['score'], "why": g.get('note', 'no line can build this yet')})
            continue
        fit = g.get('fit', 1.0)
        fam = g.get('family', i['group'])
        in_fam = sum(1 for x in tgroups.values() if groups.get(x, {}).get('family', x) == fam)
        if in_fam >= FAMILY_CAP:
            held.append({"idea": i['idea'], "group": i['group'], "market": i['score'],
                         "why": f"we already make {in_fam} types in the {fam} family; wait for their sales before adding more"})
            continue
        overlap = 0.55 ** in_fam
        lesson = 0.7 if i['group'] in rejected_groups else 1.0
        score = round(i['score'] * fit * overlap * lesson, 1)
        why = [f"market {i['score']} ({i['call']})", f"{i['searches']:,} searches a month", f"{i['listings']:,} listings",
               f"top-10 median ${i['median_revenue']:,.0f}/mo at ${i['median_price']:.2f}"]
        if fit < 1:
            why.append(f"line {g['line']} needs: {g.get('note', 'new modules')}")
        if overlap < 1:
            why.append(f"overlaps a type we already make ({g.get('family', i['group'])})")
        if lesson < 1:
            why.append('a product in this group was rejected')
        if i.get('flags'):
            why.append(i['flags'])
        picks.append({"idea": i['idea'], "group": i['group'], "line": g['line'], "score": score, "market": i['score'], "call": i['call'],
                      "type_id": slug(i['idea']), "why": why})
    picks.sort(key=lambda x: -x['score'])
    for n, p in enumerate(picks, 1):
        p['rank'] = n
    out = {"made": store.now(), "source": "data/market/opportunities.json", "picks": picks, "needs_line": sorted(needs_line, key=lambda x: -x['market']),
           "held": sorted(held, key=lambda x: -x['market'])}
    store.write(os.path.join(store.DATA, 'plan', 'picks.json'), out)
    md = ["# What to make next", "", "| # | Idea | Line | Score | Why |", "|---|---|---|---|---|"]
    md += [f"| {p['rank']} | {p['idea']} | {p['line']} | {p['score']} | {'; '.join(p['why'])} |" for p in picks[:15]]
    md += ["", "## Waiting for a new line", ""] + [f"- {x['idea']} ({x['group']}, market {x['market']}): {x['why']}" for x in out['needs_line'][:12]]
    open(os.path.join(store.DATA, 'plan', 'picks.md'), 'w').write('\n'.join(md) + '\n')
    return {"picks": len(picks), "top": [(p['rank'], p['idea'], p['score']) for p in picks[:8]], "needs_line": len(needs_line)}


def add(idea):
    ideas = {i['idea']: i for i in store.read(os.path.join(store.DATA, 'market', 'opportunities.json'), [])}
    i = ideas[idea]
    g = store.read(GROUPS)[i['group']]
    types = store.read(TYPES)
    tid = slug(idea)
    if tid in types:
        return {"ok": True, "type_id": tid, "note": "already a type"}
    words = [w for w in re.findall(r'[a-z0-9]+', idea.lower()) if w not in ('template', 'digital', 'printable', 'the', 'for', 'and')]
    types[tid] = {"name": idea[:1].upper() + idea[1:], "query": idea, "line": g['line'], "group": i['group'], "format": g['format'],
                  "include_any": sorted(set(g.get('include_any', []))), "exclude_any": g.get('exclude_any', []), "focus_any": words,
                  "added_by": "picker", "added_at": store.now()}
    store.write(TYPES, types)
    return {"ok": True, "type_id": tid, "type": types[tid], "next": f"python3 stages/teardown.py plan-a {tid}"}


if __name__ == '__main__':
    cmd = sys.argv[1]
    print(json.dumps(run() if cmd == 'run' else add(' '.join(sys.argv[2:])), indent=1))
