// حالة المشروع المفتوح: تحميل، تعديل، حفظ تلقائي مؤجَّل، وتشغيل التحليلات.
import { api } from './api.js';
import { boot, debounce } from './dom.js';

const bus = new EventTarget();
export const on = (type, fn) => {
  const l = (e) => fn(e.detail);
  bus.addEventListener(type, l);
  return () => bus.removeEventListener(type, l);
};
export const emit = (type, detail) => bus.dispatchEvent(new CustomEvent(type, { detail }));

export const state = {
  id: boot.projectId,
  data: null,
  meta: null,
  warnings: [],
  saveState: 'idle', // idle | dirty | saving | saved | error
  version: 0,
};

function setSave(s) { state.saveState = s; emit('savestate', s); }

export async function load() {
  const r = await api.get(`/api/projects/${state.id}`);
  state.data = r.project.data;
  state.meta = r.project;
  state.warnings = r.warnings || [];
  emit('loaded');
  return state;
}

let inflight = null;
const schedule = debounce(() => { flush(); }, 700);

export function change(mutator) {
  mutator(state.data);
  state.version += 1;
  setSave('dirty');
  schedule();
  emit('change', state.version);
}

export async function flush() {
  schedule.cancel();
  if (inflight) { await inflight; if (state.saveState !== 'dirty') return; }
  if (state.saveState !== 'dirty') return;
  const sent = state.version;
  setSave('saving');
  inflight = api.put(`/api/projects/${state.id}`, { data: state.data })
    .then((r) => {
      state.meta = r.project;
      state.warnings = r.warnings || [];
      if (state.version === sent) setSave('saved'); else { setSave('dirty'); schedule(); }
      emit('saved', r.project);
    })
    .catch((e) => { setSave('error'); emit('error', e.message); })
    .finally(() => { inflight = null; });
  await inflight;
}

export async function analyze(name, params = {}) {
  await flush();
  return api.post(`/api/projects/${state.id}/analyze/${name}`, { params });
}

// معاينة على المسودة الحالية دون انتظار الحفظ
export function preview(name, params = {}) {
  return api.post(`/api/preview/${name}`, { project: state.data, params });
}

export const uid = () => Math.random().toString(16).slice(2, 10);

window.addEventListener('beforeunload', (e) => {
  if (state.saveState === 'dirty' || state.saveState === 'saving') { e.preventDefault(); e.returnValue = ''; }
});
