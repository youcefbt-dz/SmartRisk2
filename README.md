# SmartRisk — منصة إدارة المخاطر المالية للمشاريع الصغيرة

> نسخة كاملة: المحرك المالي + الخادم + الواجهة العربية (RTL) بخط IBM Plex Sans Arabic وهوية مستلهمة من قالب Atos (بدون نسخ شعاره أو صوره).

## التشغيل
```bash
pip install -r requirements.txt
python run.py                 # الخادم على http://127.0.0.1:5000
python -m pytest              # الاختبارات
flask --app smartrisk seed-demo   # (اختياري) مستخدم تجريبي + 3 مشاريع نموذجية
```
الإعدادات بمتغيرات البيئة (انظر `.env.example`). `SMARTRISK_AUTH=false` يشغّل وضع مستخدم واحد محلي بلا تسجيل دخول.

## الهيكل (مصمم ليسهل التعديل والإضافة)
```
config.py            الإعدادات
run.py / wsgi.py     التشغيل (تطوير / gunicorn)
smartrisk/
  core/              المحرك الصرف (بلا Flask) — يمكن اختباره واستخدامه وحده
    engine/          schema (بيانات المشروع) · forecast (القوائم الثلاث) · loans · rules
    analysis/        كل ملف يسجّل محلّلاً بـ @analyzer ويُكتشف تلقائياً
    registry.py      سجلّ المحلّلات
  api/               كل ملف يعرّف bp ويُسجَّل تلقائياً (accounts, projects, analysis, meta, exports)
  web/               مسارات الصفحات
  data/              ملفات قابلة للتعديل بدون لمس الكود:
                     tax_rules.json · kri.json · scoring.json · funding_programs.json ·
                     glossary.json · templates/*.json (قوالب المشاريع)
  db.py · auth.py · repo.py
smartrisk/static/    css/ (tokens · base · components · layout · landing · app · report) · js/lib · js/components · js/pages
                     js/modules/ ← أقسام مساحة العمل (index.js سجلّ الأقسام)
smartrisk/templates/ قوالب Jinja (base + partials + pages)
tests/               اختبارات للمحرك والـ API
```

## كيف تضيف شيئاً؟
| تريد | افعل |
|---|---|
| تحليلاً جديداً | ملف في `core/analysis/` بدالة `@analyzer("اسم")` ← يظهر فوراً في `/api/projects/<id>/analyze/اسم` |
| نصيحة جديدة | دالة `@rule(أولوية)` في `analysis/advice.py` |
| مؤشر إنذار مبكر | سطر في `data/kri.json` |
| تعديل أوزان الجاهزية | `data/scoring.json` |
| تغيير نسب الضرائب | `data/tax_rules.json` |
| قالب مشروع جاهز | ملف JSON في `data/templates/` |
| مصطلحاً في القاموس | عنصر في `data/glossary.json` |
| نقطة API | ملف جديد في `api/` فيه `bp = Blueprint(...)` |

## المحلّلات المتوفرة
summary · statements · metrics · breakeven · montecarlo · sensitivity · reverse_stress · scenarios ·
scoring · kri · zscore · pricing · optimizer · investment · financing · tracking · advice

## تنبيهات مهمة
- نسب الضرائب والاشتراكات وبرامج التمويل (ANADE/ANGEM) **قيم إرشادية** من مصادر عامة وعليها علامة تحقق؛ راجعها من الجهات الرسمية (انظر `verify_note` في `tax_rules.json`).
- نموذج Altman Z″ مؤشر مساعد لا حكم نهائي، ومحاكاة مونت كارلو تعتمد على افتراضات التذبذب التي تضبطها.


## إضافة قسم جديد في مساحة العمل
1. أنشئ `smartrisk/static/js/modules/mysection.js` يصدّر `export default { mount(el, ctx) {...} }`.
2. أضف سطراً في `modules/index.js`: `{ id, title, icon, load: () => import('./mysection.js') }`.
3. لتحليل جديد: ملف في `core/analysis/` بـ `@analyzer("name")` ثم `ctx.store.analyze('name')` من الواجهة.

## تغيير الهوية
كل الألوان والخطوط في `static/css/tokens.css` فقط.

## تنبيه
نسب الضرائب والبرامج (ANADE/ANGEM…) تقريبية وموسومة `verify`؛ راجعها في `smartrisk/data/*.json` قبل أي استعمال حقيقي.
