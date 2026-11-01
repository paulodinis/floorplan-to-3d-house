const { chromium } = require('playwright');
(async () => {
  const S = process.env.WORK || process.cwd();   // project work dir (contains site3d/, three/)
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 640, height: 400 } });
  page.on('pageerror', e => console.log('pageerror', e.message));
  const map = { 'build/three.module.js': S + '/three/t/build/three.module.js', 'controls/OrbitControls.js': S + '/three/t/examples/jsm/controls/OrbitControls.js', 'loaders/RGBELoader.js': S + '/three/RGBELoader.js' };
  await page.route('**/*', route => {
    const u = route.request().url();
    for (const k in map) if (u.includes(k)) return route.fulfill({ path: map[k], contentType: 'text/javascript' });
    if (u.startsWith('https://fonts')) return route.abort();
    if (u.includes('/tex/')) { const n = u.split('/tex/')[1]; return route.fulfill({ path: S + '/site3d/tex/' + n, contentType: n.endsWith('.png') ? 'image/png' : n.endsWith('.txt') ? 'text/plain' : 'image/jpeg' }); }
    if (u.startsWith('http://local/')) return route.fulfill({ path: S + '/site3d/page.html', contentType: 'text/html' });
    return route.continue();
  });
  await page.goto('http://local/x.html');
  await page.waitForFunction(() => window.__ready && window.__nav, null, { timeout: 400000 });
  const out = await page.evaluate(() => {
    const { setNav, NAV, navUpdate, camera } = window.__nav;
    setNav('walk');
    const log = [];
    const p = camera.position;
    const go = (tx, tz, label, maxIt = 900) => {
      let it = 0;
      for (; it < maxIt; it++) {
        const dx = tx - p.x, dz = tz - p.z, d = Math.hypot(dx, dz);
        if (d < 0.15) break;
        NAV.yaw = Math.atan2(-dx, -dz); NAV.keys.add('KeyW'); navUpdate(0.05);
      }
      NAV.keys.clear();
      for (let i = 0; i < 40; i++) navUpdate(0.05);
      log.push(`${label}: target(${tx},${tz}) at (${p.x.toFixed(2)}, ${p.z.toFixed(2)}) feet ${(p.y - 1.65 + 32).toFixed(2)} it=${it}`);
    };
    log.push(`start (${p.x.toFixed(2)}, ${p.z.toFixed(2)}) feet ${(p.y - 1.65 + 32).toFixed(2)}`);
    go(-10.6, -3.0, 'pedestrian gate to the front door');
    go(-8.4, -3.0, 'through the front door (hall)');
    go(-8.4, -0.55, 'hall to corridor');
    go(-4.1, -0.55, 'corridor at the WC suite door');
    go(-4.1, 1.5, 'into the I.S. suite');
    go(-4.1, -0.55, 'back to the corridor');
    go(0.6, -0.57, 'onto the stair-top strip');
    go(4.4, -0.57, 'down the stair (sala)');
    go(4.2, -2.6, 'kitchen side, at the pantry door');
    go(2.3, -2.6, 'into the pantry');
    go(4.6, -2.6, 'back to the kitchen');
    go(4.2, 1.6, 'living, at the laundry door');
    go(2.6, 1.6, 'into the laundry');
    go(4.6, 1.6, 'back to the living room');
    go(4.4, -0.4, 'around the dining chairs');
    go(8.6, -0.8, 'living room');
    go(8.2, 2.9, 'living room south');
    go(8.2, 5.2, 'out to the alpendre');
    go(14.0, 5.2, 'alpendre east');
    go(14.0, 3.8, 'terrace east');
    go(18.0, 3.8, 'down garden steps W2');
    // garage route
    camera.position.set(-17.2, 0, -13.0); camera.position.y = window.__nav.floorAt(-17.2, -13.0, 5) + 1.65;
    go(-9.2, -13.0, 'vehicle gate to the (closed) garage door');
    go(-12.0, -9.5, 'side path south');
    go(-4.05, -9.3, 'garden strip to the garage side door');
    go(-4.05, -11.6, 'into the garage through the side door');
    go(-3.6, -11.05, 'to the workshop door');
    go(0.0, -11.05, 'into the workshop');
    go(1.05, -11.0, 'to the workshop south door');
    go(1.05, -8.5, 'out to the garden');
    return log;
  });
  console.log(out.join('\n'));
  await browser.close();
})();
