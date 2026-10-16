import { h, mount, $, boot } from '../lib/dom.js';
import { api } from '../lib/api.js';
import { dz, pct, fmt, months } from '../lib/format.js';
import { cashFan } from '../lib/charts.js';
import { chartBox, after, table } from '../modules/_shared.js';

const pid = boot.projectId;
$('#backLink').href = `/app/p/${pid}`;
$('#printBtn').addEventListener('click', () => window.print());
const post = (n, params = {}) => api.post(`/api/projects/${pid}/analyze/${n}`, { params });
const sec = (t, ...c) => h('section', { class: 'rp-sec' }, h('h2', {}, t), ...c);
const LV = { safe: 'جيدة', warn: 'قريبة من الخطر', crit: 'في خطر' };

(async () => {
  const root = $('#report');
  try {
    const proj = (await api.get(`/api/projects/${pid}`)).project;
    const [s, st, rs, sens] = await Promise.all([post('summary'), post('statements'), post('reverse_stress'), post('sensitivity')]);
    if (s.empty) { mount(root, h('p', {}, 'لا توجد بيانات كافية لإعداد التقرير. أدخل منتجاً واحداً على الأقل.')); return; }
    const m = s.metrics;
    const box = chartBox('chart--h260');
    const inc = (k) => st.income.find((l) => l.key === k);
    mount(root,
      h('header', { class: 'rp-head' }, h('div', {}, h('small', {}, 'تقرير المخاطر المالية'), h('h1', {}, proj.name), h('p', {}, `${new Date().toLocaleDateString('ar-DZ-u-nu-latn')} · نظام ضريبي: ${m.regime === 'ifu' ? 'IFU' : 'حقيقي'}`)),
        h('div', { class: `rp-verdict rp-verdict--${s.overall}` }, h('small', {}, 'الحكم العام'), h('b', {}, s.overall_label))),
      sec('الخلاصة', h('p', {}, `الإيراد المتوقع في السنة الأولى ${dz(m.revenue_y1)} بهامش صافٍ ${pct(m.net_margin_y1, 1)}. أدنى رصيد نقدي ${dz(m.min_cash)}، واحتمال نفاد السيولة خلال 12 شهراً ${pct(m.p_ruin_12)}، ورأس المال المعرّض للخطر (95%) ${dz(m.cash_at_risk_95)}.`),
        h('ul', { class: 'rp-pillars' }, ...s.pillars.map((p) => h('li', { class: `is-${p.level}` }, `${p.title}: ${p.label}`)))),
      sec('الأرقام الرئيسية', table(s.yearly, [
        { label: 'السنة', get: (r) => r.year }, { label: 'الإيرادات', num: true, get: (r) => fmt(r.revenue) }, { label: 'EBITDA', num: true, get: (r) => fmt(r.ebitda) },
        { label: 'الربح الصافي', num: true, get: (r) => fmt(r.net_income) }, { label: 'التدفق التشغيلي', num: true, get: (r) => fmt(r.cfo) }, { label: 'رصيد آخر السنة', num: true, get: (r) => fmt(r.end_cash) }])),
      sec('مروحة السيولة', box.el, h('p', { class: 'rp-note' }, `محاكاة ${s.mc.n.toLocaleString('en-US')} سيناريو. نقطة التعادل ${dz(m.breakeven_total)} شهرياً، ومدة الصمود ${months(m.runway_months)}.`)),
      sec('ما الذي يكسر المشروع', h('ul', {}, ...rs.items.map((i) => h('li', {}, i.statement)), h('li', {}, rs.combined.statement))),
      sec('أكثر العوامل تأثيراً على الربح', table(sens.metrics.net_income_y1.rows.slice(0, 5), [
        { label: 'العامل', get: (r) => r.label }, { label: `−${sens.pct}%`, num: true, get: (r) => fmt(r.low) }, { label: `+${sens.pct}%`, num: true, get: (r) => fmt(r.high) }])),
      sec('جاهزية التمويل', h('p', {}, `${Math.round(s.score.score)} / 100 — ${s.score.verdict}`)),
      sec('خطة العمل المقترحة', s.advice.plan.length ? h('ol', {}, ...s.advice.plan.map((p) => h('li', {}, h('b', {}, p.title), ' — ', p.action))) : h('p', {}, 'لا إجراءات عاجلة.')),
      h('footer', { class: 'rp-foot' }, 'أُعدّ هذا التقرير بنموذج محاكاة مبني على فرضيات المستخدم؛ النتائج تقديرية وليست استشارة مالية أو ضريبية. نسب الضرائب والبرامج تحتاج مراجعة من الجهة الرسمية.'));
    after(() => cashFan(box.canvas, { months: s.mc.months, bands: s.mc.bands, baseline: s.series.cash }));
  } catch (e) { mount(root, h('p', { class: 'error-text' }, e.message)); }
})();
