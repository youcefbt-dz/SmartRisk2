import { api } from '../lib/api.js';
import { h, mount } from '../lib/dom.js';

const list = document.getElementById('glList');
const search = document.getElementById('glSearch');
let terms = [];

function draw(q = '') {
  const items = terms.filter((t) => !q || (t.term + t.definition).includes(q));
  const groups = {};
  items.forEach((t) => (groups[t.group] ||= []).push(t));
  mount(list, ...(Object.keys(groups).length ? Object.entries(groups).map(([g, ts]) =>
    h('div', { class: 'gl-group' }, h('h3', {}, g), ...ts.map((t) =>
      h('details', { class: 'gl-item', id: 'term-' + t.id }, h('summary', {}, t.term),
        h('div', { class: 'body' }, t.definition, t.example ? h('div', { class: 'ex' }, h('b', {}, 'مثال: '), t.example) : null))))) : [h('p', { class: 'muted' }, 'لا توجد نتائج.')]));
}

api.get('/api/meta/glossary').then((r) => { terms = r.terms; draw(); });
search.addEventListener('input', () => draw(search.value.trim()));

// فهرس جانبي: تمييز القسم الحالي
const links = [...document.querySelectorAll('#toc a')];
const secs = links.map((a) => document.querySelector(a.getAttribute('href'))).filter(Boolean);
const io = new IntersectionObserver((entries) => {
  entries.forEach((e) => {
    if (e.isIntersecting) { links.forEach((a) => a.classList.toggle('is-on', a.getAttribute('href') === '#' + e.target.id)); }
  });
}, { rootMargin: '-20% 0px -70% 0px' });
secs.forEach((s) => io.observe(s));
if (location.hash) { const t = document.querySelector(location.hash); t && t.scrollIntoView(); }
