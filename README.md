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

## ترحيل قاعدة البيانات

```powershell
uv run alembic upgrade head
```

## الاختبارات والفحص

```powershell
uv run pytest -q
uv run ruff check .
uv run bandit -q -r app
```
