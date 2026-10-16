import { h, mount } from '../lib/dom.js';
import { dz, pct } from '../lib/format.js';
import { panel, note, pill, button, emptyState } from '../components/ui.js';
import { lines } from '../lib/charts.js';
import { asyncBlock, chartBox, after, table } from './_shared.js';

const FIELDS = [['revenue', 'الإيرادات'], ['variable_costs', 'تكاليف متغيرة'], ['fixed_costs', 'تكاليف ثابتة (أجور+ثوابت)'], ['cash', 'الرصيد النقدي']];

export default {
  mount(el, ctx) {
    const { store } = ctx;
    const d = store.state.data;
    const T = d.horizon;
    const editor = h('div', { class: 'table-wrap' });
    const result = h('div', { class: 'stack' });

    const find = (m) => d.actuals.find((a) => a.month === m);
    function drawEditor() {
      mount(editor, h('table', { class: 'table' },
        h('thead', {}, h('tr', {}, h('th', {}, 'الشهر'), ...FIELDS.map(([, l]) => h('th', {}, l)))),
        h('tbody', {}, ...Array.from({ length: Math.min(T, 24) }, (_, i) => i + 1).map((m) => h('tr', {}, h('td', {}, `الشهر ${m}`),
          ...FIELDS.map(([k]) => {
            const a = find(m);
            const inp = h('input', { class: 'track-input', type: 'number', step: 'any', value: a && a[k] !== null && a[k] !== undefined ? a[k] : '', 'aria-label': `${k} الشهر ${m}` });
            inp.addEventListener('input', () => {
              store.change((x) => {
                let row = x.actuals.find((r) => r.month === m);
                if (!row) { row = { month: m, revenue: 0, variable_costs: 0, fixed_costs: 0, cash: null }; x.actuals.push(row); x.actuals.sort((p, q) => p.month - q.month); }
                row[k] = inp.value === '' ? (k === 'cash' ? null : 0) : Number(inp.value);
                const empty = row.revenue === 0 && row.variable_costs === 0 && row.fixed_costs === 0 && row.cash === null;
                if (empty) x.actuals.splice(x.actuals.indexOf(row), 1);
              });
            });
            return h('td', {}, inp);
          }))))));
    }
    drawEditor();

    async function run() {
      mount(result, h('div', { class: 'empty' }, h('span', { class: 'spin' })));
      try {
        const t = await store.analyze('tracking');
        if (!t.months_tracked) { mount(result, emptyState('لا توجد أرقام فعلية بعد', 'أدخل إيرادات وتكاليف الأشهر المنتهية أعلاه ثم اضغط «حلّل الانحراف».')); return; }
        const v = (x) => (x === null || x === undefined ? '—' : h('span', { class: x < 0 ? 'var-neg' : 'var-pos' }, pct(x, 0)));
        const box = chartBox('chart--h260');
        const rf = t.reforecast;
        mount(result,
          t.alerts.length ? panel({ title: 'تنبيهات', ico: 'bell' }, h('ul', { class: 'advice' }, ...t.alerts.map((a) => h('li', { class: `is-${a.level}` }, h('header', {}, h('b', {}, a.title), pill(a.level)), h('p', {}, a.text))))) : note('لا توجد انحرافات مقلقة. استمر.', 'safe'),
          panel({ title: 'الفعلي مقابل المتوقع', flush: true, ico: 'table' }, table(t.rows, [
            { label: 'الشهر', get: (r) => r.month },
            { label: 'إيراد متوقع', num: true, get: (r) => dz(r.revenue.plan) },
            { label: 'إيراد فعلي', num: true, get: (r) => dz(r.revenue.actual) },
            { label: 'الانحراف', num: true, get: (r) => v(r.revenue.var) },
            { label: 'ربح متوقع', num: true, get: (r) => dz(r.profit.plan) },
            { label: 'ربح فعلي', num: true, get: (r) => dz(r.profit.actual), neg: (r) => r.profit.actual < 0 },
            { label: 'رصيد فعلي', num: true, get: (r) => (r.cash.actual === null ? '—' : dz(r.cash.actual)) },
          ])),
          rf ? panel({ title: 'توقع محدَّث', sub: `يعدّل الطلب والتكاليف المستقبلية بحسب آخر 3 أشهر فعلية (المبيعات ×${rf.scales.demand.toFixed(2)}).`, ico: 'refresh', accent: true }, box.el,
            h('p', { class: 'muted', style: { marginTop: '10px' } }, rf.cash_out_month ? `بحسب الاتجاه الفعلي تنفد السيولة في الشهر ${rf.cash_out_month}.` : `لا تنفد السيولة؛ أدنى رصيد متوقع ${dz(rf.min_cash)}.`)) : null);
        if (rf) after(() => lines(box.canvas, { labels: rf.months.map((m) => `ش${m}`), zero: true, datasets: [{ label: 'التوقع الأصلي', data: rf.base_cash, dash: [5, 4], color: '#8d8ab0' }, { label: 'التوقع المحدَّث', data: rf.cash, color: '#433ac1' }] }));
      } catch (e) { mount(result, note(e.message, 'crit')); }
    }

    el.append(h('div', { class: 'stack' },
      note('أدخل أرقامك الفعلية شهراً بشهر. «الثوابت» = الأجور والمصاريف الثابتة والاستثنائية. الحفظ تلقائي.'),
      panel({ title: 'الأرقام الفعلية', ico: 'calendar', flush: true }, editor, h('div', { style: { padding: '14px 18px' } }, button('حلّل الانحراف', { ico: 'play', onClick: run }))),
      result));
    run();
  },
};
