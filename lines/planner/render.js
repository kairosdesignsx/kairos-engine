// node render.js page.html out.pdf shotsDir anchor1,anchor2,...  (page size from CSS)
const { chromium } = require(require('path').join(__dirname, '..', '..', 'node_modules', 'playwright'));
const [,, html, pdf, shots, anchors, w, h] = process.argv;
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM || require(require('path').join(__dirname, '..', '..', 'lib', 'chromium.js'))(), args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: +(w || 1024), height: +(h || 768) }, deviceScaleFactor: 2 });
  await p.goto('file://' + html, { waitUntil: 'load' }); await p.waitForTimeout(500);
  const over = await p.evaluate(() => {
    const out = [];
    for (const b of document.querySelectorAll('.pg .body')) {
      const pg = b.parentElement.id;
      if (b.scrollHeight - b.clientHeight > 2) out.push([pg, 'page', b.scrollHeight - b.clientHeight]);
      const bb = b.getBoundingClientRect();
      for (const box of b.querySelectorAll('.box')) {               // content spilling out of a box, or a box spilling off the page
        if (box.scrollHeight - box.clientHeight > 3) out.push([pg, 'box: ' + (box.querySelector('.k') || {}).textContent, box.scrollHeight - box.clientHeight]);
        const r = box.getBoundingClientRect();
        if (r.bottom - bb.bottom > 3) out.push([pg, 'off page: ' + (box.querySelector('.k') || {}).textContent, Math.round(r.bottom - bb.bottom)]);
      }
      if (out.length > 30) break;
    }
    return out;
  });
  console.log('overflow', JSON.stringify(over));
  if (pdf !== '-') await p.pdf({ path: pdf, preferCSSPageSize: true, printBackground: true });
  if (shots && anchors) for (const a of anchors.split(',')) {
    const el = await p.$('#' + a); if (el) await el.screenshot({ path: `${shots}/${a}.png` });
  }
  await b.close();
})();
