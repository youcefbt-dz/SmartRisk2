import { api } from '../lib/api.js';
import { simulate, drawFan } from '../lib/fan.js';

const form = document.getElementById('authForm');
const err = document.getElementById('authErr');
const btn = document.getElementById('authBtn');
const bg = document.getElementById('bgfan');
if (bg) { const sim = simulate({ seed: 5, n: 60 }); const d = () => drawFan(bg, sim, 1); d(); addEventListener('resize', d); }

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  err.textContent = '';
  const mode = form.dataset.mode;
  const body = Object.fromEntries(new FormData(form).entries());
  if (!body.email || !body.password) { err.textContent = 'أدخل البريد الإلكتروني وكلمة المرور.'; return; }
  if (mode === 'register' && body.password.length < 8) { err.textContent = 'كلمة المرور يجب ألا تقل عن 8 أحرف.'; return; }
  btn.disabled = true;
  try {
    await api.post(mode === 'register' ? '/api/auth/register' : '/api/auth/login', body);
    const next = new URLSearchParams(location.search).get('next');
    location.href = next && next.startsWith('/') && !next.startsWith('//') ? next : '/app';
  } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
});
