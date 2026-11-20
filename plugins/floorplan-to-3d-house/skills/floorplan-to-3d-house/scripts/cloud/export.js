const { chromium } = require('playwright');
const fs = require('fs');
const { localAsset } = require('./local_assets');   // bundled three.js r187 + tex/ + models/ (served instead of the CDN)
(async () => {
  const S = process.env.WORK || process.cwd(), NAME = process.env.MODEL_NAME || 'model', OUT = process.argv[3], mode = process.argv[4] || 'all';
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const vp = mode === 'glb' ? { width: 320, height: 200 } : { width: 1920, height: 1080 };
  const page = await browser.newPage({ viewport: vp });
  page.on('pageerror', e => console.log('pageerror', e.message));
  page.on('console', m => { if (m.type() === 'error') console.log('console', m.text()); });
  await page.route('**/*', route => {
    const u = route.request().url();
    const f = localAsset(u, S); if (f) return route.fulfill(f);
    if (u.startsWith('https://fonts')) return route.abort();
    if (u.startsWith('http://local/')) return route.fulfill({ path: S + '/site3d/export.html', contentType: 'text/html' });
    return route.continue();
  });
  await page.goto('http://local/export.html', { waitUntil: 'domcontentloaded', timeout: 300000 });
  await page.waitForFunction(() => window.__ready && document.getElementById('loading').hidden, null, { timeout: 300000 });
  await page.waitForTimeout(1000);
  await page.evaluate(() => window.__stop());
  if (mode === 'all' || mode === 'glb') {
    const b64 = await page.evaluate(() => window.__exportGLB());
    fs.writeFileSync(OUT + '/' + NAME + '.glb', Buffer.from(b64, 'base64'));
    console.log('glb bytes', Buffer.from(b64, 'base64').length);
    fs.writeFileSync(OUT + '/tris.json', await page.evaluate(() => window.__exportTris()));
    console.log('tris ok');
  }
  if (mode === 'all' || mode === 'renders') {
    for (const v of ['aerial', 'street', 'garden', 'interior', 'top']) {
      await page.evaluate(k => { window.__view(k); window.__renderOnce(); }, v);
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${OUT}/render_${v}.png`, timeout: 600000 });
      console.log('render', v);
    }
  }
  await browser.close();
})();
