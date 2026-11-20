const { chromium } = require('playwright');
(async () => {
  const S = process.env.WORK || process.cwd();   // project work dir (contains site3d/)
  const shots = JSON.parse(process.argv[2]), page_ = process.argv[3] || 'page.html';
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: shots[0].w || 1400, height: shots[0].h || 860 } });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('console', m.type(), m.text().slice(0, 200)); });
  page.on('pageerror', e => console.log('pageerror', e.message));
  const { localAsset } = require('./local_assets');   // bundled three.js r187 + tex/ + models/
  await page.route('**/*', route => {
    const u = route.request().url();
    const f = localAsset(u, S); if (f) return route.fulfill(f);
    if (u.startsWith('https://fonts')) return route.abort();
    if (u.startsWith('http://local/')) return route.fulfill({ path: S + '/site3d/' + page_, contentType: 'text/html' });
    return route.continue();
  });
  await page.goto('http://local/x.html', { waitUntil: 'domcontentloaded', timeout: 300000 });
  await page.waitForFunction(() => window.__ready && document.getElementById('loading').hidden, null, { timeout: 400000 });
  for (const sh of shots) {
    for (const a of (sh.actions || [])) { if (a.startsWith('js:')) await page.evaluate(a.slice(3)); else await page.evaluate(sel => document.querySelector(sel).click(), a); }   // DOM click: page.click times out while the software renderer is busy   // 'js:window.__storey("0")'
    await page.waitForTimeout(sh.wait || 2500);
    await page.screenshot({ path: S + '/' + sh.out, timeout: 400000 });
    console.log('shot', sh.out);
  }
  await browser.close();
})();
