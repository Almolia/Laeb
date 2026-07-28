# Laeb — پلتفرم انتشار بازی

پروژهٔ درس **طراحی سیستم‌های میکروسرویس** — گروه سوم.

| سند | محتوا |
|---|---|
| [Phase 1 Report.md](Phase%201%20Report.md) | معماری و نیازمندی‌های فاز ۱ |
| [Phase 2 Plan.md](Phase%202%20Plan.md) | برنامهٔ پیاده‌سازی ۳روزه و نقش‌ها |
| [Project Definition.pdf](Project%20Definition.pdf) | صورت پروژه |
| [docs/contracts.md](docs/contracts.md) | قراردادهای API و رویدادها (فریزشده) |
| [docs/HANDOFF.md](docs/HANDOFF.md) | راهنمای تحویل به بقیهٔ تیم |
| [docs/adr/](docs/adr/) | تصمیم‌های معماری (ADR) |

---

## اجرای سریع

```bash
cp .env.example .env
make up
# حدود ۴۵ ثانیه صبر کنید تا healthcheckها سبز شوند
bash scripts/smoke.sh
```

| آدرس | کاربرد |
|---|---|
| http://localhost:8000 | API Gateway (Traefik) |
| http://localhost:8080 | داشبورد Traefik |
| http://localhost:15672 | RabbitMQ (`guest` / `guest`) |
| http://localhost:9001 | MinIO |
| http://localhost:9090 | Prometheus |
| http://localhost:3000 | Grafana (`admin` / `admin`) |
| http://localhost:8020/docs | درگاه پرداخت جعلی (mock-psp) |

OpenAPI هر سرویس: `http://localhost:8001/docs` تا `http://localhost:8011/docs`.

> اگر `docker compose build` با خطای **Forbidden** از Docker Hub شکست خورد، یک registry mirror تنظیم کنید و دوباره بسازید.

---

## خلاصهٔ کار انجام‌شده (نقش A1 — Platform & Foundation)

هدف A1 این نبود که منطق کسب‌وکار هر سرویس را کامل کند؛ هدف این بود که **ریپو قابل اجرا** شود و A2/A3 و Wave B بتوانند بدون بلاک شدن کار کنند.

### ۱) اسکلت ریپوزیتوری

- فایل‌های `.gitignore` و `.env.example` (JWT، دیتابیس‌ها، RabbitMQ، MinIO، ادمین)
- ساختار پوشه‌ها: `libs/` ، `services/` ، `infra/` ، `mock-psp/` ، `scripts/` ، `docs/`
- برنچ کاری: `feat/a1-platform`

### ۲) Shared Kernel (`libs/shared_kernel`)

کتابخانهٔ مشترک همهٔ سرویس‌ها با یک لیست وابستگی واحد:

- تنظیمات محیطی، لاگ JSON، `X-Correlation-Id`
- خطای یکسان (`error.code` / `message` / `correlationId`)
- JWT و RBAC (`BASE_USER` / `DEVELOPER` / `SUPPORT` / `ADMIN`)
- `/health` ، `/ready` ، `/metrics`
- SQLAlchemy همزمان (sync)
- RabbitMQ + Transactional Outbox + Inbox ایدمپوتنت
- کلید ایدمپوتنسی برای عملیات مالی
- پول فقط با **عدد صحیح minor unit** (تقسیم ۷۰/۳۰، surcharge هدیه ۰.۲٪، تخفیف)

### ۳) قالب سرویس + ۱۱ stub

- قالب در `services/_template/` — مهم: **build context ریشهٔ ریپو است** تا `libs/` در ایمیج باشد
- سرویس‌ها با لایهٔ Clean Architecture و دو کانتینر `api` + `worker`:

  `identity` · `profile` · `catalog` · `order` · `wallet` · `review` · `trading` · `forum` · `festival` · `media` · `notification`

- هر stub الان فقط سالم است:
  - `/health` برای Docker healthcheck
  - `/api/v1/<service>/health` برای smoke از gateway
  - `/api/v1/<service>/ping`
- منطق دامنه عمداً پیاده نشده؛ جزئیات کار هر سرویس در `services/<name>/README.md` است.

### ۴) زیرساخت Docker Compose

| جزء | نقش |
|---|---|
| PostgreSQL | یک دیتابیس + یک یوزر per service (`infra/postgres/init.sql`) |
| MongoDB | `review` / `forum` / `notification` |
| Redis | حضور آنلاین و کش order book |
| RabbitMQ | exchange با نام `platform.events` |
| MinIO | ذخیرهٔ فایل/رسانه |
| Traefik | gateway روی پورت ۸۰۰۰ با مسیر `/api/v1/<service>` و rate limit |
| Prometheus + Grafana | متریک سرویس‌ها + داشبورد اولیه |
| mock-psp | شبیه‌سازی درگاه بانکی روی ۸۰۲۰ (شماره کارت وارد سرویس‌های ما نمی‌شود) |

دستورهای `Makefile`: `up` · `down` · `fresh` · `smoke` · `seed` · `demo` · `logs` · `test`

### ۵) قراردادها و ADRها

- `docs/contracts.md` فریز شده: پول، JWT، هدرها، envelope خطا، پورت‌ها، کاتالوگ رویدادها
- ADR-01 تا ADR-06: Python/FastAPI، Database-per-Service، حذف Elasticsearch، REST داخلی به‌جای gRPC، توپولوژی RabbitMQ، mock PSP

### ۶) اسکریپت‌ها و CI

| فایل | کار |
|---|---|
| `scripts/smoke.sh` | health هر ۱۱ سرویس از پشت gateway |
| `scripts/seed.py` | اسکلت seed (TODO برای A2/A3/B) |
| `scripts/demo.sh` | هدر بخش‌ها برای ۳۹ داستان کاربر |
| `scripts/scaffold.sh` | ساخت مجدد stub از روی قالب |
| `.github/workflows/ci.yml` | build + compose + smoke |

### ۷) تحویل به تیم

- `docs/HANDOFF.md`: نحوهٔ اجرا، نقشهٔ ریپو، gotchaها، جدول مالک سرویس‌ها
- README داخل هر سرویس: داستان‌های کاربر، endpointها، eventهای ورودی/خروجی، چک‌لیست TODO

---

## معماری سطح‌بالا

```
Client → Traefik (:8000)
           → identity / profile / catalog / order / wallet / …
               هر سرویس: api + worker
               → Postgres | Mongo | Redis | MinIO
               → RabbitMQ (outbox → event → inbox)
Wallet ↔ mock-psp (:8020)
Prometheus ← /metrics
```

تصمیم‌های مهم Phase 2 نسبت به سند فاز ۱:

- جریان کاری انتشار داخل **Catalog** ادغام می‌شود
- فراخوانی‌های همزمان داخلی **REST** هستند (نه gRPC)
- Elasticsearch در Compose نیست (جستجو با Postgres/Mongo)

---

## کار باقی‌مانده (خارج از محدودهٔ A1)

| نقش | کار |
|---|---|
| A2 | Identity + Catalog (ثبت‌نام/نقش‌ها، ماشین وضعیت انتشار) |
| A3 | Wallet (دفتر کل، شارژ، گیفت‌کارت، تقسیم ۷۰/۳۰) |
| B1 | Order (خرید/هدیه/استرداد) + Festival |
| B2 | Trading (موتور تطابق ۵دقیقه‌ای + متریک مدت چرخه) |
| B3 | Profile / Review / Forum / Media |
| مشترک | Notification به‌عنوان consumer رویدادها؛ پر کردن `demo.sh` و `seed.py` |

---

## پورت سرویس‌ها

| سرویس | پورت |
|---|---|
| gateway | 8000 |
| identity | 8001 |
| profile | 8002 |
| catalog | 8003 |
| order | 8004 |
| wallet | 8005 |
| review | 8006 |
| trading | 8007 |
| forum | 8008 |
| festival | 8009 |
| media | 8010 |
| notification | 8011 |
| mock-psp | 8020 |
