"""Stage 7: Photos. Render the listing photos from the brief's photo plan and the listing's photo copy."""
import importlib, json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import store


def run(pid):
    pdir = store.product_dir(pid)
    brief = store.read(os.path.join(pdir, 'brief.json'))
    listing = store.read(os.path.join(pdir, 'listing.json'))
    build = store.read(os.path.join(pdir, 'build.json'))
    if not (brief and listing and build):
        return {"ok": False, "blocked": "needs brief, listing and build first"}
    ldir = os.path.join(store.ROOT, 'lines', brief['line'])
    sys.path.insert(0, ldir)
    photos = importlib.import_module('photos')
    out = os.path.join(pdir, 'photos')
    shutil.rmtree(out, ignore_errors=True)
    keys = photos.scenes(brief, listing, build, os.path.join(pdir, 'shots'), out)
    subprocess.run(['node', os.path.join(ldir, 'shoot.js'), out], check=True, timeout=600)
    files = sorted(f for f in os.listdir(out) if f.startswith('photo-'))
    rec = {"photos": files, "made": store.now(), "zoom_scale": {f"photo-{k}.jpg": v for k, v in getattr(photos, "SCALES", {}).items()}}
    store.write(os.path.join(pdir, 'photos.json'), rec)
    return {"ok": len(files) >= 5, "photos": files}


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[2] if sys.argv[1] == 'run' else sys.argv[1]), indent=1))
