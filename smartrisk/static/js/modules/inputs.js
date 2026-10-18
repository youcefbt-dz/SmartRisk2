import { h, mount, debounce, boot } from '../lib/dom.js';
import { icon } from '../lib/icons.js';
import { dz, pct, MONTH_NAMES } from '../lib/format.js';
import { note } from '../components/ui.js';
import { numberField, textField, selectField, checkField, rangeField, listEditor } from '../components/form.js';

const O = boot.options || {};
const MONTH_OPTS = Object.fromEntries(MONTH_NAMES.map((m, i) => [String(i + 1), m]));

function section(title, ico, sub, open, ...children) {
  return h('details', { class: 'acc', open: open || null },
    h('summary', {}, h('span', { class: 'ico-chip' }, icon(ico)), title, sub ? h('small', {}, sub) : null),
    h('div', { class: 'acc__body' }, ...children));
}
const grid = (...c) => h('div', { class: 'form-grid' }, ...c);
const sub = (t) => h('h4', { class: 'sub-title' }, t);

export default {
  mount(el, ctx) {
    const { store } = ctx;
    const d = store.state.data;
    const set = (fn) => store.change(fn);
    const num = (label, get, put, extra = {}) => numberField({ label, value: get(), onInput: (v) => set((x) => put(x, v)), ...extra });

    // ---------------------------------------------------------- شريط المعاينة الحية
    const live = h('div', { class: 'live', 'aria-live': 'polite' });
    const drawLive = (m) => mount(live,
      h('div', {}, h('small', {}, 'الإيراد السنوي'), h('b', { class: 'num' }, dz(m.revenue_y1))),
      h('div', {}, h('small', {}, 'هامش الربح الصافي'), h('b', { class: 'num' }, pct(m.net_margin_y1, 1))),
      h('div', {}, h('small', {}, 'أدنى رصيد نقدي'), h('b', { class: `num${m.min_cash < 0 ? ' is-neg' : ''}`, style: m.min_cash < 0 ? { color: 'var(--crit)' } : {} }, dz(m.min_cash))),
      h('div', {}, h('small', {}, 'نقطة التعادل الشهرية'), h('b', { class: 'num' }, dz(m.breakeven_total))),
      h('span', { class: 'spacer' }),
      h('small', { class: 'faint' }, m.cash_out_month ? `السيولة تنفد في الشهر ${m.cash_out_month}` : 'السيولة لا تنفد في التوقع الأساسي'));
    let seq = 0;
    const refreshLive = debounce(async () => {
      const my = ++seq;
      try { const m = await store.preview('metrics'); if (my === seq) drawLive(m); } catch { /* تجاهل أخطاء المعاينة */ }
    }, 350);
    const off = store.on('change', () => refreshLive());
    drawLive({ revenue_y1: NaN, net_margin_y1: NaN, min_cash: 0, breakeven_total: NaN });
    refreshLive();

    // ---------------------------------------------------------- 1) عام
    const general = grid(
      textField({ label: 'اسم المشروع', value: d.name, onInput: (v) => set((x) => { x.name = v || 'مشروع'; }), wide: true }),
      selectField({ label: 'القطاع', value: d.sector, options: O.sectors || {}, onInput: (v) => set((x) => { x.sector = v; }) }),
      selectField({ label: 'الشكل القانوني', value: d.legal_form, options: O.legalForms || {}, onInput: (v) => set((x) => { x.legal_form = v; }), term: 'regime', hint: 'يحدد النظام الضريبي الافتراضي.' }),
      textField({ label: 'المدينة', value: d.city, onInput: (v) => set((x) => { x.city = v; }) }),
      selectField({ label: 'شهر بداية النشاط', value: String(d.start_month), options: MONTH_OPTS, onInput: (v) => set((x) => { x.start_month = Number(v); }), hint: 'لتطبيق الموسمية على الأشهر الصحيحة.' }),
      num('مدة التوقع', () => d.horizon, (x, v) => { x.horizon = Math.min(60, Math.max(12, Math.round(v) || 36)); }, { unit: 'شهر', min: 12, max: 60, hint: 'من 12 إلى 60 شهراً.' }),
      num('السيولة النقدية الافتتاحية', () => d.start_cash, (x, v) => { x.start_cash = v; }, { unit: 'دج', min: 0, hint: 'ما تملكه فعلاً يوم البداية.' }),
      num('أصول ثابتة موجودة مسبقاً', () => d.opening_fixed_assets, (x, v) => { x.opening_fixed_assets = v; }, { unit: 'دج', min: 0, hint: 'قيمة التجهيزات التي تملكها قبل البدء.' }));

    // ---------------------------------------------------------- 2) المنتجات
    const products = listEditor({
      items: d.products, addLabel: 'إضافة منتج أو خدمة', emptyText: 'أضف أول منتج أو خدمة لتبدأ.',
      onChange: () => set(() => {}),
      newItem: () => ({ name: 'منتج جديد', activity: 'goods', price: 0, unit_cost: 0, units: 0, growth: 0, vat_rate: 19, cost_vat_rate: 19, seasonal: true, launch_month: 1, elasticity: -1.5, max_units: 0, capacity_per_unit: 0 }),
      columns: [
        { key: 'name', label: 'الاسم', type: 'text' },
        { key: 'activity', label: 'النوع', type: 'select', options: O.activities || { goods: 'بيع سلع', services: 'خدمات' } },
        { key: 'price', label: 'سعر البيع', type: 'number', unit: 'دج', min: 0, term: 'price' },
        { key: 'unit_cost', label: 'تكلفة الوحدة', type: 'number', unit: 'دج', min: 0, term: 'variable', hint: 'مواد، شراء، عمولة… بدون الأجور الثابتة.' },
        { key: 'units', label: 'المبيعات الشهرية', type: 'number', unit: 'وحدة', min: 0, term: 'units' },
        { key: 'growth', label: 'نمو شهري', type: 'number', unit: '%', min: -30, max: 50, term: 'growth' },
        { key: 'elasticity', label: 'مرونة الطلب', type: 'number', min: -10, max: 0, step: 0.1, term: 'elasticity', adv: true, hint: 'للتسعير الذكي. −1.5 قيمة معتادة.' },
        { key: 'vat_rate', label: 'TVA على المبيعات', type: 'number', unit: '%', min: 0, max: 100, adv: true },
        { key: 'cost_vat_rate', label: 'TVA على المشتريات', type: 'number', unit: '%', min: 0, max: 100, adv: true },
        { key: 'launch_month', label: 'شهر الإطلاق', type: 'number', min: 1, max: 60, adv: true },
        { key: 'seasonal', label: 'تطبَّق عليه الموسمية', type: 'check', adv: true },
        { key: 'max_units', label: 'سقف المبيعات الشهرية (للمحسّن)', type: 'number', min: 0, adv: true, hint: '0 = بلا سقف.' },
        { key: 'capacity_per_unit', label: 'الطاقة التي تستهلكها الوحدة', type: 'number', min: 0, adv: true, hint: 'مثل ساعات العمل للوحدة.' },
      ],
    });

    // ---------------------------------------------------------- 3) التكاليف
    const fixed = listEditor({
      items: d.fixed_costs, addLabel: 'إضافة مصروف ثابت', emptyText: 'لا توجد مصاريف ثابتة (إيجار، كهرباء، تسويق…).',
      onChange: () => set(() => {}),
      newItem: () => ({ name: 'مصروف', amount: 0, annual_growth: 0, start_month: 1 }),
      columns: [
        { key: 'name', label: 'البند', type: 'text' },
        { key: 'amount', label: 'المبلغ الشهري', type: 'number', unit: 'دج', min: 0, term: 'fixed' },
        { key: 'annual_growth', label: 'زيادة سنوية', type: 'number', unit: '%', adv: true },
        { key: 'start_month', label: 'يبدأ في الشهر', type: 'number', min: 1, max: 60, adv: true },
      ],
    });
    const staff = listEditor({
      items: d.staff, addLabel: 'إضافة وظيفة', emptyText: 'أضف الوظائف بالأجر الإجمالي (قبل الاقتطاعات).',
      onChange: () => set(() => {}),
      newItem: () => ({ role: 'موظف', count: 1, gross: 0, start_month: 1 }),
      columns: [
        { key: 'role', label: 'الوظيفة', type: 'text' },
        { key: 'count', label: 'العدد', type: 'number', min: 0 },
        { key: 'gross', label: 'الأجر الإجمالي الشهري', type: 'number', unit: 'دج', min: 0, hint: 'للفرد الواحد.' },
        { key: 'start_month', label: 'يبدأ في الشهر', type: 'number', min: 1, max: 60, adv: true },
      ],
    });
    const payroll = grid(
      num('اشتراكات صاحب العمل (CNAS)', () => d.payroll.employer_rate, (x, v) => { x.payroll.employer_rate = v; }, { unit: '%', term: 'cnas', min: 0, max: 60 }),
      num('زيادة الأجور سنوياً', () => d.payroll.annual_raise, (x, v) => { x.payroll.annual_raise = v; }, { unit: '%', min: 0, max: 50 }),
      num('تضخم التكاليف', () => d.macro.cost_inflation, (x, v) => { x.macro.cost_inflation = v; }, { unit: '% سنوياً', hint: 'يرفع تكلفة الوحدة كل سنة.' }),
      num('نمو الأسعار', () => d.macro.price_growth, (x, v) => { x.macro.price_growth = v; }, { unit: '% سنوياً', hint: 'ما ترفع به أسعارك سنوياً.' }));

    // ---------------------------------------------------------- 4) رأس المال العامل والموسمية
    const bars = h('div', { class: 'season-bars', 'aria-hidden': 'true' });
    const drawBars = () => mount(bars, ...d.seasonality.map((v) => h('i', { style: { height: `${Math.max(4, Math.min(100, (v / 2) * 100))}%` }, title: v.toFixed(2) })));
    drawBars();
    const season = h('div', { class: 'season-grid' }, ...MONTH_NAMES.map((m, i) =>
      numberField({ label: m, value: d.seasonality[i], step: 0.05, min: 0, max: 5, onInput: (v) => { set((x) => { x.seasonality[i] = v; }); drawBars(); } })));
    const wc = grid(
      num('مهلة تحصيل الزبائن', () => d.working_capital.customer_days, (x, v) => { x.working_capital.customer_days = v; }, { unit: 'يوم', term: 'dso', min: 0, max: 365, hint: '0 = بيع نقدي.' }),
      num('مهلة سداد الموردين', () => d.working_capital.supplier_days, (x, v) => { x.working_capital.supplier_days = v; }, { unit: 'يوم', term: 'dpo', min: 0, max: 365 }),
      num('مدة بقاء المخزون', () => d.working_capital.inventory_days, (x, v) => { x.working_capital.inventory_days = v; }, { unit: 'يوم', term: 'dio', min: 0, max: 365, hint: 'للخدمات اجعلها 0.' }));

    // ---------------------------------------------------------- 5) التمويل والاستثمارات
    const loans = listEditor({
      items: d.loans, addLabel: 'إضافة قرض', emptyText: 'لا توجد قروض.',
      onChange: () => set(() => {}),
      newItem: () => ({ name: 'قرض', principal: 0, rate: 6, months: 36, grace: 0, start_month: 1, existing: false }),
      columns: [
        { key: 'name', label: 'اسم القرض', type: 'text' },
        { key: 'principal', label: 'المبلغ', type: 'number', unit: 'دج', min: 0 },
        { key: 'rate', label: 'نسبة الفائدة السنوية', type: 'number', unit: '%', min: 0, max: 60 },
        { key: 'months', label: 'المدة', type: 'number', unit: 'شهر', min: 1, max: 360 },
        { key: 'grace', label: 'فترة الإمهال', type: 'number', unit: 'شهر', min: 0, term: 'grace', adv: true },
        { key: 'start_month', label: 'يبدأ في الشهر', type: 'number', min: 1, max: 60, adv: true },
        { key: 'existing', label: 'قرض قائم (المبلغ المتبقي لا يدخل الخزينة)', type: 'check', adv: true },
      ],
    });
    const capex = listEditor({
      items: d.capex, addLabel: 'إضافة استثمار', emptyText: 'لا توجد استثمارات (آلات، تجهيز، سيارة…).',
      onChange: () => set(() => {}),
      newItem: () => ({ name: 'استثمار', amount: 0, month: 1, life_years: 5 }),
      columns: [
        { key: 'name', label: 'البند', type: 'text' },
        { key: 'amount', label: 'المبلغ', type: 'number', unit: 'دج', min: 0, term: 'capex' },
        { key: 'month', label: 'شهر الدفع', type: 'number', min: 1, max: 60 },
        { key: 'life_years', label: 'العمر الإنتاجي', type: 'number', unit: 'سنة', min: 1, max: 50, term: 'depreciation' },
      ],
    });
    const oneoffs = listEditor({
      items: d.one_offs, addLabel: 'إضافة مصروف استثنائي', emptyText: 'لا توجد مصاريف استثنائية.',
      onChange: () => set(() => {}),
      newItem: () => ({ name: 'مصروف', amount: 0, month: 1 }),
      columns: [
        { key: 'name', label: 'البند', type: 'text' },
        { key: 'amount', label: 'المبلغ', type: 'number', unit: 'دج', min: 0, term: 'oneoff' },
        { key: 'month', label: 'الشهر', type: 'number', min: 1, max: 60 },
      ],
    });
    const equity = listEditor({
      items: d.equity_injections, addLabel: 'إضافة مساهمة', emptyText: 'لا توجد مساهمات في رأس المال.',
      onChange: () => set(() => {}),
      newItem: () => ({ name: 'مساهمة', amount: 0, month: 1 }),
      columns: [
        { key: 'name', label: 'المساهم / المصدر', type: 'text' },
        { key: 'amount', label: 'مبلغ المساهمة', type: 'number', unit: 'دج', min: 0 },
      ],
    });

    // ---------------------------------------------------------- 6) ضرائب ومخاطر وتقييم
    const taxRisk = [
      sub('الضرائب'),
      grid(
        selectField({ label: 'النظام الضريبي', value: d.tax.regime, options: O.regimes || {}, term: 'regime', onInput: (v) => set((x) => { x.tax.regime = v; }), hint: 'تلقائي = بحسب الشكل القانوني وسقف الإيراد.' }),
        numberField({ label: 'معدل IBS مخصّص', value: d.tax.ibs_rate ?? '', unit: '%', term: 'ibs', hint: 'اتركه فارغاً لاعتماد المعدل الافتراضي للقطاع.', placeholder: 'افتراضي',
          onInput: (v) => set((x) => { x.tax.ibs_rate = v > 0 ? v : null; }) })),
      sub('المخاطر (للمحاكاة)'),
      h('div', { class: 'stack' },
        rangeField({ label: 'درجة عدم اليقين', value: d.risk.uncertainty, min: 0.3, max: 2.5, step: 0.1, format: (v) => `${v.toFixed(1)}×`, term: 'uncertainty', onInput: (v) => set((x) => { x.risk.uncertainty = v; }) }),
        grid(
          num('تذبذب الطلب', () => d.risk.demand_vol, (x, v) => { x.risk.demand_vol = v; }, { unit: '%', min: 0, max: 80 }),
          num('تذبذب التكاليف', () => d.risk.cost_vol, (x, v) => { x.risk.cost_vol = v; }, { unit: '%', min: 0, max: 60 }),
          num('تذبذب الأسعار', () => d.risk.price_vol, (x, v) => { x.risk.price_vol = v; }, { unit: '%', min: 0, max: 40 }),
          num('تذبذب مهلة التحصيل', () => d.risk.collection_vol_days, (x, v) => { x.risk.collection_vol_days = v; }, { unit: 'يوم', min: 0, max: 60 }))),
      sub('التقييم والجدوى'),
      grid(
        num('معدل الخصم', () => d.valuation.discount_rate, (x, v) => { x.valuation.discount_rate = v; }, { unit: '%', term: 'discount', min: 0, max: 60 }),
        num('نمو ما بعد المدة', () => d.valuation.terminal_growth, (x, v) => { x.valuation.terminal_growth = v; }, { unit: '%', min: -10, max: 10 }),
        num('تقييم المشروع قبل دخول شريك', () => d.valuation.pre_money, (x, v) => { x.valuation.pre_money = v; }, { unit: 'دج', term: 'dilution', min: 0, hint: 'لمقارنة تمويل الشريك.' })),
      sub('الطاقة والموارد (للمحسّن)'),
      grid(
        num('الطاقة الشهرية المتاحة', () => d.capacity.total, (x, v) => { x.capacity.total = v; }, { min: 0, hint: '0 = بلا قيد.' }),
        textField({ label: 'وحدة الطاقة', value: d.capacity.unit_label, onInput: (v) => set((x) => { x.capacity.unit_label = v || 'ساعة'; }), maxlength: 20, placeholder: 'ساعة' }),
        num('ميزانية التشغيل الشهرية', () => d.capacity.budget, (x, v) => { x.capacity.budget = v; }, { unit: 'دج', min: 0, hint: '0 = بلا قيد.' })),
    ];

    mount(el,
      store.state.warnings.length ? note(store.state.warnings.join(' • '), 'warn') : null,
      live,
      section('معلومات المشروع', 'folder', 'الاسم والشكل القانوني والسيولة الافتتاحية', true, general),
      section('المنتجات والمبيعات', 'layers', `${d.products.length} منتج`, true, products),
      section('التكاليف والأجور', 'coins', 'المصاريف الثابتة والوظائف', false, sub('المصاريف الثابتة الشهرية'), fixed, sub('الأجور'), staff, sub('الاشتراكات والتضخم'), payroll),
      section('رأس المال العامل والموسمية', 'calendar', 'التحصيل والمخزون وتفاوت الأشهر', false, sub('مهل الدفع والمخزون'), wc, sub('معاملات الموسمية'), h('p', { class: 'muted' }, 'القيمة 1 = شهر عادي، 1.3 = مبيعات أعلى بـ30%، 0.8 = أقل بـ20%.'), season, bars),
      section('التمويل والاستثمارات', 'bank', 'القروض والتجهيزات والمساهمات', false, sub('القروض'), loans, sub('الاستثمارات'), capex, sub('مصاريف استثنائية'), oneoffs, sub('مساهمات رأسمالية'), equity),
      section('الضرائب والمخاطر والتقييم', 'shield', 'فرضيات متقدمة', false, ...taxRisk));

    return () => { off(); refreshLive.cancel(); };
  },
};
