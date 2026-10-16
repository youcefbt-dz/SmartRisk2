import { h, mount } from '../lib/dom.js';
import { dz, pct, fmt1, months } from '../lib/format.js';
import { panel, tabs, note, pill, button } from '../components/ui.js';
import { numberField } from '../components/form.js';
import { lines } from '../lib/charts.js';
import { asyncBlock, chartBox, after, table } from './_shared.js';

function pricing(ctx) {
  let margin = 25;
  const host = h('div', { class: 'stack' });
  const out = h('div', { class: 'stack' });
  async function run() {
    mount(out, h('div', { class: 'empty' }, h('span', { class: 'spin' })));
    try {
      const d = await ctx.store.analyze('pricing', { margin });
      mount(out, ...d.products.map((p) => {
        const box = chartBox('chart--h260');
        after(() => lines(box.canvas, { labels: p.curve.map((c) => fmt1(c.price).replace('.0', '')), datasets: [{ label: 'هامش المساهمة الشهري', data: p.curve.map((c) => c.contribution) }] }));
        return panel({ title: p.name, ico: 'coins', actions: pill(p.level) },
          h('div', { class: 'grid grid--4' },
            h('div', {}, h('small', { class: 'muted' }, 'السعر الحالي'), h('div', { class: 'big num', style: { fontWeight: 700, fontSize: '1.3rem' } }, dz(p.price))),
            h('div', {}, h('small', { class: 'muted' }, 'أدنى سعر بلا خسارة'), h('div', { class: 'num', style: { fontWeight: 700, fontSize: '1.3rem' } }, dz(p.floor))),
            h('div', {}, h('small', { class: 'muted' }, `السعر الموصى به (هامش ${d.margin}%)`), h('div', { class: 'num', style: { fontWeight: 700, fontSize: '1.3rem' } }, dz(p.recommended))),
            h('div', {}, h('small', { class: 'muted' }, 'الأمثل مع مرونة الطلب'), h('div', { class: 'num', style: { fontWeight: 700, fontSize: '1.3rem' } }, dz(p.elastic_optimum)))),
          h('div', { style: { marginTop: '14px' } }, box.el),
          h('p', { class: 'muted' }, `مرونة الطلب ${p.elasticity}. أفضل نقطة على المنحنى: ${dz(p.best_on_curve.price)} (تتحمّل تراجع المبيعات إلى ${fmt1(p.best_on_curve.units)} وحدة).`));
      }));
    } catch (e) { mount(out, note(e.message, 'crit')); }
  }
  mount(host, h('div', { class: 'row' }, numberField({ label: 'هامش الربح المستهدف', value: margin, unit: '%', min: 0, max: 90, onInput: (v) => { margin = v; } }), button('احسب', { ico: 'play', onClick: run })), out);
  run();
  return host;
}

function optimizer(ctx) {
  return asyncBlock(() => ctx.store.analyze('optimizer'), (o) => {
    if (!o.feasible) return note('لا يوجد حل ممكن بالقيود الحالية. راجع الطاقة والميزانية في بيانات المشروع.', 'crit');
    return h('div', { class: 'stack' },
      o.assumed_bounds ? note('لم تُحدَّد سقوف للمبيعات، فاستُخدم سقف افتراضي ≈ 3× المبيعات الحالية. أضف سقف الطلب والطاقة في بيانات المشروع لنتيجة أدق.', 'warn') : null,
      panel({ title: `المساهمة الشهرية: ${dz(o.current_contribution)} ← ${dz(o.optimal_contribution)}`, sub: `زيادة محتملة ${dz(o.gain)} (${pct(o.gain_pct)})`, ico: 'trend', accent: true },
        table(o.rows, [
          { label: 'المنتج', get: (r) => r.name },
          { label: 'الحالي', num: true, get: (r) => fmt1(r.current) },
          { label: 'الأمثل', num: true, get: (r) => fmt1(r.optimal) },
          { label: 'مساهمة الوحدة', num: true, get: (r) => dz(r.unit_contribution) },
        ])),
      o.shadow_prices.length ? panel({ title: 'القيمة الحدّية للموارد', sub: 'كم تربح إضافةً لو زاد المورد بوحدة واحدة.' }, table(o.shadow_prices, [
        { label: 'المورد', get: (r) => r.name || r.resource }, { label: 'القيمة', num: true, get: (r) => dz(r.value ?? r.shadow_price) }])) : null);
  });
}

function investment(ctx) {
  const st = { outlay: 500000, rate: 12, flows: [200000, 200000, 200000] };
  const host = h('div', { class: 'stack' });
  const manual = h('div', { class: 'stack' });
  const flowsBox = h('div', { class: 'form-grid' });
  const drawFlows = () => mount(flowsBox, ...st.flows.map((f, i) => numberField({ label: `تدفق السنة ${i + 1}`, value: f, unit: 'دج', onInput: (v) => { st.flows[i] = v; } })));
  drawFlows();
  async function calc() {
    try {
      const r = await ctx.store.analyze('investment', { flows: st.flows, outlay: st.outlay, rate: st.rate });
      mount(manual, h('div', { class: 'stat-row' },
        h('div', { class: 'rs' }, h('h4', {}, 'صافي القيمة الحالية NPV'), h('div', { class: 'big num' }, dz(r.npv))),
        h('div', { class: 'rs' }, h('h4', {}, 'معدل العائد الداخلي IRR'), h('div', { class: 'big num' }, r.irr === null ? '—' : `${fmt1(r.irr)}%`)),
        h('div', { class: 'rs' }, h('h4', {}, 'فترة الاسترداد'), h('div', { class: 'big num' }, r.payback_years ? `${r.payback_years} سنة` : '—')),
        h('div', { class: 'rs' }, h('h4', {}, 'مؤشر الربحية'), h('div', { class: 'big num' }, r.profitability_index === null ? '—' : fmt1(r.profitability_index)))),
        note(r.npv > 0 ? 'القيمة الحالية موجبة: المشروع يعوّض كلفة رأس المال عند هذا المعدل.' : 'القيمة الحالية سالبة: العائد لا يغطي تكلفة رأس المال.', r.npv > 0 ? 'safe' : 'crit'));
    } catch (e) { mount(manual, note(e.message, 'crit')); }
  }
  const proj = asyncBlock(() => ctx.store.analyze('investment'), (r) => h('div', { class: 'stat-row' },
    h('div', { class: 'rs' }, h('h4', {}, 'NPV (مع القيمة النهائية)'), h('div', { class: 'big num' }, dz(r.npv))),
    h('div', { class: 'rs' }, h('h4', {}, 'IRR سنوي'), h('div', { class: 'big num' }, r.irr === null ? '—' : r.irr > 200 ? '+200%' : `${fmt1(r.irr)}%`)),
    h('div', { class: 'rs' }, h('h4', {}, 'استرداد الاستثمار'), h('div', { class: 'big num' }, r.payback_months ? `${r.payback_months} شهر` : '—')),
    h('div', { class: 'rs' }, h('h4', {}, 'أقصى حاجة تمويل'), h('div', { class: 'big num' }, dz(r.peak_funding_need)))));
  mount(host,
    panel({ title: 'جدوى مشروعك الحالي', sub: 'من التدفق الحر للمشروع بعد استبعاد التمويل. القيمة النهائية تفترض استمرار آخر سنة، فاعتبرها تقديرية.', ico: 'coins', accent: true }, proj),
    panel({ title: 'حاسبة استثمار منفصلة', sub: 'جرّب فكرة مثل شراء آلة أو فتح فرع.', ico: 'scale' },
      h('div', { class: 'form-grid' }, numberField({ label: 'الاستثمار الأولي', value: st.outlay, unit: 'دج', onInput: (v) => { st.outlay = v; } }), numberField({ label: 'معدل الخصم', value: st.rate, unit: '%', onInput: (v) => { st.rate = v; } })),
      flowsBox,
      h('div', { class: 'row', style: { margin: '14px 0' } }, button('أضف سنة', { variant: 'ghost', size: 'sm', ico: 'plus', onClick: () => { if (st.flows.length < 15) { st.flows.push(st.flows[st.flows.length - 1] || 0); drawFlows(); } } }), button('احسب', { ico: 'play', onClick: calc })),
      manual));
  calc();
  return host;
}

function financing(ctx) {
  let amount = '';
  const host = h('div', { class: 'stack' });
  const out = h('div', { class: 'stack' });
  async function run() {
    mount(out, h('div', { class: 'empty', 'aria-busy': 'true' }, h('span', { class: 'spin' }), h('p', {}, 'جارٍ مقارنة المصادر بالمحاكاة…')));
    try {
      const d = await ctx.store.analyze('financing', amount ? { amount } : {});
      mount(out, note(`مبلغ التمويل المفترض ${dz(d.amount)}. ${d.verify_note}`, 'warn'),
        panel({ title: 'مقارنة المصادر', flush: true, ico: 'bank' }, table(d.options, [
          { label: 'المصدر', get: (o) => h('span', {}, o.name, o.id === d.recommended ? pill('safe', 'الأنسب') : null) },
          { label: 'أدنى رصيد', num: true, get: (o) => dz(o.min_cash), neg: (o) => o.min_cash < 0 },
          { label: 'احتمال النفاد 12ش', num: true, get: (o) => pct(o.p_ruin_12) },
          { label: 'رأس المال المعرّض 95%', num: true, get: (o) => dz(o.car95) },
          { label: 'إجمالي الفوائد', num: true, get: (o) => dz(o.total_interest) },
          { label: 'التخفيف', num: true, get: (o) => (o.dilution === null ? '—' : pct(o.dilution, 1)) },
          { label: 'ملاحظة', get: (o) => o.note || '' },
        ])));
    } catch (e) { mount(out, note(e.message, 'crit')); }
  }
  mount(host, h('div', { class: 'row' }, numberField({ label: 'مبلغ التمويل (اتركه فارغاً للتقدير التلقائي)', value: '', unit: 'دج', onInput: (v) => { amount = v || ''; } }), button('قارن', { ico: 'play', onClick: run })), out);
  run();
  return host;
}

export default {
  mount(el, ctx) {
    const TABS = [['pricing', 'التسعير'], ['optimizer', 'مزيج المنتجات'], ['investment', 'جدوى الاستثمار'], ['financing', 'مصادر التمويل']];
    const views = { pricing, optimizer, investment, financing };
    const body = h('div');
    const open = (id) => { mount(body, views[id](ctx)); };
    el.append(h('div', { class: 'stack' }, tabs(TABS, 'pricing', open), body));
    open('pricing');
  },
};
