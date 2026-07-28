# Wallet Service — A3 Integration Guide

این سرویس مالک موجودی‌ها و دفترکل مالی پلتفرم است. هیچ سرویس دیگری به جدول‌های Wallet دسترسی
مستقیم ندارد و همه‌ی مبالغ integer و بر حسب `amountMinor` هستند.

## مرز مالکیت نقش‌ها و ساختار نهایی

این مرزبندی با خواندن کامل راهنمای هر شش نقش انجام شده است:

| نقش | مالکیت در ساختار نهایی |
|---|---|
| A1 | اسکلت repository، `.gitignore` و `.env.example`، پکیج `libs/shared_kernel`، template و scaffold سرویس‌ها، Compose ریشه، gateway و infra، `mock-psp`، اسکریپت‌های سراسری، `docs/contracts.md` و `docs/HANDOFF.md` |
| A2 | فقط پیاده‌سازی و تست‌های `services/identity` و `services/catalog` |
| **A3** | فقط پیاده‌سازی، migration، Dockerfile، تست و راهنمای **`services/wallet`** |
| B1 | `services/order`، `services/review` و مسئول release؛ شامل demo، traceability، README ریشه و به‌روزرسانی نهایی `Phase 1 Report.md` |
| B2 | `services/trading`، `services/festival` و bonusهای Kubernetes در `deploy/k8s` |
| B3 | `services/profile`، `services/media`، `services/notification`، `services/forum` و bonus achievements؛ تغییر گزارش فاز یک با هماهنگی B1 |

پس پاسخ دقیق این است: A3 مجاز نیست برای تحویل نهایی مالک `libs/shared_kernel`، Compose، تنظیمات
ریشه، ADR سراسری، گزارش فاز یک یا اسکریپت سراسری شود. تنها استثنای صریح صورت نقش این است که اگر
A1 تا صبح روز دوم `mock-psp` را نساخته بود، A3 موقتاً آن را از spec بخش ۹ A1 بسازد؛ ولی در
ساختار نهایی همچنان این component متعلق به foundation است. به همین دلیل خروجی این branch فقط
زیر `services/wallet/` قرار دارد و بر foundation نقش A1 سوار می‌شود.

## پیش‌نیاز و اجرا

طبق برنامهٔ تقسیم کار، این branch باید از `feat/a1-platform` ساخته یا پس از آماده‌شدن آن روی A1
rebase/merge شود. A1 موارد `libs/shared_kernel`، `.env.example`، `docker-compose.yml`، database
و user مربوط به Wallet، RabbitMQ، gateway و `mock-psp` را فراهم می‌کند. سپس از ریشهٔ repository:

```bash
cp .env.example .env
docker compose up -d --build wallet wallet-worker
```

طبق قرارداد A1، API مستقیم روی پورت `8005` و از Gateway با prefix `/api/v1/wallet` روی پورت
`8000` route می‌شود. Dockerfile از build context ریشه، پکیج A1 در `libs/shared_kernel` را نصب
می‌کند؛ این dependency عمداً داخل Wallet کپی نشده است.

برای اجرای تست دامنه بدون Docker:

```bash
python -m venv .venv
.venv/bin/pip install -e libs/shared_kernel pytest pytest-cov
PYTHONPATH=services/wallet .venv/bin/pytest services/wallet/tests/test_domain.py -q
```

تست‌های PostgreSQL با `TEST_DATABASE_URL` و migration اجرا می‌شوند:

```bash
TEST_DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet \
DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet \
PYTHONPATH=services/wallet .venv/bin/pytest services/wallet/tests -q
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
`WALLET_CALLBACK_URL`، `PLATFORM_ACCOUNT_ID` و `EVENT_EXCHANGE`.

## تصمیم‌ها و known gaps

- REST/JSON برای callهای sync داخلی مطابق جدول endpointهای خود صورت نقش A3 استفاده شده است.
- حساب کاربر lazy ساخته می‌شود؛ Wallet به `user.registered` برای ایجاد حساب وابسته نیست.
- حساب پلتفرم در startup پس از migration seed می‌شود؛ حساب کاربران فقط در اولین دسترسی ساخته می‌شود.
- حساب platform طرف مقابل صدور اعتبار است و در صورت top-up/gift card می‌تواند منفی شود.
- برای debit عادی، `balance_minor` هرگز زیر صفر نمی‌رود؛ فقط reversal می‌تواند بدهی توسعه‌دهنده ایجاد کند.
- endpointهای internal در Compose برای سرویس‌های هم‌تیمی هستند؛ در Compose نهایی باید با network
  policy یا service credential مشترک Gateway ایزوله شوند.
- Compose و mock PSP توسط A1 تأمین می‌شوند؛ Wallet فقط URLهای آن‌ها را از env می‌گیرد.
- mock PSP عمداً پرداخت واقعی، card number و authentication بانکی ندارد.

---

## ماتریس تطبیق کامل صورت مسئله و نقش A3

این بخش، `A3-wallet-payments.md`، گزارش فاز ۱ و User Storyهای واگذارشده به A3 را بندبه‌بند
به پیاده‌سازی و شاهد تست متصل می‌کند. وضعیت‌های این جدول‌ها بر اساس اجرای واقعی در تاریخ
`2026-07-28` ثبت شده‌اند.

### User Storyها

| User Story | خواسته | مسئولیت دقیق Wallet | پیاده‌سازی | شاهد تست | وضعیت |
|---|---|---|---|---|---|
| US-14 | هر فروش به‌صورت تراکنشی ۷۰٪ برای توسعه‌دهنده و ۳۰٪ برای پلتفرم تقسیم شود | debit خریدار و دو credit در یک transaction و یک `txGroupId` | `split_revenue`، `purchase_entries` و `POST /internal/purchase-split` | unit برای rounding و E2E با مبلغ ۵۰۰٬۰۰۰ و نتیجه `-500000/+350000/+150000` | ✅ پاس |
| US-28، نیمه settlement | پس از match وجه و آیتم گم نشوند | مصرف `trade.matched`، انتقال وجه buyer→seller، پاسخ قطعی success/failure و idempotent consumer | `settle_trade`، `shared_kernel.inbox.claim`، `q.wallet` و `trade.payment_settled` | E2E موفق، insufficient funds، redelivery یک event ID و کنترل موجودی seller | ✅ پاس |
| US-34 | شارژ کیف پول از طریق درگاه پرداخت | ایجاد `PENDING`، تماس با PSP، webhook عمومی، credit یک‌باره و event | `initiate_topup`، `handle_callback` و mock PSP | E2E واقعی HTTP و integration test تکرار callback | ✅ پاس |
| US-35 | redeem گیفت‌کارت برای افزایش موجودی | تولید کد، row lock، ثبت مصرف و credit در یک transaction | `create_cards` و `redeem_card` | integration concurrency و E2E replay/second-key conflict | ✅ پاس |
| US-36 | refund باید ثبت‌های خرید را دقیقاً معکوس کند | خواندن گروه اصلی، منع reversal دوم و درج گروه flip‌شده | `reverse_group` و `POST /internal/reverse` | unit cancellation، integration restore و E2E خطاهای 404/409 | ✅ پاس |

مرزهای دامنه:

- قانون «درخواست refund حداکثر تا ۱۲ ساعت» متعلق به Order/B1 است؛ Wallet بعد از تایید Order فقط
  reversal حسابداری را انجام می‌دهد.
- انتقال مالکیت آیتم متعلق به Trading/B2 است؛ Wallet نتیجه‌ی قطعی پرداخت را برای ادامه یا جبران
  ساگا منتشر می‌کند.

### سه قانون اصلی صحت مالی

| الزام A3 | نحوه پوشش | شاهد |
|---|---|---|
| مبلغ فقط integer minor unit؛ float ممنوع | تمام schemaها `BIGINT`، مدل‌ها `int` و APIها `amountMinor` دارند | unit suite و OpenAPI schema |
| Ledger فقط append-only | برنامه فقط `INSERT` دارد و trigger دیتابیس UPDATE و DELETE را رد می‌کند | E2E هر دو دستور UPDATE و DELETE را اجرا و خطای `append-only` دریافت می‌کند |
| هر transaction group متوازن است | `assert_balanced` پیش از persist تمام entryها اجرا می‌شود | unit tests و SQL invariant روی تمام داده‌های E2E؛ صفر گروه نامتوازن |

### مدل داده

| خواسته صورت نقش | پیاده‌سازی | وضعیت |
|---|---|---|
| `accounts` با owner یکتا و cached balance | UUID، `USER/PLATFORM` check، unique owner و `BIGINT balance_minor` | ✅ migration و PostgreSQL واقعی |
| `ledger_entries` با group/account/direction/amount/reason/reference/correlation | تمام ستون‌ها، FK، indexهای account و group و checkهای direction/amount | ✅ migration و query واقعی |
| `gift_cards` با redemption metadata | code PK، amount، `redeemed_by` و `redeemed_at` | ✅ |
| `topups` با `PENDING/SUCCEEDED/FAILED` و PSP id | check وضعیت، payment id یکتا و redirect URL | ✅ |
| `idempotency_keys` | schema migration در Wallet؛ مدل و primitiveهای replay/record از A1 shared kernel | ✅ |
| Transactional Outbox | schema migration در Wallet؛ enqueue/publisher و envelope از A1 shared kernel | ✅؛ پایان E2E صفر پیام unpublished |
| Idempotent Inbox | schema migration در Wallet؛ `claim` و مدل processed event از A1 shared kernel | ✅؛ first claim true و redelivery false |
| seed حساب platform در startup | startup hook پس از Alembic، با upsert و row lock | ✅ |
| ساخت lazy حساب کاربر | upsert در اولین GET یا عملیات مالی؛ بدون وابستگی به `user.registered` | ✅ |

عدم وجود check عمومی `balance_minor >= 0` عمدی است: debitهای معمولی در application layer منفی‌شدن
کاربر را رد می‌کنند، اما reversal اجازه می‌دهد بدهی توسعه‌دهنده صادقانه ثبت شود. حساب platform نیز
طرف مقابل صدور اعتبار top-up/gift card است و می‌تواند منفی باشد.

### Endpointهای عمومی

| Endpoint | قرارداد مورد انتظار | پیاده‌سازی و تست |
|---|---|---|
| `GET /wallets/me` | JWT، `{userId,balanceMinor}` | E2E: بدون JWT برابر 401، با JWT برابر 200 و lazy account |
| `GET /wallets/me/ledger` | JWT، pagination و فهرست entryها | limit/offset validation و E2E با ledger غیرخالی |
| `POST /topups/initiate` | JWT، `{amountMinor}` → `{topupId,redirectUrl}` | E2E Wallet→mock-PSP واقعی و redirect روی 8020 |
| `POST /topups/callback` | عمومی و بدون JWT، `{paymentId,reference,status}` | reference/payment/status validation، row lock و callback idempotent |
| `POST /giftcards/redeem` | JWT، `{code}` → مبلغ و موجودی جدید | idempotency، row lock و conflict بعد از مصرف |
| `POST /giftcards` | فقط ADMIN، `{amountMinor,count}` | RBAC و تولید کدهای `XXXX-XXXX-XXXX-XXXX`؛ E2E برابر 201 |

### Endpointهای داخلی

| Endpoint | رفتار | تست واقعی |
|---|---|---|
| `/internal/purchase-split` | سه entry، ۷۰/۳۰، row lock ثابت و یک commit | success، replay، insufficient و zero purchase |
| `/internal/debit` | debit کاربر، credit platform و منع منفی‌شدن | E2E debit و balance دقیق |
| `/internal/credit` | debit platform، credit کاربر | E2E credit، replay و key-reuse conflict |
| `/internal/transfer` | debit sender و credit recipient | E2E انتقال و انتقال برگشتی با موجودی دقیق |
| `/internal/reverse` | flip تمام entryها، ref به گروه اصلی | restore، `TX_GROUP_NOT_FOUND` و `ALREADY_REVERSED` |

تمام endpointهای پولی داخلی `Idempotency-Key` را اجباری می‌کنند. قفل advisory بر اساس key، hash
شامل scope و body، نتیجه و ledger movement در یک transaction هستند. تست‌ها سه حالت missing key،
replay یکسان و استفاده همان key با body متفاوت را پوشش می‌دهند.

### خطاهای قراردادی B1/B2

| HTTP/code | شرایط | تست |
|---|---|---|
| `400 IDEMPOTENCY_KEY_REQUIRED` | header وجود ندارد | ✅ E2E |
| `409 IDEMPOTENCY_KEY_REUSED` | key یکسان و body متفاوت | ✅ E2E |
| `409 INSUFFICIENT_FUNDS` | debit/purchase/trade بیشتر از موجودی | ✅ pytest و E2E API/event |
| `404 TX_GROUP_NOT_FOUND` | reverse گروه ناشناخته | ✅ E2E |
| `409 ALREADY_REVERSED` | reverse مجدد با key جدید | ✅ E2E |
| `404 GIFTCARD_NOT_FOUND` | کد ناشناخته | پیاده‌سازی‌شده در `redeem_card` |
| `409 GIFTCARD_ALREADY_REDEEMED` | مصرف دوم کارت | ✅ pytest concurrency و E2E |

تمام خطاهای HTTP از envelope مشترک `error.code/message/correlationId` استفاده می‌کنند.

### جزئیات حساس purchase، top-up، gift card و reversal

| بند صورت نقش | نتیجه تطبیق |
|---|---|
| accountها پیش از خرید با ترتیب ثابت lock شوند | query نهایی `ORDER BY Account.id FOR UPDATE` دارد؛ تست double-spend هم‌زمان پاس است |
| idempotency و پول در یک transaction باشند | wrapper محلی روی `shared_kernel.idempotency` فقط پس از ثبت response و movement یک‌بار commit می‌کند |
| خرید صفر برای تخفیف ۱۰۰٪ موفق و دارای سه entry صفر باشد | E2E موفق و balance بدون تغییر |
| callback فقط reference متعلق به top-up را بپذیرد | UUID، وجود row، payment id، وضعیت و row lock کنترل می‌شوند |
| callback تکراری دوباره credit نکند | integration test: اول `credited=true` و دوم `credited=false` |
| اطلاعات کارت هرگز وارد Wallet نشود | قرارداد PSP فقط amount/callback/reference دارد؛ schema و log هیچ card field ندارند |
| گیفت‌کارت concurrency-safe باشد | `SELECT ... FOR UPDATE`؛ از دو thread دقیقاً یکی موفق است |
| کد کارت ۱۶ uppercase alphanumeric باشد | `new_code` خروجی چهار گروه چهارتایی می‌دهد |
| refund entryهای اصلی را تغییر ندهد | گروه جدید با `ref_type=REVERSAL` و `ref_id=original` درج می‌شود |
| developer در refund بتواند بدهکار شود | check عمومی balance حذف و تصمیم مستند شده است |

### Worker و رویدادها

| الزام | پیاده‌سازی | تست |
|---|---|---|
| worker شامل publisher و consumer باشد | thread daemon برای `shared_kernel.outbox.run_publisher` و main thread برای `q.wallet` | container مستقل `wallet-worker` سالم |
| exchange topic و queue durable | topology مشترک A1، `platform.events` و `q.wallet` با binding `trade.matched` | RabbitMQ واقعی |
| event ورودی idempotent باشد | `shared_kernel.inbox.claim` و processed-event PK | pytest regression و E2E انتشار دوباره همان event ID |
| همیشه settlement result منتشر شود | success و `DomainError` هر دو outbox event می‌سازند | E2E برای `ok=true` و `ok=false` |
| outbox پیام‌ها را از دست ندهد | تغییر مالی و outbox در یک transaction؛ publisher مشترک A1 پس از publish مقدار `published_at` را ثبت می‌کند | E2E: تمام outboxها published |

### NFRهای مرتبط با A3

| NFR | پوشش | مدرک |
|---|---|---|
| NFR-03 یکپارچگی مالی | ACID محلی، double-entry، fixed row locks، idempotency و rollback | concurrency/integration/E2E |
| NFR-04 امنیت | JWT روی routeهای کاربر، ADMIN RBAC، عدم دریافت اطلاعات کارت | auth E2E و قرارداد mock PSP |
| NFR-06 قابلیت اطمینان workflow | Transactional Outbox مشترک A1، processed events و settlement failure event | RabbitMQ E2E |
| NFR-07 حسابرسی | append-only trigger، correlation ID و reversal entry | mutation rejection و invariant SQL |
| NFR-09 استقرارپذیری | Dockerfile مبتنی بر template و build context ریشهٔ A1؛ env/Compose در مالکیت A1 | API و worker در Compose A1-compatible سالم |
| NFR-10 مشاهده‌پذیری | health/readiness/metrics/logging/correlation از `shared_kernel.app` نقش A1 | HTTP E2E و healthcheck |

### نتایج آزمون ثبت‌شده

پس از هم‌ترازکردن ساختار، برای اطمینان یک foundation موقت دقیقاً با layout و API منتشرشده در نقش
A1 ساخته شد، تست‌ها اجرا شدند و سپس آن harness از branch حذف شد تا مالکیت A1 نقض نشود. نتیجه:

- Python میزبان 3.13 و image اجرایی `python:3.12-slim`.
- PostgreSQL و RabbitMQ واقعی؛ API و worker روی شبکهٔ bridge معمول Compose healthy/running.
- `--network=host` فقط برای دانلود dependencyها در مرحلهٔ build این ماشین بود؛ runtime host نبود.

دستورها و نتیجه:

```bash
PYTHONPATH=services/wallet:libs/shared_kernel \
  .venv/bin/pytest services/wallet/tests/test_domain.py -q
# 9 passed

TEST_DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet \
DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet \
PYTHONPATH=services/wallet:libs/shared_kernel \
  .venv/bin/pytest services/wallet/tests/test_domain.py \
  services/wallet/tests/test_integration.py services/wallet/tests/test_concurrency.py -q
# 15 passed

docker build --network=host -f services/wallet/Dockerfile -t laeb-wallet .
docker compose up -d --no-build wallet wallet-worker

PYTHONPATH=services/wallet:libs/shared_kernel \
  .venv/bin/python services/wallet/tests/a3_e2e.py
# A3 end-to-end acceptance: PASS
```

Compose، PostgreSQL، RabbitMQ و mock PSP بالا متعلق به A1 هستند و برای تست موقت استفاده شدند؛
هیچ‌کدام در commit نهایی A3 وجود ندارند. اگر محیط ساخت به PyPI دسترسی عادی داشته باشد، دستور
استاندارد `docker compose build wallet wallet-worker` کافی است.

تست E2E علاوه بر HTTP، مستقیماً PostgreSQL و RabbitMQ را بررسی می‌کند؛ بنابراین پاسخ 200 به‌تنهایی
معیار قبولی نیست و ledger invariant، موجودی نهایی، outbox، redelivery و triggerهای دیتابیس نیز
اثبات می‌شوند.
