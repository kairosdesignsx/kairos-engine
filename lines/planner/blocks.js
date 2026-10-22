// node blocks.js page.html anchor1,anchor2,... W H -> JSON {anchor: [[x0,y0,x1,y1,kind,text], ...]} in page CSS px.
// Atomic pieces a photo crop must never slice: every .box, every text leaf, every svg, every calendar cell, the rail tabs.
const { chromium } = require(require('path').join(__dirname, '..', '..', 'node_modules', 'playwright'));
const [,, html, anchors, w, h] = process.argv;
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM || require('fs').readdirSync('/opt/pw-browsers').filter(d => d.startsWith('chromium_headless_shell')).map(d => '/opt/pw-browsers/' + d + '/chrome-linux/headless_shell')[0], args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: +(w || 768), height: +(h || 1024) } });
  await p.goto('file://' + html, { waitUntil: 'load' }); await p.waitForTimeout(300);
  const out = await p.evaluate((ids) => {
    const res = {};
    for (const id of ids) {
      const pg = document.getElementById(id); if (!pg) continue;
      const o = pg.getBoundingClientRect(); const list = [];
      const add = (r, kind, t) => { if (r.width > 0 && r.height > 0) list.push([r.left - o.left, r.top - o.top, r.right - o.left, r.bottom - o.top, kind, (t || '').slice(0, 30)]); };
      pg.querySelectorAll('.box, svg, .d, .rail a, .nav a, .crumb, i, .chk').forEach(e => add(e.getBoundingClientRect(), e.classList.contains('box') ? 'box' : e.tagName.toLowerCase(), e.textContent.trim()));
      const tw = document.createTreeWalker(pg, NodeFilter.SHOW_TEXT);
      let n; while ((n = tw.nextNode())) { if (!n.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(n); for (const rr of r.getClientRects()) add(rr, 'text', n.textContent.trim()); }
      res[id] = list;
    }
    return res;
  }, anchors.split(','));
  console.log(JSON.stringify(out));
  await b.close();
})();
