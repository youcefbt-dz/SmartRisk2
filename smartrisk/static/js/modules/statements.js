import { h, mount } from '../lib/dom.js';
import { fmt, monthLabel } from '../lib/format.js';
import { panel, tabs, segmented, button, note, download } from '../components/ui.js';
import { combo, lines } from '../lib/charts.js';
import { asyncBlock, chartBox, after } from './_shared.js';

const TITLES = { income: 'قائمة الدخل', cashflow: 'قائمة التدفقات النقدية', balance: 'الميزانية' };

export default {
  mount(el, ctx) {
    const { store } = ctx;
    let tab = 'income';
    let mode = 'annual';
    let data = null;
    const out = h('div', { class: 'stack' });

    function draw() {
      const lines_ = data[tab];
      const isAnnual = mode === 'annual';
      const n = isAnnual ? data.years.length : data.months.length;
      const heads = isAnnual ? data.years.map((y) => `السنة ${y}`) : data.months.map((m) => `${monthLabel(store.state.data.start_month, m)} ${m}`);
      const table = h('div', { class: 'table-wrap', style: { maxHeight: '620px' } }, h('table', { class: 'table table--statement' },
        h('thead', {}, h('tr', {}, h('th', {}, 'البند'), ...heads.map((t) => h('th', { class: 'n' }, t)))),
        h('tbody', {}, ...lines_.map((l) => {
          const vals = isAnnual ? l.annual : l.monthly;
          return h('tr', { class: l.total ? 'is-total' : '' }, h('td', {}, l.label),
            ...vals.slice(0, n).map((v) => h('td', { class: `n${v < -0.5 ? ' is-neg' : ''}` }, fmt(v))));
        }))));

      const box = chartBox('chart--h260');
      const pick = (k) => lines_.find((l) => l.key === k);
      const labels = isAnnual ? data.years.map((y) => `السنة ${y}`) : data.months.map((m) => `ش${m}`);
      const series = (l) => (isAnnual ? l.annual : l.monthly);
      after(() => {
        if (tab === 'income') combo(box.canvas, { labels, datasets: [{ label: 'الإيرادات', data: series(pick('revenue')) }, { label: 'الربح الصافي', data: series(pick('net_income')), type: 'line', color: '#ee4266' }].filter((d) => d.data) });
        else if (tab === 'cashflow') {
          combo(box.canvas, { labels, datasets: [{ label: pick('net_cash_flow').label, data: series(pick('net_cash_flow')) }, { label: pick('cash').label, data: series(pick('cash')), type: 'line', color: '#231d70' }] });
        } else {
          const cash = pick('cash');
          lines(box.canvas, { labels, datasets: [{ label: cash.label, data: series(cash) }], zero: true });
        }
      });
      mount(out, panel({ title: TITLES[tab], ico: 'table', flush: true }, table), panel({ title: 'الرسم', sub: isAnnual ? 'سنوي' : 'شهري' }, box.el),
        data.regime_notes?.length ? note(data.regime_notes.join(' • '), 'warn') : null,
        h('p', { class: 'faint' }, `فحص توازن الميزانية: ${Math.abs(data.balance_check) < 1 ? 'متوازنة ✓' : 'غير متوازنة — راجع المدخلات'}`));
    }

    const toolbar = h('div', { class: 'row row--between' },
      tabs([['income', 'الدخل'], ['cashflow', 'التدفقات النقدية'], ['balance', 'الميزانية']], tab, (t) => { tab = t; data && draw(); }),
      h('div', { class: 'row' },
        segmented([['annual', 'سنوي'], ['monthly', 'شهري']], mode, (m) => { mode = m; data && draw(); }),
        button('CSV', { variant: 'ghost', size: 'sm', ico: 'download', onClick: () => download(`/api/projects/${store.state.id}/export/${tab}.csv`) }),
        button('Excel', { variant: 'ghost', size: 'sm', ico: 'download', onClick: () => download(`/api/projects/${store.state.id}/export.xlsx`) })));

    el.append(h('div', { class: 'stack' }, toolbar, asyncBlock(() => store.analyze('statements'), (d) => { data = d; draw(); return out; })));
  },
};
