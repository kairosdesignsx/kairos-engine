"""Paths, run state and logging for the engine.

Layout
  data/types/<type>/       evidence.json, insights.json, photos/   (per product type, reused across runs)
  data/products/<pid>/     brief.json, files, photos, listing.json, check.json, status.json
  data/learn/              lessons.jsonl, style-rules.json
  runs/<run_id>/           state.json, log.jsonl, plan.json        (one per nightly run)
"""
import datetime as dt, json, os, re, time

ROOT = os.environ.get('KAIROS_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'data')
RUNS = os.path.join(ROOT, 'runs')
SCHEMAS = os.path.join(ROOT, 'schemas')
CONFIG = json.load(open(os.path.join(ROOT, 'config', 'engine.json')))


def now():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def p(*parts):
    path = os.path.join(*parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def type_dir(type_id):
    return os.path.join(DATA, 'types', type_id)


def product_dir(pid):
    return os.path.join(DATA, 'products', pid)


def read(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def write(path, obj):
    path = p(path)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
    return path


def validate(obj, schema_name):
    """Raise ValueError listing every schema problem."""
    import jsonschema
    schema = read(os.path.join(SCHEMAS, schema_name + '.json'))
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(obj), key=lambda e: list(e.path))
    if errs:
        msg = '\n'.join(f"  {'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in errs[:30])
        raise ValueError(f'{schema_name} failed validation:\n{msg}')
    return obj


class Run:
    """One engine run. Every stage records start, finish, outputs and errors in state.json and log.jsonl."""

    def __init__(self, run_id=None):
        if run_id is None:
            run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M')
        self.id = run_id
        self.dir = os.path.join(RUNS, run_id)
        os.makedirs(self.dir, exist_ok=True)
        self.state_path = os.path.join(self.dir, 'state.json')
        self.state = read(self.state_path, {'run': run_id, 'started': now(), 'started_epoch': time.time(), 'stages': {}})
        self.save()

    @classmethod
    def latest(cls):
        ids = sorted(os.listdir(RUNS)) if os.path.isdir(RUNS) else []
        return cls(ids[-1]) if ids else cls()

    def save(self):
        write(self.state_path, self.state)

    def log(self, stage, event, **kw):
        rec = {'at': now(), 'stage': stage, 'event': event, **kw}
        with open(p(self.dir, 'log.jsonl'), 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        return rec

    def stage(self, key, status, **kw):
        s = self.state['stages'].setdefault(key, {})
        s.update(status=status, at=now(), **kw)
        self.save()
        self.log(key, status, **kw)
