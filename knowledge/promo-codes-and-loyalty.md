---
id: promo-codes-and-loyalty
title: "Promo codes and loyalty"
title_ar: "رموز الخصم وبرنامج الولاء"
audience: customer
verticals: [food, grocery, pharmacy, parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: PRM-01
    title: "Promo code rules and current codes"
    title_ar: "قواعد رموز الخصم والرموز الحالية"
    visibility: public
    tags: [promo, edge-case]
    rule_keys: [promos.max_codes_per_order, promos.codes.WELCOME40.value, promos.codes.WELCOME40.max_discount_qar, promos.codes.WELCOME40.min_spend_qar, promos.codes.SAVE20.value, promos.codes.SAVE20.max_discount_qar, promos.codes.SAVE20.min_spend_qar, promos.codes.GROCERY15.value, promos.codes.GROCERY15.min_spend_qar, promos.codes.FREEDROP.min_spend_qar, promos.codes.PARCEL10.value, promos.codes.PARCEL10.min_base_fee_qar, promos.codes.SUMMER25.value, promos.codes.SUMMER25.max_discount_qar, promos.codes.SUMMER25.min_spend_qar]
  - id: PRM-02
    title: "Promo codes after a refund or cancellation"
    title_ar: "رموز الخصم بعد الاسترداد أو الإلغاء"
    visibility: public
    tags: [promo, edge-case]
    rule_keys: [promos.restore_extension_days]
  - id: PRM-03
    title: "Referral reward"
    title_ar: "مكافأة الإحالة"
    visibility: public
    tags: [referral]
    rule_keys: [promos.referral]
  - id: PRM-04
    title: "Points"
    title_ar: "النقاط"
    visibility: public
    tags: [loyalty, calculation, edge-case]
    rule_keys: [loyalty]
  - id: PRM-05
    title: "Plus membership"
    title_ar: "اشتراك Plus"
    visibility: public
    tags: [membership, edge-case]
    rule_keys: [plus.monthly_fee_qar, plus.min_subtotal_qar, plus.first_payment_refund_days]
---

# Promo codes and loyalty

<div lang="ar" dir="rtl">

# رموز الخصم وبرنامج الولاء

</div>

## PRM-01: Promo code rules and current codes

| Code | Offer | Minimum spend | Applies to | Limit | Valid until |
|---|---|---|---|---|---|
| WELCOME40 | 40% off, max QAR 30 | QAR 40 | Food, grocery, pharmacy | First delivered order | No end date |
| SAVE20 | 20% off, max QAR 25 | QAR 60 | Food | Once a calendar month | 2027-06-30 |
| GROCERY15 | QAR 15 off | QAR 100 | Grocery | Once a calendar month | 2027-06-30 |
| FREEDROP | Free delivery | QAR 50 | Food, grocery, pharmacy in Zones A, B, C | Once a calendar month | 2027-06-30 |
| PARCEL10 | QAR 10 off the parcel base fee | Base fee QAR 20 or more | Parcels | Once a calendar month | 2027-06-30 |
| SUMMER25 | 25% off, max QAR 20 | QAR 50 | Food, grocery | Once per account | Expired 2026-09-30 |

- Only 1 code can be used per order. A code can be combined with credit and points.
- Minimum spend is tested on eligible items before any discount. Prescription items are never eligible and never count toward minimum spend.
- A code is checked at `placed_at`. It runs until 23:59:59 on its last valid day.
- A code cannot be added after the order is placed. Goodwill credit is not given for a forgotten code.
- An expired code is not honoured, and support cannot extend it, except under PRM-02.
- A free delivery code covers the delivery fee only. If delivery is already free through Plus or a threshold, the app does not use up the code.
- Codes are limited per account, per device and per payment card. Using several accounts to repeat a code leads to account closure.

<div lang="ar" dir="rtl">

### قواعد رموز الخصم والرموز الحالية

| الرمز | العرض | الحد الأدنى للإنفاق | يسري على | الحد | صالح حتى |
|---|---|---|---|---|---|
| WELCOME40 | خصم 40% بحد أقصى 30 ر.ق | 40 ر.ق | الطعام والبقالة والصيدلية | أول طلب يُسلَّم | دون تاريخ انتهاء |
| SAVE20 | خصم 20% بحد أقصى 25 ر.ق | 60 ر.ق | الطعام | مرة في الشهر الميلادي | 2027-06-30 |
| GROCERY15 | خصم 15 ر.ق | 100 ر.ق | البقالة | مرة في الشهر الميلادي | 2027-06-30 |
| FREEDROP | توصيل مجاني | 50 ر.ق | الطعام والبقالة والصيدلية في المناطق A وB وC | مرة في الشهر الميلادي | 2027-06-30 |
| PARCEL10 | خصم 10 ر.ق من الرسم الأساسي للطرد | رسم أساسي 20 ر.ق فأكثر | الطرود | مرة في الشهر الميلادي | 2027-06-30 |
| SUMMER25 | خصم 25% بحد أقصى 20 ر.ق | 50 ر.ق | الطعام والبقالة | مرة واحدة لكل حساب | انتهى في 2026-09-30 |

- لا يُستخدم سوى رمز واحد (1) في الطلب، ويمكن الجمع بينه وبين الرصيد والنقاط.
- يُختبر الحد الأدنى للإنفاق على الأصناف المؤهلة قبل أي خصم. والأصناف التي تُصرف بوصفة طبية غير مؤهلة أبدًا ولا تُحسب ضمن هذا الحد.
- يُفحص الرمز عند `placed_at`، ويبقى صالحًا حتى الساعة 23:59:59 من آخر يوم في صلاحيته.
- لا يمكن إضافة الرمز بعد تقديم الطلب، ولا يُمنح رصيد ترضية عن رمز نسيه العميل.
- لا يُقبل الرمز المنتهي، ولا يستطيع الدعم تمديده إلا وفق PRM-02.
- يغطي رمز التوصيل المجاني رسوم التوصيل فقط. وإذا كان التوصيل مجانيًا أصلًا بفضل Plus أو بلوغ الحد، فلا يستهلك التطبيق الرمز.
- تُقيد الرموز لكل حساب وجهاز وبطاقة دفع، ويؤدي استخدام عدة حسابات لتكرار الرمز إلى إغلاق الحساب.

</div>

## PRM-02: Promo codes after a refund or cancellation

- **Order cancelled or fully refunded:** the code comes back if it is still valid at that moment.
- **Code has expired by then:** it does not come back. The exception is a cancellation by the merchant or Jalboot, which reissues the code for 7 days.
- **WELCOME40:** a delivered order uses it up, even if that order is later refunded. It comes back only if the order was never delivered.
- **Partial refund:** the code does not come back, and the discount is not taken back, even if the remaining items fall below the minimum spend.

<div lang="ar" dir="rtl">

### رموز الخصم بعد الاسترداد أو الإلغاء

- **إلغاء الطلب أو رده بالكامل:** يعود الرمز إذا كان ما زال صالحًا في تلك اللحظة.
- **إذا انتهت صلاحية الرمز عندئذ:** لا يعود، إلا إذا كان الإلغاء من جانب التاجر أو جالبوت، فيُعاد إصداره لمدة 7 أيام.
- **WELCOME40:** يُستهلك بتسليم الطلب، حتى لو رُد مبلغ ذلك الطلب لاحقًا، ولا يعود إلا إذا لم يُسلَّم الطلب أصلًا.
- **الاسترداد الجزئي:** لا يعود الرمز، ولا يُسترجع الخصم، حتى لو نزلت الأصناف المتبقية عن الحد الأدنى للإنفاق.

</div>

## PRM-03: Referral reward

When a referred friend's first delivered order has an item subtotal of QAR 40 or more, both people get QAR 20 of goodwill-type credit. The reward posts 48 hours after delivery. A customer can earn at most 10 referral rewards in a calendar year. No reward applies if the two accounts share a device or payment card, or if the friend's first order is fully refunded before the reward posts.

<div lang="ar" dir="rtl">

### مكافأة الإحالة

إذا بلغ إجمالي أصناف أول طلب يُسلَّم للصديق المُحال 40 ر.ق أو أكثر، يحصل الطرفان على 20 ر.ق لكل منهما من الرصيد من نوع الترضية. وتُضاف المكافأة بعد 48 ساعة من التسليم. ولا يكسب العميل أكثر من 10 مكافآت إحالة في السنة الميلادية. ولا تُمنح المكافأة إذا اشترك الحسابان في جهاز أو بطاقة دفع، أو إذا رُد مبلغ أول طلب للصديق بالكامل قبل إضافتها.

</div>

## PRM-04: Points

**Earning.** 1 point per QAR 1 of item subtotal after promo discount, rounded down. Fees, tips and prescription items earn nothing. Points post 48 hours after delivery.

**Tiers.** Silver starts at 1,000 points earned in the rolling 12 months and multiplies earning by 1.25. Gold starts at 3,000 points and multiplies by 1.5. Round down after multiplying. Tier counts use base points, before the multiplier.

**Redeeming.** 100 points are worth QAR 5. Redeem in steps of 100 points, with a minimum of 200 points. Points can cover up to 50% of the item subtotal after promo discount, and cannot pay for fees or tips.

**Expiry.** Points expire 12 months after they are earned.

**After a refund.** Redeemed points come back under REF-04. Earned points on the refunded value are removed, rounded down. If the balance is too low, removal stops at zero and the rest is forgiven.

<div lang="ar" dir="rtl">

### النقاط

**الكسب:** نقطة واحدة (1) مقابل كل 1 ر.ق من إجمالي الأصناف بعد خصم الرمز، مع التقريب إلى الأسفل. ولا تكسب الرسوم والإكرامية والأصناف التي تُصرف بوصفة طبية أي نقاط. وتُضاف النقاط بعد 48 ساعة من التسليم.

**الفئات:** تبدأ الفئة الفضية من 1,000 نقطة مكتسبة خلال 12 شهرًا متحركة، ويُضرب فيها الكسب في 1.25. وتبدأ الفئة الذهبية من 3,000 نقطة ويُضرب فيها الكسب في 1.5. ويكون التقريب إلى الأسفل بعد الضرب. وتُحتسب الفئات بالنقاط الأساسية قبل المضاعفة.

**الاستبدال:** تساوي كل 100 نقطة 5 ر.ق. ويكون الاستبدال بمضاعفات 100 نقطة، بحد أدنى 200 نقطة. ويمكن أن تغطي النقاط حتى 50% من إجمالي الأصناف بعد خصم الرمز، ولا تُستخدم لسداد الرسوم أو الإكرامية.

**انتهاء الصلاحية:** تنتهي صلاحية النقاط بعد 12 شهرًا من كسبها.

**بعد الاسترداد:** تعود النقاط المستبدلة وفق REF-04. وتُزال النقاط المكتسبة عن القيمة المردودة مع التقريب إلى الأسفل. وإذا لم يكفِ الرصيد، تتوقف الإزالة عند الصفر ويُعفى العميل من الباقي.

</div>

## PRM-05: Plus membership

Plus costs QAR 29 a month. It gives free delivery on orders with an item subtotal of QAR 50 or more in Zones A, B and C. It does not cover Zone D, parcels, or peak, weather, service and small order fees.

- Plus is paid by card or mobile wallet only, not by credit or cash.
- The customer can cancel at any time. Benefits run to the end of the paid month. No part-month refund applies.
- The first-ever payment is refunded in full if the customer cancels within 7 days of it and has not used a Plus free delivery. Renewals are never refunded.
- If a renewal payment fails, benefits stop at once.

<div lang="ar" dir="rtl">

### اشتراك Plus

تبلغ تكلفة اشتراك Plus مبلغ 29 ر.ق شهريًا، ويمنح توصيلًا مجانيًا للطلبات التي يبلغ إجمالي أصنافها 50 ر.ق أو أكثر في المناطق A وB وC. ولا يشمل المنطقة D ولا الطرود، ولا رسوم الذروة أو الطقس أو الخدمة أو الطلب الصغير.

- يُدفع الاشتراك بالبطاقة أو محفظة الهاتف فقط، لا بالرصيد ولا نقدًا.
- يمكن للعميل الإلغاء في أي وقت، وتستمر المزايا حتى نهاية الشهر المدفوع، ولا يُرد مبلغ عن جزء من الشهر.
- تُرد أول دفعة على الإطلاق كاملة إذا ألغى العميل خلال 7 أيام منها ولم يستخدم توصيلًا مجانيًا عبر Plus. ولا تُرد دفعات التجديد أبدًا.
- إذا فشلت دفعة التجديد، تتوقف المزايا فورًا.

</div>
