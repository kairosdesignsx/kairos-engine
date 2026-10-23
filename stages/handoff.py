"""Laptop handoff catch-up.

The nightly run happens in a cloud session. If it can't reach the laptop, the built files
die with that session (files/ and photos/ aren't in git). This finds queued products that
never reached the laptop and rebuilds their handoff from the saved plan.

  python3 stages/handoff.py missing          -> queued products with no delivery record
  python3 stages/handoff.py rebuild <pid>    -> build + photos (if needed) + data/handoff/<pid>/
  python3 stages/handoff.py done <pid>       -> record the laptop copy (after device_commit_files)
"""
import json, os, subprocess, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib')); sys.path.insert(0, os.path.dirname(__file__))
import store, enqueue

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _d(pid): return os.path.join(store.DATA, 'products', pid)


def missing():
    out = []
    for pid in sorted(os.listdir(os.path.join(store.DATA, 'products'))):
        d = _d(pid)
        if os.path.exists(os.path.join(d, 'queue.json')) and not os.path.exists(os.path.join(d, 'handoff.json')):
            out.append(pid)
    return out


def rebuild(pid):
    d = _d(pid)
    build = store.read(os.path.join(d, 'build.json'))
    if not all(os.path.exists(os.path.join(d, 'files', f['name'])) for f in build['files']):
        subprocess.run([sys.executable, 'stages/build.py', 'run', pid], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    ph = os.path.join(d, 'photos')
    if not (os.path.isdir(ph) and any(f.startswith('photo-') for f in os.listdir(ph))):
        subprocess.run([sys.executable, 'stages/photos.py', 'run', pid], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['git', 'checkout', '--', f'data/products/{pid}/build.json', f'data/products/{pid}/photos.json'], cwd=ROOT)
    out = enqueue._handoff(pid, d, store.read(os.path.join(d, 'listing.json')), store.read(os.path.join(d, 'build.json')))
    files = sorted(os.path.relpath(os.path.join(r, f), out) for r, _, fs in os.walk(out) for f in fs)
    return {"pid": pid, "handoff": out, "files": files,
            "laptop": f"C:\\Users\\darre\\Documents\\Kairos\\data\\products\\{pid}\\"}


def done(pid):
    rec = {"pid": pid, "laptop": f"C:\\Users\\darre\\Documents\\Kairos\\data\\products\\{pid}\\",
           "copied_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'}
    store.write(os.path.join(_d(pid), 'handoff.json'), rec)
    return rec


if __name__ == '__main__':
    cmd = sys.argv[1]
    r = missing() if cmd == 'missing' else rebuild(sys.argv[2]) if cmd == 'rebuild' else done(sys.argv[2])
    print(json.dumps(r, indent=1))
