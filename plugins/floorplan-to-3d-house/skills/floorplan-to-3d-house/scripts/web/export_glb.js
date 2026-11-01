
// ================= EXPORT v2 (local tool only, not published) =================
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
function imgData(tex) {
  const im = tex.image, cv = document.createElement('canvas'); cv.width = im.width; cv.height = im.height;
  const c = cv.getContext('2d'); c.drawImage(im, 0, 0); return { d: c.getImageData(0, 0, im.width, im.height).data, w: im.width, h: im.height };
}
function flatTex(t) { const c = t.clone(); c.repeat.set(1, 1); c.offset.set(0, 0); c.needsUpdate = true; return c; }
window.__buildExport = function () {
  const out = new THREE.Scene(); out.name = (PROJ.name || 'House').replace(/\W+/g, '_');
  const A = imgData(v2mask1), B = imgData(v2mask2), C = imgData(v2mask3);
  const smp = (Mk, u, v) => { const x = Math.min(Mk.w - 1, Math.max(0, Math.floor(u * Mk.w))), y = Math.min(Mk.h - 1, Math.max(0, Math.floor((1 - v) * Mk.h))); const i = (y * Mk.w + x) * 4; return [Mk.d[i] / 255, Mk.d[i + 1] / 255, Mk.d[i + 2] / 255]; };
  const GM = {   // name: [texture, metres, colour, roughness]
    Ground_Meadow: [soilTex, 3.0, 0xc4b58c, 1], Ground_Sidewalk: [settsTex, 1.0, 0xf0eee8, 0.9], Ground_Asphalt: [asphTex, 2.5, 0xffffff, 0.9],
    Ground_Lawn: [grassTex, 1.7, 0xb4c294, 1], Ground_Driveway_Pavers: [paverTex, 1.6, 0xffffff, 0.85], Ground_Stone_Paving: [pavTex, 1.2, 0xffffff, 0.8],
    Ground_White_Gravel: [gravelTex, 1.4, 0xffffff, 1], Ground_Planting_Bed: [soilTex, 1.2, 0x6b5a48, 1], Road_Marking: [null, 1, 0xe8e6df, 0.7],
  };
  const order = ['Ground_Sidewalk', 'Ground_Asphalt', 'Ground_Lawn', 'Ground_Driveway_Pavers', 'Ground_Stone_Paving', 'Ground_White_Gravel', 'Ground_Planting_Bed'];
  const buckets = Object.fromEntries(Object.keys(GM).map(k => [k, []]));
  const p = fineGeo.attributes.position, idx = fineGeo.index;
  for (let t = 0; t < idx.count; t += 3) {
    const ia = idx.getX(t), ib = idx.getX(t + 1), ic = idx.getX(t + 2);
    const cx = (p.getX(ia) + p.getX(ib) + p.getX(ic)) / 3, cz = (p.getZ(ia) + p.getZ(ib) + p.getZ(ic)) / 3;
    const u = (cx - G.x0) / gw, v = 1 - (cz - G.z0) / gd, a = smp(A, u, v), b = smp(B, u, v), c = smp(C, u, v);
    const w = { Ground_Sidewalk: c[0], Ground_Asphalt: a[2], Ground_Lawn: a[0], Ground_Driveway_Pavers: a[1], Ground_Stone_Paving: b[0], Ground_White_Gravel: b[1], Ground_Planting_Bed: b[2] };
    let m = 'Ground_Meadow'; for (const k of order) if (w[k] > 0.5) m = k;
    if (m === 'Ground_Asphalt' && c[1] > 0.5) m = 'Road_Marking';
    for (const i of [ia, ib, ic]) buckets[m].push([p.getX(i), p.getY(i), p.getZ(i)]);
  }
  { const q = apronGeo.attributes.position, ix = apronGeo.index;
    for (let t = 0; t < ix.count; t += 3) {
      const tri = [ix.getX(t), ix.getX(t + 1), ix.getX(t + 2)];
      const cx = tri.reduce((s, i) => s + q.getX(i), 0) / 3, cz = tri.reduce((s, i) => s + q.getZ(i), 0) / 3;
      if (cx > G.x0 && cx < G.x1 && cz > G.z0 && cz < G.z1) continue;
      for (const i of tri) buckets.Ground_Meadow.push([q.getX(i), q.getY(i), q.getZ(i)]);
    } }
  const grp = new THREE.Group(); grp.name = 'Site_Ground';
  for (const [name, pts] of Object.entries(buckets)) {
    if (!pts.length) continue;
    const [tex, metres, color, rough] = GM[name], pos = new Float32Array(pts.length * 3), uv = new Float32Array(pts.length * 2);
    pts.forEach((q, k) => { pos.set(q, k * 3); uv[k * 2] = q[0] / metres; uv[k * 2 + 1] = -q[2] / metres; });
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); g.computeVertexNormals();
    const m = new THREE.MeshStandardMaterial({ color, roughness: rough, map: tex ? flatTex(tex) : null }); m.name = name;
    const mesh = new THREE.Mesh(g, m); mesh.name = name; grp.add(mesh);
  }
  out.add(grp);
  const cache = new Map();
  const exportMat = (mt) => {
    if (cache.has(mt)) return cache.get(mt);
    let m;
    if (mt === M.glass) m = new THREE.MeshPhysicalMaterial({ color: 0xdfe9ec, roughness: 0.02, transmission: 1, ior: 1.5, thickness: 0.01 });
    else {
      m = new THREE.MeshStandardMaterial({ color: mt.color.clone(), roughness: mt.roughness, metalness: mt.metalness, side: mt.side, emissive: mt.emissive ? mt.emissive.clone() : undefined });
      if (mt.map) m.map = flatTex(mt.map);
      if (mt.normalMap) { m.normalMap = flatTex(mt.normalMap); m.normalScale = mt.normalScale.clone(); }
    }
    m.name = mt.name || 'Misc'; cache.set(mt, m); return m;
  };
  const addFrom = (root, name) => {
    const gg = new THREE.Group(); gg.name = name; root.updateMatrixWorld(true);
    root.traverse(o => {
      if (!o.isMesh) return;
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      const src = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone();
      const groups = src.groups.length ? src.groups : [{ start: 0, count: src.attributes.position.count, materialIndex: 0 }];
      for (const gr of groups) {
        const mt = mats[gr.materialIndex] || mats[0];
        const g = new THREE.BufferGeometry();
        for (const key of ['position', 'normal', 'uv']) {
          const at = src.attributes[key]; if (!at) continue;
          g.setAttribute(key, new THREE.BufferAttribute(at.array.slice(gr.start * at.itemSize, (gr.start + gr.count) * at.itemSize), at.itemSize));
        }
        if (mt.map && g.attributes.uv) { const uv = g.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * mt.map.repeat.x, uv.getY(i) * mt.map.repeat.y); }
        g.applyMatrix4(o.matrixWorld);
        const mesh = new THREE.Mesh(g, exportMat(mt)); mesh.name = mt.name || 'Mesh'; gg.add(mesh);
      }
    });
    out.add(gg);
  };
  addFrom(house, 'House'); addFrom(roofs, 'Roofs'); addFrom(furniture, 'Furniture'); addFrom(site, 'Site_Works'); addFrom(trees, 'Olive_Trees');
  const s = new THREE.DirectionalLight(0xffe2b8, 3); s.name = 'Sun_21Jun_1900'; s.position.copy(sun.position); s.target.position.copy(sun.target.position); out.add(s, s.target);
  for (const [name, key] of [['Cam_Aerial', 'aerial'], ['Cam_Street', 'street'], ['Cam_Garden', 'garden'], ['Cam_Interior_Cutaway', 'interior']]) {
    const pr = presets[key](), c = new THREE.PerspectiveCamera(42, 16 / 9, 0.1, 900); c.name = name; c.position.copy(pr.pos); c.lookAt(pr.tgt); out.add(c);
  }
  return out;
};
window.__exportGLB = async function () {
  const buf = await new GLTFExporter().parseAsync(window.__buildExport(), { binary: true, maxTextureSize: 2048 });
  let s = ''; const u8 = new Uint8Array(buf); for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(s);
};
window.__exportTris = function () {
  const res = {}, sc = window.__buildExport(); sc.updateMatrixWorld(true);
  sc.traverse(o => {
    if (!o.isMesh || (o.parent && o.parent.name === 'Site_Ground')) return;
    const g = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry, q = g.attributes.position, arr = (res[o.material.name] ||= { color: '#' + o.material.color.getHexString(), tris: [] }).tris;
    for (let i = 0; i < q.count; i++) arr.push(+q.getX(i).toFixed(3), +q.getY(i).toFixed(3), +q.getZ(i).toFixed(3));
  });
  const arr = []; for (let z = G.z0; z < G.z1; z += 1) for (let x = G.x0; x < G.x1; x += 1) {
    const qq = (xx, zz) => [+xx.toFixed(3), +heightAt(xx, zz).toFixed(3), +zz.toFixed(3)];
    arr.push(...qq(x, z), ...qq(x, z + 1), ...qq(x + 1, z), ...qq(x + 1, z), ...qq(x, z + 1), ...qq(x + 1, z + 1));
  }
  res.Terrain_1m = { color: '#8f9a62', tris: arr };
  return JSON.stringify({ materials: res, boundary: PLOT.map(([x, z]) => [x, heightAt(x, z) + 0.02, z]) });
};
window.__view = k => { const pr = presets[k](); camera.position.copy(pr.pos); controls.target.copy(pr.tgt); controls.update(); if (k === 'interior') setRoof(false); else setRoof(true); };
window.__stop = () => renderer.setAnimationLoop(null);
window.__renderOnce = () => { controls.update(); renderer.render(scene, camera); };
