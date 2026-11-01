---
id: privacy-and-data-deletion
title: "Privacy and data deletion"
title_ar: "الخصوصية وحذف البيانات"
audience: customer
verticals: [food, grocery, pharmacy, parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: PRV-01
    title: "What is kept and for how long"
    title_ar: "ما يُحتفظ به ومدة ذلك"
    visibility: public
    tags: [privacy, retention]
    rule_keys: [privacy.retention]
  - id: PRV-02
    title: "Getting a copy of your data"
    title_ar: "الحصول على نسخة من بياناتك"
    visibility: public
    tags: [privacy]
    rule_keys: [privacy.export_days, privacy.export_free_every_days]
  - id: PRV-03
    title: "Deleting an account"
    title_ar: "حذف الحساب"
    visibility: public
    tags: [privacy, deletion, edge-case]
    rule_keys: [privacy.deletion_cooloff_days, privacy.deletion_complete_days, privacy.retention.order_payment_records_years, privacy.retention.safety_records_years, privacy.retention.prescription_images_months]
  - id: PRV-04
    title: "Credit and points at deletion"
    title_ar: "الرصيد والنقاط عند الحذف"
    visibility: public
    tags: [privacy, deletion, credit, edge-case]
    rule_keys: [privacy.refund_credit_payout_min_qar, privacy.refund_credit_payout_business_days]
  - id: PRV-05
    title: "Sharing, masking and messages"
    title_ar: "المشاركة وإخفاء البيانات والرسائل"
    visibility: public
    tags: [privacy, edge-case]
    rule_keys: [privacy.masked_contact_hours_after_delivery, privacy.marketing_opt_out_hours, privacy.incident_notice_hours]
---

# Privacy and data deletion

<div lang="ar" dir="rtl">

# الخصوصية وحذف البيانات

</div>

## PRV-01: What is kept and for how long

This is Jalboot company policy. It does not describe what any law requires.

Jalboot uses account, order, location and payment details to deliver orders, handle support and prevent fraud. Full card numbers are held by the payment provider, not by Jalboot.

| Data | Kept for |
|---|---|
| Order and payment records | 5 years |
| Safety incident records | 5 years |
| Prescription images | 24 months |
| Chat transcripts | 12 months |
| Call recordings | 6 months |
| Driver GPS traces | 90 days |

<div lang="ar" dir="rtl">

### ما يُحتفظ به ومدة ذلك

هذه سياسة شركة جالبوت، ولا تصف ما يفرضه أي قانون.

تستخدم جالبوت بيانات الحساب والطلبات والموقع والدفع لتوصيل الطلبات وتقديم الدعم ومنع الاحتيال. أما أرقام البطاقات الكاملة فيحتفظ بها مزود خدمة الدفع لا جالبوت.

| البيانات | مدة الاحتفاظ |
|---|---|
| سجلات الطلبات والمدفوعات | 5 سنوات |
| سجلات حوادث السلامة | 5 سنوات |
| صور الوصفات الطبية | 24 شهرًا |
| نصوص المحادثات | 12 شهرًا |
| تسجيلات المكالمات | 6 أشهر |
| مسارات تحديد موقع المندوب | 90 يومًا |

</div>

## PRV-02: Getting a copy of your data

The customer can ask for a copy of their data in the app, after verification (ACC-01). The file arrives within 30 days. One copy is free every 90 days. Support cannot send personal data in chat.

<div lang="ar" dir="rtl">

### الحصول على نسخة من بياناتك

يمكن للعميل طلب نسخة من بياناته عبر التطبيق بعد التحقق (ACC-01)، ويصله الملف خلال 30 يومًا. وتُتاح نسخة مجانية واحدة كل 90 يومًا. ولا يرسل الدعم البيانات الشخصية عبر المحادثة.

</div>

## PRV-03: Deleting an account

1. The customer requests deletion in the app, after verification.
2. A 14-day cooling-off period starts. The customer can cancel the request during this time. Placing an order cancels it too. Signing in alone does not.
3. Deletion finishes within 30 days after the cooling-off period ends.

**Deletion cannot start while** the account has an active order, an open claim, an open bank dispute or an outstanding balance. Support cannot shorten the cooling-off period.

**After deletion, these stay for their full periods:** order and payment records (5 years), safety records (5 years) and prescription images (24 months). They are removed when those periods end, and deletion does not shorten them.

Deletion cannot be undone once finished.

<div lang="ar" dir="rtl">

### حذف الحساب

1. يطلب العميل حذف الحساب عبر التطبيق بعد التحقق.
2. تبدأ فترة تهدئة مدتها 14 يومًا، ويمكن للعميل خلالها إلغاء الطلب. كما يؤدي تقديم طلب شراء إلى إلغائه، أما تسجيل الدخول وحده فلا يلغيه.
3. يكتمل الحذف خلال 30 يومًا من انتهاء فترة التهدئة.

**لا يبدأ الحذف** إذا كان في الحساب طلب قائم، أو مطالبة مفتوحة، أو اعتراض بنكي مفتوح، أو مديونية. ولا يستطيع الدعم تقصير فترة التهدئة.

**يبقى بعد الحذف لمدته الكاملة:** سجلات الطلبات والمدفوعات (5 سنوات)، وسجلات السلامة (5 سنوات)، وصور الوصفات الطبية (24 شهرًا). وتُزال عند انتهاء هذه المدد، ولا يقصّرها الحذف.

ولا يمكن التراجع عن الحذف بعد اكتماله.

</div>

## PRV-04: Credit and points at deletion

Tell the customer all of this before they confirm:

- **Refund credit of QAR 10 or more:** paid to the last valid card on the account within 10 business days after deletion finishes.
- **Refund credit below QAR 10:** forfeited.
- **Goodwill credit and points:** forfeited.
- **Plus:** ends with no refund.
- **Outstanding balance:** must be paid first.

If there is no valid card on the account, refund credit cannot be paid out. The customer should spend it before deleting, or contact a support agent first.

<div lang="ar" dir="rtl">

### الرصيد والنقاط عند الحذف

يُبلَّغ العميل بكل ما يلي قبل التأكيد:

- **رصيد الاسترداد البالغ 10 ر.ق أو أكثر:** يُحوَّل إلى آخر بطاقة صالحة في الحساب خلال 10 أيام عمل من اكتمال الحذف.
- **رصيد الاسترداد الأقل من 10 ر.ق:** يسقط.
- **رصيد الترضية والنقاط:** يسقطان.
- **اشتراك Plus:** ينتهي دون استرداد.
- **المديونية:** يجب سدادها أولًا.

وإذا لم توجد بطاقة صالحة في الحساب، فلا يمكن تحويل رصيد الاسترداد، وينبغي للعميل إنفاقه قبل الحذف أو التواصل مع موظف الدعم أولًا.

</div>

## PRV-05: Sharing, masking and messages

- Drivers see the customer's first name, the delivery address and delivery notes. Merchants see the order and the first name. Neither sees payment details.
- Calls between driver and customer use masked numbers, which stop working 2 hours after delivery.
- Pharmacies see prescriptions. Drivers do not.
- Support discusses an account only with the verified account holder, not with a family member, employer or friend.
- Any request from an outside body goes to the Jalboot privacy team. Support does not answer it.
- If a customer pastes a card number in chat, it is masked. Tell them not to share it and move on.
- A marketing opt-out takes effect within 48 hours. Order and safety messages continue.
- If a data incident is confirmed, Jalboot aims to tell affected customers within 72 hours of confirming it.

<div lang="ar" dir="rtl">

### المشاركة وإخفاء البيانات والرسائل

- يرى المندوب الاسم الأول للعميل وعنوان التوصيل وملاحظات التوصيل، ويرى التاجر الطلب والاسم الأول، ولا يرى أي منهما بيانات الدفع.
- تتم المكالمات بين المندوب والعميل بأرقام مخفية يتوقف عملها بعد ساعتين (2) من التسليم.
- ترى الصيدلية الوصفة الطبية، ولا يراها المندوب.
- لا يناقش الدعم الحساب إلا مع صاحبه بعد التحقق منه، لا مع أحد أفراد الأسرة أو جهة العمل أو صديق.
- يُحال أي طلب من جهة خارجية إلى فريق الخصوصية في جالبوت، ولا يرد عليه الدعم.
- إذا لصق العميل رقم بطاقته في المحادثة يُخفى الرقم، ويُنبَّه إلى عدم مشاركته، ثم تستمر المحادثة.
- يسري إلغاء الاشتراك في الرسائل التسويقية خلال 48 ساعة، وتستمر رسائل الطلبات والسلامة.
- عند تأكيد حادث يمس البيانات، تسعى جالبوت إلى إبلاغ العملاء المتأثرين خلال 72 ساعة من التأكيد.

</div>
