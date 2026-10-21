// node render.js page.html out.pdf shotsDir anchor1,anchor2,...  (page size from CSS)
const { chromium } = require(require('path').join(__dirname, '..', '..', 'node_modules', 'playwright'));
const [,, html, pdf, shots, anchors, w, h] = process.argv;
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM || require('fs').readdirSync('/opt/pw-browsers').filter(d => d.startsWith('chromium_headless_shell')).map(d => '/opt/pw-browsers/' + d + '/chrome-linux/headless_shell')[0], args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: +(w || 1024), height: +(h || 768) }, deviceScaleFactor: 2 });
  await p.goto('file://' + html, { waitUntil: 'load' }); await p.waitForTimeout(500);
  const over = await p.evaluate(() => [...document.querySelectorAll('.pg .body')].map(b => [b.parentElement.id, b.scrollHeight - b.clientHeight]).filter(x => x[1] > 2).slice(0, 10));
  console.log('overflow', JSON.stringify(over));
  if (pdf !== '-') await p.pdf({ path: pdf, preferCSSPageSize: true, printBackground: true });
  if (shots && anchors) for (const a of anchors.split(',')) {
    const el = await p.$('#' + a); if (el) await el.screenshot({ path: `${shots}/${a}.png` });
  }
  await b.close();
})();
