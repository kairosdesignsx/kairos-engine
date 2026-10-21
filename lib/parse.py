"""Turn EverBee display strings into numbers."""
import re


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ('', '—', '-', 'N/A'):
        return None
    m = re.search(r'-?[\d,]*\.?\d+', s.replace('$', ''))
    if not m:
        return None
    x = float(m.group(0).replace(',', ''))
    if re.search(r'\d\s*[kK]\b', s):
        x *= 1000
    return x


def listing_id(url):
    m = re.search(r'/listing/(\d+)', url or '')
    return m.group(1) if m else None


def stars(v):
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v)
    n = s.count('★')
    if n:
        return n
    x = num(s)
    return int(x) if x else None
