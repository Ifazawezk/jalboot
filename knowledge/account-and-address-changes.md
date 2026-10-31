---
id: account-and-address-changes
title: "Account and address changes"
title_ar: "تعديل الحساب والعنوان"
audience: customer
verticals: [food, grocery, pharmacy, parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: ACC-01
    title: "Verifying the account holder"
    title_ar: "التحقق من صاحب الحساب"
    visibility: public
    tags: [account, security, edge-case]
    rule_keys: [account.otp]
  - id: ACC-02
    title: "Changing phone number or email"
    title_ar: "تغيير رقم الهاتف أو البريد الإلكتروني"
    visibility: public
    tags: [account, security, edge-case]
    rule_keys: [account.phone_recovery_cooloff_hours, account.phone_recovery_credit_limit_qar]
  - id: ACC-03
    title: "Changing the address on an active order"
    title_ar: "تغيير العنوان في طلب قائم"
    visibility: public
    tags: [address, edge-case]
    rule_keys: [account.address_change, parcels.reroute_fee_qar]
  - id: ACC-04
    title: "Saved addresses, restrictions and appeals"
    title_ar: "العناوين المحفوظة والقيود والتظلمات"
    visibility: public
    tags: [account, address]
    rule_keys: [account.saved_addresses_max, account.min_age, pharmacy.min_age, account.appeal_days, account.appeal_review_business_days]
---

# Account and address changes

<div lang="ar" dir="rtl">

# تعديل الحساب والعنوان

</div>

## ACC-01: Verifying the account holder

A one-time code sent to the registered phone is needed before support changes account details, shows a full address, or starts account deletion. The customer enters the code in the app's secure prompt, never in chat.

Support never asks for a password, a one-time code in chat, a full card number or a card security code. Support shows only the last 4 digits of a card.

After 5 failed codes, the account locks for 30 minutes. Support cannot lift this lock.

<div lang="ar" dir="rtl">

### التحقق من صاحب الحساب

يلزم رمز تحقق لمرة واحدة يُرسل إلى الهاتف المسجل قبل أن يعدل الدعم بيانات الحساب أو يعرض العنوان كاملًا أو يبدأ حذف الحساب. ويُدخل العميل الرمز في نافذة التحقق الآمنة داخل التطبيق، لا في المحادثة.

ولا يطلب الدعم أبدًا كلمة المرور، ولا رمز التحقق في المحادثة، ولا رقم البطاقة كاملًا أو رمز الأمان الخاص بها. ولا يعرض من البطاقة إلا آخر 4 أرقام.

وبعد 5 محاولات خاطئة، يُقفل الحساب مدة 30 دقيقة، ولا يستطيع الدعم رفع هذا القفل.

</div>

## ACC-02: Changing phone number or email

- **Email:** confirm with a code to the registered phone, then a link sent to the new email.
- **Phone:** confirm with codes to both the old and the new number.
- **Lost access to the old number:** a support agent checks the amounts of the last 2 orders and the last 4 digits of the card used. The change then goes through with a 48-hour cooling-off period. During that time, the customer can spend at most QAR 100 of credit, and refunds can only go to payment methods already on the account.
- **Possible account takeover:** freeze the account and hand off as P1 (ESC-01).

<div lang="ar" dir="rtl">

### تغيير رقم الهاتف أو البريد الإلكتروني

- **البريد الإلكتروني:** يُؤكد التغيير برمز يُرسل إلى الهاتف المسجل، ثم برابط يُرسل إلى البريد الجديد.
- **الهاتف:** يُؤكد التغيير برمزين يُرسلان إلى الرقمين القديم والجديد.
- **فقدان الوصول إلى الرقم القديم:** يتحقق موظف الدعم من مبلغي آخر طلبين (2) وآخر 4 أرقام من البطاقة المستخدمة، ثم يتم التغيير مع فترة تهدئة مدتها 48 ساعة. وخلال هذه الفترة لا ينفق العميل أكثر من 100 ر.ق من الرصيد، ولا يُرد أي مبلغ إلا إلى وسائل الدفع الموجودة أصلًا في الحساب.
- **اشتباه في اختراق الحساب:** يُجمد الحساب وتُحال الحالة بأولوية P1 (ESC-01).

</div>

## ACC-03: Changing the address on an active order

**Allowed once per order (limit 1), before `picked_up`,** if the new pin is within 2 km of the original pin, measured in a straight line. Exactly 2 km is allowed.

- **New zone costs more:** the customer pays the difference.
- **New zone costs less:** no refund of the difference.
- **Food cannot move to Zone D,** where food delivery is not offered.
- `promised_at` resets to the new time shown. Late credit is then measured from the new time (LAT-01).

**Not allowed:**

- Prescription or cold-chain pharmacy orders.
- Any order at `picked_up` or later. A driver cannot accept an address change outside the app.

**Parcels:** the sender can change the drop-off address free before pickup. After pickup, a change costs QAR 10, plus any fee difference if the new zone is higher.

<div lang="ar" dir="rtl">

### تغيير العنوان في طلب قائم

**يُسمح بالتغيير مرة واحدة (1) لكل طلب، قبل `picked_up`،** إذا كان الموقع الجديد في حدود 2 كم من الموقع الأصلي، مقيسًا في خط مستقيم. والمسافة البالغة 2 كم تمامًا مسموح بها.

- **إذا كانت المنطقة الجديدة أعلى كلفة:** يدفع العميل الفرق.
- **إذا كانت أقل كلفة:** لا يُرد الفرق.
- **لا يمكن نقل طلب الطعام إلى المنطقة D،** إذ لا تتوفر فيها خدمة توصيل الطعام.
- يُعاد ضبط `promised_at` على الوقت الجديد الظاهر، ويُحسب رصيد التأخير عندئذ من هذا الوقت (LAT-01).

**لا يُسمح بالتغيير في الحالات الآتية:**

- طلبات الصيدلية التي تتضمن أصنافًا بوصفة طبية أو أصنافًا من سلسلة التبريد.
- أي طلب في حالة `picked_up` أو ما بعدها، ولا يستطيع المندوب قبول تغيير العنوان خارج التطبيق.

**الطرود:** يمكن للمرسل تغيير عنوان التسليم مجانًا قبل الاستلام. وبعد الاستلام يكلف التغيير 10 ر.ق، إضافة إلى فرق الرسوم إذا كانت المنطقة الجديدة أعلى.

</div>

## ACC-04: Saved addresses, restrictions and appeals

- A customer can save up to 10 addresses. If the written address and the map pin disagree, the pin is used.
- The minimum age for an account is 16. Prescription orders need age 18 (PHR-02).
- Each person can hold one account. Accounts cannot be merged, and credit and points cannot be moved between accounts.
- A suspended customer is told the reason category and can appeal within 14 days. A decision comes within 5 business days.

<div lang="ar" dir="rtl">

### العناوين المحفوظة والقيود والتظلمات

- يمكن للعميل حفظ 10 عناوين كحد أقصى. وإذا اختلف العنوان المكتوب عن الموقع المحدد على الخريطة، يُعتمد الموقع على الخريطة.
- الحد الأدنى لعمر صاحب الحساب 16 عامًا، وتتطلب طلبات الوصفات الطبية عمر 18 عامًا (PHR-02).
- لكل شخص حساب واحد، ولا تُدمج الحسابات، ولا يُنقل الرصيد أو النقاط بينها.
- يُبلَّغ العميل الموقوف بفئة السبب، ويحق له التظلم خلال 14 يومًا، ويصدر القرار خلال 5 أيام عمل.

</div>
