import { h, mount, $, clear } from '../lib/dom.js';
import { icon } from '../lib/icons.js';
import * as store from '../lib/store.js';
import { destroyAll } from '../lib/charts.js';
import { MODULES } from '../modules/index.js';
import { pill, toast, loading, note, button } from '../components/ui.js';
import { LEVEL_AR } from '../lib/format.js';

const view = $('#view');
const shell = $('#shell');
const badges = {};
let current = null;
let cleanup = null;
let token = 0;

const SAVE_TEXT = { idle: '', dirty: 'تعديلات غير محفوظة…', saving: 'جارٍ الحفظ…', saved: 'تم الحفظ', error: 'تعذّر الحفظ' };
store.on('savestate', (s) => { const el = $('#saveState'); el.dataset.state = s; el.textContent = SAVE_TEXT[s] || ''; });
store.on('error', (m) => toast(m, 'crit'));
store.on('saved', (meta) => { $('#sbName').textContent = meta.name; $('#crumbName').textContent = meta.name; document.title = `${meta.name} — SmartRisk`; renderSidePill(); });

function renderSidePill() {
  const sn = store.state.meta?.snapshot; const lvl = sn && !sn.empty ? sn.level : null;
  mount($('#sbPill'), lvl ? pill(lvl, LEVEL_AR[lvl]) : '');
}

function buildNav() {
  const nav = $('#nav');
  mount(nav, ...MODULES.map((m) => {
    const dot = h('span', { class: 'dot' });
    badges[m.id] = dot;
    const a = h('a', { href: m.href ? m.href(store.state.id) : `#/${m.id}`, dataset: { id: m.id } }, icon(m.icon), m.title, dot);
    return a;
  }));
}

const ctx = {
  store,
  setBadge(id, level) { if (badges[id]) badges[id].className = `dot${level ? ' dot--' + level : ''}`; },
  goto(id) { location.hash = `#/${id}`; },
  title(t, d = '') { $('#viewTitle').textContent = t; $('#viewSub').textContent = d; },
};

async function route() {
  const id = (location.hash.match(/^#\/([\w-]+)/) || [])[1] || 'overview';
  const mod = MODULES.find((m) => m.id === id && !m.href) || MODULES[0];
  const my = ++token;
  if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }
  destroyAll(view);
  document.querySelectorAll('#nav a').forEach((a) => (a.dataset.id === mod.id ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  shell.classList.remove('nav-open');
  ctx.title(mod.title, mod.desc);
  mount(view, loading('جارٍ التحميل…'));
  window.scrollTo({ top: 0 });
  try {
    const m = (await mod.load()).default;
    if (my !== token) return;
    clear(view);
    cleanup = (await m.mount(view, ctx)) || null;
  } catch (e) {
    if (my !== token) return;
    console.error(e);
    mount(view, note(`تعذّر تحميل هذا القسم: ${e.message || e}`, 'crit'), h('div', { style: { marginTop: '14px' } }, button('إعادة المحاولة', { onClick: route })));
  }
  current = mod.id;
  view.focus({ preventScroll: true });
}

async function init() {
  try { await store.load(); } catch (e) { mount(view, note(e.message, 'crit')); return; }
  buildNav();
  renderSidePill();
  $('#navBurger').addEventListener('click', () => shell.classList.toggle('nav-open'));
  $('#scrim').addEventListener('click', () => shell.classList.remove('nav-open'));
  window.addEventListener('hashchange', route);
  route();
}
init();
