// سجلّ أقسام مساحة العمل. لإضافة قسم: أنشئ ملفاً يصدّر { mount(el, ctx) } وأضف سطراً هنا.
export const MODULES = [
  { id: 'overview', desc: 'الحكم العام على مشروعك وأهم المؤشرات وخطة العمل.', title: 'نظرة عامة', icon: 'home', load: () => import('./overview.js') },
  { id: 'inputs', desc: 'أدخل أرقام مشروعك؛ يُحفظ كل شيء تلقائياً وتتحدّث النتائج فوراً.', title: 'بيانات المشروع', icon: 'edit', load: () => import('./inputs.js') },
  { id: 'statements', desc: 'الدخل والتدفقات النقدية والميزانية مترابطة شهرياً وسنوياً.', title: 'القوائم المالية', icon: 'table', load: () => import('./statements.js') },
  { id: 'risk', desc: 'محاكاة الاحتمالات وما الذي قد يكسر مشروعك.', title: 'تحليل المخاطر', icon: 'shield', load: () => import('./risk.js') },
  { id: 'decisions', desc: 'التسعير ومزيج المنتجات وجدوى الاستثمار ومصادر التمويل.', title: 'القرارات', icon: 'scale', load: () => import('./decisions.js') },
  { id: 'tracking', desc: 'قارن أرقامك الفعلية بالتوقع واحصل على إنذار مبكر.', title: 'المتابعة الشهرية', icon: 'calendar', load: () => import('./tracking.js') },
  { id: 'report', title: 'التقرير', icon: 'file', href: (pid) => `/app/p/${pid}/report` },
];
