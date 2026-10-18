// مخططات Chart.js بهوية SmartRisk. تتطلب تحميل chart.umd.js قبل هذه الوحدة.
import { short, fmt } from './format.js';

export const C = {
  indigo: '#433ac1', indigoDeep: '#231d70', cyan: '#00cdfb', cyanSoft: 'rgba(0,215,255,.20)',
  blue: '#0d4bbc', ink: '#14103f', ink2: '#494678', line: '#dde2f3',
  safe: '#12b886', warn: '#f5a524', crit: '#ee4266', band: 'rgba(67,58,193,.26)',
};
export const PALETTE = [C.indigo, C.cyan, C.blue, '#8b7cf6', '#60d4e3', '#231d70'];

let ready = false;
function setup() {
  if (ready || !window.Chart) return;
  const D = Chart.defaults;
  D.font.family = "'IBM Plex Sans Arabic', 'IBM Plex Sans', Tahoma, sans-serif";
  D.font.size = 12.5;
  D.color = C.ink2;
  D.maintainAspectRatio = false;
  D.animation = { duration: 650, easing: 'easeOutQuart' };
  D.plugins.legend.rtl = true;
  D.plugins.legend.labels.usePointStyle = true;
  D.plugins.legend.labels.boxWidth = 8;
  D.plugins.tooltip.rtl = true;
  D.plugins.tooltip.titleAlign = 'right';
  D.plugins.tooltip.bodyAlign = 'right';
  D.plugins.tooltip.backgroundColor = '#140d52';
  D.plugins.tooltip.padding = 12;
  D.plugins.tooltip.cornerRadius = 10;
  D.plugins.tooltip.boxPadding = 4;
  D.plugins.tooltip.titleFont = { weight: '600' };
  D.elements.line.tension = 0.25;
  D.elements.point.radius = 0;
  D.elements.point.hoverRadius = 4;
  ready = true;
}

/** يعيد ضبط حجم كل المخططات الحيّة (بعد تحميل الخطوط، أو عودة التبويب، أو الرجوع من الذاكرة المؤقتة). */
function resizeAll() {
  if (!window.Chart) return;
  Object.values(Chart.instances).forEach((c) => { try { c.resize(); } catch { /* ignore */ } });
}
let hooked = false;
function hookGlobal() {
  if (hooked) return;
  hooked = true;
  window.addEventListener('pageshow', resizeAll);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) resizeAll(); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(resizeAll);
}

/**
 * ينتظر حتى تصبح اللوحة داخل الصفحة وبحجم فعلي (عرض وارتفاع > 0) ثم ينفّذ cb.
 * هذا يمنع رسم المخطط داخل عنصر غير مُدرج بعد أو مخفي أو بحجم صفر، وهو سبب
 * اختفاء المخططات حتى تحديث الصفحة.
 */
function whenReady(canvas, cb) {
  const ok = () => {
    const box = canvas.parentElement;
    return !!window.Chart && canvas.isConnected && box && box.clientWidth > 0 && box.clientHeight > 0;
  };
  if (ok()) { cb(); return; }
  let done = false;
  let ro = null;
  let timer = null;
  const stop = () => { done = true; if (ro) ro.disconnect(); clearInterval(timer); clearTimeout(giveUp); };
  const tryNow = () => { if (done || !ok()) return; stop(); cb(); };
  const box = canvas.parentElement;
  if (box && typeof ResizeObserver !== 'undefined') { ro = new ResizeObserver(tryNow); ro.observe(box); }
  timer = setInterval(tryNow, 100);
  // محاولة أخيرة بعد 5 ثوانٍ: نرسم إن كانت اللوحة ما زالت في الصفحة.
  const giveUp = setTimeout(() => { if (done) return; stop(); if (window.Chart && canvas.isConnected) cb(); }, 5000);
}

export function mk(canvas, config) {
  hookGlobal();
  canvas.style.direction = 'ltr';
  const token = (canvas._skToken = (canvas._skToken || 0) + 1);
  whenReady(canvas, () => {
    if (canvas._skToken !== token) return; // طلب أحدث أو تمّ تدمير اللوحة
    setup();
    const old = Chart.getChart(canvas);
    if (old) old.destroy();
    new Chart(canvas, config);
  });
}

export function destroyAll(root) {
  root.querySelectorAll('canvas').forEach((c) => {
    c._skToken = (c._skToken || 0) + 1; // يلغي أي رسم معلّق لهذه اللوحة
    const ch = window.Chart && Chart.getChart(c);
    if (ch) ch.destroy();
  });
}

const moneyTick = (v) => short(v);
const gridY = { color: C.line, drawBorder: false };
const tipMoney = (ctx) => ` ${ctx.dataset.label || ''}: ${fmt(ctx.parsed.y ?? ctx.parsed.x)} دج`;

export function monthTicks(n) { return Array.from({ length: n }, (_, i) => `ش${i + 1}`); }

/** مروحة السيولة (مونت كارلو) */
export function cashFan(canvas, { months, bands, baseline }) {
  const labels = monthTicks(months.length);
  const zero = months.map(() => 0);
  const ds = (label, data, o = {}) => ({ label, data, borderWidth: 0, pointRadius: 0, fill: false, ...o });
  return mk(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        ds('أسوأ 5%', bands.p5, { borderWidth: 1.2, borderColor: 'rgba(238,66,102,.7)', borderDash: [4, 3] }),
        ds('أفضل 5%', bands.p95, { fill: '-1', backgroundColor: C.cyanSoft, borderWidth: 1.2, borderColor: 'rgba(0,160,200,.7)', borderDash: [4, 3] }),
        ds('25%', bands.p25, { _hide: true }),
        ds('75%', bands.p75, { fill: '-1', backgroundColor: C.band, _hide: true }),
        ds('الوسيط', bands.p50, { borderWidth: 2.6, borderColor: C.indigoDeep }),
        ds('التوقع الأساسي', baseline, { borderWidth: 1.8, borderColor: C.ink, borderDash: [2, 3] }),
        ds('الصفر', zero, { borderWidth: 1.4, borderColor: C.crit, _hide: true }),
      ],
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { filter: (i, d) => !d.datasets[i.datasetIndex]._hide } },
        tooltip: { filter: (i) => !i.dataset._hide, callbacks: { label: tipMoney } },
      },
      scales: { y: { grid: gridY, ticks: { callback: moneyTick } }, x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } } },
    },
  });
}

/** أعمدة/خطوط عامة */
export function combo(canvas, { labels, datasets, stacked = false, money = true, legend = true, height }) {
  return mk(canvas, {
    type: 'bar',
    data: { labels, datasets: datasets.map((d, i) => ({
      type: d.type || 'bar', label: d.label, data: d.data,
      backgroundColor: d.type === 'line' ? 'transparent' : (d.color || PALETTE[i % PALETTE.length]),
      borderColor: d.color || PALETTE[i % PALETTE.length], borderWidth: d.type === 'line' ? 2.4 : 0,
      borderRadius: d.type === 'line' ? 0 : 5, pointRadius: d.type === 'line' ? 3 : 0, fill: false,
      borderDash: d.dash || [], order: d.type === 'line' ? 0 : 1, maxBarThickness: 46,
    })) },
    options: {
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { display: legend }, tooltip: { callbacks: { label: money ? tipMoney : undefined } } },
      scales: { x: { stacked, grid: { display: false } }, y: { stacked, grid: gridY, ticks: { callback: money ? moneyTick : undefined } } },
    },
  });
}

export function lines(canvas, { labels, datasets, money = true, zero = false }) {
  const ds = datasets.map((d, i) => ({
    label: d.label, data: d.data, borderColor: d.color || PALETTE[i], backgroundColor: 'transparent',
    borderWidth: d.width || 2.4, borderDash: d.dash || [], pointRadius: 0, fill: false,
  }));
  if (zero) ds.push({ label: 'الصفر', data: labels.map(() => 0), borderColor: C.crit, borderWidth: 1.2, pointRadius: 0, _hide: true });
  return mk(canvas, {
    type: 'line', data: { labels, datasets: ds },
    options: {
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { filter: (i, d) => !d.datasets[i.datasetIndex]._hide } }, tooltip: { filter: (i) => !i.dataset._hide, callbacks: { label: money ? tipMoney : undefined } } },
      scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } }, y: { grid: gridY, ticks: { callback: money ? moneyTick : undefined } } },
    },
  });
}

/** مخطط الإعصار (Tornado) */
export function tornado(canvas, rows, base, labels = ['−', '+']) {
  const names = rows.map((r) => r.label);
  return mk(canvas, {
    type: 'bar',
    data: {
      labels: names,
      datasets: [
        { label: labels[0], data: rows.map((r) => [base, r.low]), backgroundColor: C.indigo, borderRadius: 4 },
        { label: labels[1], data: rows.map((r) => [base, r.high]), backgroundColor: C.cyan, borderRadius: 4 },
      ],
    },
    options: {
      indexAxis: 'y', interaction: { mode: 'index', intersect: false },
      plugins: { tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${fmt(c.raw[1])} دج (${c.raw[1] - base >= 0 ? '+' : '−'}${fmt(Math.abs(c.raw[1] - base))})` } } },
      scales: { x: { grid: gridY, ticks: { callback: moneyTick } }, y: { grid: { display: false }, ticks: { font: { size: 12.5 } } } },
    },
  });
}

/** مدرج تكراري */
export function histogram(canvas, hist, { unit = 'دج', splitAtZero = true } = {}) {
  const mids = hist.counts.map((_, i) => (hist.edges[i] + hist.edges[i + 1]) / 2);
  const total = hist.counts.reduce((a, b) => a + b, 0) || 1;
  return mk(canvas, {
    type: 'bar',
    data: {
      labels: mids.map((m) => short(m)),
      datasets: [{ label: 'نسبة السيناريوهات', data: hist.counts.map((c) => (c / total) * 100), borderRadius: 3, categoryPercentage: 1, barPercentage: .96,
        backgroundColor: mids.map((m) => (splitAtZero && m < 0 ? C.crit : C.indigo)) }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: (i) => `${i[0].label} ${unit}`, label: (c) => ` ${c.parsed.y.toFixed(1)}% من السيناريوهات` } } },
      scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { grid: gridY, ticks: { callback: (v) => v + '%' } } },
    },
  });
}

/** منحنى التعادل */
export function breakevenChart(canvas, curve, avg, be) {
  const xs = curve.revenue;
  return mk(canvas, {
    type: 'line',
    data: {
      labels: xs.map((x) => short(x)),
      datasets: [
        { label: 'الإيراد', data: xs, borderColor: C.cyan, borderWidth: 2.6, pointRadius: 0 },
        { label: 'إجمالي التكاليف', data: curve.total_cost, borderColor: C.indigoDeep, borderWidth: 2.6, pointRadius: 0 },
      ],
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      plugins: { tooltip: { callbacks: { label: tipMoney } } },
      scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { grid: gridY, ticks: { callback: moneyTick } } },
    },
  });
}
