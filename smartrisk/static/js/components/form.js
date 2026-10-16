// حقول النماذج + محرّر القوائم (منتجات، أجور، قروض...) المبني على تعريف أعمدة.
import { h, append, clear } from '../lib/dom.js';
import { icon } from '../lib/icons.js';
import { term, button } from './ui.js';
import { uid } from '../lib/store.js';

const parse = (v) => (v === '' || v === null || v === undefined ? 0 : Number(String(v).replace(/,/g, '')));

/** حقل رقمي. onInput(value:number) */
export function numberField({ label, value, unit, hint, term: t, min, max, step = 'any', onInput, placeholder = '0', wide = false, id }) {
  const input = h('input', { class: 'input', type: 'number', inputmode: 'decimal', min, max, step, value: value ?? '', placeholder, id });
  input.addEventListener('input', () => { const n = parse(input.value); input.parentElement.classList.toggle('is-invalid', Number.isNaN(n) || (min !== undefined && n < min) || (max !== undefined && n > max)); onInput(Number.isNaN(n) ? 0 : n); });
  return h('label', { class: `field${wide ? ' field--wide' : ''}` },
    h('span', { class: 'field__label' }, label, t ? term(t) : null),
    h('span', { class: 'field__box' }, input, unit ? h('span', { class: 'field__unit' }, unit) : null),
    hint ? h('span', { class: 'field__hint' }, hint) : null);
}

export function textField({ label, value, hint, onInput, placeholder = '', maxlength = 60, wide = false }) {
  const input = h('input', { class: 'input', type: 'text', value: value ?? '', placeholder, maxlength });
  input.addEventListener('input', () => onInput(input.value));
  return h('label', { class: `field${wide ? ' field--wide' : ''}` },
    h('span', { class: 'field__label' }, label),
    h('span', { class: 'field__box' }, input),
    hint ? h('span', { class: 'field__hint' }, hint) : null);
}

export function selectField({ label, value, options, onInput, hint, term: t, wide = false }) {
  const sel = h('select', { class: 'select' }, ...Object.entries(options).map(([k, v]) => h('option', { value: k, selected: k === value }, v)));
  sel.addEventListener('change', () => onInput(sel.value));
  return h('label', { class: `field${wide ? ' field--wide' : ''}` },
    h('span', { class: 'field__label' }, label, t ? term(t) : null),
    h('span', { class: 'field__box' }, sel),
    hint ? h('span', { class: 'field__hint' }, hint) : null);
}

export function checkField({ label, checked, onInput }) {
  const c = h('input', { type: 'checkbox', checked });
  c.addEventListener('change', () => onInput(c.checked));
  return h('label', { class: 'check' }, c, label);
}

export function rangeField({ label, value, min, max, step = 1, format = (v) => v, onInput, term: t }) {
  const out = h('b', { class: 'num' }, format(value));
  const r = h('input', { type: 'range', min, max, step, value });
  r.addEventListener('input', () => { const v = Number(r.value); out.textContent = format(v); onInput(v); });
  return h('div', { class: 'field' },
    h('div', { class: 'row row--between' }, h('span', { class: 'field__label' }, label, t ? term(t) : null), out), r);
}

/**
 * محرّر قائمة صفوف. columns: [{key,label,type:'text'|'number'|'select'|'check',unit,options,min,max,term,width}]
 * التعديل داخل الحقل لا يعيد الرسم (يحافظ على التركيز)؛ الإضافة والحذف يعيدان الرسم.
 */
export function listEditor({ items, columns, newItem, addLabel = 'إضافة', onChange, emptyText = 'لا توجد عناصر بعد.', max = 30 }) {
  const root = h('div', { class: 'list-editor' });
  const body = h('div', { class: 'list-editor__rows' });

  const cell = (item, col) => {
    const common = { label: col.label, term: col.term, hint: col.hint };
    if (col.type === 'text') return textField({ ...common, value: item[col.key], onInput: (v) => { item[col.key] = v; onChange(items); } });
    if (col.type === 'select') return selectField({ ...common, value: item[col.key], options: col.options, onInput: (v) => { item[col.key] = v; onChange(items); } });
    if (col.type === 'check') return checkField({ label: col.label, checked: !!item[col.key], onInput: (v) => { item[col.key] = v; onChange(items); } });
    return numberField({ ...common, value: item[col.key], unit: col.unit, min: col.min, max: col.max, step: col.step, onInput: (v) => { item[col.key] = v; onChange(items); } });
  };

  function draw() {
    clear(body);
    if (!items.length) body.append(h('p', { class: 'faint', style: { padding: '8px 2px' } }, emptyText));
    items.forEach((item, idx) => {
      const del = h('button', { class: 'btn btn--quiet btn--sm list-editor__del', type: 'button', 'aria-label': 'حذف' }, icon('trash'));
      del.addEventListener('click', () => { items.splice(idx, 1); onChange(items); draw(); });
      const main = columns.filter((c) => !c.adv);
      const adv = columns.filter((c) => c.adv);
      const cells = main.map((c) => cell(item, c));
      if (adv.length) {
        cells.push(h('details', { class: 'adv-box' }, h('summary', {}, 'خيارات متقدمة'),
          h('div', { class: 'form-grid' }, ...adv.map((c) => cell(item, c)))));
      }
      body.append(h('div', { class: 'list-editor__row' }, h('div', { class: 'form-grid list-editor__cells' }, ...cells), del));
    });
  }
  draw();

  const add = button(addLabel, { variant: 'ghost', size: 'sm', ico: 'plus', onClick: () => {
    if (items.length >= max) return;
    items.push({ id: uid(), ...newItem() }); onChange(items); draw();
  } });
  append(root, [body, h('div', { style: { marginTop: '12px' } }, add)]);
  return root;
}
