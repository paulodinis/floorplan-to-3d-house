// Shared by export.js, navtest.js and shot2.js: serve the page's CDN and relative assets from local files,
// so the Playwright tests run offline.
//  - three.js r187 (WebGPU build + addons) from scripts/web/three/ (build/ and jsm/, each file under 1 MiB)
//  - tex/<file> and models/<file> from the project's site3d/ folder
const fs = require('fs');
const path = require('path');
const THREE_VERSION = '0.187.0';
const T = path.join(__dirname, '..', 'web', 'three');

const TYPES = { '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg', '.txt': 'text/plain', '.json': 'application/json' };
const typeOf = p => TYPES[path.extname(p)] || 'application/octet-stream';

function localAsset(url, work) {
  const m = url.match(/three@([\d.]+)\/(build|examples\/jsm)\/([^?#]+)/);
  if (m) {
    if (m[1] !== THREE_VERSION) console.log('warning: page asks for three@' + m[1] + ', bundled is ' + THREE_VERSION);
    const p = path.join(T, m[2] === 'build' ? 'build' : 'jsm', m[3]);
    return fs.existsSync(p) ? { path: p, contentType: 'text/javascript' } : null;
  }
  for (const dir of ['tex', 'models']) {
    const k = url.indexOf('/' + dir + '/');
    if (k >= 0) { const p = path.join(work, 'site3d', dir, url.slice(k + dir.length + 2).split(/[?#]/)[0]); return { path: p, contentType: typeOf(p) }; }
  }
  return null;
}

module.exports = { localAsset, THREE_VERSION };
