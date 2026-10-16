import { h, mount } from '../lib/dom.js';
import { icon } from '../lib/icons.js';
import { simulate, drawFan } from '../lib/fan.js';

const CHECKS = [
  ['dice', 'محاكاة السيولة', 'آلاف المسارات العشوائية للمبيعات والتكلفة وتأخر التحصيل. النتيجة نطاق احتمالات لا رقم واحد.'],
  ['table', 'القوائم المالية الثلاث', 'الدخل والتدفقات النقدية والميزانية مترابطة لمدة تصل إلى 5 سنوات، مع الموسمية ورأس المال العامل والقروض.'],
  ['target', 'ما الذي يكسر مشروعك', 'اختبار الصدمات العكسي: كم يجب أن تنخفض المبيعات أو ترتفع التكلفة أو يتأخر الزبائن لتنفد السيولة؟'],
  ['scale', 'أثر كل متغير', 'تحليل الحساسية يرتّب السعر والتكلفة والتحصيل والأجور بحسب تأثيرها على ربحك وسيولتك.'],
  ['coins', 'قرارات التسعير والتمويل', 'أدنى سعر بلا خسارة، مزيج المنتجات الأمثل، NPV وIRR، ومقارنة قرض بنكي بدعم الوكالات أو شريك.'],
  ['bell', 'المتابعة والإنذار المبكر', 'أدخل أرقامك الفعلية كل شهر لترى الانحراف عن التوقع وتنبيهات مبكرة وتوقعاً محدَّثاً.'],
];
mount(document.getElementById('checkList'), ...CHECKS.map(([ic, t, d]) =>
  h('div', { class: 'check-row' }, h('div', { class: 'check-row__icon' }, icon(ic)), h('div', {}, h('h3', {}, t), h('p', {}, d)))));

// مروحة الهيرو: حركة واحدة عند التحميل ثم تثبت
const canvas = document.getElementById('fan');
const sim = simulate();
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

function showNumbers() {
  document.getElementById('gA').textContent = Math.round(sim.ruin * 100) + '%';
  document.getElementById('gB').textContent = (Math.round(sim.car * 10)).toLocaleString('en-US') + ' ألف دج';
}
function frame(t0) {
  const step = (now) => {
    const p = Math.min(1, (now - t0) / 2100);
    const eased = 1 - Math.pow(1 - p, 3);
    drawFan(canvas, sim, eased);
    if (p < 1) requestAnimationFrame(step); else showNumbers();
  };
  requestAnimationFrame(step);
}
if (reduce) { drawFan(canvas, sim, 1); showNumbers(); } else { drawFan(canvas, sim, 0); frame(performance.now()); }
let rz; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => drawFan(canvas, sim, 1), 120); });
