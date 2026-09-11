# University Management API

REST API لإدارة الجامعات والكليات والأقسام والمقررات والطلاب وأعضاء هيئة التدريس والتسجيل.

## المتطلبات

- Python 3.14
- Docker وDocker Compose لتشغيل الخدمات بالحاويات
- uv

## الإعداد المحلي

انسخ ملف الإعدادات ثم أدخل القيم المناسبة:

```powershell
Copy-Item .env.example .env
```

ثبّت الاعتمادات وشغّل التطبيق:

```powershell
uv sync
uv run uvicorn app.main:app --reload
```

تتوفر وثائق الواجهة عند تشغيل التطبيق على `http://127.0.0.1:8000/docs`.

## التشغيل عبر Docker

أنشئ ملف `.env` من النموذج، ثم شغّل الخدمات:

```powershell
docker compose up --build
```

لإيقاف الخدمات:

```powershell
docker compose down
```

## ترحيل قاعدة البيانات وإعداد أدمن النظام

```powershell
uv run alembic upgrade head
```

## نظام تقارير الخلفية (Worker)

تقارير الـ transcript تُنفذ بواسطة worker مستقل يقرأ المهام مباشرة من PostgreSQL (المصدر الوحيد للحقيقة):

```powershell
uv run python -m app.workers.runner
```

- `POST /reports/export/{student_id}` يُسجّل Job بحالة `queued` ويعيد `202`.
- الـ worker يلتقط المهام ذريًا (`FOR UPDATE SKIP LOCKED`)، يجدد lease أثناء التوليد، ويعيد المحاولة تلقائيًا مع backoff عند الفشل المؤقت.
- استعلام الحالة عبر `GET /reports/jobs/{job_id}` يقرأ من PostgreSQL مباشرة.
- إعدادات السلوك في `app/config.py`: `job_poll_interval_seconds`, `job_lease_seconds`, `job_heartbeat_seconds`, `job_max_attempts`, `job_retry_base_seconds`, `worker_retry_attempts`.

عبر Docker تُشغَّل الخدمة تلقائيًا كحاوية `worker` في `docker-compose.yml`.

إنشاء حساب المسؤول الأول (Bootstrap Admin):

```powershell
# عبر وسائط CLI الفردية (تفاعليًا بطلب كلمة المرور في حال إزالتها):
uv run python -m app.cli create-admin --email admin@example.com --username admin

# أو عبر متغيرات البيئة (مناسب لـ Docker و CI):
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="SuperSecretAdminPass123!"
uv run python -m app.cli create-admin
```


## الاختبارات والفحص

```powershell
uv run pytest -q
uv run ruff check .
uv run bandit -q -r app
```
