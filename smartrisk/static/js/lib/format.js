// تنسيق الأرقام بأرقام لاتينية وفواصل آلاف (معتاد في الجزائر).
const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const ok = (n) => typeof n === 'number' && Number.isFinite(n);
const neg = (s) => s.replace('-', '−');

export const fmt = (n) => (ok(n) ? neg(nf0.format(Math.round(n))) : '—');
export const fmt1 = (n) => (ok(n) ? neg(nf1.format(n)) : '—');
export const dz = (n) => (ok(n) ? `${fmt(n)} دج` : '—');
export const pct = (x, d = 0) => (ok(x) ? neg((x * 100).toFixed(d)) + '%' : '—');
export const pctRaw = (x, d = 0) => (ok(x) ? neg(x.toFixed(d)) + '%' : '—');

export function short(n) {
  if (!ok(n)) return '—';
  const a = Math.abs(n), s = n < 0 ? '−' : '';
  if (a >= 1e9) return s + (a / 1e9).toFixed(1) + ' مليار';
  if (a >= 1e6) return s + (a / 1e6).toFixed(a >= 1e7 ? 0 : 1) + ' م';
  if (a >= 1e3) return s + Math.round(a / 1e3) + ' ألف';
  return s + Math.round(a);
}

export const months = (n) => (ok(n) ? (n >= 99 ? '+99 شهر' : `${fmt1(n)} شهر`) : '—');
export const LEVEL_AR = { safe: 'جيدة', warn: 'قريبة من الخطر', crit: 'في خطر' };
export const MONTH_NAMES = ['جانفي', 'فيفري', 'مارس', 'أفريل', 'ماي', 'جوان', 'جويلية', 'أوت', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

export function monthLabel(startMonth, t) {
  const m = ((startMonth - 1 + t - 1) % 12);
  return MONTH_NAMES[m];
}
