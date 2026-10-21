"""Which CSS features make planner pages heavy? Render the same 40-page sample with variants."""
import os, re, subprocess, sys
sys.path.insert(0, 'lines/planner'); import gen
spec = {"title": "Probe", "dating": {"mode": "dated", "year": 2027}, "theme": "night",
        "sections": [{"module": "index"}, {"module": "year"}, {"module": "calendar", "habits": True, "week": {"preset": "adhd"}, "day": {"preset": "adhd"}}]}
r = gen.build(spec)
html = r['html']
# keep only first 40 pages
parts = html.split('<section class="pg"')
head, pages = parts[0], parts[1:41]
tail = '</body></html>'
base = head + ''.join('<section class="pg"' + p.split('</section>')[0] + '</section>' for p in pages) + tail
variants = {
 'box_square': base.replace('.box{{border:1.3px solid'.replace('{{','{'), '.box{border-radius:0 !important;border:1.3px solid'),
 'chk_square': base.replace('border-radius:3px;flex:none', 'flex:none'),
 'box_outline_svg': base,
 'base': base,
 'no_line_gradients': base.replace('repeating-linear-gradient', 'none'),
 'no_dot_gradients': re.sub(r'background-image:radial-gradient\([^;]*\);', '', base),
 'no_rail': re.sub(r'<div class="rail">.*?</div>', '', base, flags=re.S),
 'no_radius': base.replace('border-radius', 'x-radius'),
}
variants['pills_square'] = base.replace('border-radius:99px', 'border-radius:0')
variants['circles_square'] = base.replace('border-radius:50%', 'border-radius:0')
variants['all_but_pills'] = re.sub(r'border-radius:(?!99px)[^;}]+', 'border-radius:0', base)
variants['box_square'] = base.replace('border-radius:12px', 'border-radius:0')
variants['no_radius2'] = re.sub(r'border-radius:[^;}"]+', 'border-radius:0', base)
variants['box_r4'] = base.replace('border-radius:12px', 'border-radius:4px')
variants = {k: v for k, v in variants.items() if k in ('box_square', 'no_radius2', 'box_r4')}
for k, v in variants.items():
    h = os.path.abspath(f'tests/out/probe-{k}.html'); open(h, 'w').write(v)
    pdf = h.replace('.html', '.pdf')
    subprocess.run(['node', 'lines/planner/render.js', h, pdf, '-', ''], capture_output=True)
    subprocess.run(['qpdf', '--object-streams=generate', '--recompress-flate', '--compression-level=9', pdf, pdf + '.min'], check=True)
    print(f'{k:20s} {os.path.getsize(pdf + ".min") / 40 / 1000:.1f} KB/page')
