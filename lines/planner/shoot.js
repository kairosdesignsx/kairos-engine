// node shoot.js dir  -> screenshots every mock-*.html in dir to photo-*.jpg (2700x2025)
const { chromium } = require(require('path').join(__dirname, '..', '..', 'node_modules', 'playwright'));
const fs = require('fs'); const dir = process.argv[2];
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM || require(require('path').join(__dirname, '..', '..', 'lib', 'chromium.js'))(), args: ['--no-sandbox', '--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 2700, height: 2025 } });
  for (const f of fs.readdirSync(dir).filter(f => f.startsWith('mock-') && f.endsWith('.html')).sort()) {
    await p.goto('file://' + dir + '/' + f); await p.waitForTimeout(400);
    await p.screenshot({ path: dir + '/' + f.replace('mock-', 'photo-').replace('.html', '.jpg'), type: 'jpeg', quality: 88 });
  }
  await b.close();
})();
