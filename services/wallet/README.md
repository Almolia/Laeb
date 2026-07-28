# Wallet Service — A3 Integration Guide

این سرویس مالک موجودی‌ها و دفترکل مالی پلتفرم است. هیچ سرویس دیگری به جدول‌های Wallet دسترسی
مستقیم ندارد و همه‌ی مبالغ integer و بر حسب `amountMinor` هستند.

## اجرا

```bash
cp deploy/.env.example .env
docker compose -f deploy/docker-compose.wallet.yml up --build
```

API روی `http://localhost:8005`، mock PSP روی `http://localhost:8020` و RabbitMQ Management روی
`http://localhost:15672` در دسترس است. در Compose کامل تیم، این سرویس باید با prefix
`/api/v1/wallet` از Gateway روی پورت 8000 route شود.

برای اجرای تست دامنه بدون Docker:

```bash
pytest services/wallet/tests/test_domain.py -q
```

تست‌های PostgreSQL با `TEST_DATABASE_URL` و migration اجرا می‌شوند:

```bash
TEST_DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet \
  pytest services/wallet/tests -q
```

## قرارداد HTTP

تمام خطاها این شکل را دارند:

```json
{"error":{"code":"INSUFFICIENT_FUNDS","message":"...","correlationId":"..."}}
```

`X-Correlation-Id` در تمام درخواست‌ها و رویدادها propagate می‌شود. endpointهای مالی داخلی و
redeem به `Idempotency-Key` نیاز دارند. یک key با body یکسان، پاسخ قبلی را replay می‌کند؛ همان
key با body متفاوت `409 IDEMPOTENCY_KEY_REUSED` است.

| Method | Path | Auth | توضیح |
|---|---|---|---|
| GET | `/wallets/me` | JWT | موجودی تنبل‌ساخته‌ی کاربر |
| GET | `/wallets/me/ledger?limit=50&offset=0` | JWT | دفترکل صفحه‌بندی‌شده |
| POST | `/topups/initiate` | JWT | `{amountMinor}` و ایجاد PSP payment |
| POST | `/topups/callback` | عمومی | webhook؛ فقط reference معتبر پذیرفته می‌شود |
| POST | `/giftcards` | ADMIN | `{amountMinor,count}`، کدهای `XXXX-XXXX-XXXX-XXXX` |
| POST | `/giftcards/redeem` | JWT + key | مصرف یک‌باره و concurrency-safe |
| POST | `/internal/purchase-split` | service call + key | سه ثبت ACID برای Order |
| POST | `/internal/debit` | service call + key | debit کاربر و credit پلتفرم |
| POST | `/internal/credit` | service call + key | credit کاربر و debit پلتفرم |
| POST | `/internal/transfer` | service call + key | انتقال مستقیم user→user |
| POST | `/internal/reverse` | service call + key | ثبت‌های معکوس refund |

### Purchase split — برای B1

در هر تلاش خرید، `order.id` یا یک UUID پایدار را به‌عنوان `Idempotency-Key` بفرستید:

```bash
curl -X POST http://wallet:8000/api/v1/wallet/internal/purchase-split \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: 5b2d2c2a-9a79-4ea5-9a87-000000000001' \
  -d '{"buyerId":"<buyer>","developerId":"<developer>","amountMinor":500000,"orderId":"<order>"}'
```

پاسخ موفق:

```json
{"txGroupId":"<uuid>","buyerBalanceMinor":0}
```

Wallet در همان transaction سه ledger row ثبت می‌کند: buyer `DEBIT 500000`، developer
`CREDIT 350000` و platform `CREDIT 150000`. B1 باید `txGroupId` را در order ذخیره کند. اگر
ساخت entitlement بعد از debit شکست خورد، یکی از این دو جبران را با key جدید انجام دهید:

- `POST /internal/reverse` با `txGroupId` اصلی؛ یا
- `POST /internal/credit` برای مبلغ خریدار، فقط در حالتی که قرارداد ساگا صراحتاً آن را انتخاب کرده باشد.

خطاهای قابل اتکا برای B1:

- `409 INSUFFICIENT_FUNDS`: خرید ایجاد نشده و ledger row نوشته نشده است.
- `409 IDEMPOTENCY_KEY_REUSED`: key با body متفاوت استفاده شده؛ key جدید نسازید و علت را اصلاح کنید.
- `400 IDEMPOTENCY_KEY_REQUIRED`: header ارسال نشده است.
- `404 TX_GROUP_NOT_FOUND`: گروهی برای reverse پیدا نشد.
- `409 ALREADY_REVERSED`: گروه قبلاً با یک reversal موفق جبران شده است.

### Settlement — برای B2

Wallet مصرف‌کننده‌ی `trade.matched` روی queue `q.wallet` است:

```json
{
  "tradeId":"<trade>",
  "itemId":"<item>",
  "buyerId":"<buyer>",
  "sellerId":"<seller>",
  "priceMinor":2500,
  "quantity":2
}
```

مبلغ settlement برابر `priceMinor * quantity` است. Wallet همیشه event زیر را منتشر می‌کند؛ حتی
اگر موجودی خریدار کافی نباشد:

```json
{"tradeId":"<trade>","ok":true,"reason":null}
```

یا:

```json
{"tradeId":"<trade>","ok":false,"reason":"INSUFFICIENT_FUNDS"}
```

**B2 باید در هر دو حالت منتظر `trade.payment_settled` بماند.** در `ok=true` مالکیت item را
منتقل کند؛ در `ok=false` reservation را آزاد و trade را دوباره قابل‌فروش کند. هیچ سکوتی در
شکست settlement مجاز نیست.

## جریان‌های مالی

### Top-up

1. Wallet ردیف `PENDING` می‌سازد و به mock PSP درخواست charge می‌فرستد.
2. PSP فقط payment id و reference را برمی‌گرداند و سپس webhook می‌زند.
3. callback با row lock، reference و payment id را بررسی می‌کند.
4. callback موفق یک گروه `TOPUP`، event `wallet.topped_up` و status `SUCCEEDED` می‌سازد.
5. callback تکراری برای `SUCCEEDED` با HTTP 200 پاسخ می‌گیرد و credit دوباره انجام نمی‌شود.

شماره کارت هرگز به Wallet نمی‌رسد، ذخیره یا log نمی‌شود؛ این بخشی از NFR-04 است.

### Gift card

کد با ۱۶ کاراکتر uppercase alphanumeric در چهار گروه چهارتایی تولید می‌شود. رکورد card با
`SELECT FOR UPDATE` خوانده می‌شود؛ پس از تعیین `redeemed_by`، credit و ledger در همان transaction
انجام می‌شوند. کد استفاده‌شده `409 GIFTCARD_ALREADY_REDEEMED` می‌دهد.

### Refund

`/internal/reverse` همه‌ی entryهای گروه اصلی را lock می‌کند، وجود reversal قبلی را بررسی می‌کند
و entryهای flip‌شده را با `ref_type=REVERSAL` و `ref_id=<original txGroupId>` می‌نویسد. دفترکل اصلی
هرگز update یا delete نمی‌شود. اگر developer قبلاً پول را خرج کرده باشد، balance او در reversal
منفی می‌شود؛ این تصمیم حسابداری عمداً برای جلوگیری از گم‌شدن بدهی است.

## مدل داده و invariant

- `accounts`: owner type/id و cached `balance_minor`
- `ledger_entries`: `tx_group_id`, account, direction، amount، reason، reference و correlation id
- `topups`: کاربر، مبلغ، وضعیت `PENDING|SUCCEEDED|FAILED` و PSP payment id
- `gift_cards`: code، مبلغ و redemption metadata
- `idempotency_keys`: request hash و response JSON
- `outbox`: event envelope که باید بعد از تغییر محلی در همان transaction نوشته شود
- `processed_events`: جلوگیری از پردازش دوباره‌ی event id

دفترکل با trigger دیتابیس append-only است. این query باید همیشه صفر row برگرداند:

```sql
SELECT tx_group_id,
       SUM(CASE WHEN direction='CREDIT' THEN amount_minor ELSE -amount_minor END) AS total
FROM ledger_entries
GROUP BY tx_group_id
HAVING SUM(CASE WHEN direction='CREDIT' THEN amount_minor ELSE -amount_minor END) <> 0;
```

## Eventها و تنظیمات

Wallet تولید می‌کند:

- `wallet.topped_up`: `userId, amountMinor, source`
- `trade.payment_settled`: `tradeId, ok, reason`

Wallet مصرف می‌کند:

- `trade.matched`: `tradeId, itemId, buyerId, sellerId, priceMinor, quantity`

متغیرهای اصلی: `DATABASE_URL`، `JWT_SECRET`، `RABBITMQ_URL`، `MOCK_PSP_URL`،
`WALLET_CALLBACK_URL`، `PLATFORM_ACCOUNT_ID`، `EVENT_EXCHANGE` و `OUTBOX_POLL_SECONDS`.

## تصمیم‌ها و known gaps

- REST/JSON برای callهای sync داخلی استفاده شده و transport با ADR-04 از Phase 1 به‌روزرسانی شده است.
- حساب کاربر lazy ساخته می‌شود؛ Wallet به `user.registered` برای ایجاد حساب وابسته نیست.
- حساب platform طرف مقابل صدور اعتبار است و در صورت top-up/gift card می‌تواند منفی شود.
- برای debit عادی، `balance_minor` هرگز زیر صفر نمی‌رود؛ فقط reversal می‌تواند بدهی توسعه‌دهنده ایجاد کند.
- endpointهای internal در Compose برای سرویس‌های هم‌تیمی هستند؛ در Compose نهایی باید با network
  policy یا service credential مشترک Gateway ایزوله شوند.
- این Compose فقط Wallet و پیش‌نیازهای آن را دارد و باید هنگام ورود قالب A1 در Compose کل تیم merge شود.
- mock PSP عمداً پرداخت واقعی، card number و authentication بانکی ندارد.
