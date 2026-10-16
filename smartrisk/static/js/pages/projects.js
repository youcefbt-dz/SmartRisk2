import { api } from '../lib/api.js';
import { h, mount, $ } from '../lib/dom.js';
import { icon } from '../lib/icons.js';
import { dz, pct, LEVEL_AR } from '../lib/format.js';
import { button, pill, modal, confirmModal, toast, emptyState, loading } from '../components/ui.js';

const view = $('#projectsView');
let templates = [];

function card(p) {
  const s = p.snapshot || {};
  const lvl = s.level;
  const stats = s.revenue_y1 !== undefined && !s.empty ? [
    ['الإيراد السنوي', dz(s.revenue_y1)],
    ['هامش الربح', pct(s.net_margin_y1, 0)],
    ['أدنى رصيد', dz(s.min_cash)],
    ['السيولة', s.cash_out_month ? `تنفد في ش${s.cash_out_month}` : 'مستقرة'],
  ] : null;
  const del = button('', { variant: 'quiet', size: 'sm', ico: 'trash', attrs: { 'aria-label': 'حذف المشروع', title: 'حذف' } });
  del.addEventListener('click', async () => {
    if (await confirmModal('حذف المشروع؟', `سيُحذف «${p.name}» نهائياً مع كل بياناته.`, 'احذف', true)) {
      try { await api.del(`/api/projects/${p.id}`); toast('حُذف المشروع'); load(); } catch (e) { toast(e.message, 'crit'); }
    }
  });
  const dup = button('', { variant: 'quiet', size: 'sm', ico: 'copy', attrs: { 'aria-label': 'تكرار', title: 'تكرار' } });
  dup.addEventListener('click', async () => { try { await api.post(`/api/projects/${p.id}/duplicate`); toast('تم التكرار', 'safe'); load(); } catch (e) { toast(e.message, 'crit'); } });
  const exp = button('', { variant: 'quiet', size: 'sm', ico: 'download', attrs: { 'aria-label': 'تصدير JSON', title: 'تصدير' } });
  exp.addEventListener('click', () => { location.href = `/api/projects/${p.id}/export.json`; });
  return h('article', { class: 'pcard' },
    h('div', { class: `pcard__bar${lvl ? ' pcard__bar--' + lvl : ''}` }),
    h('div', { class: 'pcard__body' },
      h('div', { class: 'row row--between' }, h('h3', { class: 'pcard__title' }, p.name), lvl ? pill(lvl, LEVEL_AR[lvl]) : null),
      stats ? h('dl', { class: 'pcard__stats' }, ...stats.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)]))
            : h('p', { class: 'muted', style: { marginTop: '10px', fontSize: '.9rem' } }, 'لم تُدخل بيانات كافية بعد.')),
    h('div', { class: 'pcard__foot' }, button('فتح', { size: 'sm', href: `/app/p/${p.id}` }), h('span', { class: 'spacer' }), exp, dup, del));
}

async function load() {
  mount(view, loading('جارٍ التحميل…'));
  try {
    const r = await api.get('/api/projects');
    if (!r.projects.length) {
      mount(view, h('div', { style: { gridColumn: '1/-1' } }, emptyState('لا توجد مشاريع بعد', 'ابدأ من قالب جاهز (محل، ورشة، مطعم) أو من مشروع فارغ.', button('مشروع جديد', { onClick: openNew }))));
      return;
    }
    mount(view, ...r.projects.map(card));
  } catch (e) { mount(view, h('p', { class: 'error-text' }, e.message)); }
}

async function openNew() {
  if (!templates.length) templates = (await api.get('/api/meta/templates')).templates;
  let chosen = templates[0]?.id;
  const nameInput = h('input', { class: 'input', placeholder: 'اسم المشروع (اختياري)', maxlength: 60 });
  const list = h('div', { class: 'tpl-list' });
  const draw = () => mount(list, ...templates.map((t) => {
    const b = h('button', { class: 'tpl', type: 'button', 'aria-pressed': String(t.id === chosen) },
      h('span', { class: 'tpl__icon' }, icon(t.icon)), h('span', {}, h('strong', {}, t.title), h('span', {}, t.description)));
    b.addEventListener('click', () => { chosen = t.id; draw(); });
    return b;
  }));
  draw();
  modal({
    title: 'مشروع جديد',
    body: [h('p', { class: 'muted', style: { marginBottom: '8px' } }, 'اختر نقطة بداية، ثم عدّل الأرقام لتطابق مشروعك.'), list,
      h('label', { class: 'field', style: { marginTop: '14px' } }, h('span', { class: 'field__label' }, 'الاسم'), h('span', { class: 'field__box' }, nameInput))],
    actions: [{ label: 'إنشاء', onClick: async () => {
      try {
        const r = await api.post('/api/projects', { template: chosen, name: nameInput.value.trim() || undefined });
        location.href = `/app/p/${r.project.id}`;
      } catch (e) { toast(e.message, 'crit'); return false; }
    } }, { label: 'إلغاء', variant: 'ghost' }],
  });
}

$('#newBtn').addEventListener('click', openNew);
$('#importBtn').addEventListener('click', () => $('#importFile').click());
$('#importFile').addEventListener('change', async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  try {
    const data = JSON.parse(await f.text());
    const r = await api.post('/api/projects/import', { data });
    location.href = `/app/p/${r.project.id}`;
  } catch (ex) { toast(ex.message || 'الملف غير صالح.', 'crit'); }
  e.target.value = '';
});
load();
