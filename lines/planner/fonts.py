"""Embed OFL fonts (Google Fonts via @fontsource) as data URIs. Safe to embed in sold PDFs."""
import base64
import os
NM = os.environ.get('FONTSOURCE', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'node_modules', '@fontsource') + '/')
FILES = {
    'Corm': [('cormorant-garamond', 400, 'normal'), ('cormorant-garamond', 600, 'normal'), ('cormorant-garamond', 500, 'italic')],
    'Jost': [('jost', 400, 'normal'), ('jost', 500, 'normal'), ('jost', 600, 'normal')],
    'Script': [('pinyon-script', 400, 'normal')],
    'Fraunces': [('fraunces', 400, 'normal'), ('fraunces', 600, 'normal')],
    'Manrope': [('manrope', 400, 'normal'), ('manrope', 500, 'normal'), ('manrope', 700, 'normal')],
    'Quicksand': [('quicksand', 500, 'normal'), ('quicksand', 700, 'normal')],
    'Nunito': [('nunito', 400, 'normal'), ('nunito', 600, 'normal'), ('nunito', 700, 'normal')],
    'DMSerif': [('dm-serif-display', 400, 'normal')],
    'Outfit': [('outfit', 400, 'normal'), ('outfit', 500, 'normal'), ('outfit', 600, 'normal')],
    'Baskerville': [('libre-baskerville', 400, 'normal'), ('libre-baskerville', 700, 'normal')],
}
_cache = {}
def face(family):
    if family in _cache: return _cache[family]
    out = []
    for pkg, w, style in FILES[family]:
        p = f'{NM}{pkg}/files/{pkg}-latin-{w}-{style}.woff2'
        b = base64.b64encode(open(p, 'rb').read()).decode()
        out.append(f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{b}) format('woff2');font-weight:{w};font-style:{style}}}")
    _cache[family] = ''.join(out)
    return _cache[family]
def faces(*families):
    return ''.join(face(f) for f in dict.fromkeys(families))
