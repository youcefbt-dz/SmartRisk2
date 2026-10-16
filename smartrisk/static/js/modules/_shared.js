// أدوات مشتركة بين أقسام مساحة العمل.
import { h, mount } from '../lib/dom.js';
import { loading, note, button } from '../components/ui.js';

/** صندوق مخطط: يرجع {el, canvas}. ارسم المخطط بعد إدراج el في الصفحة (استعمل after). */
export function chartBox(size = 'chart--h320') {
  const canvas = h('canvas');
  return { el: h('div', { class: `chart ${size}` }, canvas), canvas };
}

/** ينفّذ الدالة بعد انتهاء الإدراج الحالي في DOM (لرسم المخططات). */
export const after = (fn) => queueMicrotask(fn);

/**
 * كتلة غير متزامنة: تعرض «جارٍ الحساب» ثم تستبدلها بناتج render(data).
 * fetcher: () => Promise. render: (data) => عقدة|مصفوفة عقد. تُرجع عنصر الحاوية مع .refresh().
 */
export function asyncBlock(fetcher, render, { loadingText = 'جارٍ الحساب…' } = {}) {
  const box = h('div', { class: 'async' });
  let seq = 0;
  async function run() {
    const my = ++seq;
    mount(box, loading(loadingText));
    try {
      const data = await fetcher();
      if (my !== seq) return;
      mount(box, render(data));
    } catch (e) {
      if (my !== seq) return;
      mount(box, note(e.message || 'تعذّر الحساب.', 'crit'), h('div', { style: { marginTop: '12px' } }, button('إعادة المحاولة', { size: 'sm', variant: 'ghost', onClick: run })));
    }
  }
  box.refresh = run;
  run();
  return box;
}

export const levelOf = (x) => (x === 'safe' || x === 'warn' || x === 'crit' ? x : '');

/** يحوّل مصفوفة صفوف إلى جدول HTML. cols: [{label, get(row), cls}] */
export function table(rows, cols, { total = () => false } = {}) {
  return h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
    h('thead', {}, h('tr', {}, ...cols.map((c) => h('th', { class: c.num ? 'n' : '' }, c.label)))),
    h('tbody', {}, ...rows.map((r) => h('tr', { class: total(r) ? 'is-total' : '' },
      ...cols.map((c) => h('td', { class: `${c.num ? 'n' : ''}${c.neg && c.neg(r) ? ' is-neg' : ''}` }, c.get(r))))))));
}
