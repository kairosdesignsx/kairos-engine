"""Kairos laptop worker. Runs on Darren's laptop every 15 minutes (Windows Task Scheduler).

Picks up jobs the nightly engine drops in  Kairos\\jobs\\outbox\\*.json  and writes results to
Kairos\\jobs\\results\\  (and files under Kairos\\data\\...). Keys live only in Kairos\\worker\\.env.
Python 3.10+ standard library only: nothing to pip install.

  python kairos_worker.py once        process every job in the outbox, then exit (what the scheduler runs)
  python kairos_worker.py login       one-time Etsy sign-in (opens the browser), saves the refresh token
  python kairos_worker.py test        checks the keys and prints your shop name

Jobs
  competitor_photos  {type_id, listings:[{listing_id, rank}]}   -> description + all photos per listing
  publish            {product_id, listing:{...}, files:[...], photos:[...], state:"draft"|"active"}
  stats              {}                                         -> views, favorites, sales per listing
"""
import base64, hashlib, json, mimetypes, os, secrets, sys, threading, time, traceback, urllib.error, urllib.parse, urllib.request, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
KAIROS = os.path.dirname(HERE)                       # ...\Documents\Kairos
OUTBOX = os.path.join(KAIROS, 'jobs', 'outbox')
DONE = os.path.join(KAIROS, 'jobs', 'done')
RESULTS = os.path.join(KAIROS, 'jobs', 'results')
DATA = os.path.join(KAIROS, 'data')
ENV = os.path.join(HERE, '.env')
TOKENS = os.path.join(HERE, 'tokens.json')           # Etsy OAuth tokens (never leaves this laptop)
LOG = os.path.join(HERE, 'worker.log')
API = 'https://api.etsy.com/v3/application'
REDIRECT = 'http://localhost:3003/callback'
SCOPES = 'listings_r listings_w listings_d shops_r transactions_r'


def log(*a):
    line = time.strftime('%Y-%m-%d %H:%M:%S ') + ' '.join(str(x) for x in a)
    print(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def env():
    e = {}
    if os.path.exists(ENV):
        for line in open(ENV, encoding='utf-8'):
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.split('=', 1)
                e[k.strip()] = v.strip().strip('"')
    return e


E = env()


def api_key_variants():
    k, s = E.get('ETSY_KEYSTRING', ''), E.get('ETSY_SHARED_SECRET', '')
    return [f'{k}:{s}', k] if s else [k]


def tokens():
    return json.load(open(TOKENS)) if os.path.exists(TOKENS) else {}


def save_tokens(t):
    t['saved_at'] = time.time()
    json.dump(t, open(TOKENS, 'w'))


def refresh():
    t = tokens()
    if not t.get('refresh_token'):
        raise SystemExit('Not signed in to Etsy. Run: python kairos_worker.py login')
    body = urllib.parse.urlencode({'grant_type': 'refresh_token', 'client_id': E['ETSY_KEYSTRING'], 'refresh_token': t['refresh_token']}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request('https://api.etsy.com/v3/public/oauth/token', data=body, method='POST',
                                                               headers={'Content-Type': 'application/x-www-form-urlencoded'}), timeout=60))
    save_tokens(r)
    return r['access_token']


def access_token():
    t = tokens()
    if t.get('access_token') and time.time() - t.get('saved_at', 0) < t.get('expires_in', 3600) - 120:
        return t['access_token']
    return refresh()


def call(method, path, params=None, form=None, files=None, auth=False, raw_url=None):
    """One Etsy API call. Tries both x-api-key formats; retries on rate limits."""
    url = raw_url or (API + path + ('?' + urllib.parse.urlencode(params, doseq=True) if params else ''))
    last = None
    for key in api_key_variants():
        for attempt in range(4):
            headers = {'x-api-key': key, 'Accept': 'application/json'}
            data = None
            if auth:
                headers['Authorization'] = 'Bearer ' + access_token()
            if files:
                boundary = uuid.uuid4().hex
                parts = []
                for k, v in (form or {}).items():
                    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
                for k, (fname, content) in files.items():
                    ctype = mimetypes.guess_type(fname)[0] or 'application/octet-stream'
                    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n'.encode() + content + b'\r\n')
                parts.append(f'--{boundary}--\r\n'.encode())
                data = b''.join(parts)
                headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
            elif form is not None:
                pairs = []
                for k, v in form.items():
                    if isinstance(v, list):
                        pairs += [(k + '[]' if k in ('tags',) else k, x) for x in v]
                    else:
                        pairs.append((k, v))
                data = urllib.parse.urlencode(pairs).encode()
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            try:
                with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=120) as r:
                    body = r.read()
                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as e:
                msg = e.read()[:500].decode('utf-8', 'ignore')
                if '<html' in msg.lower():  # Etsy's server error pages are HTML: keep the log to one line
                    msg = 'server error page'
                last = f'{e.code} {msg}'
                if e.code == 429 or (e.code >= 500 and method == 'GET'):  # rate limit, or an outage on a read: wait and retry
                    # (never retry a create or upload after a server error: it may have gone through, and a retry would duplicate it)
                    time.sleep(5 * (attempt + 1)); continue
                if e.code in (401, 403) and 'api key' in msg.lower():
                    break  # try the other key format
                if e.code == 401 and auth and attempt == 0:
                    refresh(); continue
                raise RuntimeError(f'{method} {path}: {last}')
            except (urllib.error.URLError, TimeoutError) as e:
                last = f'network {e}'
                if method != 'GET':
                    raise RuntimeError(f'{method} {path}: {last} (not retried: it may have gone through)')
                time.sleep(5 * (attempt + 1)); continue
    raise RuntimeError(f'{method} {path}: {last}')


def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'KairosWorker/1.0'}), timeout=120) as r, open(dest, 'wb') as f:
        f.write(r.read())


# ---------- jobs ----------
_SHOP = {}


def shop_id():
    if E.get('ETSY_SHOP_ID'):
        return E['ETSY_SHOP_ID']
    if 'id' not in _SHOP:
        _SHOP['id'] = str(call('GET', '/users/me', auth=True)['shop_id'])
    return _SHOP['id']


def job_competitor_photos(job):
    out = {'type_id': job['type_id'], 'listings': []}
    base = os.path.join(DATA, 'types', job['type_id'], 'photos')
    first = _competitor_pass(job['listings'], base)
    failed = [L for L, rec in zip(job['listings'], first) if rec.get('error')]
    if failed:  # Etsy has short outages: one more try for the ones that failed, a minute later
        log('competitor retry', len(failed), 'listings in 60s')
        time.sleep(60)
        again = {r['listing_id']: r for r in _competitor_pass(failed, base)}
        first = [again.get(r['listing_id'], r) if r.get('error') else r for r in first]
    out['listings'] = first
    return out


def _competitor_pass(listings, base):
    recs = []
    for L in listings:
        lid = str(L['listing_id'])
        rec = {'listing_id': lid, 'rank': L.get('rank')}
        try:
            info = call('GET', f'/listings/{lid}')
            rec['description'] = info.get('description', '')
            rec['title'] = info.get('title', '')
            pr = info.get('price') or {}
            if pr.get('divisor'):  # the listing's full price in the seller's own currency (EverBee shows the price buyers pay now, in USD)
                rec['full_price'] = pr['amount'] / pr['divisor']; rec['currency'] = pr.get('currency_code')
            imgs = call('GET', f'/listings/{lid}/images').get('results', [])
            rec['photos'] = []
            for i, im in enumerate(imgs, 1):
                url = im.get('url_fullxfull') or im.get('url_570xN')
                dest = os.path.join(base, lid, f'{i:02d}.jpg')
                if not os.path.exists(dest):
                    download(url, dest)
                rec['photos'].append(os.path.relpath(dest, KAIROS))
            time.sleep(0.3)
        except Exception as e:
            rec['error'] = str(e)[:300]
        recs.append(rec)
        log('competitor', lid, len(rec.get('photos', [])), 'photos', rec.get('error', ''))
    return recs


def taxonomy_id(name_parts=('Calendars & Planners',)):
    """Etsy category id for the first name in name_parts that exists (names are tried in order of preference)."""
    cache = os.path.join(HERE, 'taxonomy.json')
    if os.path.exists(cache):
        nodes = json.load(open(cache))
    else:
        nodes = call('GET', '/seller-taxonomy/nodes').get('results', [])
        json.dump(nodes, open(cache, 'w'))
    for want in name_parts:
        stack = list(nodes)
        while stack:
            n = stack.pop(0)
            if n.get('name') == want:
                return n['id']
            stack += n.get('children', [])
    raise RuntimeError('taxonomy not found: ' + str(name_parts))


def job_publish(job):
    shop = shop_id()
    L = job['listing']
    tax = job.get('taxonomy_id') or taxonomy_id(tuple(job.get('taxonomy', ['Calendars & Planners'])))
    form = {'quantity': 999, 'title': L['title'], 'description': L['description'], 'price': L['price'],
            'who_made': 'i_did', 'when_made': 'made_to_order', 'taxonomy_id': tax,
            'type': 'download', 'is_supply': 'false', 'should_auto_renew': 'true', 'tags': L['tags']}
    created = call('POST', f'/shops/{shop}/listings', form=form, auth=True)
    lid = created['listing_id']
    log('publish', job['product_id'], 'draft listing', lid)
    for rank, rel in enumerate(job['photos'], 1):
        p = os.path.join(KAIROS, rel)
        alt = (job.get('alt') or [])[rank - 1] if rank <= len(job.get('alt') or []) else ''
        call('POST', f'/shops/{shop}/listings/{lid}/images', form={'rank': rank, 'alt_text': alt[:500]} if alt else {'rank': rank},
             files={'image': (os.path.basename(p), open(p, 'rb').read())}, auth=True)
    for rank, rel in enumerate(job['files'], 1):
        p = os.path.join(KAIROS, rel)
        call('POST', f'/shops/{shop}/listings/{lid}/files', form={'name': os.path.basename(p), 'rank': rank},
             files={'file': (os.path.basename(p), open(p, 'rb').read())}, auth=True)
    if job.get('state') == 'active':
        call('PATCH', f'/shops/{shop}/listings/{lid}', form={'state': 'active'}, auth=True)
    return {'product_id': job['product_id'], 'listing_id': lid, 'state': job.get('state', 'draft'),
            'url': f'https://www.etsy.com/listing/{lid}'}


def job_stats(job):
    shop = shop_id()
    rows, offset = [], 0
    while True:
        r = call('GET', f'/shops/{shop}/listings', params={'state': 'active', 'limit': 100, 'offset': offset}, auth=True)
        for x in r.get('results', []):
            rows.append({'listing_id': x['listing_id'], 'title': x['title'], 'views': x.get('views'), 'favorites': x.get('num_favorers'),
                         'created': x.get('creation_timestamp'), 'price': x.get('price', {}).get('amount', 0) / max(1, x.get('price', {}).get('divisor', 100))})
        offset += 100
        if offset >= r.get('count', 0):
            break
    sales, offset = {}, 0
    while offset < 2000:
        r = call('GET', f'/shops/{shop}/transactions', params={'limit': 100, 'offset': offset}, auth=True)
        for t in r.get('results', []):
            k = t['listing_id']; sales[k] = sales.get(k, 0) + t.get('quantity', 1)
        offset += 100
        if offset >= r.get('count', 0):
            break
    for x in rows:
        x['sales'] = sales.get(x['listing_id'], 0)
    return {'at': time.time(), 'listings': rows}


def job_fix_listing(job):
    """Change fields on one of OUR listings (for example category or auto-renew). Never touches other shops."""
    shop = shop_id()
    form = {k: v for k, v in job['fields'].items()}
    r = call('PATCH', f"/shops/{shop}/listings/{job['listing_id']}", form=form, auth=True)
    return {'listing_id': job['listing_id'], 'changed': list(form), 'now': {k: r.get(k) for k in list(form) + ['taxonomy_id', 'should_auto_renew', 'state']}}


def job_inspect(job):
    """Read-only: our own listings in full (to see every field Etsy exposes), and the category and attributes top competitors use."""
    out = {'own': [], 'competitors': []}
    shop = shop_id()
    for lid in job.get('own', []):
        rec = {'listing_id': lid}
        try:
            rec['listing'] = call('GET', f'/listings/{lid}', auth=True)
            rec['properties'] = call('GET', f"/shops/{shop}/listings/{lid}/properties", auth=True).get('results', [])
        except Exception as e:
            rec['error'] = str(e)[:300]
        out['own'].append(rec)
    for lid in job.get('competitors', []):
        rec = {'listing_id': str(lid)}
        try:
            info = call('GET', f'/listings/{lid}')
            rec.update({k: info.get(k) for k in ('taxonomy_id', 'shop_id', 'who_made', 'when_made', 'should_auto_renew', 'is_customizable', 'is_personalizable', 'listing_type', 'style')})
            try:
                rec['properties'] = [{'name': x.get('property_name'), 'values': x.get('values')} for x in call('GET', f"/shops/{info['shop_id']}/listings/{lid}/properties").get('results', [])]
            except Exception as e:
                rec['properties_error'] = str(e)[:200]
            time.sleep(0.3)
        except Exception as e:
            rec['error'] = str(e)[:300]
        out['competitors'].append(rec)
        log('inspect', lid, rec.get('taxonomy_id'), rec.get('error', ''))
    return out


JOBS = {'competitor_photos': job_competitor_photos, 'publish': job_publish, 'stats': job_stats, 'fix_listing': job_fix_listing, 'inspect': job_inspect}


def once():
    for d in (OUTBOX, DONE, RESULTS):
        os.makedirs(d, exist_ok=True)
    for name in sorted(os.listdir(OUTBOX)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(OUTBOX, name)
        job = json.load(open(path, encoding='utf-8'))
        res = {'job': name, 'kind': job.get('job'), 'started': time.time()}
        try:
            res['result'] = JOBS[job['job']](job)
            res['ok'] = True
        except Exception as e:
            res['ok'] = False; res['error'] = str(e)[:1000]; res['trace'] = traceback.format_exc()[-1500:]
            log('FAILED', name, e)
        res['finished'] = time.time()
        json.dump(res, open(os.path.join(RESULTS, name), 'w', encoding='utf-8'), indent=1)
        os.replace(path, os.path.join(DONE, name))


def login():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    state = secrets.token_hex(8)
    got = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200); self.end_headers()
            self.wfile.write(b'<h2>Kairos is connected to Etsy. You can close this tab.</h2>')

        def log_message(self, *a):
            pass
    srv = HTTPServer(('localhost', 3003), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    url = 'https://www.etsy.com/oauth/connect?' + urllib.parse.urlencode({'response_type': 'code', 'redirect_uri': REDIRECT, 'scope': SCOPES,
                                                                        'client_id': E['ETSY_KEYSTRING'], 'state': state, 'code_challenge': challenge, 'code_challenge_method': 'S256'})
    print('Opening Etsy in your browser. Click "Allow access".')
    webbrowser.open(url)
    for _ in range(600):
        if got:
            break
        time.sleep(0.5)
    if got.get('state') != state or 'code' not in got:
        raise SystemExit('Sign-in did not finish: ' + json.dumps(got))
    body = urllib.parse.urlencode({'grant_type': 'authorization_code', 'client_id': E['ETSY_KEYSTRING'], 'redirect_uri': REDIRECT,
                                   'code': got['code'], 'code_verifier': verifier}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request('https://api.etsy.com/v3/public/oauth/token', data=body, method='POST',
                                                               headers={'Content-Type': 'application/x-www-form-urlencoded'}), timeout=60))
    save_tokens(r)
    print('Signed in. Token saved on this laptop only.')


def test():
    me = call('GET', '/users/me', auth=True)
    shop = call('GET', f"/shops/{shop_id()}")
    print('OK. Etsy user', me.get('user_id'), 'shop', shop.get('shop_name'), 'shop id', shop.get('shop_id'))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'once'
    {'once': once, 'login': login, 'test': test}[cmd]()
