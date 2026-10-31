---
id: payments-and-failed-charges
title: "Payments and failed charges"
title_ar: "المدفوعات وعمليات الخصم الفاشلة"
audience: customer
verticals: [food, grocery, pharmacy, parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: PAY-01
    title: "Accepted payment methods"
    title_ar: "وسائل الدفع المقبولة"
    visibility: public
    tags: [payments]
    rule_keys: []
  - id: PAY-02
    title: "Holds and failed payments"
    title_ar: "الحجز المؤقت وفشل الدفع"
    visibility: public
    tags: [payments, edge-case]
    rule_keys: [payments.grocery_hold_pct, payments.hold_release_business_days, payments.retry, payments.cod.outstanding_balance_cap_qar]
  - id: PAY-03
    title: "Duplicate charges"
    title_ar: "الخصم المكرر"
    visibility: public
    tags: [payments, refunds, edge-case]
    rule_keys: [payments.duplicate_charge]
  - id: PAY-04
    title: "Cash on delivery"
    title_ar: "الدفع نقدًا عند الاستلام"
    visibility: public
    tags: [payments, cash, edge-case]
    rule_keys: [payments.cod.max_order_qar, payments.cod.new_customer_max_order_qar, payments.cod.new_customer_account_days, payments.cod.new_customer_min_delivered_orders, payments.cod.driver_change_max_qar, payments.cod.refused_limit, payments.cod.refused_window_days, payments.cod.refused_disable_days, refunds.timing.credit_minutes]
  - id: PAY-05
    title: "Bank disputes and failed refunds"
    title_ar: "الاعتراضات البنكية وفشل الاسترداد"
    visibility: public
    tags: [payments, refunds, edge-case]
    rule_keys: [payments.failed_refund_to_credit_business_days]
---

# Payments and failed charges

<div lang="ar" dir="rtl">

# المدفوعات وعمليات الخصم الفاشلة

</div>

## PAY-01: Accepted payment methods

- Bank debit and credit cards.
- Mobile wallets.
- Jalboot Credit (REF-08).
- Points, for items only (PRM-04).
- Cash on delivery, for food, grocery and pharmacy orders only (PAY-04). Parcels and Plus cannot be paid in cash.

One order can use one card or one mobile wallet, plus credit and points. A cash order can also use credit and points.

All prices are in QAR. If a card is in another currency, Jalboot does not cover the bank's exchange difference or fees, including when a refund is made.

<div lang="ar" dir="rtl">

### وسائل الدفع المقبولة

- بطاقات الخصم المباشر والبطاقات الائتمانية.
- محافظ الهاتف.
- رصيد جالبوت (REF-08).
- النقاط، لسداد قيمة الأصناف فقط (PRM-04).
- الدفع نقدًا عند الاستلام، لطلبات الطعام والبقالة والصيدلية فقط (PAY-04). ولا يمكن دفع قيمة الطرود أو اشتراك Plus نقدًا.

يمكن أن يجمع الطلب الواحد بين بطاقة واحدة أو محفظة هاتف واحدة وبين الرصيد والنقاط. ويمكن كذلك استخدام الرصيد والنقاط في الطلب النقدي.

جميع الأسعار بالريال القطري. وإذا كانت البطاقة بعملة أخرى، فلا تتحمل جالبوت فرق سعر الصرف أو رسوم البنك، بما في ذلك عند الاسترداد.

</div>

## PAY-02: Holds and failed payments

**Holds.** When an order is placed, the bank holds the amount due. For grocery orders, the hold is 110% of the estimated total, because weighed items can change the final price. The final charge happens at delivery.

A hold is not a charge, and there is nothing to refund. The bank releases it within 7 business days of a cancellation or a change in amount. If a pending amount still shows after 7 business days, a support agent investigates it as a possible charge.

**Failed payments.** If payment fails, the order is not placed and the merchant is not told. After 3 failed attempts within 15 minutes, card and mobile wallet payments are locked for 30 minutes. Support cannot lift this lock.

**Charge fails after delivery.** The full amount becomes an outstanding balance, which must be paid before the next order. The QAR 30 cap in CAN-05 applies only to cash cancellation charges, not here.

<div lang="ar" dir="rtl">

### الحجز المؤقت وفشل الدفع

**الحجز المؤقت:** عند تقديم الطلب يحجز البنك المبلغ المستحق. وفي طلبات البقالة يكون الحجز 110% من الإجمالي التقديري، لأن الأصناف الموزونة قد تغيّر السعر النهائي. ويتم الخصم النهائي عند التسليم.

والحجز ليس خصمًا، فلا يوجد ما يُرد. ويفك البنك الحجز خلال 7 أيام عمل من الإلغاء أو تغيّر المبلغ. وإذا بقي مبلغ معلق بعد 7 أيام عمل، يفحصه موظف الدعم بوصفه خصمًا محتملًا.

**فشل الدفع:** إذا فشل الدفع لا يُقدم الطلب ولا يُبلَّغ التاجر. وبعد 3 محاولات فاشلة خلال 15 دقيقة، يُقفل الدفع بالبطاقة ومحفظة الهاتف مدة 30 دقيقة، ولا يستطيع الدعم رفع هذا القفل.

**فشل الخصم بعد التسليم:** يتحول كامل المبلغ إلى مديونية يجب سدادها قبل الطلب التالي. أما سقف 30 ر.ق الوارد في CAN-05 فيخص رسوم إلغاء الطلبات النقدية فقط، ولا ينطبق هنا.

</div>

## PAY-03: Duplicate charges

A duplicate charge means two final charges of the same amount on the same order, confirmed in payment records.

- Report within 30 days of the charge date.
- A confirmed duplicate goes back to the same method. The refund starts within 3 business days.
- Automated support can approve up to QAR 300 for a confirmed duplicate. This is separate from the limit in REF-05, because the money was never owed. It needs no photo and is not counted as a claim.

**Not a duplicate:**

- A hold plus a final charge. Wait for the hold to clear (PAY-02).
- Two different orders for the same amount. Those are two orders, and normal cancellation rules apply.

<div lang="ar" dir="rtl">

### الخصم المكرر

يعني الخصم المكرر وجود عمليتي خصم نهائيتين بالمبلغ نفسه على الطلب نفسه، مؤكدتين في سجلات الدفع.

- يجب الإبلاغ خلال 30 يومًا من تاريخ الخصم.
- يعود المبلغ المؤكد تكراره إلى الوسيلة نفسها، ويبدأ الرد خلال 3 أيام عمل.
- يمكن للدعم الآلي الموافقة على ما يصل إلى 300 ر.ق في الخصم المكرر المؤكد. وهذا الحد منفصل عن الحد الوارد في REF-05، لأن المبلغ لم يكن مستحقًا أصلًا، ولا يحتاج إلى صورة ولا يُحسب مطالبة.

**لا يُعد خصمًا مكررًا:**

- حجز مؤقت مع خصم نهائي؛ فعلى العميل انتظار فك الحجز (PAY-02).
- طلبان مختلفان بالمبلغ نفسه؛ فهما طلبان منفصلان وتنطبق عليهما قواعد الإلغاء المعتادة.

</div>

## PAY-04: Cash on delivery

- Maximum cash order: QAR 300. The limit applies to the part due in cash, after credit and points.
- New customers: QAR 150. A customer is new if the account is younger than 30 days or has fewer than 3 delivered orders.
- A driver carries up to QAR 100 in change. If the driver cannot give full change, the difference is added as refund credit within 15 minutes.
- Refusing a cash order at the door without a valid reason counts as a refusal. After 2 refusals in the rolling 30 days, cash on delivery is switched off for 90 days.
- An outstanding balance switches cash on delivery off until it is paid.

<div lang="ar" dir="rtl">

### الدفع نقدًا عند الاستلام

- الحد الأقصى للطلب النقدي: 300 ر.ق، ويسري على الجزء المستحق نقدًا بعد الرصيد والنقاط.
- العملاء الجدد: 150 ر.ق. ويُعد العميل جديدًا إذا كان عمر حسابه أقل من 30 يومًا أو كان لديه أقل من 3 طلبات مُسلَّمة.
- يحمل المندوب ما يصل إلى 100 ر.ق لرد الباقي. وإذا تعذر عليه رد الباقي كاملًا، يضاف الفرق في صورة رصيد استرداد خلال 15 دقيقة.
- يُعد رفض الطلب النقدي عند الباب دون سبب مقبول رفضًا مسجلًا. وبعد رفضين (2) خلال 30 يومًا متحركة، يُوقف الدفع نقدًا مدة 90 يومًا.
- تؤدي أي مديونية قائمة إلى إيقاف الدفع نقدًا حتى سدادها.

</div>

## PAY-05: Bank disputes and failed refunds

**Open bank dispute.** Once a customer disputes a charge with their bank, support cannot refund that order until the dispute closes. Explain this plainly and do not ask the customer to withdraw it. Reporting windows keep running, but a claim logged before the dispute stays open.

**Refunded twice.** If a refund was paid and the bank also returns the money, the extra amount becomes an outstanding balance.

**Failed refund.** If the bank rejects a refund, for example because the card is closed, the amount becomes refund credit after 10 business days. The customer is told when this happens.

<div lang="ar" dir="rtl">

### الاعتراضات البنكية وفشل الاسترداد

**الاعتراض البنكي المفتوح:** إذا اعترض العميل على خصم لدى بنكه، لا يستطيع الدعم رد مبلغ ذلك الطلب حتى يُغلق الاعتراض. ويُوضح ذلك للعميل بوضوح دون مطالبته بسحب الاعتراض. وتستمر مهل الإبلاغ في السريان، لكن المطالبة المسجلة قبل الاعتراض تبقى مفتوحة.

**الاسترداد المزدوج:** إذا رُد المبلغ وأعاده البنك أيضًا، تتحول القيمة الزائدة إلى مديونية على الحساب.

**فشل الاسترداد:** إذا رفض البنك الاسترداد، كأن تكون البطاقة مغلقة، يتحول المبلغ إلى رصيد استرداد بعد 10 أيام عمل، ويُبلَّغ العميل بذلك.

</div>
