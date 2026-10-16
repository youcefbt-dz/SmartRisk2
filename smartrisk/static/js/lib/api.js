import { boot } from './dom.js';

let csrf = boot.csrf || '';

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(method, url, body) {
  const opts = { method, headers: { 'X-CSRF-Token': csrf, Accept: 'application/json' }, credentials: 'same-origin' };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try { res = await fetch(url, opts); }
  catch { throw new ApiError('تعذّر الاتصال بالخادم. تحقق من اتصالك ثم أعد المحاولة.', 0); }
  let data = null;
  try { data = await res.json(); } catch { /* جسم غير JSON */ }
  if (data && data.csrf) csrf = data.csrf;
  if (res.status === 401 && !url.startsWith('/api/auth/')) {
    location.href = '/login?next=' + encodeURIComponent(location.pathname);
    throw new ApiError('انتهت الجلسة.', 401);
  }
  if (!res.ok) throw new ApiError((data && data.message) || 'حدث خطأ غير متوقع.', res.status);
  return data;
}

export const api = {
  get: (u) => request('GET', u),
  post: (u, b = {}) => request('POST', u, b),
  put: (u, b = {}) => request('PUT', u, b),
  del: (u) => request('DELETE', u),
};
