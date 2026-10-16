// مروحة مسارات السيولة العشوائية: رسم الهوية الرئيسي (محاكاة توضيحية بذرتها ثابتة).
function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function gauss(r) { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

export function simulate({ n = 90, T = 24, start = 62, drift = 2.6, sigma = 10.5, level = 2.4, seed = 11 } = {}) {
  const r = rng(seed);
  const paths = [];
  for (let i = 0; i < n; i++) {
    const lv = gauss(r) * level;
    let x = start; const p = [x];
    for (let t = 1; t <= T; t++) { x += drift + lv + gauss(r) * sigma; p.push(x); }
    paths.push(p);
  }
  const med = Array.from({ length: T + 1 }, (_, t) => { const c = paths.map((p) => p[t]).sort((a, b) => a - b); return c[Math.floor(c.length / 2)]; });
  const horizon = 12;
  const mins = paths.map((p) => Math.min(...p.slice(0, horizon + 1))).sort((a, b) => a - b);
  const ruin = paths.filter((p) => Math.min(...p.slice(0, horizon + 1)) < 0).length / n;
  const car = Math.max(0, -mins[Math.floor(n * 0.05)]);
  return { paths, med, ruin, car, T };
}

export function drawFan(canvas, sim, progress = 1, { tone = 'light' } = {}) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  if (canvas.width !== Math.round(w * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const pad = { l: 10, r: 10, t: 24, b: 28 };
  const all = sim.paths.flat();
  const lo = Math.min(...all, -25), hi = Math.max(...all) * 1.02;
  const X = (t) => pad.l + (t / sim.T) * (w - pad.l - pad.r);
  const Y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * (h - pad.t - pad.b);
  const reveal = Math.floor(progress * sim.T);
  const frac = progress * sim.T - reveal;

  // مستوى الصفر
  ctx.save();
  ctx.setLineDash([6, 6]); ctx.strokeStyle = 'rgba(255,120,150,.9)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(pad.l, Y(0)); ctx.lineTo(w - pad.r, Y(0)); ctx.stroke();
  ctx.restore();

  const line = (p, color, width) => {
    ctx.beginPath();
    for (let t = 0; t <= reveal && t <= sim.T; t++) { t === 0 ? ctx.moveTo(X(t), Y(p[t])) : ctx.lineTo(X(t), Y(p[t])); }
    if (reveal < sim.T) { const a = p[reveal], b = p[reveal + 1]; ctx.lineTo(X(reveal + frac), Y(a + (b - a) * frac)); }
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
  };
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  sim.paths.forEach((p) => {
    const bad = Math.min(...p.slice(0, 13)) < 0;
    line(p, bad ? 'rgba(255,125,155,.50)' : 'rgba(255,255,255,.2)', 1.1);
  });
  line(sim.med, '#00d7ff', 3.4);
}
