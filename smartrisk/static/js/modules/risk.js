import { h, mount } from '../lib/dom.js';
import { dz, pct, fmt, short } from '../lib/format.js';
import { panel, tabs, segmented, note, pill, button, term } from '../components/ui.js';
import { numberField, textField } from '../components/form.js';
import { cashFan, tornado, histogram, lines, breakevenChart, destroyAll } from '../lib/charts.js';
import { asyncBlock, chartBox, after, table } from './_shared.js';

const lvlRuin = (p) => (p >= 0.2 ? 'crit' : p >= 0.05 ? 'warn' : 'safe');
const stat = (label, value, level, tip) => h('div', { class: `rs${level ? ' rs--' + level : ''}` }, h('h4', {}, h('small', { class: 'muted' }, label, tip ? term(tip) : null)), h('div', { class: 'big num' }, value));

// ---------------------------------------------------------------- مونت كارلو
function monteCarlo(ctx) {
  return asyncBlock(() => ctx.store.analyze('montecarlo'), (mc) => {
    const fan = chartBox('chart--h320');
    const h1 = chartBox('chart--h260');
    const h2 = chartBox('chart--h260');
    after(() => {
      cashFan(fan.canvas, { months: mc.months, bands: mc.bands, baseline: mc.baseline_cash });
      histogram(h1.canvas, mc.final_cash_hist);
      histogram(h2.canvas, mc.min_cash_hist);
    });
    return h('div', { class: 'stack' },
      h('div', { class: 'stat-row' },
        stat('احتمال نفاد السيولة خلال 6 أشهر', pct(mc.p_ruin_6), lvlRuin(mc.p_ruin_6), 'pruin'),
        stat('خلال 12 شهراً', pct(mc.p_ruin_12), lvlRuin(mc.p_ruin_12)),
        stat('خلال كامل المدة', pct(mc.p_ruin_horizon), lvlRuin(mc.p_ruin_horizon)),
        stat('رأس المال المعرّض للخطر 95%', dz(mc.cash_at_risk_95), '', 'car'),
        stat('رأس المال المعرّض للخطر 99%', dz(mc.cash_at_risk_99)),
        stat('احتمال خسارة السنة الأولى', pct(mc.ni_y1.p_loss), lvlRuin(mc.ni_y1.p_loss))),
      panel({ title: 'مروحة السيولة', sub: `${mc.n.toLocaleString('en-US')} سيناريو. الخط الغامق وسيط، والمظلل بين أفضل 5% وأسوأ 5%.`, ico: 'dice', accent: true }, fan.el),
      h('div', { class: 'grid grid--2' },
        panel({ title: 'توزيع الرصيد النهائي', sub: 'الأحمر = سيناريوهات تنتهي بعجز.' }, h1.el,
          h('p', { class: 'muted', style: { marginTop: '10px' } }, `الوسيط ${dz(mc.median_final_cash)} · متوسط الخسارة في أسوأ الحالات ${dz(mc.expected_shortfall_final)}`)),
        panel({ title: 'توزيع أدنى رصيد', sub: 'كم تنخفض الخزينة في أسوأ لحظة.' }, h2.el,
          h('p', { class: 'muted', style: { marginTop: '10px' } }, `المتوقع ${dz(mc.expected_min_cash)}`))),
      note('النتائج احتمالية وتعتمد على درجة عدم اليقين في بيانات المشروع (قسم «بيانات المشروع ← الضرائب والمخاطر»).'));
  }, { loadingText: 'جارٍ تشغيل المحاكاة…' });
}

// ---------------------------------------------------------------- الصدمات العكسية
function reverse(ctx) {
  return asyncBlock(() => ctx.store.analyze('reverse_stress'), (r) => {
    const rows = r.items.map((i) => {
      const lvl = i.status === 'already' ? 'crit' : i.status === 'never' ? 'safe' : i.threshold < 25 ? 'crit' : i.threshold < 50 ? 'warn' : 'safe';
      const w = i.status === 'found' ? Math.min(100, i.threshold) : i.status === 'already' ? 0 : 100;
      return h('div', { class: `rs rs--${lvl}` },
        h('h4', {}, i.label, pill(lvl, i.status === 'already' ? 'متعثر' : i.status === 'never' ? 'صامد' : `${Math.round(i.threshold)}%`)),
        h('div', { class: `meter meter--${lvl}`, role: 'img', 'aria-label': i.statement }, h('i', { style: { width: `${w}%` } })),
        h('p', { class: 'muted' }, i.statement));
    });
    const c = r.combined;
    return h('div', { class: 'stack' },
      note('كلما كان الرقم أصغر كان المشروع أهشّ أمام هذا العامل. الاختبار يبحث عن حجم الصدمة التي تُنفد السيولة (أو تحقق خسارة سنوية).', c.status === 'already' ? 'crit' : ''),
      h('div', { class: 'grid grid--2' }, ...rows),
      panel({ title: 'صدمة مركّبة', sub: 'مبيعات أقل، تكلفة أعلى وتحصيل أبطأ في آن واحد.', ico: 'target', accent: true }, h('p', { style: { fontSize: '1.1rem', fontWeight: 600 } }, c.statement)));
  });
}

// ---------------------------------------------------------------- الحساسية
function sensitivity(ctx) {
  let metric = 'net_income_y1';
  let p = 10;
  const body = h('div', { class: 'stack' });
  const host = h('div', { class: 'stack' });
  let data = null;
  const draw = () => {
    const m = data.metrics[metric];
    const box = chartBox('chart--h380');
    mount(body, panel({ title: data.labels[metric], sub: `أثر تغيير كل عامل بمقدار ±${data.pct}%.`, ico: 'scale', accent: true }, box.el),
      panel({ title: 'التفاصيل', flush: true }, table(m.rows, [
        { label: 'العامل', get: (r) => r.label },
        { label: `−${data.pct}%`, num: true, get: (r) => dz(r.low), neg: (r) => r.low < 0 },
        { label: `+${data.pct}%`, num: true, get: (r) => dz(r.high), neg: (r) => r.high < 0 },
        { label: 'المدى', num: true, get: (r) => dz(r.swing) },
      ])));
    after(() => tornado(box.canvas, m.rows, m.base, [`−${data.pct}%`, `+${data.pct}%`]));
  };
  const load = async () => {
    mount(body, h('div', { class: 'empty', 'aria-busy': 'true' }, h('span', { class: 'spin' })));
    try { data = await ctx.store.analyze('sensitivity', { pct: p }); draw(); } catch (e) { mount(body, note(e.message, 'crit')); }
  };
  mount(host,
    h('div', { class: 'row' },
      segmented([['net_income_y1', 'الربح الصافي'], ['min_cash', 'أدنى رصيد'], ['final_cash', 'الرصيد النهائي']], metric, (v) => { metric = v; data && draw(); }),
      segmented([[5, '±5%'], [10, '±10%'], [20, '±20%']], p, (v) => { p = v; load(); })),
    body);
  load();
  return host;
}

// ---------------------------------------------------------------- السيناريوهات
const DEFAULT_SC = [
  { name: 'متشائم', demand_pct: -20, price_pct: -5, cost_pct: 15, fixed_pct: 5, collect_days: 15, color: 'crit' },
  { name: 'أساسي', demand_pct: 0, price_pct: 0, cost_pct: 0, fixed_pct: 0, collect_days: 0, color: 'base' },
  { name: 'متفائل', demand_pct: 15, price_pct: 3, cost_pct: -5, fixed_pct: 0, collect_days: -5, color: 'safe' },
];
const COLORS = { crit: '#ee4266', base: '#433ac1', safe: '#12a074' };

function scenarios(ctx) {
  const scs = DEFAULT_SC.map((s) => ({ ...s }));
  const host = h('div', { class: 'stack' });
  const result = h('div', { class: 'stack' });
  const editors = panel({ title: 'عرّف سيناريوهاتك', sub: 'التغيّرات نسب مئوية عن التوقع الأساسي.', ico: 'edit' },
    ...scs.map((s) => h('div', { class: 'sc-edit' },
      textField({ label: 'الاسم', value: s.name, maxlength: 20, onInput: (v) => { s.name = v; } }),
      ...[['demand_pct', 'المبيعات %'], ['price_pct', 'السعر %'], ['cost_pct', 'التكلفة %'], ['fixed_pct', 'الثوابت %'], ['collect_days', 'تحصيل (أيام)']].map(([k, l]) =>
        numberField({ label: l, value: s[k], onInput: (v) => { s[k] = v; } })))),
    h('div', { style: { marginTop: '14px' } }, button('احسب السيناريوهات', { ico: 'play', onClick: run })));
  async function run() {
    mount(result, h('div', { class: 'empty', 'aria-busy': 'true' }, h('span', { class: 'spin' })));
    try {
      const d = await ctx.store.analyze('scenarios', { scenarios: scs });
      const box = chartBox('chart--h320');
      mount(result,
        panel({ title: 'الرصيد النقدي بحسب السيناريو', ico: 'trend', accent: true }, box.el),
        panel({ title: 'المقارنة', flush: true }, table(d.scenarios, [
          { label: 'السيناريو', get: (s) => s.name },
          ...[0, 1, 2].map((i) => ({ label: `ربح السنة ${i + 1}`, num: true, get: (s) => dz(s.net_income_by_year[i]), neg: (s) => s.net_income_by_year[i] < 0 })),
          { label: 'أدنى رصيد', num: true, get: (s) => dz(s.min_cash), neg: (s) => s.min_cash < 0 },
          { label: 'الرصيد النهائي', num: true, get: (s) => dz(s.final_cash), neg: (s) => s.final_cash < 0 },
          { label: 'نفاد السيولة', get: (s) => (s.cash_out_month ? `الشهر ${s.cash_out_month}` : 'لا ينفد') },
        ])));
      after(() => lines(box.canvas, { labels: d.months.map((m) => `ش${m}`), zero: true, datasets: d.scenarios.map((s) => ({ label: s.name, data: s.cash, color: COLORS[s.color] || COLORS.base })) }));
    } catch (e) { mount(result, note(e.message, 'crit')); }
  }
  mount(host, editors, result);
  run();
  return host;
}

// ---------------------------------------------------------------- الجاهزية والمؤشرات
function readiness(ctx) {
  return asyncBlock(async () => {
    const [sc, z, be] = await Promise.all([ctx.store.analyze('scoring'), ctx.store.analyze('zscore'), ctx.store.analyze('breakeven')]);
    return { sc, z, be };
  }, ({ sc, z, be }) => {
    const bx = chartBox('chart--h260');
    after(() => breakevenChart(bx.canvas, be.curve, be.avg_monthly_revenue, be.breakeven_total));
    return h('div', { class: 'stack' },
      panel({ title: `جاهزية التمويل: ${Math.round(sc.score)} / 100`, sub: sc.verdict, ico: 'bank', accent: true },
        h('div', { class: 'stack' }, ...sc.components.map((c) => h('div', {},
          h('div', { class: 'row row--between' }, h('b', {}, c.title, c.term ? term(c.term) : null), h('span', { class: 'num' }, `${c.points.toFixed(1)} / ${c.weight}`)),
          h('div', { class: `meter meter--${c.level}`, style: { margin: '6px 0' } }, h('i', { style: { width: `${Math.round(c.score * 100)}%` } })),
          h('p', { class: 'muted' }, c.text), c.level !== 'safe' ? h('p', { style: { color: 'var(--indigo-600)', fontWeight: 500 } }, c.action) : null)))),
      h('div', { class: 'grid grid--2' },
        panel({ title: 'مؤشر Altman Z″', sub: 'يقيس احتمال التعثر: فوق 2.6 آمن، 1.1–2.6 رمادي، دونها خطر.', ico: 'gauge' },
          table(['y1', 'y2', 'y3'].map((k, i) => ({ k, i, ...z[k] })), [
            { label: 'السنة', get: (r) => `السنة ${r.i + 1}` },
            { label: 'Z″', num: true, get: (r) => r.z.toFixed(2) },
            { label: 'المنطقة', get: (r) => pill(r.zone, r.zone === 'safe' ? 'آمنة' : r.zone === 'warn' ? 'رمادية' : 'خطر') },
          ])),
        panel({ title: 'نقطة التعادل', sub: `التعادل الشهري ${dz(be.breakeven_total)} · هامش الأمان ${pct(be.margin_of_safety)}`, ico: 'target' }, bx.el)));
  });
}

export default {
  mount(el, ctx) {
    const TABS = [['mc', 'محاكاة مونت كارلو'], ['stress', 'ما الذي يكسر مشروعك'], ['sens', 'الحساسية'], ['scen', 'السيناريوهات'], ['ready', 'الجاهزية والتعادل']];
    const views = { mc: monteCarlo, stress: reverse, sens: sensitivity, scen: scenarios, ready: readiness };
    const body = h('div', {});
    const open = (id) => { destroyAll(body); mount(body, views[id](ctx)); };
    el.append(h('div', { class: 'stack' }, tabs(TABS, 'mc', open), body));
    open('mc');
  },
};
