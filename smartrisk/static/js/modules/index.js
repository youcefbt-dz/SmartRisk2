// سجلّ أقسام مساحة العمل. لإضافة قسم: أنشئ ملفاً يصدّر { mount(el, ctx) } وأضف سطراً هنا.
export const MODULES = [
  { id: 'overview', title: 'نظرة عامة', icon: 'home', load: () => import('./overview.js') },
  { id: 'inputs', title: 'بيانات المشروع', icon: 'edit', load: () => import('./inputs.js') },
  { id: 'statements', title: 'القوائم المالية', icon: 'table', load: () => import('./statements.js') },
  { id: 'risk', title: 'تحليل المخاطر', icon: 'shield', load: () => import('./risk.js') },
  { id: 'decisions', title: 'القرارات', icon: 'scale', load: () => import('./decisions.js') },
  { id: 'tracking', title: 'المتابعة الشهرية', icon: 'calendar', load: () => import('./tracking.js') },
  { id: 'report', title: 'التقرير', icon: 'file', href: (pid) => `/app/p/${pid}/report` },
];
