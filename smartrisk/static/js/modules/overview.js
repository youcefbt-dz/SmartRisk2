import { h } from '../lib/dom.js';
import { icon } from '../lib/icons.js';
import { dz, pct, fmt, months, LEVEL_AR } from '../lib/format.js';
import { kpi, panel, pill, note, emptyState, button } from '../components/ui.js';
import { cashFan } from '../lib/charts.js';
import { asyncBlock, chartBox, after, table } from './_shared.js';

const HEAD = {
  safe: 'وضع المشروع المالي جيد',
  warn: 'المشروع قريب من منطقة الخطر',
  crit: 'المشروع في خطر مالي',
};

function description(s) {
  const m = s.metrics;
  const ruin = pct(m.p_ruin_12, 0);
  if (m.cash_out_month) return `تنفد السيولة في الشهر ${m.cash_out_month} حتى في التوقع الأساسي، واحتمال نفادها خلال 12 شهراً ${ruin}.`;
  return `السيولة مستقرة في التوقع الأساسي (أدنى رصيد ${dz(m.min_cash)})، واحتمال نفادها خلال 12 شهراً ${ruin}.`;
}

function verdict(s) {
  const lvl = s.overall;
  const sc = s.score || {};
  return h('section', { class: `verdict verdict--${lvl}` },
    h('div', { class: 'verdict__top' },
      h('div', { class: 'verdict__badge', 'aria-hidden': 'true' }, icon(lvl === 'safe' ? 'check' : 'alert')),
      h('div', {}, h('small', {}, 'الحكم العام'), h('h2', {}, HEAD[lvl] || s.overall_label), h('p', {}, description(s))),
      h('div', { class: 'ring', style: { '--v': Math.round(sc.score || 0) }, role: 'img', 'aria-label': `جاهزية التمويل ${Math.round(sc.score || 0)} من 100` },
        h('div', {}, h('b', {}, Math.round(sc.score || 0)), h('span', {}, 'جاهزية التمويل')))),
    h('div', { class: 'pillars' }, ...s.pillars.map((p) =>
      h('span', { class: `pillar pillar--${p.level}` }, h('i'), `${p.title}: `, h('b', {}, p.label)))));
}

function kpis(s) {
  const m = s.metrics;
  const lvlRuin = m.p_ruin_12 >= 0.2 ? 'crit' : m.p_ruin_12 >= 0.05 ? 'warn' : 'safe';
  const lvlMargin = m.net_margin_y1 >= 0.15 ? 'safe' : m.net_margin_y1 >= 0.05 ? 'warn' : 'crit';
  return h('div', { class: 'grid grid--4' },
    kpi({ label: 'الإيراد في السنة الأولى', value: dz(m.revenue_y1).replace(' دج', ''), unit: 'دج', sub: m.gross_margin_y1 !== undefined ? `هامش الربح الإجمالي ${pct(m.gross_margin_y1)}` : '' }),
    kpi({ label: 'هامش الربح الصافي', value: pct(m.net_margin_y1, 1), level: lvlMargin, term: 'netmargin', sub: `ربح صافٍ ${dz(m.net_income_y1)}` }),
    kpi({ label: 'أدنى رصيد نقدي', value: dz(m.min_cash).replace(' دج', ''), unit: 'دج', level: m.min_cash < 0 ? 'crit' : 'safe', sub: m.min_cash_month ? `في الشهر ${m.min_cash_month}` : '' }),
    kpi({ label: 'احتمال نفاد السيولة (12 شهراً)', value: pct(m.p_ruin_12, 0), level: lvlRuin, term: 'montecarlo', sub: `رأس المال المعرّض للخطر ${dz(m.cash_at_risk_95)}` }),
    kpi({ label: 'نقطة التعادل الشهرية', value: dz(m.breakeven_total).replace(' دج', ''), unit: 'دج', term: 'breakeven', sub: m.margin_of_safety !== null ? `هامش الأمان ${pct(m.margin_of_safety)}` : '' }),
    kpi({ label: 'مدة الصمود', value: months(m.runway_months), term: 'runway', level: m.runway_months < 6 ? 'crit' : m.runway_months < 12 ? 'warn' : 'safe', sub: 'بالتدفق الحالي' }),
    kpi({ label: 'دورة النقد', value: `${Math.round(m.cash_cycle_days)}`, unit: 'يوم', term: 'cashcycle', sub: `مخزون ${Math.round(m.inventory_days)} · زبائن ${Math.round(m.customer_days)} · موردون ${Math.round(m.supplier_days)}` }),
    kpi({ label: 'مؤشر Altman Z″', value: m.z_score === null ? '—' : m.z_score.toFixed(1), term: 'zscore', level: m.z_zone, sub: m.z_zone === 'safe' ? 'منطقة آمنة' : m.z_zone === 'warn' ? 'منطقة رمادية' : 'منطقة خطر' }));
}

function fanPanel(s) {
  const mc = s.mc;
  const box = chartBox('chart--h320');
  after(() => cashFan(box.canvas, { months: mc.months, bands: mc.bands, baseline: s.series.cash }));
  return panel({ title: 'مروحة السيولة المحتملة', sub: `${mc.n.toLocaleString('en-US')} سيناريو عشوائي للمبيعات والتكاليف وتأخر التحصيل. المنطقة المظللة هي المدى الأرجح.`, ico: 'dice', accent: true },
    box.el,
    h('div', { class: 'grid grid--3', style: { marginTop: '16px' } },
      h('div', {}, h('small', { class: 'muted' }, 'احتمال نفاد السيولة في 6 أشهر'), h('div', { class: 'num', style: { fontWeight: 700, fontSize: '1.3rem' } }, pct(mc.p_ruin_6))),
      h('div', {}, h('small', { class: 'muted' }, 'رأس المال المعرّض للخطر 95%'), h('div', { class: 'num', style: { fontWeight: 700, fontSize: '1.3rem' } }, dz(mc.cash_at_risk_95))),
      h('div', {}, h('small', { class: 'muted' }, 'احتمال خسارة السنة الأولى'), h('div', { class: 'num', style: { fontWeight: 700, fontSize: '1.3rem' } }, pct(mc.ni_y1.p_loss)))));
}

function planPanel(s) {
  const plan = s.advice.plan || [];
  return panel({ title: 'خطة العمل المقترحة', sub: 'أهم الخطوات مرتبة بالأولوية.', ico: 'target' },
    plan.length ? h('ol', { class: 'plan' }, ...plan.map((p) => h('li', {}, h('b', {}, p.title), h('span', {}, p.action))))
      : note('لا توجد إجراءات عاجلة. استمر في المتابعة الشهرية.', 'safe'));
}

function yearly(s) {
  return panel({ title: 'ملخص السنوات', ico: 'table', flush: true },
    table(s.yearly, [
      { label: 'السنة', get: (r) => `السنة ${r.year}` },
      { label: 'الإيرادات', num: true, get: (r) => dz(r.revenue) },
      { label: 'الربح الإجمالي', num: true, get: (r) => dz(r.gross_profit) },
      { label: 'EBITDA', num: true, get: (r) => dz(r.ebitda), neg: (r) => r.ebitda < 0 },
      { label: 'الربح الصافي', num: true, get: (r) => dz(r.net_income), neg: (r) => r.net_income < 0 },
      { label: 'التدفق التشغيلي', num: true, get: (r) => dz(r.cfo), neg: (r) => r.cfo < 0 },
      { label: 'رصيد آخر السنة', num: true, get: (r) => dz(r.end_cash), neg: (r) => r.end_cash < 0 },
    ]));
}

function advicePanel(s) {
  const items = s.advice.items || [];
  return panel({ title: 'ملاحظات وتوصيات', sub: `${items.length} ملاحظة`, ico: 'bolt' },
    items.length ? h('ul', { class: 'advice' }, ...items.map((a) => h('li', { class: `is-${a.level}` },
      h('header', {}, h('b', {}, a.title), h('span', { class: 'row', style: { gap: '8px' } }, h('small', { class: 'faint' }, a.area), pill(a.level))),
      h('p', {}, a.text), a.action ? h('div', { class: 'act' }, a.action) : null)))
      : note('لا توجد ملاحظات.', 'safe'));
}

function kriPanel(s) {
  const items = s.kri.items || [];
  const fmtV = (k) => (k.unit === '%' ? `${k.value.toFixed(k.value < 10 ? 1 : 0)}%` : k.unit === 'x' ? `${k.value.toFixed(2)}×` : `${Number(k.value).toLocaleString('en-US', { maximumFractionDigits: 1 })} ${k.unit || ''}`);
  return panel({ title: 'مؤشرات الإنذار المبكر', sub: 'إشارات قصيرة تُنبّه قبل أن تصبح المشكلة كبيرة.', ico: 'bell' },
    h('div', { class: 'kri-grid' }, ...items.map((k) => h('div', { class: `kri kri--${k.level}` },
      h('div', { class: 'kri__head' }, h('span', { class: 'kri__title' }, k.title), pill(k.level)),
      h('div', { class: 'kri__value num' }, fmtV(k)),
      h('div', { class: 'kri__hint' }, k.hint)))));
}

export default {
  async mount(el, ctx) {
    el.append(asyncBlock(() => ctx.store.analyze('summary'), (s) => {
      ctx.setBadge('overview', s.empty ? '' : s.overall);
      if (s.empty) {
        return emptyState('أدخل بيانات مشروعك أولاً', 'أضف منتجاً واحداً على الأقل (السعر والتكلفة والكمية) ليبدأ التحليل.', button('إدخال البيانات', { ico: 'edit', onClick: () => ctx.goto('inputs') }));
      }
      const warnings = [...(s.input_warnings || []), ...(s.regime_notes || [])];
      return h('div', { class: 'stack' },
        verdict(s),
        warnings.length ? note(warnings.join(' • '), 'warn') : null,
        kpis(s),
        h('div', { class: 'two-col' }, fanPanel(s), planPanel(s)),
        yearly(s),
        kriPanel(s),
        advicePanel(s));
    }, { loadingText: 'جارٍ تحليل مشروعك…' }));
  },
};
