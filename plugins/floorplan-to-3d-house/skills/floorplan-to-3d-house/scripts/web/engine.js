import * as THREE from 'three/webgpu';
import * as TSL from 'three/tsl';
import { ssgi } from 'three/addons/tsl/display/SSGINode.js';
import { ao as gtao } from 'three/addons/tsl/display/GTAONode.js';
import { traa } from 'three/addons/tsl/display/TRAANode.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

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
// WebGPU renderer (falls back to WebGL 2 where WebGPU is missing); post-processing per quality tier, see "quality" below
const renderer = new THREE.WebGPURenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;   // PCFSoft was removed from the WebGPU renderer; softness via shadow.radius
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
renderer.outputColorSpace = THREE.SRGBColorSpace;
stage.appendChild(renderer.domElement);
await renderer.init();
const GPU = !!renderer.backend?.isWebGPUBackend;
const maxAniso = renderer.getMaxAnisotropy ? renderer.getMaxAnisotropy() : 8;

const scene = new THREE.Scene();
const skyGrad = (top, bot) => { const cv = document.createElement('canvas'); cv.width = 2; cv.height = 256; const g = cv.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 256);
  gr.addColorStop(0, top); gr.addColorStop(1, bot); g.fillStyle = gr; g.fillRect(0, 0, 2, 256); const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t; };
const SKY_DAY = skyGrad('#9fb7cc', '#e8e4da'), SKY_NIGHT = skyGrad('#070d1a', '#18233a');
scene.background = SKY_DAY;
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
sun.shadow.radius = 3;
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
  t.userData.metres = metres; t.userData.url = url; t.userData.srgb = srgb;
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
  const flip = new Uint16Array(w * h * 4), row = w * 4;
  for (let y = 0; y < h; y++) flip.set(data.subarray(y * row, (y + 1) * row), (h - 1 - y) * row);
  const hdr = new THREE.DataTexture(flip, w, h, THREE.RGBAFormat, THREE.HalfFloatType);
  Object.assign(hdr, { colorSpace: THREE.LinearSRGBColorSpace, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, generateMipmaps: false, flipY: false, mapping: THREE.EquirectangularReflectionMapping });
  hdr.needsUpdate = true;
  envTex = hdr; scene.environment = envTex; updateSun();
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
// ground: masks (road, paving, gravel, beds, setts) blended over grass/soil in world metres — TSL node material
const planMixU = TSL.uniform(0);
const groundU = { planMix: planMixU };
const groundMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.96, metalness: 0, envMapIntensity: 0.6 });
{
  const { texture: tx_, mix, vec3, dot, smoothstep } = TSL, W = TSL.positionGeometry.xz, UV = TSL.uv();
  const tx = (t, m) => tx_(t, W.div(m)).rgb;
  const tx2 = (t, m) => mix(tx_(t, W.div(m)).rgb, tx_(t, W.yx.div(m * 2.37).add(0.31)).rgb, 0.35);
  const m1 = tx_(v2mask1, UV).rgb, m2 = tx_(v2mask2, UV).rgb, m3 = tx_(v2mask3, UV).rgb;
  const macro = tx_(soilTex, W.div(41)).r, macro2 = tx_(grassTex, W.div(29).add(0.17)).g;
  const grassC = tx2(grassTex, 1.7).mul(vec3(0.66, 0.74, 0.52)).mul(macro2.mul(0.38).add(0.8));
  const dry = mix(vec3(dot(grassC, vec3(0.333))), grassC, 0.6).mul(vec3(1.22, 1.12, 0.8));
  const soilC = tx2(soilTex, 3.2).mul(vec3(0.78, 0.74, 0.7));
  let c = mix(dry, soilC, smoothstep(0.5, 0.7, macro).mul(0.8));
  c = mix(c, tx(settsTex, 1.0).mul(vec3(1.1, 1.08, 1.05)), m3.r);
  c = mix(c, tx(asphTex, 2.5), m1.b);
  c = mix(c, grassC, m1.r);
  c = mix(c, tx(paverTex, 1.6), m1.g);
  c = mix(c, tx(pavTex, 1.2), m2.r);
  c = mix(c, tx2(gravelTex, 1.4).mul(vec3(1.45, 1.42, 1.36)), m2.g);
  c = mix(c, tx2(soilTex, 1.2).mul(vec3(0.42, 0.34, 0.27)), m2.b);
  c = mix(c, vec3(0.82, 0.81, 0.78), m3.g.mul(m1.b));
  c = mix(c, tx_(planV2, UV).rgb, planMixU);
  groundMat.colorNode = c;
}
const fineGround = new THREE.Mesh(fineGeo, groundMat), apron = new THREE.Mesh(apronGeo, groundMat);
fineGround.receiveShadow = apron.receiveShadow = true;
scene.add(fineGround, apron);

// ---------- materials (named, for export) ----------
function mat(name, opts, map, nrm, nscale = 0.6) {
  const p = { roughness: 0.9, metalness: 0, ...opts };
  if (map) { const m = map.userData.url ? photo(map.userData.url, map.userData.metres, map.userData.srgb) : map.clone(); if (m.image) m.needsUpdate = true; const [w, h] = Array.isArray(map.userData.metres) ? map.userData.metres : [map.userData.metres, map.userData.metres]; m.repeat.set(1 / w, 1 / h); p.map = m; }
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
  oak_dark: mat('Furn_Wood_Dark', { color: 0x5b3e2a, roughness: 0.45 }, oakTex),   // dark wood table tops
  oak_top: mat('Furn_Oak_Top', { color: 0xf3dcb4, roughness: 0.45 }, oakTex),   // light natural oak for table and desk tops
  granite: mat('Furn_Granite_Black', { color: 0x141516, roughness: 0.18, metalness: 0.05 }),
  wardrobe: mat('Furn_Wardrobe', { color: 0xd8cbb8, roughness: 0.6 }), white: mat('Furn_White', { color: 0xf5f4f0, roughness: 0.4 }),
  kitchen: mat('Furn_Kitchen', { color: 0x3a3836, roughness: 0.5 }), stone_top: mat('Furn_Stone_Top', { color: 0xe4e0d8, roughness: 0.3 }),
  dark: mat('Furn_Dark', { color: 0x2f2d2b, roughness: 0.5 }), rug: mat('Furn_Rug', { color: 0xcdbfa8, roughness: 1 }),
  chair: mat('Furn_Chair', { color: 0xb59a78, roughness: 0.7 }),
  bark: mat('Olive_Bark', { color: 0x6b6050, roughness: 1 }),
  olive: [0x66744d, 0x727f55, 0x5d6a46].map((c, i) => { const m = new THREE.MeshStandardMaterial({ color: c, roughness: 0.92, flatShading: true }); m.name = 'Olive_Foliage'; return m; }),
  led: (() => { const m = new THREE.MeshStandardMaterial({ color: 0xfff1d6, emissive: 0xffd9a0, emissiveIntensity: 2.2, roughness: 0.4 }); m.name = 'LED_Strip'; return m; })(),
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
      if (o.open) addMesh(g, mbox(s, e, head, head + 0.28, -0.16, 0.16), M.garage);   // open: roller drum above the opening
      else addMesh(g, mbox(s, e, y0, head, -0.04, 0.04), M.garage);
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

// ---------- furniture: simple procedural models built from the layout boxes (v1.8) ----------
// Each layout item keeps its footprint b=[x0,z0,x1,z1], y0 and h; the name (pt/en) picks the model.
// The back of a piece is the side nearest a wall (or f.back: 'n'|'s'|'e'|'w'); f.head does the same for beds.
function wallDist(x, z) {
  let d = 1e9;
  for (const w of LAY.walls) {
    if (w.y0 > 1) continue;
    const [ax, az] = w.a, [bx, bz] = w.b, dx = bx - ax, dz = bz - az, l2 = dx * dx + dz * dz || 1e-9;
    const u = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / l2));
    d = Math.min(d, Math.hypot(x - ax - u * dx, z - az - u * dz) - (w.t || 0.2) / 2);
  }
  return d;
}
function backSide(f, longOnly = true) {
  if (f.back) return f.back;
  const [x0, z0, x1, z1] = f.b, wx = x1 - x0, wz = z1 - z0;
  const c = { n: [(x0 + x1) / 2, z0], s: [(x0 + x1) / 2, z1], w: [x0, (z0 + z1) / 2], e: [x1, (z0 + z1) / 2] };
  const keys = !longOnly || Math.abs(wx - wz) < 0.15 ? ['n', 's', 'w', 'e'] : wx > wz ? ['n', 's'] : ['w', 'e'];
  let best = keys[0], bd = 1e9;
  for (const k of keys) { const d = wallDist(...c[k]); if (d < bd) { bd = d; best = k; } }
  return best;
}
// local frame: u across the front (0..W), v from the back (0) to the front (D)
function fframe(f, side, parent) {
  const [x0, z0, x1, z1] = f.b, ax = side === 'n' || side === 's';
  const W = ax ? x1 - x0 : z1 - z0, D = ax ? z1 - z0 : x1 - x0;
  const world = (u, v) => ax ? [x0 + u, side === 'n' ? z0 + v : z1 - v] : [side === 'w' ? x0 + v : x1 - v, z0 + u];
  const box = (u0, u1, v0, v1, ya, yb, m, cast = true) => {
    const [pa, qa] = world(u0, v0), [pb, qb] = world(u1, v1);
    if (yb - ya < 0.002) yb = ya + 0.002;
    return addMesh(parent, mbox(Math.min(pa, pb), Math.max(pa, pb), ya, yb, Math.min(qa, qb), Math.max(qa, qb)), m, cast, true);
  };
  const cyl = (u, v, r, ya, yb, m, seg = 18, rTop = r) => {
    const [x, z] = world(u, v), g = new THREE.CylinderGeometry(rTop, r, yb - ya, seg); g.translate(x, (ya + yb) / 2, z);
    return addMesh(parent, g, m, true, true);
  };
  const rbox = (u0, u1, v0, v1, ya, yb, m, r = 0.05) => {
    const [pa, qa] = world(u0, v0), [pb, qb] = world(u1, v1), sx = Math.abs(pb - pa), sz = Math.abs(qb - qa), sy = yb - ya;
    const rr = Math.max(0.002, Math.min(r, sx / 2 - 0.001, sy / 2 - 0.001, sz / 2 - 0.001));
    const g = new RoundedBoxGeometry(sx, sy, sz, 3, rr); g.translate((pa + pb) / 2, (ya + yb) / 2, (qa + qb) / 2);
    return addMesh(parent, g, m, true, true);
  };
  return { W, D, box, cyl, world, rbox };
}
const fLeg = (F, u, v, y0, y1, m, s = 0.04) => F.box(u - s / 2, u + s / 2, v - s / 2, v + s / 2, y0, y1, m);
function fCabinet(F, y, H, body, { top = null, topT = 0.03, plinth = 0.1, doorW = 0.6, over = 0.02, handles = true } = {}) {
  const { W, D, box } = F, yb = y + plinth, yt = y + H - (top ? topT : 0);
  if (plinth > 0) box(0.03, W - 0.03, 0, D - 0.07, y, yb, M.dark, false);
  box(0, W, 0, D - 0.02, yb, yt, body);
  const n = Math.max(1, Math.round(W / doorW));
  for (let i = 1; i < n; i++) { const u = W * i / n; box(u - 0.004, u + 0.004, D - 0.025, D - 0.017, yb + 0.02, yt - 0.02, M.dark, false); }
  if (handles) for (let i = 0; i < n; i++) {
    const u = W * (i + 0.5) / n + (i % 2 ? -1 : 1) * (W / n / 2 - 0.07);
    box(u - 0.008, u + 0.008, D - 0.035, D - 0.005, Math.max(yb + 0.05, yt - 0.25), yt - 0.06, M.frame, false);
  }
  if (top) box(0, W, 0, D + over, yt, y + H, top);
}
function fTable(F, y, H, top, leg, { t = 0.04, inset = 0.08 } = {}) {
  const { W, D, box } = F; box(0, W, 0, D, y + H - t, y + H, top);
  for (const [u, v] of [[inset, inset], [W - inset, inset], [inset, D - inset], [W - inset, D - inset]]) fLeg(F, u, v, y, y + H - t, leg, 0.05);
}
function fChair(F, y, H, seatH, m, back = true) {
  const { W, D, box } = F, s = 0.03;
  for (const [u, v] of [[0.04, 0.04], [W - 0.04, 0.04], [0.04, D - 0.04], [W - 0.04, D - 0.04]]) fLeg(F, u, v, y, y + seatH, M.dark, s);
  box(0, W, 0, D, y + seatH, y + seatH + 0.04, m);
  if (back) box(0.02, W - 0.02, 0, 0.04, y + seatH + 0.04, y + Math.max(H, seatH + 0.4), m);
}
function fSofa(f, F, y, H, arms) {     // Phase 2: soft upholstery — rounded cushions, plinth recessed in shadow
  const { W, D, box, rbox } = F, seat = y + 0.44, armW = 0.18, bd = 0.22;
  box(0.06, W - 0.06, 0.06, D - 0.06, y, y + 0.07, M.dark, false);                        // recessed plinth
  rbox(0, W, 0, D, y + 0.07, y + 0.3, M.fabric, 0.04);                                     // frame
  const u0 = arms.l ? armW : 0, u1 = W - (arms.r ? armW : 0), n = Math.max(1, Math.round((u1 - u0) / 0.9));
  for (let i = 0; i < n; i++) { const a = u0 + (u1 - u0) * i / n, b = u0 + (u1 - u0) * (i + 1) / n;
    rbox(a + 0.008, b - 0.008, bd - 0.02, D - 0.01, y + 0.28, seat, M.fabric, 0.06);      // seat cushions
    rbox(a + 0.015, b - 0.015, 0.04, bd + 0.06, seat - 0.02, y + H, M.fabric, 0.08); }   // back cushions, leaning
  rbox(0, W, 0, bd - 0.04, y + 0.28, y + H - 0.08, M.fabric, 0.04);                        // back frame
  if (arms.l) rbox(0, armW, 0, D, y + 0.28, seat + 0.2, M.fabric, 0.06);
  if (arms.r) rbox(W - armW, W, 0, D, y + 0.28, seat + 0.2, M.fabric, 0.06);
}
function fBed(f, parent) {
  const head = f.head || backSide(f, false), F = fframe(f, head, parent), { W, D, box } = F, y = f.y0;
  box(0, W, 0, D, y + 0.06, y + 0.3, M.wood);                                              // frame
  for (const [u, v] of [[0.06, 0.06], [W - 0.06, 0.06], [0.06, D - 0.06], [W - 0.06, D - 0.06]]) fLeg(F, u, v, y, y + 0.06, M.dark, 0.06);
  const { rbox } = F;
  rbox(0.03, W - 0.03, 0.03, D - 0.03, y + 0.3, y + 0.5, M.white, 0.05);                   // mattress
  rbox(-0.01, W + 0.01, D * 0.3, D + 0.02, y + 0.49, y + 0.57, M.fabric, 0.035);          // duvet
  rbox(-0.01, W + 0.01, D - 0.03, D + 0.025, y + 0.24, y + 0.57, M.fabric, 0.03);          // duvet fall at the foot
  rbox(-0.012, W + 0.012, D * 0.62, D * 0.86, y + 0.5, y + 0.6, M.rug, 0.04);              // folded throw across the foot
  const pw = W > 1.3 ? (W - 0.3) / 2 : W - 0.2;
  for (let i = 0; i < (W > 1.3 ? 2 : 1); i++) { const a = 0.1 + i * (pw + 0.1); rbox(a, a + pw, 0.06, 0.5, y + 0.5, y + 0.66, M.white, 0.07); }
}
function fToilet(F, y) {
  const { W, D, box, cyl } = F;
  box(W * 0.1, W * 0.9, 0, 0.18, y + 0.4, y + 0.8, M.white);                              // cistern
  cyl(W / 2, D * 0.55, 0.16, y, y + 0.36, M.white, 20, 0.19);                             // bowl
  cyl(W / 2, D * 0.55, 0.19, y + 0.36, y + 0.4, M.white, 20);                             // seat
}
function fVanity(F, y, H, basins) {
  fCabinet(F, y, H, M.wood, { top: M.white, plinth: 0, doorW: 0.5, handles: false, topT: 0.04 });
  const { W, D, cyl } = F;
  for (let i = 0; i < basins; i++) { const u = W * (i + 0.5) / basins; cyl(u, D * 0.5, 0.2, y + H, y + H + 0.12, M.white, 24, 0.22); cyl(u, D * 0.5, 0.17, y + H + 0.115, y + H + 0.12, M.dark, 24); }
}
function fShelves(F, y, H, m, books) {
  const { W, D, box } = F, n = Math.max(3, Math.round(H / 0.38));
  box(0, 0.02, 0, D, y, y + H, m); box(W - 0.02, W, 0, D, y, y + H, m); box(0, W, 0, 0.015, y, y + H, m);
  const cols = [M.dark, M.white, M.chair, M.wood, M.fabric];
  for (let i = 0; i <= n; i++) {
    const yy = y + 0.05 + (H - 0.07) * i / n; box(0.02, W - 0.02, 0.015, D, yy, yy + 0.02, m);
    if (books && i < n) { let u = 0.04, k = i * 7;
      while (u < W - 0.1) { const bw = 0.03 + ((k * 37) % 5) * 0.008, bh = 0.2 + ((k * 13) % 7) * 0.015;
        if ((k * 11) % 9 > 1) box(u, u + bw, 0.03, D - 0.03, yy + 0.02, yy + 0.02 + bh, cols[k % cols.length], false);
        u += bw + 0.004; k++; } }
  }
}
function fOven(f, parent) {                                  // wood-fired oven: stone base, dome, flue
  const side = f.back || backSide(f, false), F = fframe(f, side, parent), { W, D, box } = F, y = f.y0, by = y + 0.9;
  box(0, W, 0, D, y, by, M.stone);
  box(-0.03, W + 0.03, -0.03, D + 0.03, by, by + 0.08, M.stone_top);
  const [cx, cz] = F.world(W / 2, D * 0.45), r = Math.min(W, D) * 0.46;
  const g = new THREE.SphereGeometry(r, 28, 14, 0, Math.PI * 2, 0, Math.PI / 2); g.scale(1, 0.85, 1); g.translate(cx, by + 0.08, cz);
  addMesh(parent, g, M.render, true, true);
  const vf = D * 0.45 + r * 0.97; box(W / 2 - 0.2, W / 2 + 0.2, vf - 0.08, vf + 0.02, by + 0.08, by + 0.36, M.dark, false);   // mouth
  F.box(W / 2 - 0.25, W / 2 + 0.25, D * 0.45 + r * 0.8, D + 0.08, by + 0.08, by + 0.12, M.stone_top);   // landing slab
  F.cyl(W / 2, D * 0.45 + r * 0.55, 0.07, by + 0.08 + r * 0.6, by + 0.08 + r * 0.85 + 0.55, M.dark, 12);   // flue
}
// ---------- 1.10: detailed rooms and pieces (closets, laundry, pantry, bathrooms, office, hall, BBQ, pouf) ----------
const _clothM = {};
function clothMat(hex) { if (!_clothM[hex]) { _clothM[hex] = new THREE.MeshStandardMaterial({ color: hex, roughness: 0.95 }); _clothM[hex].name = 'Furn_Cloth_' + hex.toString(16); } return _clothM[hex]; }
function fBBQ(f, parent) {                                   // masonry barbecue: stone base with granite top, firebox, hood and chimney through the roof
  const side = f.back || backSide(f, false), F = fframe(f, side, parent), { W, D, box } = F, y = f.y0, by = y + 0.85;
  box(0, W, 0, D, y, by, M.stone);
  box(-0.03, W + 0.03, -0.03, D + 0.03, by, by + 0.05, M.granite || M.stone_top);
  box(W * 0.25, W * 0.29, 0, D, by + 0.05, by + 0.62, M.stone); box(W * 0.71, W * 0.75, 0, D, by + 0.05, by + 0.62, M.stone);
  box(W * 0.29, W * 0.71, 0, 0.08, by + 0.05, by + 0.62, M.stone);
  box(W * 0.29, W * 0.71, 0.08, D - 0.02, by + 0.05, by + 0.08, M.dark);                     // ember bed
  box(W * 0.30, W * 0.70, 0.12, D - 0.06, by + 0.2, by + 0.215, M.dark);                    // grill
  box(W * 0.2, W * 0.8, 0, D * 0.95, by + 0.62, by + 1.05, M.render);                        // hood
  box(W * 0.37, W * 0.63, 0.04, 0.42, by + 1.05, y + (f.chimney || 5.0), M.render);          // chimney
  box(W * 0.34, W * 0.66, 0.01, 0.45, y + (f.chimney || 5.0), y + (f.chimney || 5.0) + 0.06, M.stone_top);
}
function fBBQ2(f, parent) {              // outdoor kitchen after the reference photo (B5): clay-tile base, dark top, sink, louvred doors, wall lights, taupe BBQ tower with firewood and chimney
  const G = fframe(f, 'n', parent), { W, D, box, cyl, world } = G, y = f.y0, top = y + 0.90;
  const mk = (n, c, o = {}) => M[n] || (M[n] = Object.assign(new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.8 }, o)), { name: n }));
  const clay = mk('BBQ_ClayTile', 0xc79a6a), taupe = mk('BBQ_Render_Taupe', 0xb7a794, { roughness: 0.95 }), slate = mk('BBQ_Top_Dark', 0x2e2d2c, { roughness: 0.35 }),
        brick = mk('BBQ_Firebrick', 0x6b3a26), fire = mk('BBQ_Fire', 0xff7a1a, { emissive: 0xff5a00, emissiveIntensity: 2.5 }), logm = mk('BBQ_Logs', 0x9a6a3c), blk = mk('BBQ_Black', 0x1d1c1b, { roughness: 0.45, metalness: 0.4 });
  const t0 = 1.40, t1 = 2.40;                                       // tower between u 1.40 and 2.40
  // sink run (u 0 → 1.40): clay base with louvred doors, dark worktop, sink + black tap, LED shelf, two wall lights
  box(0, t0, 0, D - 0.04, y, top - 0.04, clay);
  for (let k = 0; k < 9; k++) box(0, t0, D - 0.045, D - 0.035, y + 0.06 + k * 0.09, y + 0.065 + k * 0.09, mk('BBQ_TileJoint', 0xa98058), false);
  box(0.35, 1.05, D - 0.05, D + 0.005, y + 0.05, top - 0.12, blk);
  for (let k = 0; k < 12; k++) box(0.37, 1.03, D, D + 0.012, y + 0.09 + k * 0.055, y + 0.105 + k * 0.055, slate, false);
  box(0.699, 0.701, D + 0.005, D + 0.013, y + 0.05, top - 0.12, clay, false);
  box(-0.01, t0, 0, D + 0.03, top - 0.04, top, slate);
  box(0.55, 0.95, 0.15, 0.50, top - 0.035, top + 0.002, blk, false);
  cyl(0.75, 0.08, 0.014, top, top + 0.36, blk, 10); box(0.735, 0.765, 0.08, 0.26, top + 0.33, top + 0.36, blk);
  box(0, t0, 0, 0.18, y + 1.30, y + 1.34, slate); box(0.04, t0 - 0.04, 0.12, 0.16, y + 1.29, y + 1.30, M.led, false);
  { const sp = new THREE.SphereGeometry(0.09, 10, 8), [px, pz] = world(1.15, 0.20); sp.translate(px, top + 0.14, pz); addMesh(parent, sp, clothMat(0x5f7044), false, false); cyl(1.15, 0.20, 0.07, top, top + 0.10, blk, 12); }
  for (const u of [0.18, 1.22]) { box(u - 0.05, u + 0.05, D - 0.04, D + 0.06, y + 0.52, y + 0.68, blk); box(u - 0.035, u + 0.035, D + 0.06, D + 0.065, y + 0.50, y + 0.54, M.led, false); }
  // tower: taupe render, firewood store, firebox with firebrick + flames + grill, sloped hood, chimney with black louvred cap
  const P = 0.12, ob = D - 0.45, fr = D + 0.05;                     // hollow tower: pillars, back wall, base / shelf / lintel slabs
  box(t0, t0 + P, 0, fr, y, y + 1.55, taupe); box(t1 - P, t1, 0, fr, y, y + 1.55, taupe); box(t0 + P, t1 - P, 0, ob, y, y + 1.55, taupe);
  box(t0 + P, t1 - P, ob, fr, y, y + 0.12, taupe); box(t0 + P, t1 - P, ob, fr, y + 0.72, y + 0.88, taupe); box(t0 + P, t1 - P, ob, fr, y + 1.45, y + 1.55, taupe);
  box(t0 + P, t1 - P, ob - 0.01, ob, y + 0.12, y + 0.72, mk('BBQ_Store', 0x3a2a1e), false);
  for (let r = 0; r < 4; r++) for (let c = 0; c < 6; c++) { const [lx, lz] = world(t0 + 0.18 + c * 0.11, D - 0.20), g = new THREE.CylinderGeometry(0.05, 0.05, 0.38, 8); g.rotateX(Math.PI / 2); g.translate(lx, y + 0.17 + r * 0.10, lz); addMesh(parent, g, logm, false, false); }
  box(t0 + P, t1 - P, ob - 0.01, ob, y + 0.88, y + 1.45, brick, false); box(t0 + P, t1 - P, ob, fr, y + 0.88, y + 0.89, brick, false); box(t0 + P - 0.005, t0 + P, ob, fr, y + 0.88, y + 1.45, brick, false); box(t1 - P, t1 - P + 0.005, ob, fr, y + 0.88, y + 1.45, brick, false);
  box(t0 + 0.25, t1 - 0.25, D - 0.35, D - 0.15, y + 0.90, y + 1.05, fire, false);
  for (let k = 0; k < 9; k++) box(t0 + 0.14, t1 - 0.14, D - 0.40 + k * 0.045, D - 0.392 + k * 0.045, y + 1.08, y + 1.09, blk, false);
  box(t0 + 0.12, t1 - 0.12, D + 0.02, D + 0.05, y + 1.08, y + 1.10, blk, false);
  for (let k = 0; k < 5; k++) { const a = k / 5; box(t0 + 0.02 * k * 2.2, t1 - 0.02 * k * 2.2, 0, D + 0.05 - a * 0.30, y + 1.55 + k * 0.10, y + 1.65 + k * 0.10, taupe); }
  const ch = y + (f.chimney || 5.0);
  box(t0 + 0.22, t1 - 0.22, 0, D - 0.30, y + 2.05, ch, taupe);
  for (let k = 0; k < 4; k++) box(t0 + 0.18, t1 - 0.18, -0.04, D - 0.26, ch + k * 0.07, ch + k * 0.07 + 0.035, blk);
  // side worktop (u 2.40 → W)
  box(t1, W, 0, D - 0.04, y, top - 0.04, clay);
  for (let k = 0; k < 9; k++) box(t1, W, D - 0.045, D - 0.035, y + 0.06 + k * 0.09, y + 0.065 + k * 0.09, mk('BBQ_TileJoint', 0xa98058), false);
  box(t1, W + 0.01, 0, D + 0.03, top - 0.04, top, slate);
}
// ---------- 1.11: wardrobe items — shoes, high heels, ankle and tall boots, bathrobes, trousers (procedural, CC0 by construction) ----------
// Each item is built in a local frame (shoes: toe towards +z, garments: front towards +z, hanging from y = 0 downwards) and placed with
// placeWear(group, x, y, z, yaw). Used by the closets and shoe racks, and by the furniture names shoes, high heels, boots, robe, trousers.
const WEAR = (() => {
  const rb = (g, w, h, d, x, y, z, m, r = 0.02, rx = 0) => {
    const geo = new RoundedBoxGeometry(w, h, d, 2, Math.max(0.002, Math.min(r, w / 2 - 0.001, h / 2 - 0.001, d / 2 - 0.001)));
    if (rx) geo.rotateX(rx); geo.translate(x, y, z); const o = new THREE.Mesh(geo, m); o.castShadow = o.receiveShadow = true; g.add(o); return o;
  };
  const cy = (g, r0, r1, h, x, y, z, m, seg = 10) => { const geo = new THREE.CylinderGeometry(r1, r0, h, seg); geo.translate(x, y + h / 2, z); const o = new THREE.Mesh(geo, m); o.castShadow = true; g.add(o); return o; };
  const sole = clothMat(0x1a1918);
  // one shoe, toe at +z, sole on y = 0
  function shoe(kind, col) {
    const g = new THREE.Group(), m = clothMat(col);
    if (kind === 'heel') {                                                   // stiletto pump: toe pad, sloped arch, heel counter, 9 cm stiletto
      const hh = 0.09, a = Math.atan2(hh, 0.15);
      rb(g, 0.068, 0.012, 0.085, 0, 0.006, 0.075, sole, 0.005);
      rb(g, 0.06, 0.008, 0.16, 0, hh / 2 + 0.006, -0.035, sole, 0.003, -a);
      rb(g, 0.072, 0.045, 0.085, 0, 0.032, 0.075, m, 0.02);                  // vamp over the toes
      rb(g, 0.066, 0.05, 0.035, 0, hh + 0.03, -0.105, m, 0.012);             // heel counter
      for (const s of [-1, 1]) rb(g, 0.006, 0.03, 0.12, s * 0.032, hh / 2 + 0.03, -0.04, m, 0.002, -a);   // side walls
      cy(g, 0.004, 0.009, hh, 0, 0, -0.112, m, 8);                           // stiletto
    } else {
      rb(g, 0.098, 0.022, 0.27, 0, 0.011, 0, sole, 0.01);                    // sole
      rb(g, 0.09, 0.07, 0.24, 0, 0.055, -0.008, m, 0.03);                    // upper
      if (kind === 'ankle') { rb(g, 0.088, 0.15, 0.11, 0, 0.13, -0.075, m, 0.03); cy(g, 0.022, 0.022, 0.035, 0, 0, -0.1, sole, 10); }
      if (kind === 'boot') { rb(g, 0.1, 0.38, 0.12, 0, 0.25, -0.07, m, 0.035); rb(g, 0.104, 0.03, 0.125, 0, 0.43, -0.07, m, 0.012); cy(g, 0.022, 0.022, 0.035, 0, 0, -0.1, sole, 10); }
      if (kind === 'shoe') rb(g, 0.06, 0.004, 0.06, 0, 0.091, 0.02, clothMat(0xf3f1ec), 0.002);   // laces / tongue
    }
    return g;
  }
  function pair(kind, col) {
    const g = new THREE.Group(), w = kind === 'heel' ? 0.05 : 0.06;
    for (const s of [-1, 1]) { const one = shoe(kind, col); one.position.x = s * w; one.rotation.y = -s * 0.06; g.add(one); }
    return g;
  }
  // wire hanger, hook top at y = 0
  function hanger(g, w = 0.42) {
    const m = M.frame || clothMat(0x2b2d30);
    cy(g, 0.003, 0.003, 0.06, 0, -0.06, 0, m, 6);
    for (const s of [-1, 1]) { const geo = new THREE.CylinderGeometry(0.003, 0.003, Math.hypot(w / 2, 0.07), 6); geo.rotateZ(s * (Math.PI / 2 - Math.atan2(0.07, w / 2))); geo.translate(s * w / 4, -0.095, 0); g.add(new THREE.Mesh(geo, m)); }
    const bar = new THREE.CylinderGeometry(0.003, 0.003, w, 6); bar.rotateZ(Math.PI / 2); bar.translate(0, -0.13, 0); g.add(new THREE.Mesh(bar, m));
  }
  // bathrobe hanging from a hook or a hanger: flared body, shawl collar, sleeves, tied belt
  function robe(col, onHanger = false) {
    const g = new THREE.Group(), m = clothMat(col), top = onHanger ? -0.13 : -0.03, L = 1.12;
    if (onHanger) hanger(g, 0.44);
    const sh = new THREE.Shape([new THREE.Vector2(-0.22, 0), new THREE.Vector2(0.22, 0), new THREE.Vector2(0.31, -L), new THREE.Vector2(-0.31, -L)]);
    const body = new THREE.ExtrudeGeometry(sh, { depth: 0.07, bevelEnabled: true, bevelThickness: 0.03, bevelSize: 0.03, bevelSegments: 3 });
    body.translate(0, top, -0.035); const bm = new THREE.Mesh(body, m); bm.castShadow = bm.receiveShadow = true; g.add(bm);
    for (const s of [-1, 1]) { rb(g, 0.14, 0.58, 0.12, s * 0.27, top - 0.33, 0, m, 0.05); rb(g, 0.1, 0.36, 0.035, s * 0.07, top - 0.2, 0.07, m, 0.02); }   // sleeves, shawl collar
    rb(g, 0.6, 0.05, 0.13, 0, top - 0.52, 0.01, m, 0.02);                    // belt
    for (const s of [-1, 1]) rb(g, 0.045, 0.34, 0.02, s * 0.04, top - 0.72, 0.085, m, 0.01);   // belt ends
    if (!onHanger) { const hk = M.frame || clothMat(0x2b2d30); rb(g, 0.02, 0.06, 0.05, 0, -0.02, -0.06, hk, 0.006); }
    return g;
  }
  // trousers on a clip hanger: waistband, two tapered legs, crease shading
  function trousers(col) {
    const g = new THREE.Group(), m = clothMat(col), L = 1.0, top = -0.14;
    hanger(g, 0.38); rb(g, 0.4, 0.05, 0.035, 0, top - 0.025, 0, m, 0.012);
    for (const s of [-1, 1]) {
      const sh = new THREE.Shape([new THREE.Vector2(0, 0), new THREE.Vector2(s * 0.195, 0), new THREE.Vector2(s * 0.18, -L), new THREE.Vector2(s * 0.025, -L)]);
      const geo = new THREE.ExtrudeGeometry(sh, { depth: 0.022, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.006, bevelSegments: 2 });
      geo.translate(s * 0.004, top - 0.05, -0.011); const o = new THREE.Mesh(geo, m); o.castShadow = o.receiveShadow = true; g.add(o);
    }
    return g;
  }
  // shirt / jacket / coat on a hanger: shaped body (extruded outline), sleeves, collar or lapels; L = length below the shoulders
  function top(kind, col, L) {
    const g = new THREE.Group(), m = clothMat(col), jk = kind !== 'shirt', t = jk ? 0.045 : 0.016, sw = jk ? 0.24 : 0.215;
    hanger(g, jk ? 0.44 : 0.4);
    const sh = new THREE.Shape([new THREE.Vector2(-0.06, -0.125), new THREE.Vector2(0.06, -0.125), new THREE.Vector2(sw, -0.17), new THREE.Vector2(sw - 0.01, -0.17 - L), new THREE.Vector2(-sw + 0.01, -0.17 - L), new THREE.Vector2(-sw, -0.17)]);
    const body = new THREE.ExtrudeGeometry(sh, { depth: t, bevelEnabled: true, bevelThickness: jk ? 0.015 : 0.006, bevelSize: jk ? 0.012 : 0.006, bevelSegments: 2 });
    body.translate(0, 0, -t / 2); const bm = new THREE.Mesh(body, m); bm.castShadow = bm.receiveShadow = true; g.add(bm);
    const sl = Math.min(jk ? 0.62 : 0.58, L * 0.95);
    for (const s of [-1, 1]) rb(g, jk ? 0.1 : 0.075, sl, jk ? 0.07 : 0.035, s * (sw - 0.02), -0.17 - sl / 2, 0.005, m, jk ? 0.03 : 0.012);   // sleeves
    if (kind === 'shirt') {
      rb(g, 0.15, 0.035, 0.045, 0, -0.135, 0.01, m, 0.012);                                         // collar
      rb(g, 0.022, L - 0.02, 0.006, 0, -0.17 - L / 2, t / 2 + 0.008, clothMat(Math.max(0, col - 0x0a0a0a)), 0.002);   // button placket
    } else {
      for (const s of [-1, 1]) { const lp = rb(g, 0.075, 0.26, 0.012, s * 0.06, -0.27, t / 2 + 0.02, m, 0.004); lp.rotation.z = s * 0.32; }   // lapels
      for (const s of [-1, 1]) rb(g, 0.11, 0.018, 0.012, s * 0.12, -0.17 - L * 0.62, t / 2 + 0.018, m, 0.004);   // pocket flaps
      for (let b = 0; b < 2; b++) cy(g, 0.008, 0.008, 0.006, 0, -0.17 - L * (0.42 + b * 0.16), t / 2 + 0.018, clothMat(0x1a1918), 8).rotation.x = Math.PI / 2;
    }
    return g;
  }
  // jewellery tray: velvet tray with rings on cones, a watch, a necklace stand with two chains, pearl earrings (top surface at y = 0)
  function jewellery() {
    const g = new THREE.Group(), velvet = clothMat(0x2a2326);
    const gold = M.Jewel_Gold || (M.Jewel_Gold = Object.assign(new THREE.MeshStandardMaterial({ color: 0xd6b25e, metalness: 1, roughness: 0.22 }), { name: 'Jewel_Gold' }));
    const silver = M.Jewel_Silver || (M.Jewel_Silver = Object.assign(new THREE.MeshStandardMaterial({ color: 0xd9dadc, metalness: 1, roughness: 0.18 }), { name: 'Jewel_Silver' }));
    const pearl = M.Jewel_Pearl || (M.Jewel_Pearl = Object.assign(new THREE.MeshStandardMaterial({ color: 0xf6f1e8, roughness: 0.25 }), { name: 'Jewel_Pearl' }));
    rb(g, 0.3, 0.03, 0.18, 0, 0.015, 0, velvet, 0.008);
    for (let i = 0; i < 3; i++) { const x = -0.11 + i * 0.045, c = new THREE.ConeGeometry(0.012, 0.05, 12); c.translate(x, 0.055, -0.04); g.add(new THREE.Mesh(c, velvet));
      const r = new THREE.TorusGeometry(0.0105, 0.0022, 6, 18); r.rotateX(Math.PI / 2); r.translate(x, 0.05, -0.04); g.add(new THREE.Mesh(r, i === 1 ? silver : gold)); }
    const w = new THREE.TorusGeometry(0.03, 0.006, 8, 24); w.rotateX(Math.PI / 2); w.translate(-0.06, 0.036, 0.045); g.add(new THREE.Mesh(w, silver));     // watch
    const face = new THREE.CylinderGeometry(0.018, 0.018, 0.008, 20); face.translate(-0.06, 0.04, 0.045); g.add(new THREE.Mesh(face, clothMat(0x1c2a3a)));
    for (const x of [0.02, 0.045]) { const p = new THREE.SphereGeometry(0.006, 10, 8); p.translate(x, 0.036, 0.05); g.add(new THREE.Mesh(p, pearl)); }   // earrings
    rb(g, 0.012, 0.22, 0.012, 0.1, 0.14, -0.03, velvet, 0.004); rb(g, 0.13, 0.012, 0.012, 0.1, 0.25, -0.03, velvet, 0.004);   // necklace stand
    for (const [dx, rad, mm] of [[-0.03, 0.045, gold], [0.03, 0.06, silver]]) {
      const n_ = new THREE.TorusGeometry(rad, 0.0018, 6, 40, Math.PI); n_.rotateZ(Math.PI); n_.scale(0.55, 1.4, 1); n_.translate(0.1 + dx, 0.25, -0.022); g.add(new THREE.Mesh(n_, mm));
      const pd = new THREE.SphereGeometry(0.007, 10, 8); pd.translate(0.1 + dx, 0.25 - rad * 1.4, -0.022); g.add(new THREE.Mesh(pd, mm)); }
    g.traverse(o => { if (o.isMesh) o.castShadow = true; });
    return g;
  }
  return { shoe, pair, robe, trousers, top, jewellery };
})();
// merge a group of wardrobe items into one mesh per material (closets hold hundreds of small parts)
function bakeWear(bag, parent) {
  bag.updateMatrixWorld(true); const buckets = new Map();
  bag.traverse(o => { if (!o.isMesh) return; const g = (o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone()).applyMatrix4(o.matrixWorld);
    for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
    if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    (buckets.get(o.material) || buckets.set(o.material, []).get(o.material)).push(g); });
  for (const [m, list] of buckets) { const g = mergeGeometries(list, false); if (g) addMesh(parent, g, m, true, true); }
}
const SHOE_COLS = { shoe: [0x1d1c1b, 0x6b4a33, 0xf2efe8, 0x2b3442], heel: [0x8a1d2b, 0x1a1a1a, 0xd9b99b, 0xc9a24a], ankle: [0x3b2a20, 0x1e1d1c, 0x8a6a4f], boot: [0x1c1b1a, 0x5a3b28, 0x7d5f48] };
function placeWear(parent, obj, x, y, z, yaw = 0, s = 1) { obj.position.set(x, y, z); obj.rotation.y = yaw; obj.scale.setScalar(s); parent.add(obj); return obj; }
function frameYaw(G) { const [ax, az] = G.world(0, 0), [bx, bz] = G.world(0, 1); return Math.atan2(bx - ax, bz - az); }   // yaw turning +z towards the frame's front
function fClosetUnit(f, parent) {          // walk-in closet unit (light oak, LED strips): style 'hang' (drawers + rail + clothes), 'shelves' (lit shelves + folded stacks), 'drawers' (low chest)
  const side = f.back || backSide(f, false), G = fframe(f, side, parent), { W, D, box } = G, y = f.y0, H = f.h;
  const wood = M.oak_top || M.wood, front = M.stone_top || M.white, st = f.style || 'shelves';
  if (st === 'drawers') {
    box(0, W, 0, D, y, y + H, front); box(-0.01, W + 0.01, 0, D + 0.01, y + H, y + H + 0.03, wood);
    for (let k = 1; k < 3; k++) box(0.02, W - 0.02, D - 0.004, D + 0.003, y + H * k / 3 - 0.004, y + H * k / 3 + 0.004, M.dark, false);
    return;
  }
  box(0, W, 0, 0.02, y, y + H, wood); box(0, 0.02, 0, D, y, y + H, wood); box(W - 0.02, W, 0, D, y, y + H, wood);
  box(0, W, 0, D, y + H - 0.03, y + H, wood);
  const n = f.zones ? f.zones.length : Math.max(1, Math.round(W / 1.0)); for (let i = 1; i < n; i++) { const u = W * i / n; box(u - 0.01, u + 0.01, 0.02, D, y, y + H - 0.03, wood); }
  const zones = f.zones || Array(n).fill(st), mw = W / n;
  const bag = new THREE.Group(), across = frameYaw(G) + Math.PI / 2;
  const rail = (u0, u1, yr, len0, lenV, cols, wd, kind = wd > 0.055 ? 'coat' : wd > 0.04 ? 'jacket' : 'shirt') => {   // rail + garments on hangers
    box(u0 + 0.02, u1 - 0.02, D * 0.5 - 0.012, D * 0.5 + 0.012, yr - 0.025, yr, M.dark);
    let u = u0 + 0.05, k = 0;
    while (u < u1 - 0.07) {
      const w = wd + (k * 37 % 3) * 0.012, hg = len0 + (k * 53 % 4) * lenV, [gx, gz] = G.world(u + w / 2, D * 0.5);
      placeWear(bag, WEAR.top(kind === 'mixed' ? ['shirt', 'jacket'][k % 2] : kind === 'coat' ? 'jacket' : kind, cols[k % cols.length], Math.max(0.3, hg - 0.17)), gx, yr - 0.025, gz, across, Math.min(1, (D - 0.06) / 0.5));
      u += w + 0.016; k++;
    }
  };
  const topShelf = (u0, u1, ys) => { box(u0 + 0.02, u1 - 0.02, 0.02, D, ys, ys + 0.025, wood); box(u0 + 0.03, u1 - 0.03, D - 0.07, D - 0.04, ys - 0.012, ys - 0.002, M.led, false); };
  const COATS = [0x2b2f38, 0xa8875f, 0x1e1e1e, 0x5d5348, 0x7a7f86, 0x3d4a5c];   // long coats: navy, camel, black, brown, grey
  const SHIRTS = [0xf4f4f2, 0xc9d6e6, 0xe9e5dc, 0x9fb3c8, 0xffffff, 0xd8cfc0];  // shirts: white, light blue, ecru
  const JACKETS = [0x3c3c3c, 0x6b5a45, 0x2a3442, 0x8c8c8c, 0x4f5b3f];          // short jackets / blazers
  zones.forEach((z, i) => {
    const u0 = i * mw, u1 = (i + 1) * mw;
    if (z === 'long') {                    // big coats: one high rail, ~1.3 m drop, shoe shelf below
      topShelf(u0, u1, y + H - 0.36); rail(u0, u1 - (u1 - u0 > 0.9 ? 0.5 : 0), y + H - 0.42, 1.15, 0.07, COATS, 0.06);
      if (u1 - u0 > 0.9) { const [rx, rz] = G.world(u1 - 0.27, D * 0.5); placeWear(bag, WEAR.robe(0xf1eee8, true), rx, y + H - 0.42, rz, across); }   // bathrobe on a hanger, across the rail like the other garments
      box(u0 + 0.02, u1 - 0.02, 0.02, D, y + 0.18, y + 0.205, wood);
      { let k = 0; for (let u = u0 + 0.13; u + 0.1 < u1 - 0.04; u += 0.26, k++) {             // shoe shelf: tall boots, heels, ankle boots
        const kind = ['boot', 'heel', 'ankle', 'heel'][k % 4], [sx, sz] = G.world(u, D * 0.55);
        placeWear(bag, WEAR.pair(kind, SHOE_COLS[kind][k % SHOE_COLS[kind].length]), sx, y + 0.205, sz, frameYaw(G)); } }
    } else if (z === 'double') {           // two rails: shirts above, short coats / blazers below
      topShelf(u0, u1, y + H - 0.36); rail(u0, u1, y + H - 0.42, 0.72, 0.04, SHIRTS, 0.035);
      box(u0 + 0.02, u1 - 0.02, 0.02, D, y + 1.12, y + 1.145, wood);
      rail(u0, u0 + (u1 - u0) * 0.45, y + 1.08, 0.62, 0.05, JACKETS, 0.05);
      box(u0 + (u1 - u0) * 0.45, u1 - 0.02, D * 0.5 - 0.012, D * 0.5 + 0.012, y + 1.055, y + 1.08, M.dark);
      { const TR = [0x2a2f3a, 0xb7a68b, 0x1d1d1d, 0x6f7177, 0xe6dfd2], yaw = frameYaw(G) + Math.PI / 2; let k = 0;
        for (let u = u0 + (u1 - u0) * 0.45 + 0.05; u < u1 - 0.05; u += 0.06, k++) { const [tx, tz] = G.world(u, D * 0.5); placeWear(bag, WEAR.trousers(TR[k % TR.length]), tx, y + 1.055, tz, yaw, 0.92); } }
    } else if (z === 'hang') {             // drawers + rail
      box(u0 + 0.02, u1 - 0.02, 0.02, D, y, y + 0.85, front); box(u0 + 0.02, u1 - 0.02, 0.02, D + 0.01, y + 0.85, y + 0.88, wood);
      for (const hh of [0.29, 0.57]) box(u0 + 0.03, u1 - 0.03, D - 0.004, D + 0.003, y + hh - 0.004, y + hh + 0.004, M.dark, false);
      topShelf(u0, u1, y + H - 0.40); rail(u0, u1, y + H - 0.45, 0.62, 0.07, [0x3c3c3c, 0xe9e5dc, 0x8c8c8c, 0x1e1e1e, 0xc9b79c], 0.035);
    } else {                               // lit shelves with folded stacks
      const cols = [0xe9e5dc, 0x2a2a2a, 0xb8aa96, 0x8c8c8c, 0xf4f4f2]; let k = 0;
      for (let s2 = 0.36; s2 < H - 0.12; s2 += 0.36) {
        topShelf(u0, u1, y + s2);
        for (let u = u0 + 0.08; u + 0.3 < u1 - 0.04; u += 0.38, k++) { const hh = 0.08 + (k % 3) * 0.05; box(u, u + 0.3, 0.08, D - 0.08, y + s2 + 0.025, y + s2 + 0.025 + hh, clothMat(cols[k % cols.length]), false); }
      }
    }
  });
  bakeWear(bag, parent);
}
function fHallEntry(f, parent) {        // entrance feature wall (B5): oak slat panel + round oak mirror, sconces, floating fluted console with LED, pebble planter, olive tree, pendant
  const G = fframe(f, f.back || 'e', parent), { W, box, cyl, world } = G, y = f.y0, H = f.h, oak = M.oak_top || M.wood;
  const sph = (u, v, yy, r, m) => { const [x, z] = world(u, v), g = new THREE.SphereGeometry(r, 10, 8); g.translate(x, yy, z); addMesh(parent, g, m, true, false); };
  const leaf = clothMat(0x6d7a45), leaf2 = clothMat(0x8a9a5b), pc = W / 2;
  box(pc - 0.55, pc + 0.55, 0, 0.012, y, y + H, oak);                                   // slat panel
  for (let u = pc - 0.53; u < pc + 0.53; u += 0.05) box(u, u + 0.028, 0.012, 0.04, y, y + H - 0.01, oak);
  const mc = y + 1.62, r = 0.45, [mx, mz] = world(pc, 0.055);                           // round mirror with oak frame
  if (!M.mirror) { M.mirror = new THREE.MeshStandardMaterial({ color: 0xdfe6ea, metalness: 1.0, roughness: 0.04 }); M.mirror.name = 'Mirror'; }
  const ax = f.back === 'n' || f.back === 's';
  let g = new THREE.CylinderGeometry(r, r, 0.02, 48); if (ax) g.rotateX(Math.PI / 2); else g.rotateZ(Math.PI / 2); g.translate(mx, mc, mz); addMesh(parent, g, M.mirror, false, false);
  g = new THREE.TorusGeometry(r, 0.022, 10, 56); if (!ax) g.rotateY(Math.PI / 2); g.translate(mx, mc, mz); addMesh(parent, g, oak, false, false);
  for (const su of [pc - 0.68, pc + 0.68]) { box(su - 0.025, su + 0.025, 0.04, 0.09, y + 1.30, y + 1.78, M.led, false); box(su - 0.03, su + 0.03, 0.04, 0.10, y + 1.27, y + 1.30, oak); box(su - 0.03, su + 0.03, 0.04, 0.10, y + 1.78, y + 1.81, oak); }
  const c0 = pc - 1.05, c1 = pc + 1.05;                                                 // floating console, fluted front, LED underneath
  box(c0, c1, 0.04, 0.40, y + 0.62, y + 0.86, oak);
  for (let u = c0 + 0.02; u < c1 - 0.02; u += 0.035) box(u, u + 0.012, 0.40, 0.408, y + 0.635, y + 0.845, M.wood, false);
  box(c0 + 0.03, c1 - 0.03, 0.30, 0.34, y + 0.61, y + 0.62, M.led, false);
  cyl(c0 + 0.30, 0.22, 0.09, y + 0.86, y + 1.16, M.white, 20, 0.05);                  // vase + branches
  for (let k = 0; k < 7; k++) sph(c0 + 0.30 + Math.sin(k * 2.1) * 0.14, 0.22 + Math.cos(k * 1.7) * 0.08, y + 1.22 + (k % 3) * 0.1, 0.07, k % 2 ? leaf : leaf2);
  cyl(c0 + 0.62, 0.22, 0.10, y + 0.86, y + 0.91, oak, 20);                             // bowl
  box(c1 - 0.55, c1 - 0.30, 0.10, 0.30, y + 0.86, y + 0.92, M.white); cyl(c1 - 0.18, 0.22, 0.08, y + 0.86, y + 1.04, clothMat(0xb9a58a), 18, 0.06);
  box(c0 + 0.08, c1 - 0.08, 0.04, 0.34, y, y + 0.14, oak);                             // planter with pebbles and succulents
  for (let k = 0, u = c0 + 0.14; u < c1 - 0.12; u += 0.07, k++) sph(u, 0.12 + (k % 3) * 0.08, y + 0.15, 0.035, k % 3 ? M.white : clothMat(0xc8c1b5));
  for (let u = c0 + 0.30; u < c1 - 0.2; u += 0.36) for (let a = 0; a < 6; a++) { const [x, z] = world(u + Math.cos(a) * 0.05, 0.19 + Math.sin(a) * 0.05), cg = new THREE.ConeGeometry(0.025, 0.24, 6); cg.translate(x, y + 0.27, z); addMesh(parent, cg, leaf2, false, false); }
  const ou = W + 0.42, ov = 0.30;                                                       // oak coat stand with two coats (replaces the olive tree)
  cyl(ou, ov, 0.20, y, y + 0.025, oak, 28); cyl(ou, ov, 0.018, y + 0.025, y + 1.78, oak, 10); sph(ou, ov, y + 1.80, 0.03, oak);
  for (let k = 0; k < 4; k++) { const a = k * Math.PI / 2 + 0.4, [hx, hz] = world(ou + Math.cos(a) * 0.09, ov + Math.sin(a) * 0.09), hg = new THREE.CylinderGeometry(0.008, 0.008, 0.16, 6); hg.rotateZ(Math.cos(a) * 0.9); hg.rotateX(-Math.sin(a) * 0.9); hg.translate(hx, y + 1.66, hz); addMesh(parent, hg, oak, false, false); }
  box(ou - 0.24, ou - 0.03, ov - 0.13, ov + 0.13, y + 0.62, y + 1.66, clothMat(0xa8875f));   // long camel coat
  box(ou - 0.26, ou - 0.04, ov - 0.12, ov + 0.12, y + 1.40, y + 1.60, clothMat(0xa8875f));   // shoulders
  box(ou + 0.03, ou + 0.22, ov - 0.12, ov + 0.12, y + 0.95, y + 1.66, clothMat(0x2b2f38));   // short navy coat
  cyl(c0 + 0.40, 0.75, 0.004, y + 2.05, y + H, M.dark, 6);                              // pendant over the console
  cyl(c0 + 0.40, 0.75, 0.13, y + 1.88, y + 2.05, clothMat(0xefe8dc), 24, 0.03); cyl(c0 + 0.40, 0.75, 0.10, y + 1.875, y + 1.885, M.led, 24);
}
function fLaundry(f, parent) {          // laundry run (B5, after the reference photo): light oak, open shelves with woven baskets, sink, washer + dryer side by side, tall cabinet
  const G = fframe(f, f.back || 'w', parent), { W, D, box, cyl, world } = G, y = f.y0, oak = M.oak_top || M.wood, top = y + 0.90;
  const bask = clothMat(0xb08a5a), towel = clothMat(0xf1ede4), conc = M.stone_top || M.white;
  const basket = (u0, u1, ya, h) => box(u0 + 0.04, u1 - 0.04, 0.06, D - 0.06, ya, ya + h, bask);
  // tall cabinet next to the window (south end)
  const tc = W - 0.60; box(tc, W, 0, D, y, y + 2.40, oak); for (const yy of [0.80, 1.60]) box(tc + 0.02, W - 0.02, D - 0.002, D + 0.004, y + yy - 0.004, y + yy, M.dark, false);
  box(tc + 0.04, tc + 0.06, D, D + 0.03, y + 1.05, y + 1.45, M.dark, false);
  // worktop (light concrete/stone) over the rest
  box(0, tc, 0, D + 0.02, top - 0.04, top, conc);
  // washer + dryer side by side
  const m0 = tc - 1.22;
  for (let i = 0; i < 2; i++) { const u0 = m0 + 0.01 + i * 0.61; box(u0, u0 + 0.59, 0.02, D - 0.02, y, top - 0.05, M.white);
    const [cx, cz] = world(u0 + 0.295, D - 0.01), g = new THREE.CylinderGeometry(0.19, 0.19, 0.03, 32); g.rotateZ(Math.PI / 2); g.translate(cx + 0.01, y + 0.45, cz); addMesh(parent, g, M.dark, false, false);
    const g2 = new THREE.CylinderGeometry(0.15, 0.15, 0.035, 32); g2.rotateZ(Math.PI / 2); g2.translate(cx + 0.012, y + 0.45, cz); addMesh(parent, g2, M.glass, false, false); }
  // sink unit: 2 drawers + open shelf with 2 baskets ; open basket shelves at the north end
  const s0 = 0.58, s1 = m0;
  box(s0, s1, 0, 0.03, y, top - 0.04, oak); box(s0, s0 + 0.02, 0, D, y, top - 0.04, oak); box(s1 - 0.02, s1, 0, D, y, top - 0.04, oak);
  box(s0 + 0.02, s1 - 0.02, 0.03, D, top - 0.26, top - 0.04, oak); box((s0 + s1) / 2 - 0.004, (s0 + s1) / 2 + 0.004, D - 0.002, D + 0.004, top - 0.26, top - 0.04, M.dark, false);
  for (const uu of [s0 + (s1 - s0) * 0.25, s0 + (s1 - s0) * 0.75]) box(uu - 0.08, uu + 0.08, D + 0.004, D + 0.02, top - 0.16, top - 0.145, M.dark, false);
  box(s0 + 0.02, s1 - 0.02, 0.03, D, y + 0.30, y + 0.33, oak);
  for (const [a, b] of [[s0, (s0 + s1) / 2], [(s0 + s1) / 2, s1]]) { basket(a, b, y + 0.02, 0.26); basket(a, b, y + 0.33, 0.26); }
  box(0, 0.02, 0, D, y, top - 0.04, oak); box(0.02, s0, 0, 0.03, y, top - 0.04, oak); box(0.02, s0, 0.03, D, y + 0.42, y + 0.45, oak); basket(0, s0, y + 0.02, 0.36); basket(0, s0, y + 0.45, 0.36);
  const su = (s0 + s1) / 2; box(su - 0.30, su + 0.30, 0.10, D - 0.10, top - 0.035, top + 0.001, M.white, false);           // sink + brass tap
  if (!M.brass) { M.brass = new THREE.MeshStandardMaterial({ color: 0xb08d57, metalness: 0.9, roughness: 0.3 }); M.brass.name = 'Brass'; }
  cyl(su, 0.06, 0.015, top, top + 0.32, M.brass, 10); box(su - 0.01, su + 0.01, 0.06, 0.22, top + 0.30, top + 0.33, M.brass);
  // concrete splashback, open oak shelves with baskets / towels, closed cabinets on top
  box(0, tc, 0, 0.012, top, y + 1.50, conc);
  for (const ys of [1.50, 1.92]) box(0, tc, 0, 0.36, y + ys, y + ys + 0.035, oak);
  for (let u = 0.15, k = 0; u + 0.34 < tc - 0.05; u += 0.50, k++) {
    if (k % 2) box(u, u + 0.32, 0.03, 0.30, y + 1.535, y + 1.535 + 0.06 * 4, towel); else box(u, u + 0.34, 0.03, 0.32, y + 1.535, y + 1.535 + 0.28, bask);
    if (k % 2) box(u, u + 0.34, 0.03, 0.32, y + 1.955, y + 1.955 + 0.26, bask); else box(u, u + 0.32, 0.03, 0.30, y + 1.955, y + 1.955 + 0.20, towel);
  }
  box(0, tc, 0, 0.38, y + 2.25, y + 2.60, oak); for (let u = 0.6; u < tc; u += 0.6) box(u - 0.004, u + 0.004, 0.38, 0.384, y + 2.27, y + 2.58, M.dark, false);
}
function fMainBath(f, parent) {          // main bathroom after the reference photo (B5): world coords from the room box
  const [x0, z0, x1, z1] = f.b, y = f.y0, oak = M.oak_top || M.wood, B = (a, b, c, d, e, g, m, cs = true) => addMesh(parent, mbox(a, b, e, g, c, d), m, cs, true);
  const mk = (n, c, o = {}) => M[n] || (M[n] = Object.assign(new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.6 }, o)), { name: n }));
  const tile = mk('Bath_Tile_Greige', 0xb9b0a4), rib = mk('Bath_Tile_Ribbed', 0xc2b9ad, { roughness: 0.8 }), blk = mk('Matte_Black', 0x1d1c1b, { roughness: 0.45, metalness: 0.4 }), stoneT = mk('Bath_Top_Stone', 0xcfc8bd, { roughness: 0.4 });
  if (!M.mirror) { M.mirror = new THREE.MeshStandardMaterial({ color: 0xdfe6ea, metalness: 1, roughness: 0.04 }); M.mirror.name = 'Mirror'; }
  // greige tile cladding on the walls (thin layer)
  B(x0, x0 + 0.01, z0, z1, y, y + 2.60, tile, false); B(x1 - 0.01, x1, z0, z1, y, y + 2.60, tile, false); if (f.window) { const [wx0, wx1] = f.window, ws = y + (f.window_sill ?? 1.5), wh = y + (f.window_head ?? 2.2);      // ribbed tiles around a window in the z0 wall (f.window = [x from, x to]), left open
    B(x0, x1, z0, z0 + 0.01, y, ws, rib, false); B(x0, x1, z0, z0 + 0.01, wh, y + 2.60, rib, false);
    B(x0, wx0, z0, z0 + 0.01, ws, wh, rib, false); B(wx1, x1, z0, z0 + 0.01, ws, wh, rib, false); }
  // walk-in shower at the north end: flush tray, fixed glass panel with black profile, rain head + hand shower, lit niche
  const sz = z0 + 1.00, gx0 = x0 + 0.80;   // B5: shower 1,00 m deep (WC moved between it and the basin)
  B(x0 + 0.01, x1 - 0.01, z0 + 0.01, sz, y, y + 0.012, mk('Bath_Tray', 0xd2cbc0), false);
  const gA = x0 + 0.01, gB = x1 - 0.80;                    // B5: fixed glass against the WEST wall, entry on the east side
  B(gA, gB, sz - 0.005, sz + 0.005, y + 0.02, y + 2.05, M.glass, false);
  for (const [a, b, c, d] of [[gB - 0.02, gB, y, y + 2.05], [x0, gB, y + 2.03, y + 2.05], [x0, gB, y, y + 0.02]]) B(a, b, sz - 0.01, sz + 0.01, c, d, blk, false);
  const shz = z0 + 0.50, sx = x0 + 0.32;                    // B5: rain head on an arm from the WEST wall, hand shower + mixer on that wall
  B(x0 + 0.01, sx, shz - 0.01, shz + 0.01, y + 2.15, y + 2.17, blk); { const g = new THREE.CylinderGeometry(0.13, 0.13, 0.012, 28); g.translate(sx, y + 2.13, shz); addMesh(parent, g, blk, false, false); }
  B(x0 + 0.01, x0 + 0.04, shz + 0.13, shz + 0.15, y + 0.95, y + 1.45, blk); B(x0 + 0.01, x0 + 0.06, shz + 0.11, shz + 0.17, y + 1.05, y + 1.12, blk);
  { const r = new THREE.CylinderGeometry(0.02, 0.02, 0.01, 12); r.translate(sx + 0.15, y + 0.013, z0 + 0.50); addMesh(parent, r, blk, false, false); }
  // wall-hung WC on the east wall, black flush plate, paper holder
  const wz = sz + 0.42;                                     // B5: wall-hung WC on the WEST wall, between the shower and the basin
  B(x0 + 0.002, x0 + 0.012, wz - 0.12, wz + 0.12, y + 0.95, y + 1.10, blk, false);
  { const g = new THREE.CylinderGeometry(0.18, 0.16, 0.30, 28); g.scale(1.45, 1, 1); g.translate(x0 + 0.27, y + 0.27, wz); addMesh(parent, g, M.white, true, false);
    const l = new THREE.CylinderGeometry(0.185, 0.185, 0.04, 28); l.scale(1.45, 1, 1); l.translate(x0 + 0.27, y + 0.44, wz); addMesh(parent, l, M.white, true, false); }
  B(x0 + 0.01, x0 + 0.12, wz + 0.26, wz + 0.36, y + 0.70, y + 0.80, M.white, false);
  // floating oak vanity on the west wall with stone top, LED underneath, integrated basin, black tap, black-framed mirror + two sconces
  const vz0 = sz + 0.85, vz1 = Math.min(z1 - 0.25, vz0 + 1.30), vx = x0 + 0.50, vc = (vz0 + vz1) / 2;
  B(x0, vx, vz0, vz1, y + 0.40, y + 0.82, oak); B(vx - 0.002, vx + 0.004, vz0 + 0.01, vz1 - 0.01, y + 0.605, y + 0.615, M.dark, false);
  B(x0, vx + 0.03, vz0 - 0.02, vz1 + 0.02, y + 0.82, y + 0.86, stoneT); B(x0 + 0.10, vx - 0.06, vc - 0.28, vc + 0.28, y + 0.85, y + 0.861, M.white, false);
  B(x0 + 0.02, vx - 0.03, vz0 + 0.05, vz1 - 0.05, y + 0.39, y + 0.40, M.led, false);
  B(x0 + 0.01, x0 + 0.12, vc - 0.02, vc + 0.02, y + 0.86, y + 1.10, blk); B(x0 + 0.08, x0 + 0.20, vc - 0.015, vc + 0.015, y + 1.07, y + 1.10, blk);
  B(x0 + 0.01, x0 + 0.04, vc - 0.40, vc + 0.40, y + 1.15, y + 2.05, blk); B(x0 + 0.04, x0 + 0.045, vc - 0.38, vc + 0.38, y + 1.17, y + 2.03, M.mirror, false);
  for (const zz of [vc - 0.48, vc + 0.48]) { B(x0 + 0.01, x0 + 0.08, zz - 0.035, zz + 0.035, y + 1.40, y + 1.85, M.led, false); B(x0 + 0.01, x0 + 0.09, zz - 0.04, zz + 0.04, y + 1.58, y + 1.66, blk); }
  { const g = new THREE.CylinderGeometry(0.06, 0.07, 0.16, 14); g.translate(x0 + 0.35, y + 0.94, vz0 + 0.12); addMesh(parent, g, M.white, false, false);
    const sp = new THREE.SphereGeometry(0.09, 10, 8); sp.translate(x0 + 0.35, y + 1.08, vz0 + 0.12); addMesh(parent, sp, clothMat(0x6d7a45), false, false); }
  B(x0 + 0.01, x0 + 0.06, vz1 - 0.02, vz1 + 0.02, y + 0.20, y + 0.80, clothMat(0x9a958e));
  // small wooden stool + towel on the east wall near the door, textured rug
  B(x1 - 0.06, x1 - 0.01, z1 - 1.10, z1 - 0.75, y + 0.85, y + 1.55, clothMat(0x6f6a64));
  B(vx + 0.15, vx + 0.75, vc - 0.45, vc + 0.45, y + 0.005, y + 0.02, mk('Bath_Rug', 0xa79f95, { roughness: 1 }), false);
  // recessed downlights
  for (const [px, pz] of [[(x0 + x1) / 2, z0 + 0.55], [(x0 + x1) / 2, vc], [(x0 + x1) / 2, z1 - 0.35]]) { const d = new THREE.CylinderGeometry(0.035, 0.035, 0.01, 14); d.translate(px, y + 2.595, pz); addMesh(parent, d, M.led, false, false); }
}
function fOfficeChair(f, parent) {     // B5: comfortable ergonomic office chair (mesh back, headrest, armrests, 5-star base)
  const [x0, z0, x1, z1] = f.b, y = f.y0, cx = (x0 + x1) / 2, cz = (z0 + z1) / 2, face = f.face || 'e', dx = { e: 1, w: -1 }[face] || 0, dz = { s: 1, n: -1 }[face] || 0;
  const blk = M.Matte_Black || M.dark, mesh = clothMat(0x2f3134), B = (a, b, c, d, e, g, m) => addMesh(parent, mbox(a, b, e, g, c, d), m, true, false);
  for (let k = 0; k < 5; k++) { const a = k * 2 * Math.PI / 5, g = new THREE.BoxGeometry(0.30, 0.03, 0.04); g.translate(0.15, 0, 0); g.rotateY(a); g.translate(cx, y + 0.08, cz); addMesh(parent, g, blk, true, false);
    const w = new THREE.SphereGeometry(0.03, 8, 6); w.translate(cx + Math.cos(a) * 0.29, y + 0.03, cz - Math.sin(a) * 0.29); addMesh(parent, w, blk, false, false); }
  { const p = new THREE.CylinderGeometry(0.025, 0.025, 0.36, 10); p.translate(cx, y + 0.27, cz); addMesh(parent, p, blk, true, false); }
  B(cx - 0.25, cx + 0.25, cz - 0.24, cz + 0.24, y + 0.44, y + 0.52, mesh);                        // seat
  const bx = cx - dx * 0.24, bz = cz - dz * 0.24, hw = 0.23;                                       // back opposite the facing side
  if (dx) { B(bx - 0.04, bx + 0.02 * -dx + 0.0, cz - hw, cz + hw, y + 0.55, y + 1.05, mesh); B(bx - 0.04, bx, cz - 0.13, cz + 0.13, y + 1.08, y + 1.20, mesh);
    for (const s_ of [-1, 1]) B(cx - 0.12, cx + 0.12, cz + s_ * 0.25 - 0.025, cz + s_ * 0.25 + 0.025, y + 0.66, y + 0.69, blk); }
  else { B(cx - hw, cx + hw, bz - 0.04, bz, y + 0.55, y + 1.05, mesh); B(cx - 0.13, cx + 0.13, bz - 0.04, bz, y + 1.08, y + 1.20, mesh);
    for (const s_ of [-1, 1]) B(cx + s_ * 0.25 - 0.025, cx + s_ * 0.25 + 0.025, cz - 0.12, cz + 0.12, y + 0.66, y + 0.69, blk); }
}
function fOfficeDesk(f, parent) {      // B5: one large desk, dark grey top, 2 laptops each wired to a 4K monitor, printer at one end
  const G = fframe(f, f.back || 'e', parent), { W, D, box, cyl } = G, y = f.y0, top = y + f.h;
  const mk = (n, c, o = {}) => M[n] || (M[n] = Object.assign(new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.5 }, o)), { name: n }));
  const grey = mk('Desk_Top_DarkGrey', 0x3a3c3f, { roughness: 0.45 }), alu = mk('Laptop_Alu', 0xb9bcc0, { metalness: 0.7, roughness: 0.3 }),
        scr = mk('Screen_On', 0x1d2733, { emissive: 0x4d6f96, emissiveIntensity: 0.55, roughness: 0.2 }), blk = mk('Matte_Black', 0x1d1c1b, { roughness: 0.45, metalness: 0.4 });
  box(0, W, 0, D, top - 0.035, top, grey);
  for (const u of [0.03, W - 0.07]) box(u, u + 0.04, 0.05, D - 0.05, y, top - 0.035, blk);           // slim black legs
  box(0.03, W - 0.03, 0.05, 0.09, y + 0.05, y + 0.09, blk);
  const ws = [0.55, 1.55];
  for (const c of ws) {
    box(c - 0.08, c + 0.08, 0.08, 0.24, top, top + 0.012, blk); box(c - 0.02, c + 0.02, 0.12, 0.16, top, top + 0.38, blk);   // monitor stand
    box(c - 0.36, c + 0.36, 0.14, 0.17, top + 0.12, top + 0.53, blk); box(c - 0.345, c + 0.345, 0.17, 0.172, top + 0.135, top + 0.515, scr, false);  // 32" 4K
    const lu = c + 0.47;                                                                           // laptop to the right of its monitor, lid open
    box(lu - 0.16, lu + 0.16, 0.30, 0.52, top, top + 0.015, alu);
    box(lu - 0.16, lu + 0.16, 0.27, 0.285, top + 0.015, top + 0.225, alu); box(lu - 0.15, lu + 0.15, 0.285, 0.287, top + 0.025, top + 0.215, scr, false);
    box(c - 0.22, c + 0.22, 0.42, 0.56, top, top + 0.012, mk('Keyboard', 0x2b2b2d)); box(c + 0.27, c + 0.33, 0.45, 0.55, top, top + 0.02, mk('Keyboard', 0x2b2b2d));
    box(lu - 0.005, c, 0.20, 0.205, top, top + 0.004, blk, false);                                 // cable laptop → monitor
  }
  const pu = W - 0.22; box(pu - 0.20, pu + 0.20, 0.06, 0.46, top, top + 0.24, mk('Printer', 0xe6e6e3, { roughness: 0.6 })); box(pu - 0.15, pu + 0.15, 0.30, 0.47, top + 0.24, top + 0.25, blk);
}
function fPantry(f, parent) {          // B5: pantry wall — pull-out drawers below (closed oak fronts + wire baskets), shelves with uneven dividers and goods above
  const G = fframe(f, f.back || 'w', parent), { W, D, box, cyl } = G, y = f.y0, H = f.h, oak = M.oak_top || M.wood;
  const mk = (n, c, o = {}) => M[n] || (M[n] = Object.assign(new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.6 }, o)), { name: n }));
  const wire = mk('Wire_Chrome', 0x9aa0a6, { metalness: 0.85, roughness: 0.3 }), blk = M.dark;
  box(0, W, 0, 0.015, y, y + H, oak); box(0, 0.02, 0, D, y, y + H, oak); box(W - 0.02, W, 0, D, y, y + H, oak);
  // lower part: 3 columns × 2 pull-out drawers
  const V2 = f.v === 2, cols = V2 ? 2 : 3, cw = (W - 0.04) / cols, kinds = V2 ? [['m', 'c'], ['c', 'm']] : [['c', 'c'], ['m', 'm'], ['c', 'm']], LH = 0.74;
  box(0, W, 0, D, y + LH, y + LH + 0.03, oak);
  for (let i = 1; i < cols; i++) box(0.02 + i * cw - 0.01, 0.02 + i * cw + 0.01, 0.015, D, y, y + LH, oak);
  for (let i = 0; i < cols; i++) for (let j = 0; j < 2; j++) {
    const u0 = 0.02 + i * cw + 0.015, u1 = 0.02 + (i + 1) * cw - 0.015, y0 = y + 0.04 + j * 0.35, y1 = y0 + 0.32;
    if (kinds[i][j] === 'c') { box(u0, u1, D - 0.02, D, y0, y1, oak); box((u0 + u1) / 2 - 0.08, (u0 + u1) / 2 + 0.08, D, D + 0.02, y1 - 0.06, y1 - 0.045, blk); }
    else {                                                                          // wire basket: front rails + vertical wires, goods visible inside
      for (const yy of [y0, y0 + 0.15, y1 - 0.01]) box(u0, u1, D - 0.015, D, yy, yy + 0.01, wire);
      for (let u = u0; u <= u1 + 1e-6; u += 0.035) box(u - 0.003, u + 0.003, D - 0.012, D - 0.006, y0, y1, wire, false);
      box(u0, u1, 0.05, D - 0.02, y0, y0 + 0.008, wire, false);
      const goods = j ? [0xc9a36b, 0xe7d9b4, 0x8a5a2b] : [0xd9a441, 0x9b2f22, 0xe8e0c8];   // potatoes / onions / bread-like
      for (let k = 0; k < 6; k++) { const g = new THREE.SphereGeometry(0.045, 8, 6), [gx, gz] = G.world(u0 + 0.05 + (k % 3) * (u1 - u0 - 0.1) / 2, 0.12 + Math.floor(k / 3) * 0.14); g.translate(gx, y0 + 0.055, gz); addMesh(parent, g, clothMat(goods[k % 3]), false, false); }
    }
  }
  // upper part: shelves with dividers in different places (compartments of different sizes)
  const lv = V2 ? [LH + 0.03, 1.05, 1.38, 1.62, 1.95, H - 0.03] : [LH + 0.03, 1.10, 1.48, 1.80, 2.12, H - 0.03], dv = V2 ? [[0.55], [0.30, 0.95], [0.80], [0.40, 0.70, 1.05], []] : [[0.45, 1.05], [0.70], [0.35, 0.80, 1.15], [0.60, 1.00], [0.75]];
  for (const l of lv.slice(1)) box(0.02, W - 0.02, 0.015, D - 0.02, y + l, y + l + 0.025, oak);
  dv.forEach((us, i) => { for (const u of us) box(u - 0.01, u + 0.01, 0.015, D - 0.02, y + lv[i] + 0.025, y + lv[i + 1], oak); });
  const jar = (u, v, yb, h, r, c) => { cyl(u, v, r, yb, yb + h, M.glass, 16); cyl(u, v, r * 0.92, yb + 0.005, yb + h * 0.75, clothMat(c), 14); cyl(u, v, r * 0.9, yb + h, yb + h + 0.02, oak, 14); };
  const can = (u, v, yb, c) => cyl(u, v, 0.037, yb, yb + 0.11, mk('Can_' + c.toString(16), c, { metalness: 0.5, roughness: 0.4 }), 14);
  const boxI = (u, v, yb, w, h, c) => box(u, u + w, v, v + 0.20, yb, yb + h, clothMat(c));
  const bottle = (u, v, yb, c) => { cyl(u, v, 0.035, yb, yb + 0.22, mk('Bottle_' + c.toString(16), c, { roughness: 0.15, transparent: true, opacity: 0.85 }), 12); cyl(u, v, 0.012, yb + 0.22, yb + 0.30, blk, 8); };
  const b0 = y + lv[0] + 0.03, b1 = y + lv[1] + 0.025, b2 = y + lv[2] + 0.025, b3 = y + lv[3] + 0.025, b4 = y + lv[4] + 0.025, v = D * 0.5;
  if (V2) {                                                                        // second wall: other goods
    for (let k = 0; k < 4; k++) bottle(0.08 + k * 0.10, v, b0, [0x2a4d1f, 0x7a1424, 0xd8c27a, 0x3a2416][k]);   // oil, wine, vinegar, soy
    boxI(0.62, 0.06, b0, 0.30, 0.20, 0x6b8e4e); boxI(0.95, 0.06, b0, 0.33, 0.14, 0xefe3c8);                    // tea crates, flour
    for (let k = 0; k < 3; k++) jar(0.06 + k * 0.08, v, b1, 0.14, 0.03, [0xd04a2a, 0xe8b83a, 0x7b4a2a][k]);   // spices
    boxI(0.34, 0.06, b1, 0.55, 0.20, 0xb8c9a6); for (let k = 0; k < 4; k++) can(1.00 + k * 0.08, v, b1, [0x2e7d4f, 0xe0c23a, 0xb22d2d, 0x3b6ea5][k]);
    for (let k = 0; k < 6; k++) jar(0.06 + k * 0.12, v, b2, 0.16, 0.045, [0xf3efe3, 0xdcc48a, 0x8a5a2b, 0xf0d9a0, 0x5c3b1e, 0xe4dccb][k]);
    boxI(0.84, 0.06, b2, 0.45, 0.18, 0xd9cbb4);
    boxI(0.04, 0.05, b3, 0.33, 0.22, 0x5d6b78); boxI(0.44, 0.05, b3, 0.24, 0.24, 0xe6dcc9); boxI(0.74, 0.05, b3, 0.28, 0.20, 0xc9b28d); boxI(1.08, 0.05, b3, 0.22, 0.22, 0x9fb6c6);
    boxI(0.06, 0.05, b4, 1.20, 0.25, 0xd9cbb4);
    return;
  }
  for (let k = 0; k < 5; k++) jar(0.09 + k * 0.075, v, b0, 0.18, 0.032, [0xe8d6a8, 0x8b5a2b, 0xf3efe3, 0xc8913a, 0x5b3b22][k]);   // pasta, coffee, rice, lentils…
  boxI(0.50, 0.08, b0, 0.20, 0.26, 0xd8432e); boxI(0.73, 0.08, b0, 0.16, 0.22, 0xf2c14e); boxI(0.92, 0.08, b0, 0.10, 0.24, 0x3b6ea5);
  for (let k = 0; k < 3; k++) bottle(1.13 + k * 0.10, v, b0, [0x5f7d2a, 0x8a1c2b, 0xcaa64a][k]);
  for (let k = 0; k < 7; k++) can(0.08 + (k % 4) * 0.085, 0.12 + Math.floor(k / 4) * 0.12, b1, [0xb22d2d, 0xe0c23a, 0x2e7d4f, 0xd36b2b][k % 4]);
  for (let k = 0; k < 4; k++) jar(0.78 + k * 0.10, v, b1, 0.22, 0.04, [0xf2e2b0, 0xb07a3c, 0xe9e1d0, 0x6e4b2a][k]);
  boxI(0.05, 0.08, b2, 0.26, 0.22, 0xece6da); boxI(0.40, 0.08, b2, 0.36, 0.20, 0x9fb6c6); for (let k = 0; k < 4; k++) can(0.88 + k * 0.08, v, b2, 0xb22d2d + k * 0x101010);
  boxI(1.20, 0.10, b2, 0.25, 0.25, 0xc6a272);
  boxI(0.06, 0.06, b3, 0.48, 0.24, 0xc9b28d); boxI(0.66, 0.06, b3, 0.30, 0.26, 0xe6dcc9); boxI(1.05, 0.06, b3, 0.38, 0.22, 0xb59b74);   // storage baskets
  boxI(0.10, 0.06, b4, 0.55, 0.22, 0xe6dcc9); boxI(0.82, 0.06, b4, 0.55, 0.22, 0xc9b28d);
}
function fPouf(f, parent) {
  const [x0, z0, x1, z1] = f.b, r = Math.min(x1 - x0, z1 - z0) / 2, g = new THREE.CylinderGeometry(r, r, f.h, 32);
  g.translate((x0 + x1) / 2, f.y0 + f.h / 2, (z0 + z1) / 2); addMesh(parent, g, M.fabric);
}
function fPowderRoom(f, parent) {       // small WC after the reference photo (B5): world coords from the room box; WC on the north wall, basin on the west wall
  const [x0, z0, x1, z1] = f.b, y = f.y0, oak = M.oak_top || M.wood, B = (a, b, c, d, e, g, m, cs = true) => addMesh(parent, mbox(a, b, e, g, c, d), m, cs, true);   // B(x0, x1, z0, z1, y0, y1)
  if (!M.beige) { M.beige = new THREE.MeshStandardMaterial({ color: 0xcfc3b3, roughness: 0.55 }); M.beige.name = 'Stone_Beige'; }
  if (!M.cab) { M.cab = new THREE.MeshStandardMaterial({ color: 0xd9cdbd, roughness: 0.7 }); M.cab.name = 'Cabinet_Taupe'; }
  if (!M.matblack) { M.matblack = new THREE.MeshStandardMaterial({ color: 0x1d1c1b, roughness: 0.45, metalness: 0.4 }); M.matblack.name = 'Matte_Black'; }
  // B5 rev.: WC on the west wall (stone duct + lit niche), basin + large backlit oval mirror facing the door (north wall), tall cabinet on the east wall (living-room side)
  const zc = (z0 + z1) / 2, dxw = x0 + 0.22;
  B(x0, dxw, z0, z1, y, y + 1.15, M.beige);                                              // stone-clad duct along the west wall
  B(x0, x0 + 0.02, z0, z1, y + 1.15, y + 1.48, oak); B(x0, dxw, z0, z1, y + 1.47, y + 1.50, oak);
  B(dxw - 0.06, dxw - 0.04, z0 + 0.03, z1 - 0.03, y + 1.455, y + 1.465, M.led, false);
  { const g = new THREE.CylinderGeometry(0.06, 0.05, 0.10, 14); g.translate(x0 + 0.11, y + 1.20, z0 + 0.30); addMesh(parent, g, M.white, false, false);
    const sp = new THREE.SphereGeometry(0.09, 10, 8); sp.translate(x0 + 0.11, y + 1.32, z0 + 0.30); addMesh(parent, sp, clothMat(0x6d7a45), false, false);
    B(x0 + 0.06, x0 + 0.12, z1 - 0.32, z1 - 0.26, y + 1.15, y + 1.27, clothMat(0x4a3526), false); }
  B(dxw, dxw + 0.012, zc - 0.12, zc + 0.12, y + 0.92, y + 1.08, M.matblack, false);       // flush plate
  { const g = new THREE.CylinderGeometry(0.18, 0.16, 0.30, 28); g.scale(1.45, 1, 1); g.translate(dxw + 0.27, y + 0.27, zc); addMesh(parent, g, M.white, true, false);
    const l = new THREE.CylinderGeometry(0.185, 0.185, 0.04, 28); l.scale(1.45, 1, 1); l.translate(dxw + 0.27, y + 0.44, zc); addMesh(parent, l, M.white, true, false); }
  const bx = f.basin_x ?? (x0 + x1) / 2, bz1 = z0 + 0.42;                                // floating basin on the z0 wall (f.basin_x: e.g. on the door axis)
  B(bx - 0.32, bx + 0.32, z0, bz1, y + 0.68, y + 0.86, M.beige); B(bx - 0.24, bx + 0.24, z0 + 0.10, bz1 - 0.06, y + 0.80, y + 0.861, M.white, false);
  B(bx - 0.28, bx + 0.28, z0, bz1 - 0.06, y + 0.48, y + 0.68, oak);
  B(bx - 0.03, bx + 0.03, z0, z0 + 0.05, y + 0.97, y + 1.00, M.matblack); B(bx - 0.012, bx + 0.012, z0 + 0.04, z0 + 0.20, y + 0.985, y + 1.005, M.matblack);
  B(bx + 0.32, bx + 0.36, z0 + 0.06, z0 + 0.36, y + 0.40, y + 0.84, clothMat(0xb9b0a3));
  if (!M.mirror) { M.mirror = new THREE.MeshStandardMaterial({ color: 0xdfe6ea, metalness: 1, roughness: 0.04 }); M.mirror.name = 'Mirror'; }
  for (const [r, m, dz_] of [[1.0, M.led, 0.005], [0.95, M.mirror, 0.02]]) {             // large backlit oval mirror 0,64 × 1,20 m
    const g = new THREE.CylinderGeometry(0.32 * r, 0.32 * r, 0.012, 48); g.rotateX(Math.PI / 2); g.scale(1, 1.875, 1); g.translate(bx, y + 1.58, z0 + dz_); addMesh(parent, g, m, false, false); }
  for (const px of [bx - 0.50]) { const c = new THREE.CylinderGeometry(0.003, 0.003, 0.60, 6); c.translate(px, y + 2.25, z0 + 0.25); addMesh(parent, c, M.matblack, false, false);
    const p = new THREE.CylinderGeometry(0.03, 0.03, 0.40, 16); p.translate(px, y + 1.75, z0 + 0.25); addMesh(parent, p, M.matblack, false, false);
    const d = new THREE.CylinderGeometry(0.02, 0.02, 0.01, 12); d.translate(px, y + 1.545, z0 + 0.25); addMesh(parent, d, M.led, false, false); }
  const cx0 = x1 - 0.30, cz1 = z1 - 0.20;                                                // tall cabinet on the east wall with a lit niche
  B(cx0, x1, z0, cz1, y, y + 1.00, M.cab); B(cx0, x1, z0, cz1, y + 1.30, y + 2.45, M.cab);
  B(x1 - 0.02, x1, z0, cz1, y + 1.00, y + 1.30, oak); B(cx0, x1, z0, cz1, y + 1.00, y + 1.02, oak); B(cx0 + 0.04, cx0 + 0.06, z0 + 0.03, cz1 - 0.03, y + 1.285, y + 1.295, M.led, false);
  for (const yy of [0.5, 1.88]) B(cx0 - 0.004, cx0, z0 + 0.02, cz1 - 0.02, y + yy - 0.003, y + yy + 0.003, M.dark, false);
  B(cx0 - 0.004, cx0, (z0 + cz1) / 2 - 0.003, (z0 + cz1) / 2 + 0.003, y + 0.02, y + 2.43, M.dark, false);
  B(x1 - 0.20, x1 - 0.12, z0 + 0.15, z0 + 0.23, y + 1.02, y + 1.14, clothMat(0x4a3526), false); B(x1 - 0.22, x1 - 0.10, cz1 - 0.30, cz1 - 0.18, y + 1.02, y + 1.08, M.white, false);
}
function fShoeUnit(f, parent) {        // B5: slim divider unit (0,35 m) — open shelves to the closet side: shoes low, bags middle, hats on top; oak back to the bed
  const G = fframe(f, f.back || 'e', parent), { W, D, box, cyl } = G, y = f.y0, H = f.h, oak = M.oak_top || M.wood;
  box(0, W, 0.012, 0.03, y, y + H, oak); box(0, W, 0, 0.012, y, y + H, M.render_in || M.white);   // back to the bedroom painted like the walls
  box(0, 0.025, 0.012, D, y, y + H, oak); box(W - 0.025, W, 0.012, D, y, y + H, oak);
  const levels = [0.0, 0.18, 0.36, 0.54, 0.72, 1.05, 1.45, 1.85, 2.25, H - 0.03];
  for (const l of levels) box(0.025, W - 0.025, 0.03, D, y + l, y + l + 0.025, oak);
  for (let i = 0; i < levels.length - 1; i++) box(0.03, W - 0.03, D - 0.05, D - 0.04, y + levels[i + 1] - 0.012, y + levels[i + 1] - 0.004, M.led, false);
  const shoe = [0x1d1c1b, 0xc8a27a, 0xf2efe8, 0x8a2f35, 0x5a4636, 0xd8c6b0];
  const bag = new THREE.Group();
  for (let i = 0; i < 4; i++) for (let u = 0.17, k = 0; u + 0.12 < W - 0.04; u += 0.30, k++) {               // pairs: trainers/loafers, stilettos, ankle boots
    const kind = ['shoe', 'heel', 'ankle', 'heel', 'shoe'][(i + k) % 5], [sx, sz] = G.world(u, D * 0.55), s2 = Math.min(1, (D - 0.04) / 0.28);
    placeWear(bag, WEAR.pair(kind, SHOE_COLS[kind][(i * 3 + k) % SHOE_COLS[kind].length]), sx, y + levels[i] + 0.025, sz, frameYaw(G), s2); }
  bakeWear(bag, parent);
  const BAGS = [0xe8d8c4, 0x2b2a28, 0xb5876a, 0xf4e9e2, 0x7d5a44];
  for (let i = 4; i < 7; i++) for (let u = 0.08, k = 0; u + 0.30 < W - 0.05; u += 0.42, k++) {
    const c = clothMat(BAGS[(i + k) % BAGS.length]); box(u, u + 0.30, 0.08, 0.28, y + levels[i] + 0.025, y + levels[i] + 0.25, c);
    box(u + 0.08, u + 0.22, 0.17, 0.19, y + levels[i] + 0.25, y + levels[i] + 0.32, c); }
  for (let i = 7; i < 9; i++) for (let u = 0.20, k = 0; u + 0.15 < W - 0.05; u += 0.40, k++) {
    const c = clothMat([0xd9c3a0, 0x3a3532, 0xefe6d6][(i + k) % 3]); cyl(u, D / 2, 0.17, y + levels[i] + 0.025, y + levels[i] + 0.035, c, 24); cyl(u, D / 2, 0.09, y + levels[i] + 0.035, y + levels[i] + 0.14, c, 20, 0.08); }
}
function fSlatDivider(f, parent) {      // floor-to-ceiling oak slat divider (B5, reference photo): slats along the long side, top and bottom rails
  const [x0, z0, x1, z1] = f.b, y = f.y0, H = f.h, oak = M.oak_top || M.wood, alongZ = (z1 - z0) >= (x1 - x0);
  const L = alongZ ? z1 - z0 : x1 - x0, B = (a, b, c, d, e, g, m) => addMesh(parent, mbox(a, b, e, g, c, d), m, true, true);
  const sw = 0.045, gap = 0.035, n = Math.floor((L + gap) / (sw + gap)), off = (L - (n * sw + (n - 1) * gap)) / 2;
  for (let i = 0; i < n; i++) { const u = off + i * (sw + gap);
    if (alongZ) B(x0 + 0.02, x1 - 0.02, z0 + u, z0 + u + sw, y, y + H, oak); else B(x0 + u, x0 + u + sw, z0 + 0.02, z1 - 0.02, y, y + H, oak); }
  if (alongZ) { B(x0, x1, z0, z1, y + H - 0.05, y + H, oak); B(x0, x1, z0, z1, y, y + 0.04, oak); } else { B(x0, x1, z0, z1, y + H - 0.05, y + H, oak); B(x0, x1, z0, z1, y, y + 0.04, oak); }
}
function fVanityMakeup(f, parent) {     // B5: make-up corner — floating oak desk with drawer, large mirror with LED frame, stool, small accessories
  const G = fframe(f, f.back || 'n', parent), { W, D, box, cyl } = G, y = f.y0, oak = M.oak_top || M.wood;
  if (!M.mirror) { M.mirror = new THREE.MeshStandardMaterial({ color: 0xdfe6ea, metalness: 1, roughness: 0.04 }); M.mirror.name = 'Mirror'; }
  box(0, W, 0, D, y + 0.62, y + 0.76, oak); box(0.04, W - 0.04, D - 0.004, D + 0.002, y + 0.685, y + 0.69, M.dark, false);
  box(0.02, 0.06, 0.02, D - 0.04, y, y + 0.62, oak); box(W - 0.06, W - 0.02, 0.02, D - 0.04, y, y + 0.62, oak);
  box(0.06, W - 0.06, 0, 0.02, y + 0.95, y + 2.15, M.led, false); box(0.10, W - 0.10, 0.02, 0.03, y + 0.99, y + 2.11, M.mirror, false);
  for (let k = 0; k < 6; k++) { const u = 0.10 + k * (W - 0.20) / 5; cyl(u, 0.04, 0.03, y + 2.14, y + 2.20, M.led, 12); }
  cyl(W * 0.25, D * 0.45, 0.04, y + 0.76, y + 0.86, clothMat(0xe7c3c8), 12); cyl(W * 0.33, D * 0.40, 0.03, y + 0.76, y + 0.90, M.glass, 12); box(W * 0.65, W * 0.85, 0.15, 0.30, y + 0.76, y + 0.80, clothMat(0x2b2a28));
  cyl(W / 2, D + 0.22, 0.20, y + 0.40, y + 0.46, clothMat(0xf2e6dc), 24); cyl(W / 2, D + 0.22, 0.03, y, y + 0.40, oak, 10);
  { const [jx, jz] = G.world(W * 0.5, D * 0.42), bag = new THREE.Group(); placeWear(bag, WEAR.jewellery(), jx, y + 0.76, jz, frameYaw(G)); bakeWear(bag, parent); }   // jewellery tray
}
function furnModel(f, parent) {
  const n = (f.name || '').toLowerCase(), [x0, z0, x1, z1] = f.b, y = f.y0, H = f.h, m = M[f.mat] || M.white;
  const plain = () => addMesh(parent, mbox(x0, x1, y, y + Math.max(0.01, H), z0, z1), m, H > 0.05, true);
  const F = (s = backSide(f)) => fframe(f, s, parent);
  if (n.startsWith('expositor') || n.startsWith('teto') || f.mat === 'rug' || H < 0.06 || /base de duche|churrasqueira \(base\)/.test(n)) {
    plain();
    if (/base de duche/.test(n)) { const G = F(); G.box(G.W - 0.01, G.W, 0, G.D, y + H, y + 2.0, M.glass, false); }   // glass screen on the open side
    return;
  }
  if (/^luz|^spot/.test(n)) {   // small recessed downlight: emissive disc just under the ceiling surface
    const r = Math.min(x1 - x0, z1 - z0) / 2, g = new THREE.CylinderGeometry(r, r, Math.max(0.01, H), 16); g.translate((x0 + x1) / 2, y + Math.max(0.01, H) / 2, (z0 + z1) / 2);
    return addMesh(parent, g, M.led, false, false);
  }
  if (/^espelho|^mirror/.test(n)) {     // round wall mirror: thin disc against the wall (axis across the thin side of the box)
    if (!M.mirror) { M.mirror = new THREE.MeshStandardMaterial({ color: 0xdfe6ea, metalness: 1.0, roughness: 0.04 }); M.mirror.name = 'Mirror'; }
    const thinX = (x1 - x0) < (z1 - z0), r = H / 2, t = thinX ? x1 - x0 : z1 - z0;
    const g = new THREE.CylinderGeometry(r, r, t, 40); if (thinX) g.rotateZ(Math.PI / 2); else g.rotateX(Math.PI / 2);
    g.translate((x0 + x1) / 2, y + r, (z0 + z1) / 2); addMesh(parent, g, M.mirror, false, false);
    const fr = new THREE.TorusGeometry(r, 0.012, 8, 48); if (thinX) fr.rotateY(Math.PI / 2); fr.translate((x0 + x1) / 2, y + r, (z0 + z1) / 2);
    return addMesh(parent, fr, M.dark, false, false);
  }
  if (/^churrasqueira$|barbecue|^bbq/.test(n)) return /cozinha|kitchen/.test(f.style || '') ? fBBQ2(f, parent) : fBBQ(f, parent);   // f.style 'kitchen': outdoor kitchen run
  if (/^despensa (fundo|lado)|^pantry (back|side)/.test(n)) return fPantry(f, parent);
  if (/^mesa escritório dupla|^(double|office) desk/.test(n)) return fOfficeDesk(f, parent);
  if (/^cadeira escritório|^office chair/.test(n)) return fOfficeChair(f, parent);
  if (/^closet sapatos|^shoe (rack|unit)/.test(n)) return fShoeUnit(f, parent);
  if (/^toucador|^dressing table|^make-?up/.test(n)) return fVanityMakeup(f, parent);
  if (/^closet |^walk-in /.test(n)) return fClosetUnit(f, parent);
  if (/^hall ripado|^hall (slats|entry)/.test(n)) return fHallEntry(f, parent);
  if (/^lavandaria móvel|^laundry unit/.test(n)) return fLaundry(f, parent);
  if (/^is social|^powder room|^guest wc/.test(n)) return fPowderRoom(f, parent);
  if (/^is principal|^main bath/.test(n)) return fMainBath(f, parent);
  if (/^ripado|^slat (screen|divider)/.test(n)) return fSlatDivider(f, parent);
  if (/^puff|^pouf/.test(n)) return fPouf(f, parent);
  if (/^(sapatos|shoes|saltos? altos?|sapatos de salto|high heels|heels|botas|boots|botins|ankle boots)\b/.test(n)) {   // pairs on the floor, along the footprint, toes to the front
    const G = F(f.back || backSide(f, false)), kind = /salto|heel/.test(n) ? 'heel' : /botins|ankle/.test(n) ? 'ankle' : /bota|boot/.test(n) ? 'boot' : 'shoe', cols = SHOE_COLS[kind];
    const bag = new THREE.Group(); let k = 0;
    for (let u = 0.12; u < G.W - 0.1; u += 0.28, k++) { const [sx, sz] = G.world(u, Math.min(0.18, G.D / 2)); placeWear(bag, WEAR.pair(kind, f.color ? parseInt(String(f.color).replace('#', ''), 16) : cols[k % cols.length]), sx, y, sz, frameYaw(G)); }
    bakeWear(bag, parent); return;
  }
  if (/^(roupão|robe|bathrobe)/.test(n)) {                                    // bathrobe on a wall hook (hook at f.y0 + f.h)
    const G = F(f.back || backSide(f, false)), [hx, hz] = G.world(G.W / 2, 0.08);
    placeWear(parent, WEAR.robe(f.color ? parseInt(String(f.color).replace('#', ''), 16) : 0xf1eee8), hx, y + H, hz, frameYaw(G)); return;
  }
  if (/^(camisas?|shirts?|casacos?|jackets?|blazers?|coats?|sobretudos?)\b/.test(n)) {   // garments on hangers along a rail at f.y0 + f.h
    const G = F(f.back || backSide(f, false)), bag = new THREE.Group(), kind = /camisa|shirt/.test(n) ? 'shirt' : 'jacket', L = /coat|sobretudo/.test(n) ? 0.95 : kind === 'shirt' ? 0.55 : 0.5;
    const cols = kind === 'shirt' ? [0xf4f4f2, 0xc9d6e6, 0xe9e5dc, 0x9fb3c8] : [0x3c3c3c, 0x6b5a45, 0x2a3442, 0x8c8c8c], step = kind === 'shirt' ? 0.055 : 0.09;
    G.box(0, G.W, G.D / 2 - 0.012, G.D / 2 + 0.012, y + H - 0.025, y + H, M.dark);
    let k = 0; for (let u = 0.06; u < G.W - 0.05; u += step, k++) { const [tx, tz] = G.world(u, G.D / 2); placeWear(bag, WEAR.top(kind, cols[k % cols.length], L), tx, y + H - 0.025, tz, frameYaw(G) + Math.PI / 2); }
    bakeWear(bag, parent); return;
  }
  if (/^(jóias|joias|joalharia|bijuteria|jewel?lery|jewelry)/.test(n)) {        // jewellery tray standing on the surface at f.y0
    const G = F(f.back || backSide(f, false)), [jx, jz] = G.world(G.W / 2, G.D / 2), bag = new THREE.Group();
    placeWear(bag, WEAR.jewellery(), jx, y, jz, frameYaw(G)); bakeWear(bag, parent); return;
  }
  if (/^(calças|trousers|pants)/.test(n)) {                                   // trousers on hangers along a rail at f.y0 + f.h
    const G = F(f.back || backSide(f, false)), TR = [0x2a2f3a, 0xb7a68b, 0x1d1d1d, 0x6f7177];
    G.box(0, G.W, G.D / 2 - 0.012, G.D / 2 + 0.012, y + H - 0.025, y + H, M.dark);
    const bag = new THREE.Group(); let k = 0;
    for (let u = 0.06; u < G.W - 0.05; u += 0.07, k++) { const [tx, tz] = G.world(u, G.D / 2); placeWear(bag, WEAR.trousers(TR[k % TR.length]), tx, y + H - 0.025, tz, frameYaw(G) + Math.PI / 2, 0.92); }
    bakeWear(bag, parent); return;
  }
  if (/forno a lenha|wood.?fired/.test(n)) return fOven(f, parent);
  if (/^carro|^car\b/.test(n)) return fCar(f, parent);
  if (/^cama|bed\b/.test(n)) return fBed(f, parent);
  if (/cabeceira|headboard/.test(n)) { const G = F(false); G.box(0, G.W, 0, G.D, y + 0.25, y + H, M.fabric); G.box(0.02, G.W - 0.02, 0, G.D * 0.4, y, y + 0.25, M.dark, false); return; }
  if (/sofá|sofa/.test(n)) {
    const G = F(), touch = o => o !== f && /sofá|sofa/i.test(o.name || '') && !(o.b[0] > x1 + 0.02 || o.b[2] < x0 - 0.02 || o.b[1] > z1 + 0.02 || o.b[3] < z0 - 0.02);
    const others = LAY.furniture.filter(touch), ends = [G.world(0.05, G.D / 2), G.world(G.W - 0.05, G.D / 2)];
    const free = ([px, pz]) => !others.some(o => px > o.b[0] - 0.1 && px < o.b[2] + 0.1 && pz > o.b[1] - 0.1 && pz < o.b[3] + 0.1);
    return fSofa(f, G, y, H, { l: free(ends[0]) && !/perna|leg/.test(n), r: free(ends[1]) && !/perna|leg/.test(n) });
  }
  if (/ondulad|wave/.test(n)) {   // wave chaise longue: curved shell extruded across its width, two dark supports
    const alongZ = (z1 - z0) >= (x1 - x0), L = alongZ ? z1 - z0 : x1 - x0, Wd = alongZ ? x1 - x0 : z1 - z0;
    const flip = alongZ ? f.head === 's' : f.head === 'e';
    const prof = [[0, 0.72], [0.12, 0.62], [0.3, 0.38], [0.45, 0.3], [0.62, 0.36], [0.76, 0.47], [0.9, 0.34], [1, 0.2]];
    const curve = new THREE.SplineCurve(prof.map(([t, h]) => new THREE.Vector2(t * L, h)));
    const top = curve.getPoints(40), sh = new THREE.Shape();
    top.forEach((p, i) => i ? sh.lineTo(p.x, p.y) : sh.moveTo(p.x, p.y));
    for (let i = top.length - 1; i >= 0; i--) sh.lineTo(top[i].x, top[i].y - 0.05);
    sh.closePath();
    const g = new THREE.ExtrudeGeometry(sh, { depth: Wd, bevelEnabled: false, curveSegments: 4 });
    const P = g.attributes.position;
    for (let i = 0; i < P.count; i++) {
      const v = flip ? L - P.getX(i) : P.getX(i), hh = P.getY(i), u = P.getZ(i);
      if (alongZ) P.setXYZ(i, x0 + u, y + hh, z0 + v); else P.setXYZ(i, x0 + v, y + hh, z0 + u);
    }
    g.computeVertexNormals(); addMesh(parent, g, M.white);
    for (const t of [0.22, 0.86]) {
      const v = (flip ? 1 - t : t) * L, hb = curve.getPoint(t).y - 0.05;
      if (alongZ) addMesh(parent, mbox(x0 + 0.06, x1 - 0.06, y, y + hb, z0 + v - 0.03, z0 + v + 0.03), M.dark);
      else addMesh(parent, mbox(x0 + v - 0.03, x0 + v + 0.03, y, y + hb, z0 + 0.06, z1 - 0.06), M.dark);
    }
    return;
  }
  if (/espreguiçadeira|lounger/.test(n) || (f.mat === 'white' && Math.abs(H - 0.35) < 0.01)) {
    const G = F('n'), { W, D, box } = G; box(0, W, 0.5, D, y + 0.18, y + 0.3, M.white);
    for (const [u, v] of [[0.05, 0.55], [W - 0.05, 0.55], [0.05, D - 0.05], [W - 0.05, D - 0.05]]) fLeg(G, u, v, y, y + 0.18, M.dark, 0.03);
    const back = mbox(0, W, 0, 0.08, 0, 0.62); back.rotateX(-0.9); const [bx, bz] = G.world(0, 0.5); back.translate(Math.min(x0, x1), y + 0.28, bz);
    addMesh(parent, back, M.white); return;
  }
  if (/banco ilha|stool/.test(n)) { const G = F(); G.cyl(G.W / 2, G.D / 2, 0.02, y, y + 0.66, M.dark, 10); G.cyl(G.W / 2, G.D / 2, 0.18, y, y + 0.02, M.dark, 20); G.cyl(G.W / 2, G.D / 2, 0.19, y + 0.66, y + 0.71, M.chair, 20); return; }
  if (f.mat === 'chair' || /cadeira|chair/.test(n)) {
    // back toward the side away from the nearest table
    const tabs = LAY.furniture.filter(o => /mesa|table|ilha/i.test(o.name || ''));
    const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2;
    let side = 'n';
    if (tabs.length) { const t = tabs.reduce((a, o) => { const d = Math.hypot((o.b[0] + o.b[2]) / 2 - cx, (o.b[1] + o.b[3]) / 2 - cz); return d < a[0] ? [d, o] : a; }, [1e9, null])[1];
      const dx = Math.max(t.b[0] - cx, 0, cx - t.b[2]) * Math.sign((t.b[0] + t.b[2]) / 2 - cx), dz = Math.max(t.b[1] - cz, 0, cz - t.b[3]) * Math.sign((t.b[1] + t.b[3]) / 2 - cz);
      side = Math.abs(dx) > Math.abs(dz) ? (dx > 0 ? 'w' : 'e') : (dz > 0 ? 'n' : 's'); }
    return fChair(fframe(f, side, parent), y, Math.max(H, 0.85), 0.45, M.chair);
  }
  if (/sanita|toilet|wc\b/.test(n)) return fToilet(F(false), y);
  if (/banheira|bath/.test(n)) { const G = F(), { W, D, box } = G; box(0, W, 0, 0.07, y, y + H, M.white); box(0, W, D - 0.07, D, y, y + H, M.white); box(0, 0.07, 0, D, y, y + H, M.white); box(W - 0.07, W, 0, D, y, y + H, M.white); box(0.07, W - 0.07, 0.07, D - 0.07, y, y + 0.12, M.white); return; }
  if (/lavatório|bancada dupla|vanity|basin/.test(n)) return fVanity(F(), y, H, /dupla|double/.test(n) ? 2 : 1);
  if (/bancada cozinha|kitchen/.test(n) || f.mat === 'kitchen' && H < 1.2) {
    const G = F(); fCabinet(G, y, H, M.kitchen, { top: M.stone_top });
    const { W, D, box } = G; box(W * 0.62, W * 0.62 + 0.6, 0.12, 0.5, y + H, y + H + 0.008, M.dark, false);      // hob
    box(W * 0.25, W * 0.25 + 0.7, 0.1, 0.48, y + H - 0.006, y + H + 0.002, M.frame, false);                     // sink
    G.cyl(W * 0.25 + 0.35, 0.05, 0.015, y + H, y + H + 0.3, M.frame, 8); return;
  }
  if (/colunas|frigorífico|tall/.test(n) || (f.mat === 'kitchen' && H >= 1.2)) {
    const G = F(); fCabinet(G, y, H, M.kitchen, { doorW: 0.6 });
    G.box(G.W / 2 + 0.03, G.W - 0.03, G.D - 0.02, G.D, y + 0.85, y + 1.45, M.dark, false); return;            // built-in oven + microwave
  }
  if (/ilha|island/.test(n)) { const G = F(), { W, D, box } = G; fCabinet(G, y, H, M.kitchen, { top: null, plinth: 0.1 });
    box(0, W, -0.0, D + 0.25, y + H - 0.03, y + H + 0.01, M.stone_top); return; }                            // worktop overhang for the stools
  if (/bancada|worktop|máquinas/.test(n)) { const G = F(); fCabinet(G, y, H, f.mat === 'stone_top' ? M.stone : M.white, { top: M.stone_top });
    if (/máquinas|lavandaria/.test(n)) for (const u of [0.35, 1.0]) G.box(u - 0.17, u + 0.17, G.D - 0.021, G.D - 0.01, y + 0.25, y + 0.59, M.glass, false);   // machine doors
    return; }
  if (/roupeiro|wardrobe|armário|armario/.test(n) || f.mat === 'wardrobe') return fCabinet(F(), y, H, M.wardrobe, { plinth: 0.06, doorW: 0.5 });
  if (/aparador|sideboard/.test(n)) return fCabinet(F(), y, H, m, { top: M.wood, plinth: 0.12, doorW: 0.5 });
  if (/móvel tv|tv/.test(n)) { const G = F(); fCabinet(G, y, H, M.dark, { top: M.wood, plinth: 0.08, doorW: 0.5, handles: false });
    const { W, box } = G; box(W / 2 - 0.62, W / 2 + 0.62, 0.0, 0.04, y + 0.95, y + 1.66, M.dark); box(W / 2 - 0.6, W / 2 + 0.6, 0.04, 0.045, y + 0.97, y + 1.64, M.glass, false); return; }
  if (/estante|prateleira|shelf|shelves/.test(n)) return fShelves(F(), y, H, m, /estante$|books|livros/.test(n) || n === 'estante');
  if (/secretária|desk/.test(n)) { const G = F(), { W, D, box } = G; box(0, W, 0, D, y + H - 0.04, y + H, M.wood);
    box(0, 0.03, 0.02, D - 0.02, y, y + H - 0.04, M.wood); box(W - 0.45, W - 0.42, 0.02, D - 0.02, y, y + H - 0.04, M.wood);
    box(W - 0.42, W, 0.02, D - 0.02, y + 0.05, y + H - 0.04, M.white);                                          // drawer unit
    box(W / 2 - 0.27, W / 2 + 0.27, 0.06, 0.08, y + H, y + H + 0.36, M.dark); return; }                           // screen
  if (/mesa|table/.test(n) || (f.mat === 'wood' && H <= 0.8 && (x1 - x0) * (z1 - z0) > 0.5)) {
    if (H < 0.5) { const G = F(); fTable(G, y, H, M.wood, M.dark, { t: 0.05, inset: 0.06 }); return; }               // coffee table
    return fTable(F(), y, H, M.wood, M.dark);
  }
  if (f.mat === 'wood' && H <= 0.7 && (x1 - x0) * (z1 - z0) <= 0.5) {                                            // bedside table + lamp
    const G = F(); fCabinet(G, y, H, M.wood, { plinth: 0.05, doorW: 1, handles: false });
    G.box(0.04, G.W - 0.04, G.D - 0.021, G.D - 0.017, y + H - 0.17, y + H - 0.165, M.dark, false);
    G.cyl(G.W / 2, G.D / 2, 0.025, y + H, y + H + 0.28, M.dark, 10); G.cyl(G.W / 2, G.D / 2, 0.13, y + H + 0.22, y + H + 0.42, M.white, 20, 0.09); return;
  }
  plain();
}
// cars: f.front = side the bonnet points to ('e' = east); f.color = paint (hex)
function fCar(f, parent) {     // Phase 2: generic modern hatchback/crossover (no brand): extruded rounded side profile, tinted glasshouse, alloy wheels
  const front = f.front || 'e', rear = { e: 'w', w: 'e', n: 's', s: 'n' }[front], F = fframe(f, rear, parent), { W, D, box } = F, y = f.y0, L = D;
  const paint = new THREE.MeshPhysicalMaterial({ color: f.color || 0x8a9097, metalness: 0.55, roughness: 0.32, clearcoat: 1, clearcoatRoughness: 0.06 }); paint.name = 'Car_Paint';
  const tint = M.Car_Glass || (M.Car_Glass = Object.assign(new THREE.MeshPhysicalMaterial({ color: 0x0f151b, metalness: 0.2, roughness: 0.04, clearcoat: 1 }), { name: 'Car_Glass' }));
  const trim = M.Car_Trim || (M.Car_Trim = Object.assign(new THREE.MeshStandardMaterial({ color: 0x151617, roughness: 0.7 }), { name: 'Car_Trim' }));
  const alloy = M.Car_Alloy || (M.Car_Alloy = Object.assign(new THREE.MeshStandardMaterial({ color: 0xb8bcc2, metalness: 0.9, roughness: 0.28 }), { name: 'Car_Alloy' }));
  const rubber = M.Car_Tyre || (M.Car_Tyre = Object.assign(new THREE.MeshStandardMaterial({ color: 0x1b1b1c, roughness: 0.92 }), { name: 'Car_Tyre' }));
  const red = M.Car_Taillight || (M.Car_Taillight = Object.assign(new THREE.MeshStandardMaterial({ color: 0x7a0c0c, emissive: 0x3a0000, roughness: 0.3 }), { name: 'Car_Taillight' }));
  // local (sx = along the car from the rear, sy = height, sz = across) → world; flip the winding if the frame mirrors
  const [ox, oz] = F.world(0, 0), [ux, uz] = F.world(1, 0), [vx, vz] = F.world(0, 1);
  const Ud = [ux - ox, uz - oz], Vd = [vx - ox, vz - oz], mirrored = (Vd[0] * Ud[1] - Vd[1] * Ud[0]) < 0;   // det[V, up, U] < 0: the extrusion is mirrored
  function part(pts, u0, u1, m, bevel = 0.05, taper = null) {   // taper: [h0, h1, k] — narrow the section by k between heights h0→h1 (tumblehome)
    const sh = new THREE.Shape(pts.map(([v, h]) => new THREE.Vector2(v, h)));
    const g = new THREE.ExtrudeGeometry(sh, { depth: Math.max(0.01, u1 - u0 - 2 * bevel), bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel * 0.8, bevelSegments: 4, curveSegments: 12 });
    const P = g.attributes.position;
    for (let i = 0; i < P.count; i++) {
      let u = u0 + bevel + P.getZ(i); const h = P.getY(i);
      if (taper) { const t = Math.max(0, Math.min(1, (h - taper[0]) / (taper[1] - taper[0]))); u = W / 2 + (u - W / 2) * (1 - taper[2] * t * t); }
      const [wx, wz] = F.world(u, P.getX(i)); P.setXYZ(i, wx, y + h, wz);
    }
    if (mirrored) { const ix = g.index; if (ix) { for (let i = 0; i < ix.count; i += 3) { const t = ix.getX(i + 1); ix.setX(i + 1, ix.getX(i + 2)); ix.setX(i + 2, t); } }
      else for (const att of Object.values(g.attributes)) for (let i = 0; i < att.count; i += 3) for (let c = 0; c < att.itemSize; c++) { const t = att.getComponent(i + 1, c); att.setComponent(i + 1, c, att.getComponent(i + 2, c)); att.setComponent(i + 2, c, t); } }
    g.computeVertexNormals(); return addMesh(parent, g, m);
  }
  const sp = (pts) => { const c = new THREE.SplineCurve(pts.map(([v, h]) => new THREE.Vector2(v, h))); return c.getPoints(40).map(p => [p.x, p.y]); };
  // lower body: rear bumper → tailgate → (belt) → bonnet → front bumper, flat floor
  const belt = 0.9, body = [[0.08, 0.24], ...sp([[0.0, 0.42], [0.02, 0.7], [0.07, belt + 0.02]]), [L * 0.2, belt + 0.03], [L * 0.74, belt + 0.02], ...sp([[L * 0.8, belt], [L * 0.93, 0.8], [L, 0.62], [L - 0.02, 0.4]]), [L - 0.12, 0.24]];
  part(body, 0.04, W - 0.04, paint, 0.07, [0.62, belt + 0.05, 0.05]);                                // soft shoulder
  // glasshouse (tumblehome: narrower than the body), then roof skin + pillars in paint
  const cab = [[0.16, belt], ...sp([[0.2, belt + 0.05], [0.32, 1.25], [0.55, 1.37]]), [L * 0.58, 1.38], ...sp([[L * 0.64, 1.35], [L * 0.73, 1.1], [L * 0.79, belt + 0.02]])];
  part(cab, 0.1, W - 0.1, tint, 0.05, [belt, 1.38, 0.2]);                                         // raked, narrowing glasshouse
  part([[0.5, 1.33], [L * 0.6, 1.34], [L * 0.6, 1.4], [0.56, 1.4]], 0.1, W - 0.1, paint, 0.03, [1.3, 1.41, 0.2]);   // roof skin (same taper)
  for (const [va, vb] of [[L * 0.47, L * 0.5]]) box(0.2, W - 0.2, va, vb, y + belt, y + 1.3, trim);                   // B pillar (black)
  box(0.1, W - 0.1, L * 0.22, L * 0.25, y + belt + 0.02, y + belt + 0.05, trim, false);                 // window line trim
  // lights, grille, plates, mirrors
  // details sit on the bevelled skin, which stands ~6 cm proud of the profile at both ends
  const FR = L + 0.035, RR = -0.035;
  for (const [ua, ub] of [[0.12, 0.52], [W - 0.52, W - 0.12]]) box(ua, ub, FR - 0.06, FR + 0.03, y + 0.6, y + 0.7, tint, false);   // headlamp units
  box(0.12, W - 0.12, FR - 0.04, FR + 0.035, y + 0.7, y + 0.715, M.led, false);                          // full-width light bar
  box(0.3, W - 0.3, FR - 0.08, FR + 0.03, y + 0.27, y + 0.47, trim, false);                              // lower intake
  box(W / 2 - 0.26, W / 2 + 0.26, FR - 0.02, FR + 0.04, y + 0.48, y + 0.59, M.white, false);              // front plate
  box(0.12, W - 0.12, RR - 0.035, RR + 0.06, y + 0.8, y + 0.85, red, false);                             // rear light bar
  box(W / 2 - 0.26, W / 2 + 0.26, RR - 0.04, RR + 0.02, y + 0.5, y + 0.61, M.white, false);               // rear plate
  box(0.25, W - 0.25, RR - 0.03, RR + 0.08, y + 0.24, y + 0.38, trim, false);                            // rear diffuser
  for (const [ua, ub] of [[0.02, 0.045], [W - 0.045, W - 0.02]]) box(ua, ub, 0.12, L - 0.12, y + 0.22, y + 0.36, trim, false);   // sill cladding
  for (const u of [0.0, W - 0.14]) box(u, u + 0.14, L * 0.74, L * 0.79, y + belt + 0.05, y + belt + 0.17, paint);   // mirrors
  // wheels: tyre, alloy rim with spokes
  const alongX = rear === 'n' || rear === 's';
  for (const v of [0.82, L - 0.92]) for (const [u, side] of [[0.15, -1], [W - 0.15, 1]]) {
    const [x, z] = F.world(u, v), axis = g => { if (alongX) g.rotateZ(Math.PI / 2); else g.rotateX(Math.PI / 2); return g; };
    const tg = axis(new THREE.CylinderGeometry(0.34, 0.34, 0.23, 28)); tg.translate(x, y + 0.34, z); addMesh(parent, tg, rubber);
    { const [ax, az] = F.world(u + side * 0.105, v), arch = new THREE.TorusGeometry(0.4, 0.04, 6, 20, Math.PI);   // black wheel-arch trim
      if (alongX) arch.rotateY(Math.PI / 2); arch.translate(ax, y + 0.34, az); addMesh(parent, arch, trim, false); }
    const [sx2, sz2] = F.world(u + side * 0.118, v);
    const rim = axis(new THREE.CylinderGeometry(0.22, 0.22, 0.012, 28)); rim.translate(sx2, y + 0.34, sz2); addMesh(parent, rim, alloy, false);
    const hub = axis(new THREE.CylinderGeometry(0.05, 0.05, 0.02, 12)); hub.translate(sx2, y + 0.34, sz2); addMesh(parent, hub, trim, false);
    for (let k = 0; k < 5; k++) {                                                                        // 5 spokes
      const a = k * Math.PI * 2 / 5, sg_ = new THREE.BoxGeometry(0.03, 0.2, 0.012); sg_.translate(0, 0.11, 0); sg_.rotateZ(a);
      if (alongX) sg_.rotateY(Math.PI / 2);                                                               // spoke plane faces across the car
      const [px, pz] = F.world(u + side * 0.126, v);
      sg_.translate(px, y + 0.34, pz); addMesh(parent, sg_, alloy, false);
    }
  }
}
for (const f of LAY.furniture) furnModel(f, sg(f, furniture));

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
// garage access (layout.garage_access, optional): concrete ramp from the road up to the garage floor, with kerbs,
// and n steps inside the garage from a door at a higher level down to the garage floor (references/layout-schema.md)
if (LAY.garage_access) {
  // ramp: runs along x ({x_road, x_door, z0, z1}) or along z ({axis: "z", z_road, z_door, x0, x1}); y_door = garage floor (m from FFL)
  const R = LAY.garage_access.ramp, alongZ = R && R.axis === 'z';
  if (R) {
    const aR = alongZ ? R.z_road : R.x_road, aD = alongZ ? R.z_door : R.x_door, w0 = alongZ ? R.x0 : R.z0, w1 = alongZ ? R.x1 : R.z1;
    const XZ = (a, w) => alongZ ? [w, a] : [a, w], roadAt = w => idw(...XZ(aR, w)) - FFL, N = 12, pos = [], idx = [], uvs = [];
    const ramp = M.Ramp_Concrete || (M.Ramp_Concrete = mat('Ramp_Concrete', { roughness: 0.85 }, paverTex));
    for (let i = 0; i <= N; i++) for (let k = 0; k <= N; k++) {
      const a = aR + (aD - aR) * i / N, w = w0 + (w1 - w0) * k / N, road = roadAt(w), [x, z] = XZ(a, w);
      pos.push(x, road + (R.y_door - road) * i / N + 0.005, z); uvs.push(x, z);                       // straight grade road → door
    }
    for (let i = 0; i < N; i++) for (let k = 0; k < N; k++) { const a = i * (N + 1) + k, b = a + N + 1; idx.push(a, a + 1, b, b, a + 1, b + 1); }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    g.setIndex(idx); g.computeVertexNormals();
    { const nz = g.attributes.normal; let up = 0; for (let i = 0; i < nz.count; i++) up += nz.getY(i); if (up < 0) { g.setIndex(idx.map((v, k) => idx[k - (k % 3) + [0, 2, 1][k % 3]])); g.computeVertexNormals(); } }
    addMesh(site, g, ramp, false, true);
    for (const w of [w0, w1]) for (let i = 0; i < N; i++) {                                            // kerbs + skirts down to the ground
      const aa = aR + (aD - aR) * i / N, ab = aR + (aD - aR) * (i + 1) / N, road = roadAt(w);
      const ya = road + (R.y_door - road) * i / N, yb = road + (R.y_door - road) * (i + 1) / N, gnd = Math.min(heightAt(...XZ(aa, w)), heightAt(...XZ(ab, w))) - 0.25;
      const ws = w === w0 ? [w - 0.15, w] : [w, w + 0.15], [xa, za] = XZ(Math.min(aa, ab), ws[0]), [xb, zb] = XZ(Math.max(aa, ab), ws[1]);
      addMesh(site, mbox(xa, xb, gnd, Math.max(ya, yb) + 0.08, za, zb), M.stone);
    }
    window.__ramp = { slope_pct: +(Math.abs((R.y_door - roadAt((w0 + w1) / 2)) / (aD - aR)) * 100).toFixed(1) };
  }
  // steps: {x0, x1, z_top, y_top, y_bot, n, run, dir: +1 (towards +z, default) or -1}, with a handrail on the x0 side
  const S_ = LAY.garage_access.steps;
  if (S_) {
    const rise = (S_.y_top - S_.y_bot) / S_.n, dir = S_.dir || 1;
    for (let k = 0; k < S_.n; k++) {                                                                   // tread k: top one riser lower each step, first at the door sill
      const za = S_.z_top + dir * k * S_.run, zb = za + dir * S_.run;
      addMesh(furniture, mbox(S_.x0, S_.x1, S_.y_bot - 0.02, S_.y_top - k * rise, Math.min(za, zb), Math.max(za, zb)), M.stone_floor, false, true);
    }
    const zEnd = S_.z_top + dir * S_.n * S_.run, L = Math.hypot(zEnd - S_.z_top, S_.y_top - S_.y_bot), hr = new THREE.CylinderGeometry(0.02, 0.02, L, 8);
    hr.rotateX(-Math.atan2(zEnd - S_.z_top, S_.y_top - S_.y_bot)); hr.translate(S_.x0 - 0.04, (S_.y_top + S_.y_bot) / 2 + 0.9, (S_.z_top + zEnd) / 2);
    addMesh(furniture, hr, M.frame, false, false);
  }
}
// olive trees
const trees = new THREE.Group(); scene.add(trees);
// olive tree (Olea europaea), procedural and CC0 by construction: twisted twin trunk tapering into 4–6 branches,
// silver-green crown of instanced leaf cards (alpha-tested canvas texture of narrow olive leaves)
const OLIVE = (() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 256; const g = cv.getContext('2d'), r = rand(907);
  g.clearRect(0, 0, 256, 256);
  for (let k = 0; k < 70; k++) {                                     // dense spray of narrow lanceolate leaves (dense so mipmapped alpha survives at distance)
    const x = 22 + r() * 212, y = 22 + r() * 212, a = r() * Math.PI * 2, L = 46 + r() * 30, W = 7 + r() * 4, under = r() < 0.35;
    g.save(); g.translate(x, y); g.rotate(a);
    const gr = g.createLinearGradient(0, -W, 0, W);
    if (under) { gr.addColorStop(0, '#a9b29a'); gr.addColorStop(1, '#8f9a80'); } else { gr.addColorStop(0, '#5f6d3f'); gr.addColorStop(1, '#4a5631'); }
    g.fillStyle = gr; g.beginPath(); g.moveTo(-L / 2, 0); g.quadraticCurveTo(0, -W, L / 2, 0); g.quadraticCurveTo(0, W, -L / 2, 0); g.fill();
    g.strokeStyle = under ? 'rgba(220,225,210,.55)' : 'rgba(150,160,120,.5)'; g.lineWidth = 0.8; g.beginPath(); g.moveTo(-L / 2 + 3, 0); g.lineTo(L / 2 - 3, 0); g.stroke();
    g.restore();
  }
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const leaf = new THREE.MeshStandardMaterial({ map: tex, alphaTest: 0.3, side: THREE.DoubleSide, roughness: 0.75, metalness: 0, color: 0xe6ecd8 }); leaf.name = 'Olive_Leaves';
  // bark: vertical fissured grey-brown
  const B = 256, bh = fbmTile(B, [[4, .5], [16, .35], [64, .3]], 911);
  const barkTex = canvasTex(B, B, (ctx, w, h) => pixels(ctx, w, h, (x, y, k) => {
    const fiss = Math.abs(Math.sin(x / B * Math.PI * 9 + bh[k] * 5)); const v = (0.55 + bh[k] * 0.6) * (0.55 + 0.45 * Math.min(1, fiss * 2.2));
    return [clamp255(118 * v), clamp255(108 * v), clamp255(92 * v)];
  }), 0.6, 1.2);
  const barkH = new Float32Array(B * B); for (let y = 0; y < B; y++) for (let x = 0; x < B; x++) barkH[y * B + x] = Math.abs(Math.sin(x / B * Math.PI * 9 + bh[y * B + x] * 5));
  const bark = mat('Olive_Bark', { roughness: 0.95 }, barkTex, normalFromHeight(barkH, B, B, 4, 0.6, 1.2), 1.0);
  const mass = new THREE.MeshStandardMaterial({ color: 0x55623c, roughness: 0.9, flatShading: true }); mass.name = 'Olive_Crown_Mass';   // inner foliage mass: reads at distance where leaf cards thin out
  return { leaf, bark, mass, card: new THREE.PlaneGeometry(0.5, 0.5) };
})();
function limb(points, r0, r1, seg = 14, rad = 8) {                  // tapered tube along a curve, metre UVs for the bark
  const curve = new THREE.CatmullRomCurve3(points), fr = curve.computeFrenetFrames(seg, false), pos = [], uv = [], idx = [];
  const len = curve.getLength();
  for (let i = 0; i <= seg; i++) {
    const t = i / seg, p = curve.getPointAt(t), N = fr.normals[i], Bn = fr.binormals[i], r = r0 + (r1 - r0) * Math.pow(t, 0.8);
    for (let j = 0; j <= rad; j++) {
      const a = j / rad * Math.PI * 2, wob = 1 + 0.18 * Math.sin(a * 3 + t * 9);                  // lumpy section, like an old olive
      const c = Math.cos(a) * r * wob, s_ = Math.sin(a) * r * wob;
      pos.push(p.x + N.x * c + Bn.x * s_, p.y + N.y * c + Bn.y * s_, p.z + N.z * c + Bn.z * s_);
      uv.push(j / rad * 2 * Math.PI * r0, t * len);
    }
  }
  for (let i = 0; i < seg; i++) for (let j = 0; j < rad; j++) { const a = i * (rad + 1) + j, b = a + rad + 1; idx.push(a, b, a + 1, b, b + 1, a + 1); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx); g.computeVertexNormals(); return { g, curve };
}
LAY.trees.forEach((t, i) => {
  const r = rand(300 + i), R = t.r * 1.35, g = new THREE.Group(), Ht = 1.0 + r() * 0.4;       // crown radius ~1.5 m, trunk splits at ~1.2 m
  const tips = [];
  const stems = 2;
  for (let k = 0; k < stems; k++) {
    const a = k * Math.PI + r() * 0.8, lean = 0.25 + r() * 0.2, sx = Math.cos(a), sz = Math.sin(a);
    const pts = [new THREE.Vector3(0, -0.1, 0), new THREE.Vector3(sx * 0.08, Ht * 0.35, sz * 0.08 + 0.04), new THREE.Vector3(sx * lean * 0.6, Ht * 0.7, sz * lean * 0.6 - 0.05), new THREE.Vector3(sx * lean, Ht, sz * lean)];
    const st = limb(pts, 0.17, 0.11); const m = new THREE.Mesh(st.g, OLIVE.bark); m.castShadow = m.receiveShadow = true; g.add(m);
    const nb = 2 + Math.floor(r() * 2);
    for (let j = 0; j < nb; j++) {                                    // branches spreading up and out
      const ba = a + (j - (nb - 1) / 2) * 0.9 + (r() - 0.5) * 0.5, out = R * (0.55 + r() * 0.35), up = 0.8 + r() * 0.7;
      const p0 = pts[3].clone(), p2 = new THREE.Vector3(Math.cos(ba) * out, Ht + up, Math.sin(ba) * out);
      const p1 = p0.clone().lerp(p2, 0.5).add(new THREE.Vector3((r() - 0.5) * 0.3, 0.15, (r() - 0.5) * 0.3));
      const br = limb([p0, p1, p2], 0.09, 0.03, 10, 6); const bm = new THREE.Mesh(br.g, OLIVE.bark); bm.castShadow = true; g.add(bm);
      tips.push(p2, p1.clone().lerp(p2, 0.4));
    }
  }
  // crown: leaf-card clusters around branch tips and a few in between, flattened dome like a pruned olive
  const centres = [...tips]; for (let k = 0; k < 6; k++) { const a = r() * Math.PI * 2, d = R * (0.2 + r() * 0.5); centres.push(new THREE.Vector3(Math.cos(a) * d, Ht + 1.2 + r() * 0.7, Math.sin(a) * d)); }
  const per = 46, inst = new THREE.InstancedMesh(OLIVE.card, OLIVE.leaf, centres.length * per), mtx = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sc = new THREE.Vector3(), p = new THREE.Vector3();
  let n = 0;
  for (const c of centres) for (let k = 0; k < per; k++) {
    const u = r() * 2 - 1, th = r() * Math.PI * 2, rr = Math.cbrt(r()) * 0.62, sxy = Math.sqrt(1 - u * u);
    p.set(c.x + Math.cos(th) * sxy * rr * 1.25, c.y + u * rr * 0.75, c.z + Math.sin(th) * sxy * rr * 1.25);
    e.set(r() * Math.PI, r() * Math.PI * 2, r() * Math.PI); q.setFromEuler(e); const s0 = 0.75 + r() * 0.6; sc.set(s0, s0, s0);
    mtx.compose(p, q, sc); inst.setMatrixAt(n++, mtx);
  }
  inst.count = n; inst.castShadow = true; inst.receiveShadow = true; inst.frustumCulled = false; g.add(inst);
  for (const c of centres) {                                            // irregular inner mass per cluster, slightly smaller than the card shell
    const geo = new THREE.IcosahedronGeometry(0.5, 1), P = geo.attributes.position;
    for (let j = 0; j < P.count; j++) { const k = 0.75 + 0.35 * Math.abs(Math.sin(P.getX(j) * 13.1 + P.getY(j) * 7.7 + P.getZ(j) * 5.3 + c.x)); P.setXYZ(j, P.getX(j) * k * 1.15, P.getY(j) * k * 0.7, P.getZ(j) * k * 1.15); }
    geo.computeVertexNormals(); geo.translate(c.x, c.y, c.z);
    const mm = new THREE.Mesh(geo, OLIVE.mass); mm.castShadow = mm.receiveShadow = true; g.add(mm);
  }
  g.rotation.y = r() * Math.PI * 2;
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
// ---------- Phase 2: CC0 models (Poly Haven, 512 px textures) ----------
// Each placement first builds the procedural piece (already done above); when its GLB arrives the procedural group is
// hidden and the model takes its place. A model that fails to load leaves the procedural piece in place.
// Models face +Z (glTF from Blender: front −Y → +Z). yawFor(front): rotation that turns +Z towards that direction.
const MODELS = { ctable: 'modern_coffee_table_01', pillows: 'throw_pillows_01', plant: 'potted_plant_04', pendant: 'modern_ceiling_lamp_01', basket: 'wicker_basket_01', jug: 'jug_01' };
const gltfLoader = new GLTFLoader(), MODEL_SRC = {};
const yawFor = d => ({ s: 0, n: Math.PI, e: Math.PI / 2, w: -Math.PI / 2 })[d];        // front pointing to +z (s), −z (n), +x (e), −x (w)
const opp = { n: 's', s: 'n', e: 'w', w: 'e' };
const PLACE = [];      // { key, x, z, y, yaw, s, align: {side, at} | null, parent, hide: Object3D[] }
function placeModel(key, o) { PLACE.push({ key, ...o }); }
// Poly Haven seating (sofa_01/02/03, dining_chair_02) is classic/ornate: sofas, chaises and chairs stay procedural (soft upholstery above)
const PROC_HIDE = [];   // [footprint b, y0, y1] regions whose procedural meshes are hidden once the models are in
for (const f of LAY.furniture) {
  const n = (f.name || '').toLowerCase(), [x0, z0, x1, z1] = f.b, cx = (x0 + x1) / 2, cz = (z0 + z1) / 2, y = f.y0, par = sg(f, furniture);
  const back = f.back || (/^(cama|bed)\b/.test(n) ? null : backSide(f));
  if (/^(mesa (de )?centro|coffee table)/.test(n)) { const longX = (x1 - x0) > (z1 - z0); placeModel('ctable', { x: cx, z: cz, y, yaw: longX ? Math.PI / 2 : 0, fit: [x1 - x0, z1 - z0], parent: par }); PROC_HIDE.push(f);
    placeModel('plant', { x: cx + (longX ? 0.3 : 0), z: cz + (longX ? 0 : 0.3), y: y + f.h * (longX ? 0.97 : 0.95), yaw: 0.6, parent: par }); }
  else if (/^(cama|bed)\b/.test(n)) {
    const head = f.head || backSide(f, false), W = head === 'e' || head === 'w' ? z1 - z0 : x1 - x0;
    const at = { n: z0, s: z1, w: x0, e: x1 }[head], inward = { n: 1, s: -1, w: 1, e: -1 }[head], off = 0.30;
    const px = head === 'e' || head === 'w' ? at + inward * off : cx, pz = head === 'n' || head === 's' ? at + inward * off : cz;
    placeModel('pillows', { x: px, z: pz, y: y + 0.5, yaw: yawFor(opp[head]), s: Math.min(1, (W - 0.35) / 1.02), align: { side: head, at: at + inward * 0.12 }, parent: par });
  }
  else if (/^(mesa (de )?jantar|dining table)/.test(n)) {
    placeModel('jug', { x: cx - 0.25, z: cz, y: y + f.h, yaw: 0.4, parent: par }); placeModel('plant', { x: cx + 0.25, z: cz + 0.05, y: y + f.h, yaw: 2.1, parent: par });
    placeModel('pendant', { x: cx - 0.45, z: cz, y: y + f.h + 0.75, yaw: 0, pendant: true, parent: par });
    placeModel('pendant', { x: cx + 0.45, z: cz, y: y + f.h + 0.75, yaw: 0, pendant: true, parent: par });
  }
  else if (/^(ilha|island)/.test(n)) {
    for (const u of [-0.6, 0.6]) placeModel('pendant', { x: cx + u, z: cz, y: y + f.h + 0.75, yaw: 0, pendant: true, parent: par });
    placeModel('plant', { x: cx - 0.95, z: cz + 0.15, y: y + f.h + 0.01, yaw: 1.2, parent: par });
  }
  else if (/^(bancada (de )?cozinha|kitchen counter)/.test(n)) placeModel('basket', { x: x1 - 0.45, z: (z0 + z1) / 2 + 0.05, y: y + f.h + 0.01, yaw: 0.15, parent: par });
}
const ceilAt = (x, z, floorY) => { const r = (LAY.roofs || []).find(r => x > r.rect[0] && x < r.rect[2] && z > r.rect[1] && z < r.rect[3]); return r ? r.eave - 0.24 : floorY + 2.6; };   // soffit under the roof above
function hideProcedural() {      // hide procedural meshes whose bounds sit inside a replaced footprint
  const box = new THREE.Box3();
  furniture.traverse(o => {
    if (!o.isMesh || o.userData.model) return;
    box.setFromObject(o);
    for (const f of PROC_HIDE) {
      const [x0, z0, x1, z1] = f.b, e = 0.03;
      if (box.min.x >= x0 - e && box.max.x <= x1 + e && box.min.z >= z0 - e && box.max.z <= z1 + e && box.min.y >= f.y0 - 0.05 && box.max.y <= f.y0 + f.h + 0.6) { o.visible = false; break; }
    }
  });
}
function instantiate(p) {
  const src = MODEL_SRC[p.key]; if (!src) return;
  const m = src.clone(true), g = new THREE.Group();
  g.add(m); m.rotation.y = p.yaw || 0; m.scale.setScalar(p.s || 1);
  m.updateMatrixWorld(true);
  const b = new THREE.Box3().setFromObject(m);
  if (p.fit) { const sx = p.fit[0] / (b.max.x - b.min.x), sz = p.fit[1] / (b.max.z - b.min.z), k = Math.max(0.7, Math.min(1.3, Math.min(sx, sz)));
    m.scale.multiplyScalar(k); m.updateMatrixWorld(true); b.setFromObject(m); }
  let tx = p.x - (b.min.x + b.max.x) / 2, tz = p.z - (b.min.z + b.max.z) / 2;
  if (p.align) { const { side, at } = p.align;                                                           // back edge on the wall line
    if (side === 'n') tz = at - b.min.z; if (side === 's') tz = at - b.max.z; if (side === 'w') tx = at - b.min.x; if (side === 'e') tx = at - b.max.x;
    if (side === 'n' || side === 's') tx = p.x - (b.min.x + b.max.x) / 2; else tz = p.z - (b.min.z + b.max.z) / 2; }
  m.position.set(tx, p.y - b.min.y, tz);
  m.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.userData.model = p.key; } });
  if (p.pendant) {                                                                                      // cable from the shade up to the ceiling
    const top = p.y + (b.max.y - b.min.y), L = ceilAt(p.x, p.z, p.y - 1.5) - top;
    if (L > 0.02) { const c = new THREE.CylinderGeometry(0.004, 0.004, L, 6); c.translate(p.x, top + L / 2, p.z); const cm = addMesh(g, c, M.dark, false, false); cm.userData.model = 'cable'; }
  }
  p.parent.add(g);
}
// recolour a model's base texture: keep its luminance (weave, pattern, shading), swap the hue to a target tone
const RETINT = { pillows: [0.80, 0.74, 0.64] };
function retint(m, [tr, tg, tb]) {
  const img = m.map && m.map.image; if (!img) return;
  const w = img.width, h = img.height, cv = document.createElement('canvas'); cv.width = w; cv.height = h;
  const c = cv.getContext('2d'); c.drawImage(img, 0, 0); const d = c.getImageData(0, 0, w, h), a = d.data;
  let mean = 0; for (let i = 0; i < a.length; i += 4) mean += 0.2126 * a[i] + 0.7152 * a[i + 1] + 0.0722 * a[i + 2]; mean /= a.length / 4;
  for (let i = 0; i < a.length; i += 4) { const l = (0.2126 * a[i] + 0.7152 * a[i + 1] + 0.0722 * a[i + 2]) / mean, k = 0.75 + 0.25 * l;   // soften the pattern contrast
    a[i] = clamp255(255 * tr * k); a[i + 1] = clamp255(255 * tg * k); a[i + 2] = clamp255(255 * tb * k); }
  c.putImageData(d, 0, 0);
  const t = new THREE.CanvasTexture(cv); t.flipY = m.map.flipY; t.colorSpace = THREE.SRGBColorSpace; t.wrapS = m.map.wrapS; t.wrapT = m.map.wrapT; t.anisotropy = 4;
  m.map = t; m.needsUpdate = true;
}
const toLoad = [...new Set(PLACE.map(p => p.key))];
let modelsLeft = toLoad.length;
for (const key of toLoad) {
  // GLB shipped as base64 JSON (the artifact host serves no .glb/.bin types)
  const url = `models/${MODELS[key]}.glb.json`; manager.itemStart(url);
  fetch(url).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(j => {
    const bin = atob(j.data), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Promise((res, rej) => gltfLoader.parse(u8.buffer, '', res, rej));
  }).then(gl => {
    MODEL_SRC[key] = gl.scene;
    gl.scene.traverse(o => { if (o.isMesh && o.material) { o.material.envMapIntensity = 0.8; if (RETINT[key]) retint(o.material, RETINT[key]); } });
    for (const p of PLACE.filter(p => p.key === key)) instantiate(p);
    if (--modelsLeft === 0) hideProcedural();
  }).catch(err => { console.warn('model not loaded (the procedural piece stays):', MODELS[key], err && err.message); if (--modelsLeft === 0) hideProcedural(); })
    .finally(() => manager.itemEnd(url));
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
// room dimensions ("Areas" layer): wall-to-wall lines across and along each room, with their length, like a plan
// dimension: measured on the room polygon (inside faces), along x at 30 % of the depth and along z at 30 % of the width, 2,3 m above the floor
const dimGroup = new THREE.Group(); dimGroup.name = 'Room_Dimensions'; dimGroup.visible = false; scene.add(dimGroup);
const dimEls = [];
{
  const dec = (PROJ.ui && PROJ.ui.decimal) || '.';
  const dimMat = new THREE.MeshBasicMaterial({ color: 0x1d1c1a, depthTest: true }); dimMat.name = 'Dimension_Line';
  const tickMat = new THREE.MeshBasicMaterial({ color: 0xc8102e }); tickMat.name = 'Dimension_Tick';
  // wall-to-wall span of the polygon on a line (axis 'x': z = c; axis 'z': x = c); the inside segment holding `at`, else the longest
  function span(poly, axis, c, at) {
    const hits = [];
    for (let i = 0; i < poly.length; i++) {
      const [ax, az] = poly[i], [bx, bz] = poly[(i + 1) % poly.length];
      const [pa, qa, pb, qb] = axis === 'x' ? [az, ax, bz, bx] : [ax, az, bx, bz];   // p: coordinate across the line, q: along it
      if ((pa > c) !== (pb > c)) hits.push(qa + (qb - qa) * (c - pa) / (pb - pa));
    }
    hits.sort((u, v) => u - v);
    let best = null;
    for (let i = 0; i + 1 < hits.length; i += 2) { const s = [hits[i], hits[i + 1]]; if (at >= s[0] && at <= s[1]) return s; if (!best || s[1] - s[0] > best[1] - best[0]) best = s; }
    return best;
  }
  for (const r of (LAY.rooms || [])) {
    if (/^(escada|stair)/i.test(r.name)) continue;
    const p = r.poly, xs = p.map(q => q[0]), zs = p.map(q => q[1]);
    const X0 = Math.min(...xs), X1 = Math.max(...xs), Z0 = Math.min(...zs), Z1 = Math.max(...zs);
    const y = (r.level != null ? r.level - FFL : 0) + 2.3, st = r.storey || 0;   // just under the wall tops: reads from above like the room labels
    for (const axis of ['x', 'z']) {
      const c = axis === 'x' ? Z0 + Math.min(0.9, (Z1 - Z0) * 0.22) : X0 + Math.min(0.9, (X1 - X0) * 0.22), at = axis === 'x' ? (X0 + X1) / 2 : (Z0 + Z1) / 2;
      const s_ = span(p, axis, c, at); if (!s_ || s_[1] - s_[0] < 0.6) continue;
      const [a, b] = s_, L = b - a, g = new THREE.Group(); g.userData.storey = st;
      const seg = (u0, u1, w = 0.03) => { const geo = axis === 'x' ? new THREE.BoxGeometry(u1 - u0, w, w) : new THREE.BoxGeometry(w, w, u1 - u0);
        if (axis === 'x') geo.translate((u0 + u1) / 2, y, c); else geo.translate(c, y, (u0 + u1) / 2); return geo; };
      const line = new THREE.Mesh(seg(a, b), dimMat); line.renderOrder = 3; g.add(line);
      for (const u of [a, b]) {                                                     // end ticks: short 45° strokes + a stop against the wall
        const t = new THREE.BoxGeometry(0.035, 0.035, 0.3); t.rotateY(Math.PI / 4 * (axis === 'x' ? 1 : -1));
        if (axis === 'x') t.translate(u, y, c); else t.translate(c, y, u); g.add(new THREE.Mesh(t, tickMat));
        const stop = new THREE.BoxGeometry(0.03, 0.25, 0.03);
        if (axis === 'x') stop.translate(u, y, c); else stop.translate(c, y, u); g.add(new THREE.Mesh(stop, dimMat));
      }
      dimGroup.add(g);
      const el = document.createElement('div'); el.className = 'spot dim'; el.hidden = true; el.style.left = el.style.top = '0';
      el.textContent = L.toFixed(2).replace('.', dec) + ' m'; labelsEl.appendChild(el);
      el.hidden = false; const bw = el.offsetWidth || 50, bh = el.offsetHeight || 16; el.hidden = true;
      const at_ = t => axis === 'x' ? new THREE.Vector3(a + (b - a) * t, y, c) : new THREE.Vector3(c, y, a + (b - a) * t);
      const spots = [0.5, 0.35, 0.65, 0.22, 0.78].map(at_);                       // label slides along its line to a free spot
      dimEls.push({ el, st, bw, bh, g, spots, v: () => spots[0] });
    }
  }
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
  dimGroup.visible = showAreas;
  for (const o of dimEls) {
    const onSt = o.st === Math.min(stShown, MAX_STOREY); o.g.visible = onSt;
    let vis = showAreas && onSt, spot = null;
    if (vis) for (const v of o.spots) {                                            // first spot along the line that is on screen and free
      const p = v.clone().project(camera); if (!(p.z < 1 && Math.abs(p.x) < 1.05 && Math.abs(p.y) < 1.05)) continue;
      const x = (p.x * 0.5 + 0.5) * w, y = (-p.y * 0.5 + 0.5) * h, bw = o.bw / 2 + 1, bh = o.bh / 2 + 1;
      if (placed.some(q => Math.abs(q[0] - x) < q[2] + bw && Math.abs(q[1] - y) < q[3] + bh)) continue;
      spot = [x, y, bw, bh, v]; break;
    }
    if (spot && (recheck || o.occ === undefined)) o.occ = occluded(spot[4]);
    vis = !!spot && !o.occ;
    if (vis) { placed.push(spot.slice(0, 4)); o.el.style.transform = `translate(${spot[0]}px, ${spot[1]}px) translate(-50%, -50%)`; }
    o.el.hidden = !vis;
  }
}

// ---------- sun (latitude from project.json, true north NORTH_DEG clockwise from sheet-up) ----------
const toRad = d => d * Math.PI / 180;
const north = new THREE.Vector3(Math.sin(toRad(NORTH_DEG)), 0, -Math.cos(toRad(NORTH_DEG)));
const east = new THREE.Vector3(Math.cos(toRad(NORTH_DEG)), 0, Math.sin(toRad(NORTH_DEG)));
let dec = 23.44, hour = PROJ.sun_hour ?? 15.5;   // default 15:30: low sun on the facades, long readable shadows (project.json "sun_hour")
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
  scene.environmentIntensity = 1 - 0.97 * night; scene.background = night > 0.5 ? SKY_NIGHT : SKY_DAY;
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
hourIn.value = String(hour);
const fmtH = h => `${String(Math.floor(h)).padStart(2, '0')}:${String(Math.round((h % 1) * 60)).padStart(2, '0')}`;
hourIn.addEventListener('input', () => { hour = parseFloat(hourIn.value); hourOut.textContent = fmtH(hour); updateSun(); });
hourOut.textContent = fmtH(hour);
const panel = document.getElementById('panel'), tp = document.getElementById('toggle-panel');
tp.addEventListener('click', () => {
  const c = panel.classList.toggle('collapsed');
  tp.textContent = c ? T.show : T.hide; tp.setAttribute('aria-expanded', String(!c));
});
if (matchMedia('(max-width: 640px)').matches) { panel.classList.add('collapsed'); tp.textContent = T.show; tp.setAttribute('aria-expanded', 'false'); }
// hide the whole menu (full view of the scene); remembered per viewer
const pHide = document.getElementById('panel-hide'), pShow = document.getElementById('panel-show');
function setPanelHidden(h, focus = false) {
  panel.classList.toggle('offscreen', h); panel.inert = h;
  pShow.hidden = !h; pShow.setAttribute('aria-expanded', String(!h)); pHide.setAttribute('aria-expanded', String(!h));
  try { localStorage.setItem('fp3d.menuHidden', h ? '1' : '0'); } catch (e) {}
  if (focus) (h ? pShow : pHide).focus();
}
pHide.addEventListener('click', () => setPanelHidden(true, true));
pShow.addEventListener('click', () => setPanelHidden(false, true));
try { if (localStorage.getItem('fp3d.menuHidden') === '1') setPanelHidden(true); } catch (e) {}

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

// ---------- quality: Alta = SSGI (indirect light + AO) + TRAA, Média = GTAO + TRAA, Leve = forward + MSAA ----------
const QK = 'fp3d.quality';
const Q = { pref: 'auto', tier: null, pipe: null, frames: 0, t0: 0, fps: 0, settle: 0 };
try { Q.pref = localStorage.getItem(QK) || 'auto'; } catch (e) {}
const AUTO_TIER = GPU ? (coarse ? 'media' : 'alta') : (coarse ? 'leve' : 'media');
const TIERS = ['alta', 'media', 'leve'];
const qNames = { alta: T.q_high || 'High', media: T.q_medium || 'Medium', leve: T.q_light || 'Light' };
const DPR = { alta: 1.25, media: 1.5, leve: 2 };
function buildPipe(tier) {
  if (Q.pipe) { try { Q.pipe.dispose(); } catch (e) {} Q.pipe = null; }
  Q.tier = tier;
  renderer.setPixelRatio(Math.min(devicePixelRatio, DPR[tier]));
  if (tier !== 'leve') {
    const rp = new THREE.RenderPipeline(renderer);
    if (tier === 'alta') {
      const sp = TSL.pass(scene, camera, { samples: 0 });
      sp.setMRT(TSL.mrt({ output: TSL.output, diffuseColor: TSL.diffuseColor, normal: TSL.packNormalToRGB(TSL.normalView), velocity: TSL.velocity }));
      sp.getTexture('diffuseColor').type = THREE.UnsignedByteType; sp.getTexture('normal').type = THREE.UnsignedByteType;
      const col = sp.getTextureNode('output'), dif = sp.getTextureNode('diffuseColor'), dep = sp.getTextureNode('depth'), vel = sp.getTextureNode('velocity'), nt = sp.getTextureNode('normal');
      const nrm = TSL.sample(u => TSL.unpackRGBToNormal(nt.sample(u)));
      const gi = ssgi(col, dep, nrm, camera);
      gi.sliceCount.value = 2; gi.stepCount.value = 10; gi.radius.value = 5; gi.thickness.value = 0.6;
      gi.giIntensity.value = 4; gi.aoIntensity.value = 1.0; gi.expFactor.value = 2;
      const comp = TSL.vec4(TSL.add(col.rgb.mul(gi.getAONode()), dif.rgb.mul(gi.getGINode().rgb)), col.a);
      rp.outputNode = TSL.vec4(traa(comp, dep, vel, camera).rgb, 1);
      Q.gi = gi;
    } else {
      const pre = TSL.pass(scene, camera, { samples: 0 }); pre.transparent = false;
      pre.setMRT(TSL.mrt({ output: TSL.packNormalToRGB(TSL.normalView), velocity: TSL.velocity }));
      pre.getTexture('output').type = THREE.UnsignedByteType;
      const pt = pre.getTextureNode(), pd = pre.getTextureNode('depth'), pv = pre.getTextureNode('velocity');
      const pn = TSL.sample(u => TSL.unpackRGBToNormal(pt.sample(u)));
      const a = gtao(pd, pn, camera); a.radius.value = 0.9; a.thickness.value = 1; a.samples.value = 12;
      const sp = TSL.pass(scene, camera, { samples: 0 });
      sp.contextNode = TSL.builtinAOContext(a.getTextureNode().sample(TSL.screenUV).r);
      rp.outputNode = TSL.vec4(traa(sp, pd, pv, camera).rgb, 1);
      Q.ao = a;
    }
    Q.pipe = rp;
  }
  Q.frames = 0; Q.settle = 0; Q.t0 = 0;
  if (typeof resize === 'function') resize();
  updateQualityUI();
}
// switching level recompiles shaders (a few seconds, the image may freeze): say so, then hide once 3 frames have rendered
const busyEl = document.getElementById('busy'), busyTxt = document.getElementById('busy-txt');
function busy(msg) {
  busyTxt.textContent = msg; Q.busyOn = true; busyEl.hidden = !loadingEl.hidden; Q.busyFrames = -1;
  document.querySelectorAll('[data-q]').forEach(b => { b.disabled = true; });
}
function busyDone() {
  busyEl.hidden = true; Q.busyOn = false; Q.busyFrames = 0;
  document.querySelectorAll('[data-q]').forEach(b => { b.disabled = false; });
}
function switchTier(tier, msg) {
  busy(msg);
  requestAnimationFrame(() => requestAnimationFrame(() => { buildPipe(tier); Q.busyFrames = 3; }));   // let the notice paint before the stall
}
function setQuality(pref) {
  Q.pref = pref; try { localStorage.setItem(QK, pref); } catch (e) {}
  const tier = pref === 'auto' ? AUTO_TIER : pref;
  switchTier(tier, (T.busy_switch || 'Preparing {q} quality… the image pauses for a few seconds.').replace('{q}', qNames[tier]));
}
function draw(now) {
  try { if (Q.pipe) Q.pipe.render(); else renderer.render(scene, camera); }
  catch (e) { console.error('render (' + Q.tier + '):', e); if (Q.pipe) { Q.pipe = null; Q.tier = 'leve'; updateQualityUI(); } else throw e; }
  if (Q.busyOn) busyEl.hidden = !loadingEl.hidden;   // wait for the materials screen to go first
  if (Q.busyFrames > 0 && loadingEl.hidden && --Q.busyFrames === 0) busyDone();
  // frame-rate probe: 2 s windows; in Auto, drop one tier when a loaded scene stays under 24 fps
  if (!loadingEl.hidden || document.hidden) { Q.t0 = 0; return; }
  if (!Q.t0) { Q.t0 = now; Q.frames = 0; Q.last = now; Q.stall = false; return; }
  Q.frames++; if (now - Q.last > 400) Q.stall = true; Q.last = now;
  if (Q.stall && now - Q.t0 > 2000) { Q.t0 = now; Q.frames = 0; Q.stall = false; return; }   // a stall is not a slow device
  if (now - Q.t0 > 2000) {
    Q.fps = Q.frames * 1000 / (now - Q.t0); Q.t0 = now; Q.frames = 0; Q.settle++;
    if (Q.pref === 'auto' && Q.settle >= 2 && Q.fps < 24 && Q.tier !== 'leve') {
      const nt = TIERS[TIERS.indexOf(Q.tier) + 1];
      switchTier(nt, (T.busy_slow || 'Slow image on this device ({fps} fps): switching to {q} quality…').replace('{fps}', Math.round(Q.fps)).replace('{q}', qNames[nt]));
    }
    else updateQualityUI();
  }
}
function updateQualityUI() {
  document.querySelectorAll('[data-q]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.q === Q.pref)));
  const o = document.getElementById('q-out');
  if (o) o.textContent = `${qNames[Q.tier] || ''}${Q.pref === 'auto' ? ' (auto)' : ''} · ${GPU ? 'WebGPU' : 'WebGL 2'}${Q.fps ? ' · ' + Math.round(Q.fps) + ' fps' : ''}`;
}
document.querySelectorAll('[data-q]').forEach(b => b.addEventListener('click', () => setQuality(b.dataset.q)));
window.__quality = { Q, setQuality, buildPipe };
renderer.backend?.device?.addEventListener?.('uncapturederror', e => console.error('WebGPU:', e.error && e.error.message));

// ---------- loop ----------
function resize() { const w = stage.clientWidth, h = stage.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
addEventListener('resize', resize); resize();
{ const t0 = Q.pref === 'auto' ? AUTO_TIER : Q.pref; busy((T.busy_init || 'Preparing the image ({q} quality)…').replace('{q}', qNames[t0])); buildPipe(t0); Q.busyFrames = 3; }
goTo('aerial', true);
renderer.domElement.addEventListener('pointerdown', () => { document.getElementById('hint').hidden = true; }, { once: true });
let lastT = performance.now();
renderer.setAnimationLoop(now => {
  const dt = Math.min(0.1, (now - lastT) / 1000); lastT = now;
  if (NAV.mode !== 'orbit') { navUpdate(dt); draw(now); updateLabels(); updateCompass(); return; }
  if (anim) {
    const t = Math.min(1, (now - anim.t0) / anim.dur), e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    camera.position.lerpVectors(anim.fromP, anim.toP, e); controls.target.lerpVectors(anim.fromT, anim.toT, e);
    if (t >= 1) anim = null;
  }
  controls.update(); draw(now); updateLabels(); updateCompass();
});
window.__ready = true;
