---
id: cancellations
title: "Cancellations"
title_ar: "إلغاء الطلبات"
audience: customer
verticals: [food, grocery, pharmacy, parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: CAN-01
    title: "Cancelling a food order"
    title_ar: "إلغاء طلب الطعام"
    visibility: public
    tags: [cancellation, calculation]
    rule_keys: [cancellations.food]
  - id: CAN-02
    title: "Cancelling grocery, pharmacy and parcel orders"
    title_ar: "إلغاء طلبات البقالة والصيدلية والطرود"
    visibility: public
    tags: [cancellation, calculation, edge-case]
    rule_keys: [cancellations.grocery, cancellations.pharmacy, cancellations.parcel]
  - id: CAN-03
    title: "Grace period and scheduled orders"
    title_ar: "فترة السماح والطلبات المجدولة"
    visibility: public
    tags: [cancellation, edge-case]
    rule_keys: [cancellations.grace_minutes, cancellations.scheduled_free_until_minutes_before_slot]
  - id: CAN-04
    title: "Free exits and cancellations by the merchant or the company"
    title_ar: "الإلغاء المجاني والإلغاء من جانب التاجر أو الشركة"
    visibility: public
    tags: [cancellation, edge-case]
    rule_keys: [late_delivery.free_cancel_after_minutes_late, late_delivery.eta_slip_free_cancel_minutes, cancellations.merchant_cancel_credit_qar, cancellations.merchant_cancel_credit_min_minutes_after_placed]
  - id: CAN-05
    title: "Cash orders and repeat cancellations"
    title_ar: "الطلبات النقدية وتكرار الإلغاء"
    visibility: public
    tags: [cancellation, cash, edge-case]
    rule_keys: [payments.cod.outstanding_balance_cap_qar, cancellations.repeat]
---

# Cancellations

<div lang="ar" dir="rtl">

# إلغاء الطلبات

</div>

## CAN-01: Cancelling a food order

"Net items" below means item subtotal minus promo discount.

| Status at cancellation | Charge | Refund |
|---|---|---|
| `placed` | None | Amount paid |
| `accepted`, `preparing` | 50% of net items | Amount paid minus the charge |
| `ready`, `picked_up`, `on_the_way` | 100% of net items, plus all fees | Tip only |

The status when the customer asks to cancel decides the charge, not the status when support replies.

Example: item subtotal QAR 100, code QAR 20, delivery fee QAR 8, service fee QAR 3, tip QAR 5, amount paid QAR 96. In `preparing`, the charge is QAR 40 and the refund is QAR 56. In `ready`, the refund is QAR 5.

<div lang="ar" dir="rtl">

### إلغاء طلب الطعام

يُقصد بصافي الأصناف أدناه إجمالي الأصناف مطروحًا منه خصم الرمز.

| الحالة عند الإلغاء | الرسوم | المبلغ المردود |
|---|---|---|
| `placed` | لا يوجد | المبلغ المدفوع |
| `accepted` أو `preparing` | 50% من صافي الأصناف | المبلغ المدفوع بعد طرح الرسوم |
| `ready` أو `picked_up` أو `on_the_way` | 100% من صافي الأصناف مع جميع الرسوم | الإكرامية فقط |

والعبرة بحالة الطلب وقت طلب العميل الإلغاء، لا وقت رد الدعم عليه.

مثال: إجمالي الأصناف 100 ر.ق، وخصم الرمز 20 ر.ق، ورسوم التوصيل 8 ر.ق، ورسوم الخدمة 3 ر.ق، والإكرامية 5 ر.ق، والمبلغ المدفوع 96 ر.ق. في حالة `preparing` تكون رسوم الإلغاء 40 ر.ق والمبلغ المردود 56 ر.ق، وفي حالة `ready` يكون المبلغ المردود 5 ر.ق.

</div>

## CAN-02: Cancelling grocery, pharmacy and parcel orders

| Order type | Status | Charge |
|---|---|---|
| Grocery | `placed`, `accepted` | None |
| Grocery | `picking` | 15% of net items, minimum QAR 10, maximum QAR 50 |
| Grocery | `picked_up`, `on_the_way` | 100% of net items, plus all fees |
| Pharmacy | `placed`, `accepted` | None |
| Pharmacy | `packed` | QAR 10 |
| Pharmacy | `picked_up`, `on_the_way` | 100% of net items, plus all fees |
| Parcel | `placed` | None |
| Parcel | `driver_assigned` | QAR 5 |
| Parcel | `picked_up`, `on_the_way` | Cannot be cancelled. Use return to sender (PCL-05). |

On grocery and pharmacy orders, a charge can never exceed the net items. The tip is always returned when an order is cancelled before delivery. A rejected prescription is never charged (PHR-02).

<div lang="ar" dir="rtl">

### إلغاء طلبات البقالة والصيدلية والطرود

| نوع الطلب | الحالة | الرسوم |
|---|---|---|
| بقالة | `placed` أو `accepted` | لا يوجد |
| بقالة | `picking` | 15% من صافي الأصناف، بحد أدنى 10 ر.ق وحد أقصى 50 ر.ق |
| بقالة | `picked_up` أو `on_the_way` | 100% من صافي الأصناف مع جميع الرسوم |
| صيدلية | `placed` أو `accepted` | لا يوجد |
| صيدلية | `packed` | 10 ر.ق |
| صيدلية | `picked_up` أو `on_the_way` | 100% من صافي الأصناف مع جميع الرسوم |
| طرد | `placed` | لا يوجد |
| طرد | `driver_assigned` | 5 ر.ق |
| طرد | `picked_up` أو `on_the_way` | لا يمكن الإلغاء، ويُستخدم خيار الإعادة إلى المرسل (PCL-05). |

ولا يجوز في طلبات البقالة والصيدلية أن تتجاوز رسوم الإلغاء صافي الأصناف. وتُعاد الإكرامية دائمًا إذا أُلغي الطلب قبل التسليم. ولا تُفرض أي رسوم عند رفض الوصفة الطبية (PHR-02).

</div>

## CAN-03: Grace period and scheduled orders

**Grace period.** For the first 2 minutes after `placed_at`, a food, grocery or pharmacy order can be cancelled free at any status before `picked_up`. Parcels have no grace period.

**Scheduled orders.** Cancelling is free up to these limits before the slot starts:

| Order type | Free until |
|---|---|
| Food | 60 minutes before the slot |
| Pharmacy | 60 minutes before the slot |
| Grocery | 120 minutes before the slot |

After that limit, the charge is at least the `preparing`, `picking` or `packed` charge, even if work has not started. Cancelling exactly at the limit is free.

The grace period beats the scheduled limit. A customer who books a slot 30 minutes ahead can still cancel free during the first 2 minutes.

<div lang="ar" dir="rtl">

### فترة السماح والطلبات المجدولة

**فترة السماح:** خلال أول دقيقتين (2) بعد `placed_at`، يمكن إلغاء طلب الطعام أو البقالة أو الصيدلية مجانًا في أي حالة تسبق `picked_up`. ولا توجد فترة سماح للطرود.

**الطلبات المجدولة:** الإلغاء مجاني حتى الحدود الآتية قبل بداية الفترة الزمنية:

| نوع الطلب | مجاني حتى |
|---|---|
| طعام | 60 دقيقة قبل الفترة |
| صيدلية | 60 دقيقة قبل الفترة |
| بقالة | 120 دقيقة قبل الفترة |

وبعد هذا الحد تكون الرسوم على الأقل مساوية لرسوم حالة `preparing` أو `picking` أو `packed`، حتى لو لم يبدأ العمل على الطلب. أما الإلغاء عند الحد تمامًا فمجاني.

وتتقدم فترة السماح على حد الطلب المجدول؛ فالعميل الذي يحجز فترة تبدأ بعد 30 دقيقة يمكنه الإلغاء مجانًا خلال أول دقيقتين.

</div>

## CAN-04: Free exits and cancellations by the merchant or the company

The customer can cancel a food, grocery or pharmacy order with a full refund including tip, at any status before delivery, when:

- It is 45 minutes or more past `promised_at` and the order is not delivered.
- The live estimate is 30 minutes or more later than `promised_at` and the order is not yet `picked_up`.
- The customer takes the option in GRC-05 for a large grocery shortfall.

**Cancelled by the merchant or Jalboot.** The customer gets a full refund including tip. If the cancellation happened 30 minutes or more after `placed_at`, add QAR 10 cancellation credit. This is the only credit paid on top of a full refund. It is limited to one per order.

A rejected prescription is a pharmacist's decision, not a merchant cancellation, so no cancellation credit applies.

<div lang="ar" dir="rtl">

### الإلغاء المجاني والإلغاء من جانب التاجر أو الشركة

يمكن للعميل إلغاء طلب الطعام أو البقالة أو الصيدلية مع استرداد كامل يشمل الإكرامية، في أي حالة تسبق التسليم، إذا تحقق أحد الآتي:

- مرور 45 دقيقة أو أكثر بعد `promised_at` دون تسليم الطلب.
- تأخر الوقت المتوقع المباشر 30 دقيقة أو أكثر عن `promised_at` ولم يصل الطلب بعد إلى حالة `picked_up`.
- اختيار العميل الإلغاء عند النقص الكبير في طلب البقالة وفق GRC-05.

**الإلغاء من جانب التاجر أو جالبوت:** يحصل العميل على استرداد كامل يشمل الإكرامية. وإذا وقع الإلغاء بعد 30 دقيقة أو أكثر من `placed_at`، يضاف رصيد إلغاء بقيمة 10 ر.ق. وهو الرصيد الوحيد الذي يضاف فوق الاسترداد الكامل، ولا يُمنح سوى مرة واحدة لكل طلب.

ورفض الوصفة الطبية قرار يتخذه الصيدلي وليس إلغاءً من التاجر، فلا يُمنح عنه رصيد إلغاء.

</div>

## CAN-05: Cash orders and repeat cancellations

- On a cash order no money has been collected, so a cancellation charge becomes an outstanding balance on the account. The balance is capped at QAR 30, and anything above that is waived.
- An outstanding balance must be paid by card or mobile wallet before the next order.
- If a customer has 3 chargeable cancellations in the rolling 7 days, cash on delivery is switched off for 30 days. Free cancellations do not count toward the 3.

<div lang="ar" dir="rtl">

### الطلبات النقدية وتكرار الإلغاء

- لا يُحصَّل أي مبلغ في الطلب النقدي قبل التسليم، فتتحول رسوم الإلغاء إلى مديونية على الحساب بحد أقصى 30 ر.ق، ويُعفى العميل مما زاد على ذلك.
- يجب سداد المديونية بالبطاقة أو المحفظة الإلكترونية قبل الطلب التالي.
- إذا وقعت 3 عمليات إلغاء برسوم خلال 7 أيام متحركة، يُوقف الدفع نقدًا عند الاستلام مدة 30 يومًا. ولا تُحسب عمليات الإلغاء المجانية ضمن هذا العدد.

</div>
