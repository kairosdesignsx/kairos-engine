// Finds a Chromium for Playwright in the cloud session. Browser folder layouts change between images,
// so try every known spelling instead of one hard-coded path.
const fs = require('fs'), path = require('path');
module.exports = () => {
  const root = '/opt/pw-browsers';
  const cands = [];
  try {
    for (const d of fs.readdirSync(root).filter(d => d.startsWith('chromium_headless_shell'))) {
      cands.push(path.join(root, d, 'chrome-headless-shell-linux64', 'chrome-headless-shell'), path.join(root, d, 'chrome-linux', 'headless_shell'));
    }
  } catch (e) {}
  cands.push(path.join(root, 'chromium'));
  return cands.find(p => { try { return fs.statSync(p).isFile(); } catch (e) { return false; } });
};
