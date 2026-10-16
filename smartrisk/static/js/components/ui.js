// مكوّنات واجهة صغيرة قابلة لإعادة الاستخدام.
import { h, append } from '../lib/dom.js';
import { icon } from '../lib/icons.js';
import { api } from '../lib/api.js';
import { LEVEL_AR } from '../lib/format.js';

export function button(label, { variant = '', ico, onClick, type = 'button', size = '', href, attrs = {} } = {}) {
  const cls = ['btn', variant && `btn--${variant}`, size && `btn--${size}`].filter(Boolean).join(' ');
  const el = href ? h('a', { class: cls, href, ...attrs }) : h('button', { class: cls, type, ...attrs });
  if (ico) el.append(icon(ico));
  if (label) el.append(document.createTextNode(label));
  if (onClick) el.addEventListener('click', onClick);
  return el;
}

export const pill = (level, text) => h('span', { class: `pill pill--${level}` }, text || LEVEL_AR[level] || level);

export function kpi({ label, value, unit, sub, level, term: t }) {
  return h('div', { class: `kpi${level ? ' kpi--' + level : ' kpi--brand'}` },
    h('div', { class: 'kpi__label' }, label, t ? term(t) : null),
    h('div', { class: 'kpi__value' }, value, unit ? h('small', {}, unit) : null),
    sub ? h('div', { class: 'kpi__sub' }, sub) : null);
}

export function panel({ title, sub, actions, accent = false, flush = false, ico } = {}, ...children) {
  const head = (title || actions) ? h('div', { class: 'panel__head' },
    h('div', {}, title ? h('h3', { class: 'panel__title' }, ico ? h('span', { class: 'ico-chip' }, icon(ico)) : null, title) : null, sub ? h('p', { class: 'panel__sub' }, sub) : null),
    actions ? h('div', { class: 'row' }, actions) : null) : null;
  return h('section', { class: `panel${accent ? ' panel--accent' : ''}${flush ? ' panel--flush' : ''}` }, head, ...children);
}

export const note = (text, level = '') => h('div', { class: `note${level ? ' note--' + level : ''}`, role: level === 'crit' ? 'alert' : null }, text);

export function emptyState(title, text, action) {
  return h('div', { class: 'empty' }, icon('layers', 'icon'), h('h3', {}, title), text ? h('p', {}, text) : null, action ? h('div', { style: { marginTop: '16px' } }, action) : null);
}

export function loading(text = 'جارٍ الحساب…') {
  return h('div', { class: 'empty', 'aria-busy': 'true' }, h('span', { class: 'spin' }), h('p', { style: { marginTop: '10px' } }, text));
}

export function segmented(options, value, onChange) {
  const wrap = h('div', { class: 'seg', role: 'group' });
  const btns = options.map(([v, label]) => {
    const b = h('button', { type: 'button', 'aria-pressed': String(v === value) }, label);
    b.addEventListener('click', () => { btns.forEach((x) => x.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true'); onChange(v); });
    return b;
  });
  append(wrap, btns);
  return wrap;
}

export function tabs(items, active, onChange) {
  const wrap = h('div', { class: 'tabs', role: 'tablist' });
  const btns = items.map(([id, label]) => {
    const b = h('button', { type: 'button', role: 'tab', 'aria-selected': String(id === active) }, label);
    b.addEventListener('click', () => { btns.forEach((x) => x.setAttribute('aria-selected', 'false')); b.setAttribute('aria-selected', 'true'); onChange(id); });
    return b;
  });
  append(wrap, btns);
  return wrap;
}

// ---------------------------------------------------------------- نوافذ
export function modal({ title, body, actions = [], onClose }) {
  const dlg = h('dialog', { class: 'modal', 'aria-labelledby': 'mdl-t' },
    h('div', { class: 'modal__head', id: 'mdl-t' }, title),
    h('div', { class: 'modal__body' }, body),
    h('div', { class: 'modal__foot' }, ...actions.map((a) => {
      const b = button(a.label, { variant: a.variant ?? '', size: 'sm', onClick: async () => { const r = a.onClick ? await a.onClick(dlg) : undefined; if (r !== false) dlg.close(); } });
      return b;
    })));
  dlg.addEventListener('close', () => { dlg.remove(); onClose && onClose(); });
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  document.body.append(dlg);
  dlg.showModal();
  return dlg;
}

export function confirmModal(title, text, confirmLabel = 'تأكيد', danger = false) {
  return new Promise((resolve) => {
    let result = false;
    modal({
      title, body: h('p', {}, text), onClose: () => resolve(result),
      actions: [{ label: confirmLabel, variant: danger ? 'danger' : '', onClick: () => { result = true; } },
        { label: 'إلغاء', variant: 'ghost' }],
    });
  });
}

// ---------------------------------------------------------------- إشعارات
let toastBox;
export function toast(text, level = '', ms = 3600) {
  if (!toastBox) { toastBox = h('div', { class: 'toasts', role: 'status', 'aria-live': 'polite' }); document.body.append(toastBox); }
  const t = h('div', { class: `toast${level ? ' toast--' + level : ''}` }, text);
  toastBox.append(t);
  setTimeout(() => t.remove(), ms);
}

// ---------------------------------------------------------------- مصطلحات
let glossary;
async function loadGlossary() {
  if (!glossary) { const r = await api.get('/api/meta/glossary'); glossary = Object.fromEntries(r.terms.map((t) => [t.id, t])); }
  return glossary;
}

export function term(id) {
  const b = h('button', { class: 'term', type: 'button', 'aria-label': 'شرح المصطلح' }, '؟');
  b.addEventListener('click', async (e) => {
    e.preventDefault(); e.stopPropagation();
    const g = await loadGlossary();
    const t = g[id];
    if (!t) return;
    modal({
      title: t.term,
      body: [h('p', {}, t.definition), t.example ? h('div', { class: 'modal__example' }, h('b', {}, 'مثال: '), t.example) : null],
      actions: [{ label: 'فهمت' }],
    });
  });
  return b;
}

export function levelDot(level) { return h('span', { class: `dot dot--${level}` }); }

export function download(url) {
  const a = h('a', { href: url, download: '' });
  document.body.append(a); a.click(); a.remove();
}
