# گزارش نهایی فارسی Wallet — نقش A3

این فایل خلاصهٔ نهایی پیاده‌سازی و تست نقش A3 است. محدودهٔ تحویل A3 فقط
`services/wallet/` است؛ زیرساخت سراسری پروژه باید از نقش A1 وارد شود.

## وضعیت Git

- branch: `feat/a3-wallet`
- commit پیاده‌سازی: `50d8d55 refactor(wallet): align A3 ownership with platform foundation`
- commit گزارش نهایی: `28f9aa7 docs(wallet): add final Persian verification report`
- push انجام نشده است.
- working tree قبل از افزودن همین فایل تمیز بود.
- اختلاف نهایی با `main` فقط در `services/wallet/` است.

## مرز مالکیت نهایی

| نقش | محل فایل‌های نهایی |
|---|---|
| A1 | shared kernel، Compose ریشه، gateway، infra، mock PSP، تنظیمات ریشه و اسکریپت‌های سراسری |
| A2 | `services/identity` و `services/catalog` |
| **A3** | **`services/wallet`** شامل application، domain، infrastructure، migration، Dockerfile، تست‌ها و READMEها |
| B1 | order/review و release/report نهایی |
| B2 | trading/festival و Kubernetes bonus |
| B3 | profile/media/notification/forum/achievements |

در نتیجه Wallet shared kernel یا Compose جداگانهٔ دائمی ندارد. Dockerfile با build context ریشه،
shared kernel نقش A1 را نصب می‌کند و سرویس از قراردادهای مشترک A1 استفاده می‌کند.

## قابلیت‌های پیاده‌سازی‌شده

- حساب کاربر با ساخت lazy و حساب platform با seed هنگام startup
- دفترکل double-entry با مبالغ integer و `amountMinor`
- تقسیم خرید ۷۰٪ توسعه‌دهنده و ۳۰٪ platform در یک تراکنش ACID
- قفل‌گذاری ثابت accountها برای جلوگیری از deadlock و double-spend
- ledger append-only با trigger دیتابیس؛ refund با entryهای معکوس جدید
- idempotency برای تمام endpointهای جابه‌جایی پول و redeem گیفت‌کارت
- top-up با mock PSP، webhook عمومی و callback idempotent
- gift card یک‌بارمصرف و امن در برابر redeem هم‌زمان
- مصرف `trade.matched` از queue `q.wallet`
- انتشار قطعی `trade.payment_settled` در هر دو حالت موفق و ناموفق
- transactional outbox و idempotent inbox از shared kernel
- correlation ID در HTTP و event envelope
- endpointهای `/health`، `/ready` و `/metrics`

## قراردادهای مهم برای B1 و B2

مسیر داخلی سرویس:

```text
/api/v1/wallet/internal/purchase-split
/api/v1/wallet/internal/debit
/api/v1/wallet/internal/credit
/api/v1/wallet/internal/transfer
/api/v1/wallet/internal/reverse
```

خطاهای قراردادی:

- `409 INSUFFICIENT_FUNDS`
- `409 IDEMPOTENCY_KEY_REUSED`
- `404 TX_GROUP_NOT_FOUND`
- `409 ALREADY_REVERSED`

برای `trade.matched`، Wallet همیشه رویداد زیر را منتشر می‌کند:

```json
{"tradeId":"...","ok":true,"reason":null}
```

یا در شکست پرداخت:

```json
{"tradeId":"...","ok":false,"reason":"INSUFFICIENT_FUNDS"}
```

B2 در حالت موفق باید آیتم را منتقل کند و در حالت ناموفق reservation را آزاد کند.

## تست نهایی انجام‌شده

تست‌ها با image اجرایی Python 3.12، PostgreSQL و RabbitMQ واقعی، mock PSP و شبکهٔ bridge معمول
Compose اجرا شدند. `network_mode: host` در runtime استفاده نشده است.

### تست‌های Python

```bash
PYTHONPATH=services/wallet .venv/bin/pytest \
  services/wallet/tests/test_domain.py -q
# 9 passed
```

```bash
TEST_DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet \
DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet \
PYTHONPATH=services/wallet:<A1_SHARED_KERNEL> \
.venv/bin/pytest \
  services/wallet/tests/test_integration.py \
  services/wallet/tests/test_concurrency.py -q
# 6 passed
```

در branch مستقل A3، چون `pytest.ini` متعلق به A1 هنوز وارد نشده است، pytest برای marker
`integration` دو warning غیرمسدودکننده نشان می‌دهد؛ هر دو تست سبز هستند. پس از merge شدن
foundation نقش A1، marker در تنظیمات ریشه ثبت می‌شود.

### تست E2E

```bash
PYTHONPATH=services/wallet:<A1_SHARED_KERNEL> \
.venv/bin/python services/wallet/tests/a3_e2e.py
# A3 end-to-end acceptance: PASS
```

این تست موارد زیر را پوشش داد:

- احراز هویت و پاسخ خطای بدون JWT
- lazy account و موجودی
- credit/debit/transfer
- replay idempotency و reuse با body متفاوت
- purchase split و تقسیم ۷۰/۳۰
- insufficient funds
- خرید صفر برای تخفیف ۱۰۰٪
- reversal، `TX_GROUP_NOT_FOUND` و `ALREADY_REVERSED`
- gift card، replay و مصرف دوم
- top-up واقعی از طریق mock PSP و callback تکراری
- `trade.matched` موفق، ناموفق و redelivery با همان event ID
- بررسی موجودی نهایی seller
- بررسی append-only بودن ledger
- بررسی outbox و event settlement

### بررسی مستقیم runtime و دیتابیس

نتیجهٔ بررسی نهایی:

```text
wallet       healthy / running
postgres     healthy / running
rabbitmq     healthy / running
mock-psp     healthy / running
wallet-worker running

/health      {"status":"ok"}
/ready       {"status":"ready"}
/metrics     HTTP 200

unbalanced ledger groups: 0
unpublished outbox rows: 0
```

## تصمیم‌های حسابداری

- همهٔ مبالغ integer minor unit هستند و float استفاده نشده است.
- ledger اصلی هرگز update یا delete نمی‌شود.
- developer در زمان reversal می‌تواند منفی شود تا بدهی واقعی از بین نرود.
- حساب platform counterparty صدور اعتبار top-up و gift card است.
- ایجاد حساب کاربر به event `user.registered` وابسته نیست.
- اطلاعات کارت بانکی وارد Wallet نمی‌شود؛ mock PSP فقط amount، reference و callback را می‌بیند.

## اجرای نهایی پس از ورود A1

از ریشهٔ repository کامل:

```bash
cp .env.example .env
docker compose up -d --build wallet wallet-worker
```

سپس تست‌های دامنه و integration را با shared kernel نصب‌شدهٔ A1 اجرا کنید و برای acceptance:

```bash
PYTHONPATH=services/wallet \
.venv/bin/python services/wallet/tests/a3_e2e.py
```

این branch آمادهٔ review است. پس از خواندن این گزارش و بررسی commitها، push را به تصمیم شما
موکول می‌کنم.
