import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const SITE = __SITE_JSON__;
const PROJ = __PROJECT_JSON__;     // project.json: name, location, north, UI strings, views (see project.example.json)
const T = Object.assign({ load_fail: 'Could not load', show: 'Show controls', hide: 'Hide controls' }, PROJ.ui || {});
const FFL = SITE.meta.ffl;
const NORTH_DEG = PROJ.north_deg ?? SITE.meta.north_deg ?? 0;   // true north, clockwise from sheet-up
const LAT = PROJ.location?.lat ?? 40.0;                         // site latitude (sun path)
const WALL_H = 3.0, SLAB_T = 0.35, EAVE_T = 0.22, PITCH = THREE.MathUtils.degToRad(20);
const SCALE = parseFloat(String(SITE.meta.scale || '1:200').split(':').pop()) || 200;
const K = 25.4 / 72 * SCALE / 1000, OX = SITE.meta.origin_pt[0], OY = SITE.meta.origin_pt[1];
const P2M = (x, y) => [(x - OX) * K, -(y - OY) * K];

const stage = document.getElementById('stage');
const labelsEl = document.getElementById('labels');
const loadingEl = document.getElementById('loading');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- renderer / scene ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
renderer.outputColorSpace = THREE.SRGBColorSpace;
stage.appendChild(renderer.domElement);
const maxAniso = renderer.capabilities.getMaxAnisotropy();

const scene = new THREE.Scene();
let envTex = null;   // sky environment map; switched off at night
scene.fog = new THREE.Fog(0xd9dcd6, 160, 420);
const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 900);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.495;
controls.minDistance = 2;
controls.maxDistance = 220;

const hemi = new THREE.HemisphereLight(0xdfe9f3, 0x7d7058, 0.55);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff1dc, 2.6);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
Object.assign(sun.shadow.camera, { left: -45, right: 45, top: 45, bottom: -45, near: 1, far: 260 });
sun.shadow.bias = -0.0003;
sun.shadow.normalBias = 0.025;
scene.add(sun, sun.target);

// ---------- loading ----------
const manager = new THREE.LoadingManager();
manager.onLoad = () => { loadingEl.hidden = true; };
manager.onError = url => { loadingEl.textContent = `${T.load_fail} ${url.split('/').pop()}`; };
const texLoader = new THREE.TextureLoader(manager);
function photo(url, metres, srgb = true) {
  const t = texLoader.load(url);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = maxAniso;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.userData.metres = metres;
  return t;
}
function maskTex(url) {
  const t = texLoader.load(url);
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  t.colorSpace = THREE.NoColorSpace;
  t.anisotropy = 4;
  return t;
}

// sky lighting: equirectangular sky stored as an sRGB JPEG at 1/SKY_SCALE of its HDR radiance
// (the host serves no .hdr type); decoded back to linear half-float before PMREM. The sun disc,
// which clips, is added back below.
const SKY_SCALE = 4.0;
new THREE.ImageLoader().load('tex/sky.jpg', img => {
  const w = img.width, h = img.height, cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  const g = cv.getContext('2d', { willReadFrequently: true }); g.drawImage(img, 0, 0);
  const px = g.getImageData(0, 0, w, h).data, lut = new Uint16Array(256);
  for (let i = 0; i < 256; i++) { const v = i / 255; lut[i] = THREE.DataUtils.toHalfFloat((v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)) * SKY_SCALE); }
  const data = new Uint16Array(w * h * 4), one = THREE.DataUtils.toHalfFloat(1);
  for (let i = 0; i < px.length; i += 4) { data[i] = lut[px[i]]; data[i + 1] = lut[px[i + 1]]; data[i + 2] = lut[px[i + 2]]; data[i + 3] = one; }
  // re-inject the clipped sun disc (half the sky's energy) as a small gaussian so PMREM keeps its warmth:
  // centre in px, solid-angle-weighted excess linear RGB above SKY_SCALE, measured from the source HDR
  const SUN = { x: 613.9, y: 227.0, sigma: 2.5, rgb: [162030, 112331, 43191] }, rad = Math.ceil(SUN.sigma * 4), blob = [];
  let norm = 0;
  for (let y = Math.round(SUN.y) - rad; y <= Math.round(SUN.y) + rad; y++) for (let x = Math.round(SUN.x) - rad; x <= Math.round(SUN.x) + rad; x++) {
    const gw = Math.exp(-((x - SUN.x) ** 2 + (y - SUN.y) ** 2) / (2 * SUN.sigma ** 2));
    norm += gw * Math.cos(((y + 0.5) / h - 0.5) * Math.PI); blob.push([x, y, gw]);
  }
  for (const [x, y, gw] of blob) {
    const i = (y * w + ((x % w) + w) % w) * 4;
    for (let c = 0; c < 3; c++) data[i + c] = THREE.DataUtils.toHalfFloat(THREE.DataUtils.fromHalfFloat(data[i + c]) + SUN.rgb[c] * gw / norm);
  }
  const hdr = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, THREE.HalfFloatType);
  Object.assign(hdr, { colorSpace: THREE.LinearSRGBColorSpace, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, generateMipmaps: false, flipY: true, mapping: THREE.EquirectangularReflectionMapping });
  hdr.needsUpdate = true;
  const pm = new THREE.PMREMGenerator(renderer);
  envTex = pm.fromEquirectangular(hdr).texture; scene.environment = envTex;
  hdr.dispose(); pm.dispose(); updateSun();
}, undefined, () => {});

// ---------- procedural textures (canvas) ----------
function rand(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
function tileNoise(size, cells, seed) {        // periodic value noise, smoothstep-interpolated
  const r = rand(seed), g = new Float32Array(cells * cells).map(() => r());
  const out = new Float32Array(size * size), f = cells / size;
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const gx = x * f, gy = y * f, ix = Math.floor(gx), iy = Math.floor(gy);
    let tx = gx - ix, ty = gy - iy; tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty);
    const a = g[(iy % cells) * cells + ix % cells], b = g[(iy % cells) * cells + (ix + 1) % cells];
    const c = g[((iy + 1) % cells) * cells + ix % cells], d = g[((iy + 1) % cells) * cells + (ix + 1) % cells];
    out[y * size + x] = (a + (b - a) * tx) + ((c + (d - c) * tx) - (a + (b - a) * tx)) * ty;
  }
  return out;
}
function fbmTile(size, octs, seed) {
  const out = new Float32Array(size * size);
  octs.forEach(([cells, amp], i) => { const n = tileNoise(size, cells, seed + i * 17); for (let k = 0; k < out.length; k++) out[k] += (n[k] - 0.5) * amp; });
  return out;
}
function canvasTex(w, h, paint, metresW, metresH, srgb = true) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
  const ctx = cv.getContext('2d'); const extra = paint(ctx, w, h);
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = maxAniso;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.userData.metres = [metresW, metresH ?? metresW];
  t.userData.extra = extra;
  return t;
}
function normalFromHeight(hgt, w, h, strength, metresW, metresH) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
  const ctx = cv.getContext('2d'), id = ctx.createImageData(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const L = hgt[y * w + (x - 1 + w) % w], R = hgt[y * w + (x + 1) % w];
    const U = hgt[((y - 1 + h) % h) * w + x], D = hgt[((y + 1) % h) * w + x];
    let nx = (L - R) * strength, ny = (D - U) * strength, nz = 1;
    const l = Math.hypot(nx, ny, nz); nx /= l; ny /= l; nz /= l;
    const i = (y * w + x) * 4;
    id.data[i] = (nx * 0.5 + 0.5) * 255; id.data[i + 1] = (ny * 0.5 + 0.5) * 255; id.data[i + 2] = (nz * 0.5 + 0.5) * 255; id.data[i + 3] = 255;
  }
  ctx.putImageData(id, 0, 0);
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = maxAniso; t.colorSpace = THREE.NoColorSpace;
  t.userData.metres = [metresW, metresH ?? metresW];
  return t;
}
function pixels(ctx, w, h, fn) {
  const id = ctx.createImageData(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const [r, g, b] = fn(x, y, y * w + x), i = (y * w + x) * 4;
    id.data[i] = r; id.data[i + 1] = g; id.data[i + 2] = b; id.data[i + 3] = 255;
  }
  ctx.putImageData(id, 0, 0);
}
const clamp255 = v => Math.max(0, Math.min(255, v));

// lime render (reboco areado) — 2 m tile
const RENDER_N = 512;
const renderH = fbmTile(RENDER_N, [[4, .5], [16, .35], [64, .3], [256, .5]], 11);
const grainR = rand(5);
const renderTex = canvasTex(RENDER_N, RENDER_N, (ctx, w, h) => pixels(ctx, w, h, (x, y, k) => {
  const v = 1 + renderH[k] * 0.07 + (grainR() - 0.5) * 0.035;
  return [clamp255(241 * v), clamp255(236 * v), clamp255(226 * v)];
}), 2.0);
const renderNrm = normalFromHeight(renderH, RENDER_N, RENDER_N, 3.2, 2.0);

// terracotta roof tiles (telha) — 5 x 3 tiles, 1.05 m x 0.96 m
const TC = 5, TR = 3, TW = 105 * 4, TH = 96 * 4, tw = TW / TC, th = TH / TR;
const tileHeight = new Float32Array(TW * TH);
const tileTex = canvasTex(TW, TH, (ctx) => {
  const r = rand(23);
  const grain = fbmTile(TW > TH ? TW : TH, [[8, .4], [32, .3], [128, .4]], 41);
  const tones = [];
  for (let row = 0; row < TR; row++) for (let col = 0; col < TC; col++) {
    const age = r();
    tones.push([0.72 + r() * 0.08 - age * 0.12, 0.36 + r() * 0.06 - age * 0.05, 0.22 + r() * 0.05 - age * 0.04]);
  }
  pixels(ctx, TW, TH, (x, y, k) => {
    const col = Math.floor(x / tw), row = Math.floor(y / th);
    const fx = (x % tw) / tw, fy = (y % th) / th;           // fy 0 = uphill edge, 1 = lower lip
    const prof = Math.sin(Math.PI * fx);                      // rounded tile across its width
    const lip = fy > 0.9 ? 1 - (fy - 0.9) * 4 : 1;
    const shadow = fy < 0.16 ? 0.55 + 0.45 * (fy / 0.16) : 1; // shade under the course above
    const gap = (fx < 0.035 || fx > 0.965) ? 0.45 : 1;
    const h = prof * 0.8 + (fy > 0.86 ? 0.25 : 0) - (fy < 0.12 ? 0.4 * (1 - fy / 0.12) : 0);
    tileHeight[k] = h * gap;
    const t = tones[row * TC + col], g = 1 + grain[(y % TW) * TW + (x % TW)] * 0.18;
    const light = (0.62 + 0.45 * prof) * shadow * gap * lip * g;
    return [clamp255(t[0] * 255 * light), clamp255(t[1] * 255 * light), clamp255(t[2] * 255 * light)];
  });
}, 1.05, 0.96);
const tileNrm = normalFromHeight(tileHeight, TW, TH, 6, 1.05, 0.96);

// limestone slabs 0.6 m — 2 x 2 slabs per 1.2 m tile
const SLN = 512, slabH = new Float32Array(SLN * SLN);
const slabTex = canvasTex(SLN, SLN, (ctx, w, h) => {
  const r = rand(77), tones = [0, 1, 2, 3].map(() => 0.95 + r() * 0.09);
  const n = fbmTile(SLN, [[6, .4], [24, .3], [128, .35]], 81), sp = rand(9);
  pixels(ctx, w, h, (x, y, k) => {
    const joint = (x % 256 < 3) || (y % 256 < 3);
    slabH[k] = joint ? 0 : 1;
    const t = tones[(y < 256 ? 0 : 2) + (x < 256 ? 0 : 1)] * (1 + n[k] * 0.08) * (sp() < 0.004 ? 0.85 : 1);
    return joint ? [150, 142, 128] : [clamp255(222 * t), clamp255(213 * t), clamp255(193 * t)];
  });
}, 1.2);
const slabNrm = normalFromHeight(slabH, SLN, SLN, 1.5, 1.2);

// asphalt — 2.5 m tile
const asphTex = canvasTex(512, 512, (ctx, w, h) => {
  const r = rand(3), n = fbmTile(512, [[4, .5], [32, .3]], 91);
  pixels(ctx, w, h, (x, y, k) => {
    const s = r(), v = 74 * (1 + n[k] * 0.12) + (s - 0.5) * 34 + (s > 0.985 ? 45 : 0);
    return [clamp255(v), clamp255(v), clamp255(v + 2)];
  });
}, 2.5);

// smooth concrete (garage floor) — 3 m tile
const concTex = canvasTex(512, 512, (ctx, w, h) => {
  const r = rand(4), n = fbmTile(512, [[3, .6], [12, .3], [64, .2]], 101);
  pixels(ctx, w, h, (x, y, k) => { const v = 1 + n[k] * 0.1 + (r() - .5) * 0.03; return [clamp255(176 * v), clamp255(173 * v), clamp255(166 * v)]; });
}, 3.0);

// photo textures
const grassTex = photo('tex/grass.jpg', 1.6);
const soilTex = photo('tex/soil.jpg', 3.0);
const settsTex = photo('tex/setts.jpg', 1.2);
const oakTex = photo('tex/oak.jpg', 2.2);
const gravelTex = photo('tex/gravel.jpg', 2.0);


function scaleTex(t, mat) {   // for meshes with metre-based UVs
  const [w, h] = Array.isArray(t.userData.metres) ? t.userData.metres : [t.userData.metres, t.userData.metres];
  t.repeat.set(1 / w, 1 / h);
}


// =================== v2: new split-level house ===================
const LAY = __LAYOUT_JSON__;
const GR = LAY.grading;
const PLOT = LAY.plot;

// ---------- extra procedural textures ----------
// dark flat roof tiles (telha plana cinza) — 4 x 4 tiles, 1.32 m x 1.36 m
const DTW = 4 * 96, DTH = 4 * 100, dtH = new Float32Array(DTW * DTH);
const darkTileTex = canvasTex(DTW, DTH, (ctx) => {
  const r = rand(61), tones = Array.from({ length: 32 }, () => 0.85 + r() * 0.3);
  const g = fbmTile(DTW, [[8, .3], [64, .25]], 63);
  pixels(ctx, DTW, DTH, (x, y, k) => {
    const row = Math.floor(y / 100), off = (row % 2) * 48, col = Math.floor(((x + off) % DTW) / 96);
    const fy = (y % 100) / 100, fx = (((x + off) % DTW) % 96) / 96;
    const shadow = fy < 0.14 ? 0.5 + 0.5 * (fy / 0.14) : 1;
    const gap = (fx < 0.02 || fx > 0.98) ? 0.55 : 1;
    dtH[k] = (fy < 0.14 ? fy / 0.14 * 0.5 : 0.5 + fy * 0.5) * gap;
    const v = 62 * tones[(row * 4 + col) % 32] * shadow * gap * (1 + g[(y % DTW) * DTW + x] * 0.12);
    return [clamp255(v), clamp255(v * 1.02), clamp255(v * 1.07)];
  });
}, 1.32, 1.36);
const darkTileNrm = normalFromHeight(dtH, DTW, DTH, 5, 1.32, 1.36);

// natural limestone cladding — irregular courses, 2.0 m x 1.6 m
const STW = 640, STH = 512, stH = new Float32Array(STW * STH);
const stoneTex = canvasTex(STW, STH, (ctx) => {
  const r = rand(71), id = new Int32Array(STW * STH).fill(-1), tone = [];
  let y = 0, n = 0;
  const courses = [];
  while (y < STH) { const h = Math.min(STH - y, 40 + Math.floor(r() * 50)); courses.push([y, h]); y += h; }
  if (courses.length > 1 && courses[courses.length - 1][1] < 30) { const last = courses.pop(); courses[courses.length - 1][1] += last[1]; }
  for (const [y0, h] of courses) {
    let x = Math.floor(r() * 60);
    const start = x;
    while (x < start + STW) {
      const w = 60 + Math.floor(r() * 120);
      tone.push([0.86 + r() * 0.16, r()]);
      for (let yy = y0; yy < y0 + h; yy++) for (let xx = x; xx < x + w; xx++) id[yy * STW + (xx % STW)] = n;
      x += w; n++;
    }
  }
  const g = fbmTile(STW, [[10, .4], [40, .3], [160, .4]], 73);
  pixels(ctx, STW, STH, (x, y, k) => {
    const c = id[k], L_ = x > 0 ? id[k - 1] : id[k + STW - 1], U = y > 0 ? id[k - STW] : id[k + (STH - 1) * STW];
    const mortar = (c !== L_) || (c !== U) || x % STW === 0 && false;
    const gg = g[(y % STW) * STW + x];
    stH[k] = mortar ? 0 : 0.6 + gg * 0.4;
    if (mortar) return [178, 170, 155];
    const [t, hue] = tone[c];
    const v = t * (1 + gg * 0.12);
    return [clamp255(224 * v + hue * 8), clamp255(210 * v + hue * 4), clamp255(182 * v)];
  });
}, 2.0, 1.6);
const stoneNrm = normalFromHeight(stH, STW, STH, 4, 2.0, 1.6);

// vertical wood slats (ripado) — 0.07 m slats, 0.6 m wide tile, 2 m tall
const woodSlatTex = canvasTex(256, 512, (ctx) => {
  const r = rand(81), g = fbmTile(512, [[4, .3], [64, .25]], 83);
  const tones = Array.from({ length: 8 }, () => 0.85 + r() * 0.25);
  pixels(ctx, 256, 512, (x, y, k) => {
    const s = Math.floor(x / 32), fx = (x % 32) / 32;
    if (fx > 0.84) return [38, 30, 24];
    const grain = Math.sin((y / 512) * 40 + s * 3 + g[(y % 512) * 512 + x] * 6) * 0.06;
    const v = tones[s] * (1 + grain) * (0.9 + 0.1 * Math.sin(Math.PI * fx / 0.84));
    return [clamp255(168 * v), clamp255(118 * v), clamp255(78 * v)];
  });
}, 0.6, 2.0);

// large light porcelain / limestone paving 0.6 x 1.2 m
const pavTex = canvasTex(512, 512, (ctx, w, h) => {
  const r = rand(91), tones = Array.from({ length: 8 }, () => 0.94 + r() * 0.08), g = fbmTile(512, [[6, .3], [48, .2], [256, .25]], 93);
  pixels(ctx, w, h, (x, y, k) => {
    const row = Math.floor(y / 128), off = (row % 2) * 128;
    const joint = (y % 128 < 2) || ((x + off) % 256 < 2);
    if (joint) return [160, 156, 148];
    const v = tones[(row * 2 + Math.floor(((x + off) % 512) / 256)) % 8] * (1 + g[k] * 0.06);
    return [clamp255(214 * v), clamp255(209 * v), clamp255(198 * v)];
  });
}, 1.2, 2.4);

// concrete driveway pavers (grey, 0.2 x 0.1)
const paverTex = canvasTex(512, 512, (ctx, w, h) => {
  const r = rand(97), g = fbmTile(512, [[4, .3], [32, .2]], 99);
  const tone = Array.from({ length: 4096 }, () => 0.88 + r() * 0.2);
  pixels(ctx, w, h, (x, y, k) => {
    const row = Math.floor(y / 32), off = (row % 2) * 32, cx = Math.floor((x + off) / 64);
    if (y % 32 < 2 || (x + off) % 64 < 2) return [110, 108, 104];
    const v = tone[(row * 16 + cx) % 4096] * (1 + g[k] * 0.06);
    return [clamp255(158 * v), clamp255(156 * v), clamp255(150 * v)];
  });
}, 1.6, 1.6);

const hedgeTex = canvasTex(256, 256, (ctx, w, h) => {
  const r = rand(5), g = fbmTile(256, [[8, .5], [32, .4], [128, .5]], 7);
  pixels(ctx, w, h, (x, y, k) => { const v = 0.55 + g[k] * 0.9 + (r() - .5) * 0.25; return [clamp255(52 * v), clamp255(78 * v), clamp255(40 * v)]; });
}, 1.0);

const v2mask1 = maskTex('tex/v2_mask1.png'), v2mask2 = maskTex('tex/v2_mask2.png'), v2mask3 = maskTex('tex/v2_mask3.png');
const planV2 = photo('tex/plan_v2.jpg', 1); planV2.wrapS = planV2.wrapT = THREE.ClampToEdgeWrapping;

// ---------- terrain (natural survey outside the plot, graded terraces inside) ----------
function pointInPoly(x, z, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}
function idw(x, z) {
  let sw = 0, sh = 0;
  for (const s of SITE.spots) { const w = 1 / Math.pow((x - s.x) ** 2 + (z - s.z) ** 2 + 4, 1.3); sw += w; sh += w * s.h; }
  return sh / sw;
}
const smooth = t => t * t * (3 - 2 * t);
const BAND = 0.2;
function upperAt(x, z) {
  let h = GR.upper;
  if (z > GR.upper_slope_from_z) h -= (z - GR.upper_slope_from_z) * GR.upper_slope;
  // ramp from the road to the court at the gates
  if (x < LAY.meta.cut_x + 4 && z > LAY.gate.z0 - 1 && z < LAY.ped_gate.z1 + 1) {
    const road = idw(LAY.meta.cut_x, z);
    h = road + (h - road) * smooth(Math.min(1, Math.max(0, (x - LAY.meta.cut_x) / 4)));
  }
  return h;
}
const levelsX = [[GR.x_w1, null], [GR.x_w2, GR.lower], [GR.x_w3, GR.t1]];
function designed(x, z) {
  const zoneH = xx => xx < GR.x_w1 ? upperAt(xx, z) : xx < GR.x_w2 ? GR.lower : xx < GR.x_w3 ? GR.t1 : GR.t2;
  for (const [xw] of levelsX) {
    if (Math.abs(x - xw) < BAND) {
      const a = zoneH(xw - BAND - 1e-3), b = zoneH(xw + BAND + 1e-3);
      return a + (b - a) * ((x - (xw - BAND)) / (2 * BAND));
    }
  }
  return zoneH(x);
}
let relief = true;
// inside a built volume the ground must stay under its slab (pantry/laundry/living sit 1 m below the upper garden)
const BLOCK_LEVELS = Object.values(LAY.blocks).map(b => [b.rect, b.level]);
function underSlab(x, z, h) {
  for (const st of LAY.stairs) if (x > Math.min(st.x0, st.x1) - 0.3 && x < Math.max(st.x0, st.x1) + 0.3 && z > st.z0 - 0.3 && z < st.z1 + 0.3) return Math.min(h, Math.min(st.ybot, st.ytop) + FFL - 0.4);
  for (const [r, lv] of BLOCK_LEVELS) if (x > r[0] + 0.02 && x < r[2] - 0.02 && z > r[1] + 0.02 && z < r[3] - 0.02) return Math.min(h, lv - 0.4);
  return h;
}
function groundAbs(x, z) {
  if (!relief) return underSlab(x, z, pointInPoly(x, z, PLOT) ? (x < GR.x_w1 ? GR.upper : GR.lower) : 31.0);
  return underSlab(x, z, pointInPoly(x, z, PLOT) ? designed(x, z) : idw(x, z));
}
const heightAt = (x, z) => groundAbs(x, z) - FFL;

// ---------- ground: fine graded grid in the window + coarse apron ----------
const G = SITE.ground, gw = G.x1 - G.x0, gd = G.z1 - G.z0;
const STEP = 0.25, NX = Math.round(gw / STEP), NZ = Math.round(gd / STEP);
const fineGeo = new THREE.PlaneGeometry(gw, gd, NX, NZ);
fineGeo.rotateX(-Math.PI / 2); fineGeo.translate((G.x0 + G.x1) / 2, 0, (G.z0 + G.z1) / 2);
const EXT = 90, apronGeo = new THREE.PlaneGeometry(gw + 2 * EXT, gd + 2 * EXT, 90, 90);
apronGeo.rotateX(-Math.PI / 2); apronGeo.translate((G.x0 + G.x1) / 2, 0, (G.z0 + G.z1) / 2);
function prepGround(geo, dy) {
  const p = geo.attributes.position, uv = geo.attributes.uv, xz = [];
  for (let i = 0; i < p.count; i++) { const x = p.getX(i), z = p.getZ(i); xz.push([x, z]); uv.setXY(i, (x - G.x0) / gw, 1 - (z - G.z0) / gd); }
  geo.userData = { xz, dy };
}
prepGround(fineGeo, 0); prepGround(apronGeo, -0.06);
function applyHeights() {
  for (const geo of [fineGeo, apronGeo]) {
    const p = geo.attributes.position, { xz, dy } = geo.userData;
    for (let i = 0; i < p.count; i++) p.setY(i, heightAt(xz[i][0], xz[i][1]) + dy);
    p.needsUpdate = true; geo.computeVertexNormals(); geo.computeBoundingSphere();
  }
}
applyHeights();
const groundU = {
  mask2: { value: v2mask2 }, mask3: { value: v2mask3 },
  tGrass: { value: grassTex }, tSoil: { value: soilTex }, tPaver: { value: paverTex }, tGravel: { value: gravelTex },
  tPav: { value: pavTex }, tAsph: { value: asphTex }, tSetts: { value: settsTex }, tPlan: { value: planV2 }, planMix: { value: 0 },
};
const groundMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.96, metalness: 0, map: v2mask1, envMapIntensity: 0.6 });
groundMat.onBeforeCompile = sh => {
  Object.assign(sh.uniforms, groundU);
  sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec2 vWXZ;')
    .replace('#include <begin_vertex>', '#include <begin_vertex>\nvWXZ = position.xz;');
  sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
varying vec2 vWXZ;
uniform sampler2D mask2, mask3, tGrass, tSoil, tPaver, tGravel, tPav, tAsph, tSetts, tPlan;
uniform float planMix;
vec3 tx(sampler2D t, float m) { return texture2D(t, vWXZ / m).rgb; }
vec3 tx2(sampler2D t, float m) { return mix(texture2D(t, vWXZ / m).rgb, texture2D(t, vWXZ.yx / (m * 2.37) + 0.31).rgb, 0.35); }`)
    .replace('#include <map_fragment>', `
vec3 m1 = texture2D(map, vMapUv).rgb, m2 = texture2D(mask2, vMapUv).rgb, m3 = texture2D(mask3, vMapUv).rgb;
float macro = texture2D(tSoil, vWXZ / 41.0).r, macro2 = texture2D(tGrass, vWXZ / 29.0 + 0.17).g;
vec3 grassC = tx2(tGrass, 1.7) * vec3(0.66, 0.74, 0.52) * (0.8 + 0.38 * macro2);
vec3 dry = mix(vec3(dot(grassC, vec3(0.333))), grassC, 0.6) * vec3(1.22, 1.12, 0.8);
vec3 soilC = tx2(tSoil, 3.2) * vec3(0.78, 0.74, 0.7);
vec3 c = mix(dry, soilC, smoothstep(0.5, 0.7, macro) * 0.8);
c = mix(c, tx(tSetts, 1.0) * vec3(1.1, 1.08, 1.05), m3.r);
c = mix(c, tx(tAsph, 2.5), m1.b);
c = mix(c, grassC, m1.r);
c = mix(c, tx(tPaver, 1.6), m1.g);
c = mix(c, tx(tPav, 1.2), m2.r);
c = mix(c, tx2(tGravel, 1.4) * vec3(1.45, 1.42, 1.36), m2.g);
c = mix(c, tx2(tSoil, 1.2) * vec3(0.42, 0.34, 0.27), m2.b);
c = mix(c, vec3(0.82, 0.81, 0.78), m3.g * m1.b);
c = mix(c, texture2D(tPlan, vMapUv).rgb, planMix);
diffuseColor.rgb *= c;`);
};
const fineGround = new THREE.Mesh(fineGeo, groundMat), apron = new THREE.Mesh(apronGeo, groundMat);
fineGround.receiveShadow = apron.receiveShadow = true;
scene.add(fineGround, apron);

// ---------- materials (named, for export) ----------
function mat(name, opts, map, nrm, nscale = 0.6) {
  const p = { roughness: 0.9, metalness: 0, ...opts };
  if (map) { const m = map.clone(); if (m.image) m.needsUpdate = true; const [w, h] = Array.isArray(map.userData.metres) ? map.userData.metres : [map.userData.metres, map.userData.metres]; m.repeat.set(1 / w, 1 / h); p.map = m; }
  if (nrm) { const n = nrm.clone(); n.needsUpdate = true; const [w, h] = nrm.userData.metres; n.repeat.set(1 / w, 1 / h); p.normalMap = n; p.normalScale = new THREE.Vector2(nscale, nscale); }
  const m = new THREE.MeshStandardMaterial(p); m.name = name; return m;
}
const M = {
  render: mat('Wall_White_Render', { envMapIntensity: 0.7 }, renderTex, renderNrm),
  render_in: mat('Wall_Interior_White', { color: 0xf7f5f1, roughness: 0.85 }),
  stone: mat('Wall_Limestone_Cladding', { roughness: 0.92 }, stoneTex, stoneNrm, 0.9),
  slats: mat('Wood_Slats', { roughness: 0.6 }, woodSlatTex),
  soffit: mat('Eave_Soffit_White', { color: 0xf4f2ee, roughness: 0.8 }),
  roof: mat('Roof_Tile_DarkGrey', { roughness: 0.72, side: THREE.DoubleSide, envMapIntensity: 0.9 }, darkTileTex, darkTileNrm, 1.0),
  ridge: mat('Roof_Ridge', { color: 0x34373a, roughness: 0.7 }),
  oak: mat('Floor_Oak', { roughness: 0.55 }, oakTex),
  porcelain: mat('Floor_Porcelain', { color: 0xe6e3dd, roughness: 0.4 }, pavTex),
  stone_floor: mat('Floor_Limestone', { roughness: 0.6 }, pavTex),
  terrace: mat('Terrace_Paving', { roughness: 0.8 }, pavTex),
  concrete: mat('Floor_Concrete', { roughness: 0.85 }, concTex),
  plinth: mat('Plinth_Grey', { color: 0x9c968c, roughness: 0.95 }, concTex),
  glass: (() => { const m = new THREE.MeshStandardMaterial({ color: 0x7f97a1, roughness: 0.03, metalness: 0.2, transparent: true, opacity: 0.38, envMapIntensity: 2.0, depthWrite: false, side: THREE.DoubleSide }); m.name = 'Glass'; return m; })(),
  frame: mat('Window_Frame_Anthracite', { color: 0x2b2d30, roughness: 0.4, metalness: 0.4 }),
  front: mat('Door_Front_DarkWood', { color: 0x5a3e2c, roughness: 0.5 }, woodSlatTex),
  door: mat('Door_Interior_White', { color: 0xf3f1ec, roughness: 0.6 }),
  garage: mat('Door_Garage_WoodSlats', { roughness: 0.6 }, woodSlatTex),
  retain: mat('Retaining_Wall_Stone', { color: 0xe8e2d6, roughness: 0.95 }, stoneTex, stoneNrm, 0.9),
  hedge: mat('Hedge', { roughness: 1 }, hedgeTex),
  // furniture
  fabric: mat('Furn_Fabric_Linen', { color: 0xe7e1d5, roughness: 0.95 }), wood: mat('Furn_Wood_Oak', { roughness: 0.6 }, oakTex),
  wardrobe: mat('Furn_Wardrobe', { color: 0xd8cbb8, roughness: 0.6 }), white: mat('Furn_White', { color: 0xf5f4f0, roughness: 0.4 }),
  kitchen: mat('Furn_Kitchen', { color: 0x3a3836, roughness: 0.5 }), stone_top: mat('Furn_Stone_Top', { color: 0xe4e0d8, roughness: 0.3 }),
  dark: mat('Furn_Dark', { color: 0x2f2d2b, roughness: 0.5 }), rug: mat('Furn_Rug', { color: 0xcdbfa8, roughness: 1 }),
  chair: mat('Furn_Chair', { color: 0xb59a78, roughness: 0.7 }),
  bark: mat('Olive_Bark', { color: 0x6b6050, roughness: 1 }),
  olive: [0x66744d, 0x727f55, 0x5d6a46].map((c, i) => { const m = new THREE.MeshStandardMaterial({ color: c, roughness: 0.92, flatShading: true }); m.name = 'Olive_Foliage'; return m; }),
  bollard: (() => { const m = new THREE.MeshStandardMaterial({ color: 0x2b2b2b, emissive: 0xffc77a, emissiveIntensity: 0, roughness: 0.5 }); m.name = 'Garden_Light'; return m; })(),
};
// ---------- style preset (project.json "style" → PROJ.style_data, see references/style-guide.md) ----------
// tint: per-material RGB multipliers on the default look (1 = unchanged, > 1 lightens); roof_tile: flat_dark | terracotta
{
  const ST = PROJ.style_data || {};
  if (ST.roof_tile === 'terracotta') {
    const m = tileTex.clone(); m.needsUpdate = true; const [w, h] = Array.isArray(tileTex.userData.metres) ? tileTex.userData.metres : [tileTex.userData.metres, tileTex.userData.metres];
    m.repeat.set(1 / w, 1 / h); M.roof.map = m; M.roof.name = 'Roof_Tile_Terracotta';
    const n = tileNrm.clone(); n.needsUpdate = true; const [nw, nh] = tileNrm.userData.metres; n.repeat.set(1 / nw, 1 / nh); M.roof.normalMap = n;
    M.ridge.color.set(0x9a4a2e); M.roof.needsUpdate = true;
  }
  for (const [k, t] of Object.entries(ST.tint || {})) {
    const m = M[k]; if (!m || Array.isArray(m) || !Array.isArray(t)) continue;
    m.color.setRGB(m.color.r * t[0], m.color.g * t[1], m.color.b * t[2]);
  }
}

// metre-UV box (local frame), so textures run continuously along walls
function mbox(x0, x1, y0, y1, z0, z1, uOff = 0) {
  const g = new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0);
  g.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
  const p = g.attributes.position, n = g.attributes.normal, uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) {
    const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i));
    const x = p.getX(i) + uOff, y = p.getY(i), z = p.getZ(i);
    if (ay > 0.5) uv.setXY(i, x, z); else if (ax > 0.5) uv.setXY(i, z, y); else uv.setXY(i, x, y);
  }
  return g;
}
const house = new THREE.Group(), roofs = new THREE.Group(), furniture = new THREE.Group(), site = new THREE.Group();
// ---------- storeys: any wall, floor, stair, slat, column, railing or furniture item may carry "storey" (0 = ground, default) ----------
const STOREYS = new Map();
function sg(o, parent = house) {
  const k = o.storey || 0, key = parent.uuid + ':' + k;
  if (!STOREYS.has(key)) { const g = new THREE.Group(); g.name = 'storey_' + k; g.userData.storey = k; parent.add(g); STOREYS.set(key, g); }
  return STOREYS.get(key);
}
const MAX_STOREY = Math.max(0, ...[...LAY.walls, ...LAY.floors].map(o => o.storey || 0));
scene.add(house, roofs, furniture, site);
function addMesh(parent, geo, m, cast = true, recv = true) { const o = new THREE.Mesh(geo, m); o.castShadow = cast; o.receiveShadow = recv; parent.add(o); return o; }

// ---------- walls with openings ----------
function buildWall(w) {
  const [ax, az] = w.a, [bx, bz] = w.b, Lw = Math.hypot(bx - ax, bz - az), t = w.t;
  const g = new THREE.Group(); g.position.set(ax, 0, az); g.rotation.y = -Math.atan2(bz - az, bx - ax);
  const wm = M[w.mat] || M.render, y0 = w.y0, y1 = w.y0 + w.h;
  const ops = [...w.ops].sort((a, b) => a.o - b.o);
  let cur = 0;
  const solid = (s, e, ya, yb) => { if (e - s > 0.005 && yb - ya > 0.005) addMesh(g, mbox(s, e, ya, yb, -t / 2, t / 2, ax + az), wm); };
  for (const o of ops) {
    solid(cur, o.o, y0, y1);
    const s = o.o, e = o.o + o.w, head = y0 + o.head, sill = y0 + o.sill;
    solid(s, e, head, y1);                                           // lintel
    if (o.sill > 0) solid(s, e, y0, sill);                           // sill wall
    const k = o.kind, F = 0.05;
    if (k === 'window' || k === 'slide' || k === 'door_glass') {
      addMesh(g, mbox(s + 0.01, e - 0.01, sill, head, -0.012, 0.012), M.glass, false, false).renderOrder = 2;
      addMesh(g, mbox(s, e, head - F, head, -0.04, 0.04), M.frame);
      addMesh(g, mbox(s, e, sill, sill + (o.sill > 0 ? F : 0.03), -0.05, 0.05), M.frame);
      const n = Math.max(1, Math.ceil(o.w / (k === 'slide' ? 1.35 : 1.2)));
      for (let i = 0; i <= n; i++) { const x = s + (e - s) * i / n; addMesh(g, mbox(Math.max(s, x - F / 2), Math.min(e, x + F / 2), sill, head, -0.04, 0.04), M.frame); }
      if (o.sill > 0) addMesh(g, mbox(s - 0.02, e + 0.02, sill - 0.03, sill, -t / 2 - 0.04, t / 2 + 0.04), M.stone_floor);   // stone sill
    } else if (k === 'front') {
      addMesh(g, mbox(s + 0.02, e - 0.02, y0, head, -0.03, 0.03), M.front);
      addMesh(g, mbox(e - 0.2, e - 0.17, y0 + 0.6, y0 + 1.6, -0.09, -0.05), M.frame);
    } else if (k === 'door') {
      addMesh(g, mbox(s + 0.02, e - 0.02, y0, head, -0.02, 0.02), M.door);
    } else if (k === 'garage') {
      addMesh(g, mbox(s, e, y0, head, -0.04, 0.04), M.garage);
    }
    cur = e;
  }
  solid(cur, Lw, y0, y1);
  sg(w).add(g);
}
LAY.walls.forEach(buildWall);
// slatted timber panels flanking the front door (as in the reference image)
{
  for (const s of (LAY.slats || [])) addMesh(sg(s), mbox(s.x0, s.x1, s.y0, s.y1, s.z0, s.z1), M.slats);
}
// columns
for (const c of LAY.columns) addMesh(sg(c), mbox(c.x - c.s / 2, c.x + c.s / 2, c.y0, c.y0 + c.h, c.z - c.s / 2, c.z + c.s / 2), M.stone);

// floors (slabs) — top at the finished level, 0.35 thick so the plinth reads
function shape(poly, holes = []) {
  const s = new THREE.Shape(); poly.forEach(([x, z], i) => i ? s.lineTo(x, -z) : s.moveTo(x, -z)); s.closePath();
  for (const h of holes) s.holes.push(new THREE.Path(h.map(([x, z]) => new THREE.Vector2(x, -z))));   // stair voids, double-height spaces
  return s;
}
for (const f of LAY.floors) {
  const g = new THREE.ExtrudeGeometry(shape(f.poly, f.holes || []), { depth: 0.35, bevelEnabled: false });
  g.rotateX(-Math.PI / 2); g.translate(0, f.y - 0.35, 0);
  addMesh(sg(f), g, [M[f.mat] || M.oak, M.plinth], (f.storey || 0) > 0, true);
}
// railings / balustrades: glass panel + anthracite handrail, [{a, b, y, h = 1.0, storey}]
for (const r of (LAY.railings || [])) {
  const [ax, az] = r.a, [bx, bz] = r.b, Lr = Math.hypot(bx - ax, bz - az), h = r.h ?? 1.0;
  const g = new THREE.Group(); g.position.set(ax, 0, az); g.rotation.y = -Math.atan2(bz - az, bx - ax);
  addMesh(g, mbox(0.02, Lr - 0.02, r.y + 0.05, r.y + h - 0.04, -0.01, 0.01), M.glass, false, false).renderOrder = 2;
  addMesh(g, mbox(0, Lr, r.y + h - 0.04, r.y + h, -0.03, 0.03), M.frame);
  addMesh(g, mbox(0, Lr, r.y, r.y + 0.05, -0.03, 0.03), M.frame);
  sg(r).add(g);
}
// interior stair
for (const st of LAY.stairs) {
  const rise = (st.ytop - st.ybot) / st.n, run = (st.x1 - st.x0) / st.n;
  // one solid block per tread: tread i spans [x0+(i-1)run, x0+i*run] with its top one riser lower than the previous (the old version stacked full-length boxes, so the top box hid every step)
  for (let i = 1; i <= st.n; i++) addMesh(sg(st), mbox(st.x0 + (i - 1) * run, st.x0 + i * run, st.ybot - 0.05, st.ytop - i * rise, st.z0, st.z1), M.stone_floor, false);
}

// ---------- hipped roofs (union of rectangles), soffit + fascia ----------
const PITCH2 = THREE.MathUtils.degToRad(LAY.meta.pitch);
function hipRoof(x0, z0, x1, z1, RY) {
  addMesh(roofs, mbox(x0, x1, RY - 0.22, RY, z0, z1), M.soffit, true, true);
  let swap = (z1 - z0) > (x1 - x0);
  const [a0, a1, b0, b1] = swap ? [z0, z1, x0, x1] : [x0, x1, z0, z1];
  const half = (b1 - b0) / 2, h = half * Math.tan(PITCH2), bc = (b0 + b1) / 2;
  const R1 = [a0 + half, RY + h, bc], R2 = [a1 - half, RY + h, bc];
  const faces = [{ v: [[a0, RY, b1], [a1, RY, b1], R2, R1], n: [0, -1] }, { v: [[a1, RY, b0], [a0, RY, b0], R1, R2], n: [0, 1] },
                 { v: [[a0, RY, b0], [a0, RY, b1], R1], n: [1, 0] }, { v: [[a1, RY, b1], [a1, RY, b0], R2], n: [-1, 0] }];
  const pos = [], uvs = [], cosP = Math.cos(PITCH2);
  for (const f of faces) {
    const E0 = f.v[0], E1 = f.v[1], d = [E1[0] - E0[0], E1[2] - E0[2]], dl = Math.hypot(d[0], d[1]); d[0] /= dl; d[1] /= dl;
    for (const t of (f.v.length === 4 ? [[0, 1, 2], [0, 2, 3]] : [[0, 1, 2]])) {
      for (const i of (swap ? [t[0], t[2], t[1]] : t)) {
        const p = f.v[i], [x, z] = swap ? [p[2], p[0]] : [p[0], p[2]];
        pos.push(x, p[1] + 0.01, z);
        const du = p[0] - E0[0], dv = p[2] - E0[2];
        uvs.push(du * d[0] + dv * d[1], (du * f.n[0] + dv * f.n[1]) / cosP);
      }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2)); g.computeVertexNormals();
  addMesh(roofs, g, M.roof);
  const S = p => swap ? new THREE.Vector3(p[2], p[1], p[0]) : new THREE.Vector3(p[0], p[1], p[2]);
  const cap = (p, q) => { const A = S(p), B = S(q), L_ = A.distanceTo(B); if (L_ < 0.05) return;
    const c = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.06, L_), M.ridge); c.position.copy(A).add(B).multiplyScalar(0.5); c.position.y += 0.03; c.lookAt(B.x, B.y + 0.03, B.z); c.castShadow = true; roofs.add(c); };
  cap(R1, R2); cap([a0, RY, b0], R1); cap([a0, RY, b1], R1); cap([a1, RY, b0], R2); cap([a1, RY, b1], R2);
}
for (const r of LAY.roofs) hipRoof(r.rect[0], r.rect[1], r.rect[2], r.rect[3], r.eave);

// ---------- furniture ----------
for (const f of LAY.furniture) {
  const [x0, z0, x1, z1] = f.b;
  const fg = sg(f, furniture);
  addMesh(fg, mbox(x0, x1, f.y0, f.y0 + Math.max(0.01, f.h), z0, z1), M[f.mat] || M.white, f.h > 0.05, true);
  if (/cama|bed/i.test(f.name)) addMesh(fg, mbox(x0 + 0.1, x1 - 0.1, f.y0 + f.h, f.y0 + f.h + 0.14, z0 + 0.12, z0 + 0.55), M.white);     // pillows
  if (/sofá|sofa/i.test(f.name)) addMesh(fg, mbox(x0, x1, f.y0, f.y0 + 0.42, z0, z1), M.fabric, true);
}

// ---------- site works ----------
function plotZRange(x) {
  let lo = Infinity, hi = -Infinity;
  for (let z = -32; z <= 22; z += 0.1) if (pointInPoly(x, z, PLOT)) { lo = Math.min(lo, z); hi = Math.max(hi, z); }
  return [lo, hi];
}
// retaining walls with gaps for steps and the house
for (const rw of LAY.retaining) {
  const [lo, hi] = plotZRange(rw.x); if (!isFinite(lo)) continue;
  let segs = [[lo + 0.2, hi - 0.2]];
  const cuts = LAY.garden_steps.filter(s => Math.abs(s.x - rw.x) < 0.01).map(s => [s.z0, s.z1]);
  for (const [cx, z0, z1] of (LAY.meta.retaining_cuts ?? [])) if (Math.abs(rw.x - cx) < 0.01) cuts.push([z0, z1]);   // house walls replace the retaining wall here
  for (const [a, b] of cuts) segs = segs.flatMap(([s, e]) => [[s, Math.min(e, a)], [Math.max(s, b), e]]).filter(([s, e]) => e - s > 0.1);
  for (const [s, e] of segs) {
    for (let z = s; z < e - 1e-6; z += 1.0) {
      const z2 = Math.min(e, z + 1.0), zm = (z + z2) / 2;
      const top = groundAbs(rw.x - BAND - 0.01, zm) - FFL + 0.12, bot = groundAbs(rw.x + BAND + 0.01, zm) - FFL - 0.1;
      if (top - bot > 0.15) addMesh(site, mbox(rw.x - 0.2, rw.x + 0.2, bot, top, z, z2), M.retain);
    }
  }
}
// garden steps (descending east on the lower side of each wall)
for (const st of LAY.garden_steps) {
  const zm = (st.z0 + st.z1) / 2, up = groundAbs(st.x - BAND - 0.01, zm) - FFL, dn = groundAbs(st.x + BAND + 0.01, zm) - FFL;
  const n = Math.max(1, Math.round((up - dn) / 0.17)), rise = (up - dn) / n;
  addMesh(site, mbox(st.x - BAND, st.x + BAND, dn - 0.1, up, st.z0, st.z1), M.terrace, false);
  for (let i = 1; i < n; i++) addMesh(site, mbox(st.x + BAND + (i - 1) * 0.32, st.x + BAND + i * 0.32, dn - 0.1, up - i * rise, st.z0, st.z1), M.terrace, false);
}
// boundary: stone wall (low on the road side), hedge behind it on the other sides, gaps at the gates
{
  const n = PLOT.length, seg = 1.5;
  for (let i = 0; i < n; i++) {
    const [ax, az] = PLOT[i], [bx, bz] = PLOT[(i + 1) % n], Ls = Math.hypot(bx - ax, bz - az); if (Ls < 0.05) continue;
    const ux = (bx - ax) / Ls, uz = (bz - az) / Ls, west = Math.abs(ax - LAY.meta.cut_x) < 0.05 && Math.abs(bx - LAY.meta.cut_x) < 0.05;
    // inward normal: test side
    let nx = -uz, nz = ux; if (!pointInPoly(ax + ux * Ls / 2 + nx * 0.5, az + uz * Ls / 2 + nz * 0.5, PLOT)) { nx = -nx; nz = -nz; }
    for (let s = 0; s < Ls - 1e-6; s += seg) {
      const e = Math.min(Ls, s + seg), m = (s + e) / 2, px = ax + ux * m, pz = az + uz * m;
      if (west && ((pz > LAY.gate.z0 && pz < LAY.gate.z1) || (pz > LAY.ped_gate.z0 && pz < LAY.ped_gate.z1))) continue;
      const hin = groundAbs(px + nx * 0.6, pz + nz * 0.6) - FFL, hout = idw(px - nx * 0.6, pz - nz * 0.6) - FFL;
      const top = Math.max(hin, hout) + (west ? 0.75 : 0.6), bot = Math.min(hin, hout) - 0.15;
      const g = new THREE.Group(); g.position.set(px, 0, pz); g.rotation.y = -Math.atan2(uz, ux);
      addMesh(g, mbox(-(e - s) / 2 - 0.01, (e - s) / 2 + 0.01, bot, top, -0.18, 0.18, m), M.retain);
      site.add(g);
      if (!west) {
        const h = new THREE.Group(); h.position.set(px + nx * 0.75, 0, pz + nz * 0.75); h.rotation.y = g.rotation.y;
        addMesh(h, mbox(-(e - s) / 2 - 0.05, (e - s) / 2 + 0.05, hin, hin + 1.7, -0.45, 0.45, m), M.hedge);
        site.add(h);
      }
    }
  }
  // gate pillars + stone wall with house number
  const cx = LAY.meta.cut_x;
  for (const z of [LAY.gate.z0, LAY.gate.z1, LAY.ped_gate.z0, LAY.ped_gate.z1]) {
    const hb = groundAbs(cx + 0.3, z) - FFL;
    addMesh(site, mbox(cx - 0.25, cx + 0.25, hb - 0.2, hb + 1.6, z - 0.25, z + 0.25), M.stone);
  }
}
// olive trees
const trees = new THREE.Group(); scene.add(trees);
LAY.trees.forEach((t, i) => {
  const r = rand(300 + i), R = t.r, H = 2.2 + R * 0.9, g = new THREE.Group();
  for (let k = 0; k < 3; k++) {   // gnarled multi-stem trunk
    const a = r() * Math.PI * 2, lean = 0.25 + r() * 0.25;
    const c = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.18, H, 7), M.bark);
    c.position.set(Math.cos(a) * 0.12, H / 2, Math.sin(a) * 0.12); c.rotation.set(Math.sin(a) * lean, 0, Math.cos(a) * lean); c.castShadow = true; g.add(c);
  }
  for (let k = 0; k < 7; k++) {
    const s = R * (0.45 + r() * 0.35), geo = new THREE.IcosahedronGeometry(s, 1), p = geo.attributes.position, seed = r() * 100;
    for (let j = 0; j < p.count; j++) { const x = p.getX(j), y = p.getY(j), z = p.getZ(j); const hsh = Math.sin(Math.round(x * 50) * 12.99 + Math.round(y * 50) * 78.23 + Math.round(z * 50) * 37.72 + seed) * 43758.55; const f = 0.82 + (hsh - Math.floor(hsh)) * 0.32; p.setXYZ(j, x * f, y * f * 0.7, z * f); }
    geo.computeVertexNormals();
    const c = new THREE.Mesh(geo, M.olive[(i + k) % 3]); const a = r() * Math.PI * 2, rr = k === 0 ? 0 : R * (0.4 + r() * 0.35);
    c.position.set(Math.cos(a) * rr, H + (r() - 0.4) * R * 0.5, Math.sin(a) * rr); c.castShadow = true; c.receiveShadow = true; g.add(c);
  }
  g.userData = t; trees.add(g);
});
function placeTrees() { trees.children.forEach(g => g.position.set(g.userData.x, heightAt(g.userData.x, g.userData.z), g.userData.z)); }
placeTrees();
// garden lights along paths
const lights = PROJ.garden_lights ?? [];   // bollard positions [[x, z], ...] in scene metres
for (const [x, z] of lights) {
  const y = heightAt(x, z);
  const b = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.6, 10), M.bollard); b.position.set(x, y + 0.3, z); site.add(b);
}
// interior lights that switch on at dusk
const roomLights = (LAY.room_lights || [])
  .map(([x, z, y]) => { const l = new THREE.PointLight(0xffc98a, 0, 9, 2); l.position.set(x, y, z); scene.add(l); return l; });
// night: the garden bollards light the paths, and wall lights sit outside the front door, garage door and sliding doors
const bollardLights = lights.map(([x, z]) => { const l = new THREE.PointLight(0xffc77a, 0, 5, 2); l.position.set(x, heightAt(x, z) + 0.65, z); scene.add(l); return l; });
const inBlock = (x, z) => Object.values(LAY.blocks).some(b => x > b.rect[0] && x < b.rect[2] && z > b.rect[1] && z < b.rect[3]);
const wallLights = [];
for (const w of LAY.walls) for (const o of (w.ops || [])) {
  if (!['front', 'garage', 'slide'].includes(o.kind)) continue;
  const [ax, az] = w.a, [bx, bz] = w.b, L_ = Math.hypot(bx - ax, bz - az), ux = (bx - ax) / L_, uz = (bz - az) / L_;
  const cx = ax + ux * (o.o + o.w / 2), cz = az + uz * (o.o + o.w / 2);
  let nx = -uz, nz = ux; if (inBlock(cx + nx * 0.7, cz + nz * 0.7)) { nx = -nx; nz = -nz; }
  if (inBlock(cx + nx * 0.7, cz + nz * 0.7)) continue;                       // interior opening
  const l = new THREE.PointLight(0xffd29a, 0, 7, 2); l.position.set(cx + nx * 0.35, w.y0 + (o.head || 2.1) + 0.3, cz + nz * 0.35); scene.add(l); wallLights.push(l);
  const fx = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.12, 0.12), M.bollard); fx.position.copy(l.position).add(new THREE.Vector3(-nx * 0.2, 0, -nz * 0.2)); site.add(fx);
}

// ---------- labels: spot heights + floor levels ----------
const spotEls = SITE.spots.map(s => {
  const el = document.createElement('div'); el.className = 'spot'; el.textContent = s.label; el.hidden = true; el.style.left = el.style.top = '0';
  labelsEl.appendChild(el); return { el, v: () => new THREE.Vector3(s.x, heightAt(s.x, s.z) + 0.4, s.z) };
});
for (const [txt, x, y, z] of (PROJ.level_labels ?? [])) {   // [['Bedrooms 32.00', x, y, z], ...]
  const el = document.createElement('div'); el.className = 'spot ffl'; el.textContent = txt; el.hidden = true; el.style.left = el.style.top = '0';
  labelsEl.appendChild(el); spotEls.push({ el, v: () => new THREE.Vector3(x, y, z) });
}
let showSpots = false;
// room names + areas: one label per room at its centroid, a little above its floor ("Areas" layer)
const roomEls = [];
{
  const dec = (PROJ.ui && PROJ.ui.decimal) || '.', m2 = (PROJ.ui && PROJ.ui.m2) || 'm²';
  for (const r of (LAY.rooms || [])) {
    if (/^(escada|stair)/i.test(r.name)) continue;                     // the treads say it
    const p = r.poly; let a = 0, cx = 0, cz = 0;
    for (let i = 0; i < p.length; i++) { const [x0, z0] = p[(i + p.length - 1) % p.length], [x1, z1] = p[i], c = x0 * z1 - x1 * z0; a += c; cx += (x0 + x1) * c; cz += (z0 + z1) * c; }
    if (Math.abs(a) < 1e-6) continue; cx /= 3 * a; cz /= 3 * a;
    const y = (r.level != null ? r.level - FFL : 0) + 2.5,   // near the wall tops: readable from above, rarely hidden by its own walls
          area = (r.area ?? Math.abs(a / 2)).toFixed(2).replace('.', dec);
    const el = document.createElement('div'); el.className = 'spot room'; el.hidden = true; el.style.left = el.style.top = '0';
    el.innerHTML = `<b></b>${area} ${m2}`; el.firstChild.textContent = r.name;
    labelsEl.appendChild(el); el.hidden = false; const bw = el.offsetWidth || 80, bh = el.offsetHeight || 28; el.hidden = true;   // measure once
    roomEls.push({ el, st: r.storey || 0, a: Math.abs(a / 2), bw, bh, v: () => new THREE.Vector3(cx, y, cz) });
  }
  roomEls.sort((p, q) => q.a - p.a);                                   // big rooms keep their label when labels collide
}
let showAreas = false;
const occRay = new THREE.Raycaster(); let occTick = 0;
function occluded(pt) {                                               // an opaque wall between the camera and the label (glass doesn't count)
  const d = pt.clone().sub(camera.position), dist = d.length(); occRay.set(camera.position, d.normalize()); occRay.far = Math.max(0, dist - 0.3);
  const occ = [house]; if (roofs.visible) occ.push(roofs);
  return occRay.intersectObjects(occ, true).some(hh => hh.object.visible && !/glass/i.test(hh.object.material?.name || ''));
}
function updateLabels() {
  const w = renderer.domElement.clientWidth, h = renderer.domElement.clientHeight;
  for (const o of spotEls) {
    const p = o.v().project(camera), vis = showSpots && p.z < 1 && Math.abs(p.x) < 1.05 && Math.abs(p.y) < 1.05;
    o.el.hidden = !vis;
    if (vis) o.el.style.transform = `translate(${(p.x * 0.5 + 0.5) * w}px, ${(-p.y * 0.5 + 0.5) * h}px) translate(-50%, -100%)`;
  }
  const stShown = typeof storeyShown === 'undefined' ? Infinity : storeyShown;
  const placed = [], recheck = (occTick++ % 3) === 0;                 // ray tests every 3rd frame
  for (const o of roomEls) {
    const p = o.v().project(camera);
    let vis = showAreas && o.st === Math.min(stShown, MAX_STOREY) && p.z < 1 && Math.abs(p.x) < 1.05 && Math.abs(p.y) < 1.05;   // top storey shown only
    if (vis && (recheck || o.occ === undefined)) o.occ = occluded(o.v());
    if (o.occ) vis = false;
    if (vis) {                                                         // skip a label that would cover a bigger room's label
      const x = (p.x * 0.5 + 0.5) * w, y = (-p.y * 0.5 + 0.5) * h, bw = o.bw / 2 + 2, bh = o.bh / 2 + 1;
      if (placed.some(q => Math.abs(q[0] - x) < q[2] + bw && Math.abs(q[1] - y) < q[3] + bh)) vis = false;
      else { placed.push([x, y, bw, bh]); o.el.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`; }
    }
    o.el.hidden = !vis;
  }
}

// ---------- sun (latitude from project.json, true north NORTH_DEG clockwise from sheet-up) ----------
const toRad = d => d * Math.PI / 180;
const north = new THREE.Vector3(Math.sin(toRad(NORTH_DEG)), 0, -Math.cos(toRad(NORTH_DEG)));
const east = new THREE.Vector3(Math.cos(toRad(NORTH_DEG)), 0, Math.sin(toRad(NORTH_DEG)));
let dec = 23.44, hour = 19.0;
const target = new THREE.Vector3(2, 0, 0);
function updateSun() {
  const phi = toRad(LAT), d = toRad(dec), H = toRad(15 * (hour - 12));
  const sinAlt = Math.sin(phi) * Math.sin(d) + Math.cos(phi) * Math.cos(d) * Math.cos(H), alt = Math.asin(sinAlt);
  const az = Math.atan2(Math.sin(H), Math.cos(H) * Math.sin(phi) - Math.tan(d) * Math.cos(phi)) + Math.PI;
  const dir = north.clone().multiplyScalar(Math.cos(az)).add(east.clone().multiplyScalar(Math.sin(az))).multiplyScalar(Math.cos(alt)).setY(Math.max(sinAlt, 0.02)).normalize();
  sun.position.copy(target).addScaledVector(dir, 120); sun.target.position.copy(target);
  const up = Math.max(0, Math.min(1, sinAlt * 2.2));
  const night = Math.max(0, Math.min(1, (0.03 - sinAlt) / 0.15));      // 0 by day, 1 after dusk: moonlight, dark sky, lamps (slider goes to 24:00)
  sun.intensity = (0.15 + 2.5 * up) * (1 - night) + 0.4 * night;
  sun.color.setHSL(0.085, 0.75 - 0.45 * up, 0.58 + 0.3 * up).lerp(new THREE.Color(0x9fb3e6), night);
  hemi.intensity = (0.2 + 0.4 * up) * (1 - night) + 0.18 * night;
  hemi.color.set(0xdfe9f3).lerp(new THREE.Color(0x3a4a6e), night); hemi.groundColor.set(0x7d7058).lerp(new THREE.Color(0x1c1a17), night);
  if (envTex) scene.environment = night > 0.5 ? null : envTex;
  if (scene.fog) scene.fog.color.set(0xd9dcd6).lerp(new THREE.Color(0x0d1424), night);
  document.body.classList.toggle('night', night > 0.5);
  const dusk = Math.max(0, Math.min(1, (0.32 - sinAlt) / 0.3));       // lights come on as the sun gets low
  roomLights.forEach(l => { l.intensity = 9 * dusk; });
  bollardLights.forEach(l => { l.intensity = 2.2 * dusk; });
  wallLights.forEach(l => { l.intensity = 4.5 * dusk; });
  M.bollard.emissiveIntensity = 2.5 * dusk;
}
updateSun();

// ---------- camera presets ----------
// project.json "views": {"street": {"pos": [x, y|null, z], "tgt": [x, y, z]}, ...}; y = null puts the eye 1.7 m above the ground
function view(name, pos, tgt) {
  const v = (PROJ.views || {})[name] || {}; const p = v.pos || pos, t = v.tgt || tgt;
  const y = p[1] == null ? heightAt(p[0], p[2]) + 1.7 : p[1];
  return { pos: new THREE.Vector3(p[0], y, p[2]), tgt: new THREE.Vector3(t[0], t[1], t[2]) };
}
const presets = {
  aerial:   () => view('aerial', [30, 24, 34], [1, 0, -2]),
  street:   () => view('street', [-20.5, null, -1.5], [-9.5, 1.2, -7.0]),
  garden:   () => view('garden', [21, null, 1.5], [6, -0.2, 3.5]),
  interior: () => view('interior', [1.5, 24, 22], [1.5, -1, 0.5]),
  top:      () => view('top', [3, 95, 0.01], [3, 0, 0]),
};
let anim = null;
function goTo(name, instant = false) {
  const p = presets[name]();
  document.querySelectorAll('button.view[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === name)));
  if (name === 'interior') setRoof(false);
  if (instant || reduceMotion) { camera.position.copy(p.pos); controls.target.copy(p.tgt); controls.update(); return; }
  anim = { t0: performance.now(), dur: 900, fromP: camera.position.clone(), fromT: controls.target.clone(), toP: p.pos, toT: p.tgt };
}
document.querySelectorAll('button.view[data-view]').forEach(b => b.addEventListener('click', () => goTo(b.dataset.view)));
controls.addEventListener('start', () => { anim = null; });

// ---------- UI ----------
function setRoof(on) {
  roofs.visible = on && (typeof storeyShown === 'undefined' || storeyShown >= MAX_STOREY);
  const cb = document.getElementById('t-roof'); if (cb) cb.checked = on;
}
document.getElementById('t-roof').addEventListener('change', e => setRoof(e.target.checked));
// storey cut-away: show storeys up to k (roof only when the top storey is shown)
let storeyShown = Infinity;
function setStorey(v) {
  storeyShown = v === 'all' ? Infinity : +v;
  for (const g of STOREYS.values()) g.visible = g.userData.storey <= storeyShown;
  roofs.visible = storeyShown >= MAX_STOREY && document.getElementById('t-roof').checked;
  const sel = document.getElementById('t-storey'); if (sel) sel.value = String(v);
}
if (MAX_STOREY > 0) {
  const lab = document.createElement('label'); lab.className = 'toggle'; lab.htmlFor = 't-storey'; lab.textContent = (T.l_storey || 'Storeys') + ' ';
  const sel = document.createElement('select'); sel.id = 't-storey';
  const names = PROJ.storey_names || T.storey_names || [];
  sel.innerHTML = `<option value="all">${T.storey_all || 'All'}</option>` + Array.from({ length: MAX_STOREY + 1 }, (_, k) => `<option value="${k}">${names[k] || (T.l_storey || 'Storey') + ' ' + k}</option>`).join('');
  lab.appendChild(sel); document.querySelector('.toggles').appendChild(lab);
  sel.addEventListener('change', () => setStorey(sel.value));
}
window.__storey = setStorey;
document.getElementById('t-furn').addEventListener('change', e => { furniture.visible = e.target.checked; });
document.getElementById('t-trees').addEventListener('change', e => { trees.visible = e.target.checked; });
document.getElementById('t-spots').addEventListener('change', e => { showSpots = e.target.checked; });
// room labels sit on the floors: switching them on takes the roof off so they read from above
let roofBeforeAreas = null;
document.getElementById('t-areas').addEventListener('change', e => {
  showAreas = e.target.checked;
  if (showAreas) { roofBeforeAreas = document.getElementById('t-roof').checked; setRoof(false); }
  else if (roofBeforeAreas) { setRoof(true); roofBeforeAreas = null; }                  // put the roof back if the labels took it off
});
window.__areas = on => { const cb = document.getElementById('t-areas'); cb.checked = on; cb.dispatchEvent(new Event('change')); };
document.getElementById('t-plan').addEventListener('change', e => { groundU.planMix.value = e.target.checked ? 0.9 : 0; });
document.getElementById('t-terrain').addEventListener('change', e => { relief = e.target.checked; applyHeights(); placeTrees(); });
document.querySelectorAll('.dseg button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.dseg button').forEach(o => o.setAttribute('aria-pressed', String(o === b)));
  dec = parseFloat(b.dataset.dec); updateSun();
}));
const hourIn = document.getElementById('hour'), hourOut = document.getElementById('hour-out');
const fmtH = h => `${String(Math.floor(h)).padStart(2, '0')}:${String(Math.round((h % 1) * 60)).padStart(2, '0')}`;
hourIn.addEventListener('input', () => { hour = parseFloat(hourIn.value); hourOut.textContent = fmtH(hour); updateSun(); });
const panel = document.getElementById('panel'), tp = document.getElementById('toggle-panel');
tp.addEventListener('click', () => {
  const c = panel.classList.toggle('collapsed');
  tp.textContent = c ? T.show : T.hide; tp.setAttribute('aria-expanded', String(!c));
});
if (matchMedia('(max-width: 640px)').matches) { panel.classList.add('collapsed'); tp.textContent = T.show; tp.setAttribute('aria-expanded', 'false'); }

// ---------- compass ----------
const needle = document.getElementById('needle'), nlabel = document.getElementById('nlabel');
function updateCompass() {
  const fwd = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion); fwd.y = 0;
  if (fwd.lengthSq() < 1e-6) { camera.getWorldDirection(fwd); fwd.y = 0; }
  fwd.normalize();
  const deg = (Math.atan2(north.x, -north.z) - Math.atan2(fwd.x, -fwd.z)) * 180 / Math.PI;
  needle.setAttribute('transform', `rotate(${deg.toFixed(1)})`);
  const r = toRad(deg); nlabel.setAttribute('x', (Math.sin(r) * 13).toFixed(1)); nlabel.setAttribute('y', (-Math.cos(r) * 13 + 3).toFixed(1)); nlabel.textContent = 'N';
}


// =================== free navigation: walk (eye level, collisions) and drone ===================
const NAV = { mode: 'orbit', yaw: 0, pitch: 0, keys: new Set(), joy: { x: 0, y: 0 }, lookTouch: null, vy: 0, upDown: 0 };
const EYE = 1.65, RADIUS = 0.28;
// ---- obstacles: 2D segments with half-thickness and a vertical range ----
const OBST = [];
function addSeg(ax, az, bx, bz, half, y0, y1) { OBST.push({ ax, az, bx, bz, half, y0, y1 }); }
const PASSABLE = new Set(['door', 'front', 'slide', 'door_glass', 'open']);
for (const w of LAY.walls) {
  const [ax, az] = w.a, [bx, bz] = w.b, L_ = Math.hypot(bx - ax, bz - az), ux = (bx - ax) / L_, uz = (bz - az) / L_;
  const ops = [...w.ops].sort((a, b) => a.o - b.o);
  let cur = 0;
  const span = (s, e, y0, y1) => { if (e - s > 0.01) addSeg(ax + ux * s, az + uz * s, ax + ux * e, az + uz * e, w.t / 2, y0, y1); };
  for (const o of ops) {
    span(cur, o.o, w.y0, w.y0 + w.h);
    if (PASSABLE.has(o.kind)) span(o.o, o.o + o.w, w.y0 + o.head, w.y0 + w.h);     // only the lintel blocks
    else span(o.o, o.o + o.w, w.y0, w.y0 + w.h);                                     // windows, garage door
    cur = o.o + o.w;
  }
  span(cur, L_, w.y0, w.y0 + w.h);
}
for (const c of LAY.columns) addSeg(c.x - 0.01, c.z, c.x + 0.01, c.z, c.s / 2, c.y0, c.y0 + c.h);
for (const f of LAY.furniture) {
  if (f.h < 0.3 || /mesa centro|espreguiçadeira|coffee table|lounger|rug/i.test(f.name)) continue;
  const [x0, z0, x1, z1] = f.b, cx = (x0 + x1) / 2, cz = (z0 + z1) / 2;
  if (x1 - x0 > z1 - z0) addSeg(x0 + (z1 - z0) / 2, cz, x1 - (z1 - z0) / 2, cz, (z1 - z0) / 2, f.y0, f.y0 + f.h);
  else addSeg(cx, z0 + (x1 - x0) / 2, cx, z1 - (x1 - x0) / 2, (x1 - x0) / 2, f.y0, f.y0 + f.h);
}
for (const r of (LAY.railings || [])) addSeg(r.a[0], r.a[1], r.b[0], r.b[1], 0.04, r.y, r.y + (r.h ?? 1.0));   // balustrades
// retaining walls (same gaps as the meshes) and the plot boundary (gaps at the gates)
for (const rw of LAY.retaining) {
  const [lo, hi] = plotZRange(rw.x); if (!isFinite(lo)) continue;
  let segs = [[lo + 0.2, hi - 0.2]];
  const cuts = LAY.garden_steps.filter(s => Math.abs(s.x - rw.x) < 0.01).map(s => [s.z0, s.z1]);
  for (const [cx, z0, z1] of (LAY.meta.retaining_cuts ?? [])) if (Math.abs(rw.x - cx) < 0.01) cuts.push([z0, z1]);   // house walls replace the retaining wall here
  for (const [a, b] of cuts) segs = segs.flatMap(([s, e]) => [[s, Math.min(e, a)], [Math.max(s, b), e]]).filter(([s, e]) => e - s > 0.1);
  for (const [s, e] of segs) addSeg(rw.x, s, rw.x, e, 0.2, -9, 9);
}
for (let i = 0; i < PLOT.length; i++) {
  const [ax, az] = PLOT[i], [bx, bz] = PLOT[(i + 1) % PLOT.length];
  const west = Math.abs(ax - LAY.meta.cut_x) < 0.05 && Math.abs(bx - LAY.meta.cut_x) < 0.05;
  if (!west) { addSeg(ax, az, bx, bz, 0.2, -9, 9); continue; }
  // west line: split around the vehicle and pedestrian gates
  const z0 = Math.min(az, bz), z1 = Math.max(az, bz);
  let parts = [[z0, z1]];
  for (const g of [LAY.gate, LAY.ped_gate]) parts = parts.flatMap(([s, e]) => [[s, Math.min(e, g.z0 + 0.25)], [Math.max(s, g.z1 - 0.25), e]]).filter(([s, e]) => e - s > 0.05);
  for (const [s, e] of parts) addSeg(ax, s, ax, e, 0.2, -9, 9);
}
// garage: block the closed sectional door in walk mode is already in the wall list

// ---- walkable height under a point ----
function inPolyXZ(x, z, p) { return pointInPoly(x, z, p); }
const BLOCKS = Object.values(LAY.blocks).map(b => b.rect).concat(LAY.floors.filter(f => f.mat === 'terrace').map(f => [Math.min(...f.poly.map(q => q[0])), Math.min(...f.poly.map(q => q[1])), Math.max(...f.poly.map(q => q[0])), Math.max(...f.poly.map(q => q[1]))]));
function floorAt(x, z, feet) {
  let best = -Infinity;
  for (const st of LAY.stairs) {
    if (x >= st.x0 - 0.05 && x <= st.x1 + 0.05 && z >= st.z0 && z <= st.z1) {
      const t = Math.min(1, Math.max(0, (x - st.x0) / (st.x1 - st.x0)));
      const h = st.ytop + (st.ybot - st.ytop) * t;
      if (h <= feet + 0.45) best = Math.max(best, h);
    }
  }
  if (best === -Infinity) for (const f of LAY.floors) if (f.y <= feet + 0.45 && inPolyXZ(x, z, f.poly) && !(f.holes || []).some(h => inPolyXZ(x, z, h))) best = Math.max(best, f.y);
  // inside the building footprint the slabs and stair rule; the terrain only counts outside it
  if (best > -Infinity && BLOCKS.some(r => x >= r[0] && x <= r[2] && z >= r[1] && z <= r[3])) return best;
  const g = heightAt(x, z);
  return Math.max(best, g);
}
function collide(p, feet, head) {
  for (let it = 0; it < 3; it++) {
    for (const o of OBST) {
      if (o.y1 <= feet + 0.25 || o.y0 >= head) continue;        // below a step-over height or above the head
      const dx = o.bx - o.ax, dz = o.bz - o.az, L2 = dx * dx + dz * dz;
      const t = L2 > 0 ? Math.max(0, Math.min(1, ((p.x - o.ax) * dx + (p.z - o.az) * dz) / L2)) : 0;
      const cx = o.ax + dx * t, cz = o.az + dz * t;
      let ex = p.x - cx, ez = p.z - cz, d = Math.hypot(ex, ez);
      const min = o.half + RADIUS;
      if (d < min) {
        if (d < 1e-5) { ex = -dz; ez = dx; d = Math.hypot(ex, ez) || 1; }
        p.x = cx + ex / d * min; p.z = cz + ez / d * min;
      }
    }
  }
}
// ---- input ----
const cvs = renderer.domElement;
const navHelp = document.getElementById('nav-help'), crosshair = document.getElementById('crosshair');
const joyEl = document.getElementById('joy'), joyKnob = document.getElementById('joy-knob'), dUp = document.getElementById('drone-up'), dDn = document.getElementById('drone-down');
const coarse = matchMedia('(pointer: coarse)').matches;
function setLookFromCamera() {
  const d = new THREE.Vector3(); camera.getWorldDirection(d);
  NAV.yaw = Math.atan2(-d.x, -d.z); NAV.pitch = Math.asin(Math.max(-1, Math.min(1, d.y)));
}
function applyLook() { camera.rotation.set(NAV.pitch, NAV.yaw, 0, 'YXZ'); }
function setNav(mode) {
  if (mode === NAV.mode) return;
  NAV.mode = mode; anim = null;
  document.querySelectorAll('.nseg button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.nav === mode)));
  const free = mode !== 'orbit';
  controls.enabled = !free;
  navHelp.hidden = !free; crosshair.hidden = !free || coarse;
  joyEl.hidden = !(free && coarse); dUp.hidden = dDn.hidden = !(mode === 'drone' && coarse);
  document.getElementById('hint').hidden = true;
  navHelp.querySelector('.drone-only').hidden = mode !== 'drone';
  if (free && !panel.classList.contains('collapsed')) { panel.classList.add('collapsed'); tp.textContent = T.show; tp.setAttribute('aria-expanded', 'false'); }
  if (mode === 'walk') {
    const [x, z] = PROJ.walk_spawn ?? [-17.2, -3.0];   // where Walk mode starts (scene metres, usually on the street at the gate)
    camera.position.set(x, heightAt(x, z) + EYE, z); NAV.yaw = -Math.PI / 2; NAV.pitch = -0.04; NAV.vy = 0;
    setRoof(true); applyLook();
  } else if (mode === 'drone') {
    if (camera.position.y < 6) camera.position.y = 12;
    setLookFromCamera(); applyLook();
  } else {
    if (document.pointerLockElement) document.exitPointerLock();
    const d = new THREE.Vector3(); camera.getWorldDirection(d);
    controls.target.copy(camera.position).addScaledVector(d, 12);
    controls.update();
  }
}
document.querySelectorAll('.nseg button').forEach(b => b.addEventListener('click', () => setNav(b.dataset.nav)));
// presets return to orbit
document.querySelectorAll('button.view[data-view]').forEach(b => b.addEventListener('click', () => { if (NAV.mode !== 'orbit') { setNav('orbit'); goTo(b.dataset.view); } }, true));
addEventListener('keydown', e => {
  if (NAV.mode === 'orbit' || e.target.closest('input, button, select, textarea')) return;
  NAV.keys.add(e.code);
  if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
});
addEventListener('keyup', e => NAV.keys.delete(e.code));
addEventListener('blur', () => NAV.keys.clear());
cvs.addEventListener('click', () => {
  if (NAV.mode === 'orbit' || coarse || document.pointerLockElement) return;
  try { const r = cvs.requestPointerLock(); if (r && r.catch) r.catch(() => {}); } catch (_) { /* drag fallback below */ }
});
document.addEventListener('pointerlockchange', () => { navHelp.classList.toggle('locked', document.pointerLockElement === cvs); });
const LOOK = 0.0024;
document.addEventListener('mousemove', e => {
  if (NAV.mode === 'orbit' || document.pointerLockElement !== cvs) return;
  NAV.yaw -= e.movementX * LOOK; NAV.pitch = Math.max(-1.45, Math.min(1.45, NAV.pitch - e.movementY * LOOK)); applyLook();
});
// drag-to-look fallback (no pointer lock) and touch look on the canvas
let drag = null;
cvs.addEventListener('pointerdown', e => {
  if (NAV.mode === 'orbit' || document.pointerLockElement === cvs) return;
  drag = { id: e.pointerId, x: e.clientX, y: e.clientY }; cvs.setPointerCapture(e.pointerId);
});
cvs.addEventListener('pointermove', e => {
  if (!drag || e.pointerId !== drag.id) return;
  const k = e.pointerType === 'touch' ? 0.005 : 0.004;
  NAV.yaw -= (e.clientX - drag.x) * k; NAV.pitch = Math.max(-1.45, Math.min(1.45, NAV.pitch - (e.clientY - drag.y) * k));
  drag.x = e.clientX; drag.y = e.clientY; applyLook();
});
const endDrag = e => { if (drag && e.pointerId === drag.id) drag = null; };
cvs.addEventListener('pointerup', endDrag); cvs.addEventListener('pointercancel', endDrag);
// virtual joystick (touch)
let joyId = null;
const joyMove = e => {
  const r = joyEl.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2, R = r.width / 2;
  let dx = e.clientX - cx, dy = e.clientY - cy; const d = Math.hypot(dx, dy); if (d > R) { dx *= R / d; dy *= R / d; }
  joyKnob.style.transform = `translate(${dx}px, ${dy}px)`; NAV.joy.x = dx / R; NAV.joy.y = dy / R;
};
joyEl.addEventListener('pointerdown', e => { joyId = e.pointerId; joyEl.setPointerCapture(e.pointerId); joyMove(e); e.preventDefault(); });
joyEl.addEventListener('pointermove', e => { if (e.pointerId === joyId) joyMove(e); });
const joyEnd = e => { if (e.pointerId !== joyId) return; joyId = null; NAV.joy.x = NAV.joy.y = 0; joyKnob.style.transform = ''; };
joyEl.addEventListener('pointerup', joyEnd); joyEl.addEventListener('pointercancel', joyEnd);
for (const [el, v] of [[dUp, 1], [dDn, -1]]) {
  el.addEventListener('pointerdown', e => { NAV.upDown = v; el.setPointerCapture(e.pointerId); });
  const off = () => { NAV.upDown = 0; }; el.addEventListener('pointerup', off); el.addEventListener('pointercancel', off);
}
// ---- per-frame update ----
const v3 = new THREE.Vector3();
function navUpdate(dt) {
  const k = NAV.keys, run = k.has('ShiftLeft') || k.has('ShiftRight');
  let f = (k.has('KeyW') || k.has('ArrowUp') ? 1 : 0) - (k.has('KeyS') || k.has('ArrowDown') ? 1 : 0) - NAV.joy.y;
  let s = (k.has('KeyD') || k.has('ArrowRight') ? 1 : 0) - (k.has('KeyA') || k.has('ArrowLeft') ? 1 : 0) + NAV.joy.x;
  const mag = Math.hypot(f, s); if (mag > 1) { f /= mag; s /= mag; }
  const p = camera.position;
  if (NAV.mode === 'walk') {
    const speed = run ? 3.2 : 1.5;
    const fx = -Math.sin(NAV.yaw), fz = -Math.cos(NAV.yaw), rx = Math.cos(NAV.yaw), rz = -Math.sin(NAV.yaw);
    let feet = p.y - EYE;
    const nx = p.x + (fx * f + rx * s) * speed * dt, nz = p.z + (fz * f + rz * s) * speed * dt;
    const q = { x: nx, z: nz };
    collide(q, feet, feet + 1.8);
    const target = floorAt(q.x, q.z, feet);
    if (target - feet > 0.45) { q.x = p.x; q.z = p.z; }       // too high to step up (e.g. retaining wall top)
    p.x = q.x; p.z = q.z;
    const tgt = floorAt(p.x, p.z, feet) + EYE;
    if (tgt > p.y) p.y += (tgt - p.y) * Math.min(1, dt * 12);  // climb steps smoothly
    else { NAV.vy -= 9.8 * dt; p.y = Math.max(tgt, p.y + NAV.vy * dt); if (p.y === tgt) NAV.vy = 0; }
    // keep the walker on the site
    p.x = Math.max(G.x0 + 1, Math.min(G.x1 - 1, p.x)); p.z = Math.max(G.z0 + 1, Math.min(G.z1 - 1, p.z));
  } else {
    const speed = run ? 16 : 6;
    camera.getWorldDirection(v3);
    const rx = Math.cos(NAV.yaw), rz = -Math.sin(NAV.yaw);
    const up = (k.has('Space') || k.has('KeyE') ? 1 : 0) - (k.has('KeyC') || k.has('KeyQ') || k.has('ControlLeft') ? 1 : 0) + NAV.upDown;
    const q = { x: p.x + (v3.x * f + rx * s) * speed * dt, z: p.z + (v3.z * f + rz * s) * speed * dt };
    let ny = p.y + (v3.y * f + up) * speed * dt;
    collide(q, ny - 0.3, ny + 0.3);
    ny = Math.max(heightAt(q.x, q.z) + 0.6, Math.min(80, ny));
    p.set(Math.max(TXL, Math.min(TXH, q.x)), ny, Math.max(TZL, Math.min(TZH, q.z)));
  }
  applyLook();
}
const TXL = G.x0 - 40, TXH = G.x1 + 40, TZL = G.z0 - 40, TZH = G.z1 + 40;
window.__nav = { setNav, NAV, navUpdate, floorAt, camera };

// ---------- loop ----------
function resize() { const w = stage.clientWidth, h = stage.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
addEventListener('resize', resize); resize();
goTo('aerial', true);
renderer.domElement.addEventListener('pointerdown', () => { document.getElementById('hint').hidden = true; }, { once: true });
let lastT = performance.now();
renderer.setAnimationLoop(now => {
  const dt = Math.min(0.1, (now - lastT) / 1000); lastT = now;
  if (NAV.mode !== 'orbit') { navUpdate(dt); renderer.render(scene, camera); updateLabels(); updateCompass(); return; }
  if (anim) {
    const t = Math.min(1, (now - anim.t0) / anim.dur), e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    camera.position.lerpVectors(anim.fromP, anim.toP, e); controls.target.lerpVectors(anim.fromT, anim.toT, e);
    if (t >= 1) anim = null;
  }
  controls.update(); renderer.render(scene, camera); updateLabels(); updateCompass();
});
window.__ready = true;
