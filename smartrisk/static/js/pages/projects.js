import { api } from '../lib/api.js';
import { h, mount, $ } from '../lib/dom.js';
import { icon } from '../lib/icons.js';
import { dz, pct, LEVEL_AR } from '../lib/format.js';
import { button, pill, modal, confirmModal, toast, loading } from '../components/ui.js';

const view = $('#projectsView');
const LOGO_PREFIX = 'smartrisk.project.logo.';
const PENDING_LOGO = 'smartrisk.project.logo.pending';
let templates = [];

function logoKey(id) { return `${LOGO_PREFIX}${id}`; }
function getLogo(id) {
  try { return localStorage.getItem(logoKey(id)) || ''; } catch { return ''; }
}
function setLogo(id, value) {
  try {
    if (value) localStorage.setItem(logoKey(id), value);
    else localStorage.removeItem(logoKey(id));
  } catch { toast('تعذّر حفظ الشعار في المتصفح.', 'crit'); }
}
function readPendingLogo() {
  try { return localStorage.getItem(PENDING_LOGO) || ''; } catch { return ''; }
}
function clearPendingLogo() {
  try { localStorage.removeItem(PENDING_LOGO); } catch {}
}

function logoNode(id, name, size = 'card') {
  const src = getLogo(id);
  if (src) return h('div', { class: `project-logo project-logo--${size}` },
    h('img', { src, alt: `شعار ${name}`, loading: 'lazy' }));
  return h('div', { class: `project-logo project-logo--${size} project-logo--empty`, 'aria-hidden': 'true' },
    icon('folder'));
}

function formatDate(value) {
  if (!value) return 'لم يُعدّل بعد';
  const d = new Date(value.replace(' ', 'T') + 'Z');
  if (Number.isNaN(d.getTime())) return 'آخر تعديل';
  return new Intl.DateTimeFormat('ar-DZ', { day: 'numeric', month: 'short' }).format(d);
}

function card(p) {
  const s = p.snapshot || {};
  const lvl = s.level;
  const stats = s.revenue_y1 !== undefined && !s.empty ? [
    ['الإيراد السنوي', dz(s.revenue_y1)],
    ['هامش الربح', pct(s.net_margin_y1, 0)],
    ['أدنى رصيد', dz(s.min_cash)],
  ] : [];
  const logo = logoNode(p.id, p.name);

  const del = button('', { variant: 'quiet', size: 'sm', ico: 'trash', attrs: { 'aria-label': 'حذف المشروع', title: 'حذف' } });
  del.addEventListener('click', async () => {
    if (await confirmModal('حذف المشروع؟', `سيُحذف «${p.name}» نهائياً مع كل بياناته.`, 'احذف', true)) {
      try { await api.del(`/api/projects/${p.id}`); setLogo(p.id, ''); toast('حُذف المشروع'); load(); }
      catch (e) { toast(e.message, 'crit'); }
    }
  });

  const dup = button('', { variant: 'quiet', size: 'sm', ico: 'copy', attrs: { 'aria-label': 'تكرار', title: 'تكرار' } });
  dup.addEventListener('click', async () => {
    try {
      const r = await api.post(`/api/projects/${p.id}/duplicate`);
      const srcLogo = getLogo(p.id);
      if (srcLogo && r.project?.id) setLogo(r.project.id, srcLogo);
      toast('تم تكرار المشروع', 'safe'); load();
    } catch (e) { toast(e.message, 'crit'); }
  });

  const exp = button('', { variant: 'quiet', size: 'sm', ico: 'download', attrs: { 'aria-label': 'تصدير JSON', title: 'تصدير' } });
  exp.addEventListener('click', () => { location.href = `/api/projects/${p.id}/export.json`; });

  const open = button('فتح المشروع', { size: 'sm', href: `/app/p/${p.id}` });
  return h('article', { class: `pcard pcard--${lvl || 'neutral'}` },
    h('div', { class: 'pcard__top' },
      h('div', { class: 'pcard__identity' }, logo,
        h('div', { class: 'pcard__namebox' },
          h('span', { class: 'pcard__eyebrow' }, 'مشروع'),
          h('h3', { class: 'pcard__title' }, p.name))),
      lvl ? pill(lvl, LEVEL_AR[lvl]) : h('span', { class: 'pcard__status' }, 'مسودة')),
    stats.length ? h('dl', { class: 'pcard__stats' },
      ...stats.map(([k, v]) => h('div', { class: 'pcard__stat' }, h('dt', {}, k), h('dd', {}, v))))
      : h('div', { class: 'pcard__empty' }, icon('info'), h('span', {}, 'أكمل بيانات المشروع للحصول على قراءة مالية.')),
    h('div', { class: 'pcard__meta' }, h('span', {}, `آخر تعديل ${formatDate(p.updated_at)}`),
      h('span', { class: 'pcard__save' }, icon('check'), 'محفوظ تلقائياً')),
    h('div', { class: 'pcard__foot' }, open, h('span', { class: 'spacer' }), exp, dup, del));
}

function updateCount(n) {
  const el = $('#projectsCount');
  if (el) {
    el.querySelector('b').textContent = n;
    el.querySelector('span').textContent = n === 1 ? 'مشروع' : 'مشاريع';
  }
}

async function load() {
  mount(view, loading('جارٍ تحميل مشاريعك…'));
  try {
    const r = await api.get('/api/projects');
    updateCount(r.projects.length);
    if (!r.projects.length) {
      mount(view, h('section', { class: 'projects-empty' },
        h('div', { class: 'projects-empty__mark' }, icon('folder')),
        h('div', {}, h('span', { class: 'projects-empty__kicker' }, 'ابدأ من هنا'),
          h('h3', {}, 'لا توجد مشاريع بعد'),
          h('p', {}, 'أنشئ مشروعاً جديداً، واختر له اسماً وشعاراً ليصبح له مساحة عمل خاصة بك.')),
        button('إنشاء أول مشروع', { onClick: openNew })));
      return;
    }
    mount(view, ...r.projects.map(card));
  } catch (e) { mount(view, h('p', { class: 'error-text' }, e.message)); }
}

function imageToDataURL(file) {
  return new Promise((resolve, reject) => {
    if (!file || !file.type.startsWith('image/')) return reject(new Error('اختر ملف صورة صالحاً.'));
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const max = 320;
        const scale = Math.min(1, max / Math.max(img.width, img.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(img.width * scale));
        canvas.height = Math.max(1, Math.round(img.height * scale));
        canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/webp', .86));
      };
      img.onerror = () => reject(new Error('تعذّر قراءة الصورة.'));
      img.src = reader.result;
    };
    reader.onerror = () => reject(new Error('تعذّر قراءة الملف.'));
    reader.readAsDataURL(file);
  });
}

async function openNew() {
  if (!templates.length) templates = (await api.get('/api/meta/templates')).templates;
  let chosen = templates[0]?.id;
  let selectedLogo = readPendingLogo();

  const nameInput = h('input', { class: 'input project-name-input', placeholder: 'مثلاً: مطعم النخبة', maxlength: 60 });
  const logoInput = h('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp,image/svg+xml', hidden: true });
  const logoPreview = h('div', { class: 'new-project-logo project-logo--new' },
    selectedLogo ? h('img', { src: selectedLogo, alt: 'معاينة الشعار' }) : icon('folder'));
  const logoHint = h('span', { class: 'logo-upload__hint' }, selectedLogo ? 'الشعار جاهز للحفظ' : 'PNG أو JPG أو WebP — اختياري');

  const logoBox = h('button', { class: 'logo-upload', type: 'button' }, logoPreview,
    h('span', { class: 'logo-upload__copy' }, h('strong', {}, 'هوية المشروع'), logoHint),
    h('span', { class: 'logo-upload__action' }, selectedLogo ? 'تغيير' : 'إضافة'));
  logoBox.addEventListener('click', () => logoInput.click());
  logoInput.addEventListener('change', async () => {
    try {
      selectedLogo = await imageToDataURL(logoInput.files[0]);
      logoPreview.replaceChildren(h('img', { src: selectedLogo, alt: 'معاينة الشعار' }));
      logoHint.textContent = 'الشعار جاهز للحفظ';
      logoBox.querySelector('.logo-upload__action').textContent = 'تغيير';
    } catch (e) { toast(e.message, 'crit'); }
    logoInput.value = '';
  });

  const list = h('div', { class: 'tpl-list' });
  const draw = () => mount(list, ...templates.map((t) => {
    const b = h('button', { class: 'tpl', type: 'button', 'aria-pressed': String(t.id === chosen) },
      h('span', { class: 'tpl__icon' }, icon(t.icon)),
      h('span', {}, h('strong', {}, t.title), h('span', {}, t.description)));
    b.addEventListener('click', () => { chosen = t.id; draw(); });
    return b;
  }));
  draw();

  modal({
    title: 'مشروع جديد',
    body: [
      h('p', { class: 'muted', style: { marginBottom: '8px' } }, 'ابنِ هوية مشروعك أولاً، ثم اختر نقطة البداية.'),
      h('div', { class: 'new-project-identity' },
        logoBox, logoInput,
        h('label', { class: 'field' }, h('span', { class: 'field__label' }, 'اسم المشروع'),
          h('span', { class: 'field__box' }, nameInput))),
      h('div', { class: 'new-project-section' }, h('span', { class: 'new-project-section__label' }, 'نقطة البداية'), list)
    ],
    actions: [{ label: 'إنشاء المشروع', onClick: async () => {
      try {
        const r = await api.post('/api/projects', { template: chosen, name: nameInput.value.trim() || undefined });
        if (selectedLogo && r.project?.id) setLogo(r.project.id, selectedLogo);
        clearPendingLogo();
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
