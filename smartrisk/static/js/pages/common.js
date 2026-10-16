// سلوك مشترك: قائمة الجوال في الترويسة العامة + تسجيل الخروج.
import { api } from '../lib/api.js';

const header = document.getElementById('siteHeader');
const burger = document.getElementById('burger');
if (header && burger) {
  burger.addEventListener('click', () => {
    const open = header.classList.toggle('is-open');
    burger.setAttribute('aria-expanded', String(open));
  });
}

document.addEventListener('click', async (e) => {
  const b = e.target.closest('[data-action="logout"]');
  if (!b) return;
  try { await api.post('/api/auth/logout'); } finally { location.href = '/'; }
});
