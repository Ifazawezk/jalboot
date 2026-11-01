---
id: late-or-missing-orders
title: "Late or missing orders"
title_ar: "الطلبات المتأخرة أو المفقودة"
audience: customer
verticals: [food, grocery, pharmacy]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: LAT-01
    title: "Measuring lateness and late credit"
    title_ar: "حساب التأخير ورصيد التأخير"
    visibility: public
    tags: [late, calculation, edge-case]
    rule_keys: [late_delivery.tiers, late_delivery.credit_cap_pct_of_item_subtotal, compensation_credit_cap_per_order_qar, refunds.windows_hours.late_credit]
  - id: LAT-02
    title: "When late credit does not apply"
    title_ar: "متى لا ينطبق رصيد التأخير"
    visibility: public
    tags: [late, exceptions, edge-case]
    rule_keys: [late_delivery.iftar_tier_shift_minutes, late_delivery.iftar_window_before_sunset_minutes, late_delivery.iftar_window_after_sunset_minutes]
  - id: LAT-03
    title: "Order still has not arrived"
    title_ar: "الطلب لم يصل بعد"
    visibility: public
    tags: [late, cancellation, edge-case]
    rule_keys: [late_delivery.free_cancel_after_minutes_late, late_delivery.auto_cancel_after_minutes_late, cancellations.merchant_cancel_credit_qar]
  - id: LAT-04
    title: "Marked delivered but not received"
    title_ar: "طلب مسجل كمسلَّم ولم يصل"
    visibility: public
    tags: [missing, edge-case]
    rule_keys: [refunds.windows_hours.not_received, not_received]
  - id: LAT-05
    title: "Customer cannot be reached"
    title_ar: "تعذر الوصول إلى العميل"
    visibility: public
    tags: [failed-delivery, edge-case]
    rule_keys: [failed_delivery, cancellations.grocery.picking_charge_pct, cancellations.grocery.picking_charge_min_qar, cancellations.grocery.picking_charge_max_qar, cancellations.pharmacy.packed_charge_qar, payments.cod.outstanding_balance_cap_qar]
---

# Late or missing orders

<div lang="ar" dir="rtl">

# الطلبات المتأخرة أو المفقودة

</div>

## LAT-01: Measuring lateness and late credit

`promised_at` is the latest time shown at checkout. For a scheduled order it is the end of the slot. An updated time shown later in the app does not move `promised_at`. Only a customer address change resets it (ACC-03).

Minutes late is `delivered_at` minus `promised_at`, rounded down to whole minutes.

| Minutes late | Late credit | Delivery fee |
|---|---|---|
| 0 to 19 | None | Kept |
| 20 to 39 | QAR 5 | Kept |
| 40 to 59 | QAR 10 | Kept |
| 60 or more | QAR 20 | Refunded |

- Late credit cannot exceed 30% of the item subtotal. It also counts toward the QAR 30 per order cap in REF-07. A refunded delivery fee is a refund, not credit, so it does not count toward that cap.
- If delivery was free, there is no delivery fee to refund. Peak and weather fees are not refunded here.
- The customer must ask within 24 hours of `delivered_at`.
- Late credit is goodwill-type credit. It applies to delivered food, grocery and pharmacy orders. Parcels have their own rules (PCL-04).

<div lang="ar" dir="rtl">

### حساب التأخير ورصيد التأخير

`promised_at` هو أقصى وقت يظهر عند إتمام الطلب، وفي الطلب المجدول هو نهاية الفترة الزمنية المختارة. ولا يتغير هذا الموعد إذا عرض التطبيق لاحقًا وقتًا محدثًا، ولا يعيد ضبطه إلا تغيير العميل للعنوان (ACC-03).

دقائق التأخير هي الفرق بين `delivered_at` و`promised_at`، مقربًا إلى الأسفل لأقرب دقيقة كاملة.

| دقائق التأخير | رصيد التأخير | رسوم التوصيل |
|---|---|---|
| من 0 إلى 19 | لا يوجد | لا تُرد |
| من 20 إلى 39 | 5 ر.ق | لا تُرد |
| من 40 إلى 59 | 10 ر.ق | لا تُرد |
| 60 فأكثر | 20 ر.ق | تُرد |

- لا يتجاوز رصيد التأخير 30% من إجمالي الأصناف، ويدخل كذلك في سقف 30 ر.ق للطلب الواحد الوارد في REF-07. أما رسوم التوصيل المردودة فتُعد استردادًا لا رصيدًا، فلا تدخل في هذا السقف.
- إذا كان التوصيل مجانيًا فلا توجد رسوم توصيل تُرد. ولا تُرد هنا رسوم الذروة أو الطقس.
- على العميل أن يطلب الرصيد خلال 24 ساعة من `delivered_at`.
- رصيد التأخير من نوع رصيد الترضية، وينطبق على طلبات الطعام والبقالة والصيدلية التي سُلّمت. أما الطرود فلها قواعدها الخاصة (PCL-04).

</div>

## LAT-02: When late credit does not apply

No late credit and no delivery fee refund when:

- The severe weather flag was active at any point between `placed_at` and `delivered_at`.
- The driver logged a failed contact attempt under LAT-05.
- The order received a full-order refund.

A slow merchant is not an exception. The customer gets the same credit whether the delay came from the merchant or the driver.

**Iftar window in Ramadan.** If `promised_at` falls between 90 minutes before and 30 minutes after the sunset time shown in the app, every tier starts 10 minutes later. The tiers become 30, 50 and 70 minutes. The amounts do not change.

<div lang="ar" dir="rtl">

### متى لا ينطبق رصيد التأخير

لا يُمنح رصيد تأخير ولا تُرد رسوم التوصيل في الحالات الآتية:

- إذا كان مؤشر الطقس السيئ مفعلًا في أي وقت بين `placed_at` و`delivered_at`.
- إذا سجل المندوب محاولة اتصال فاشلة وفق LAT-05.
- إذا حصل الطلب على استرداد كامل.

وبطء التاجر ليس استثناءً؛ فالعميل يحصل على الرصيد نفسه سواء كان سبب التأخير التاجر أو المندوب.

**فترة الإفطار في رمضان:** إذا وقع `promised_at` بين 90 دقيقة قبل وقت الغروب الظاهر في التطبيق و30 دقيقة بعده، تبدأ كل شريحة بعد 10 دقائق من موعدها المعتاد، فتصبح الشرائح 30 و50 و70 دقيقة، دون تغيير في المبالغ.

</div>

## LAT-03: Order still has not arrived

Check live status first, then follow the time since `promised_at`:

| Time past `promised_at`, order not delivered | Outcome |
|---|---|
| Less than 45 minutes | Share the live status. Normal cancellation charges apply (CAN-01, CAN-02). |
| 45 minutes or more | The customer can cancel free. Full refund including tip, even if the order is `on_the_way`. No late credit. |
| 120 minutes or more | Jalboot cancels the order. Full refund including tip, plus QAR 10 cancellation credit. |

Both time limits also apply during severe weather. The weather exception in LAT-02 removes late credit only.

<div lang="ar" dir="rtl">

### الطلب لم يصل بعد

تُراجع الحالة المباشرة للطلب أولًا، ثم يُتبع الجدول بحسب الوقت المنقضي بعد `promised_at`:

| الوقت بعد `promised_at` والطلب لم يُسلَّم | النتيجة |
|---|---|
| أقل من 45 دقيقة | تُعرض الحالة المباشرة للطلب، وتنطبق رسوم الإلغاء المعتادة (CAN-01 و CAN-02). |
| 45 دقيقة فأكثر | يمكن للعميل الإلغاء مجانًا مع استرداد كامل يشمل الإكرامية، حتى لو كان الطلب في حالة `on_the_way`، ودون رصيد تأخير. |
| 120 دقيقة فأكثر | تلغي جالبوت الطلب مع استرداد كامل يشمل الإكرامية، إضافة إلى رصيد إلغاء بقيمة 10 ر.ق. |

وتسري هاتان المهلتان أيضًا في الطقس السيئ، فاستثناء الطقس في LAT-02 يلغي رصيد التأخير فقط.

</div>

## LAT-04: Marked delivered but not received

The customer must report within 24 hours of `delivered_at`. Check two things: proof of delivery (a photo or a handover code), and the distance between the driver's GPS and the delivery pin at `delivered_at`.

| Result | Action |
|---|---|
| No proof, or GPS more than 150 m from the pin | Treat as not delivered. Full refund including tip. Approval limits in REF-05 apply. |
| Proof exists and GPS within 150 m | A support agent reviews it. Automated support makes no refund. |

- Exactly 150 m counts as within range.
- For a "leave at door" order, a proof photo showing the right door within 150 m means the order counts as delivered, and no refund applies.
- Refunds under this section are limited in the rolling 90 days. Beyond that limit, a person reviews the case, even if there is no proof of delivery.

<div lang="ar" dir="rtl">

### طلب مسجل كمسلَّم ولم يصل

على العميل الإبلاغ خلال 24 ساعة من `delivered_at`. ويُتحقق من أمرين: إثبات التسليم (صورة أو رمز تسليم)، والمسافة بين موقع المندوب وفق نظام تحديد المواقع والموقع المحدد على الخريطة وقت `delivered_at`.

| النتيجة | الإجراء |
|---|---|
| لا يوجد إثبات، أو تزيد المسافة على 150 مترًا | يُعامل الطلب على أنه لم يُسلَّم، ويُرد كامل المبلغ مع الإكرامية، مع مراعاة حدود الموافقة في REF-05. |
| يوجد إثبات والمسافة في حدود 150 مترًا | يراجع موظف الدعم الحالة، ولا يجري الدعم الآلي أي استرداد. |

- المسافة البالغة 150 مترًا تمامًا تُعد ضمن النطاق.
- في طلب "اترك الطلب عند الباب"، إذا أظهرت صورة الإثبات الباب الصحيح وكانت المسافة في حدود 150 مترًا، يُعد الطلب مسلَّمًا ولا يُرد المبلغ.
- عمليات الاسترداد بموجب هذا القسم محدودة خلال 90 يومًا متحركة، وبعد تجاوز الحد يراجع موظف الحالة حتى لو لم يوجد إثبات تسليم.

</div>

## LAT-05: Customer cannot be reached

The driver waits 7 minutes at the delivery point and makes 2 calls through the app. If that fails, the order closes as `failed_customer`. No late credit applies.

| Order type | Outcome |
|---|---|
| Food | No refund. Tip is returned. |
| Grocery | Refund net items minus the picking charge in CAN-02 (15% of net items, minimum QAR 10, maximum QAR 50). Delivery and service fees are kept. Tip is returned. |
| Pharmacy | Refund net items minus QAR 10. Delivery and service fees are kept. Tip is returned. Cold-chain items are not refunded. |
| Parcel | See PCL-05. |

On a cash order, no money has been collected, so the amount owed becomes an outstanding balance capped at QAR 30 (CAN-05).

If records show the driver waited less than 7 minutes or made fewer than 2 calls, this section does not apply. Treat the order as not delivered and give a full refund including tip. The exception is a driver who left for safety reasons under DRV-04. That order stays `failed_customer`, and the outcomes in the table apply.

<div lang="ar" dir="rtl">

### تعذر الوصول إلى العميل

ينتظر المندوب 7 دقائق عند نقطة التسليم ويجري مكالمتين (2) عبر التطبيق. فإذا لم ينجح ذلك، يُغلق الطلب بحالة `failed_customer` ولا يُمنح رصيد تأخير.

| نوع الطلب | النتيجة |
|---|---|
| طعام | لا يُرد المبلغ، وتُعاد الإكرامية. |
| بقالة | يُرد صافي الأصناف بعد طرح رسوم التجهيز الواردة في CAN-02 (15% من صافي الأصناف، بحد أدنى 10 ر.ق وحد أقصى 50 ر.ق)، ولا تُرد رسوم التوصيل والخدمة، وتُعاد الإكرامية. |
| صيدلية | يُرد صافي الأصناف بعد طرح 10 ر.ق، ولا تُرد رسوم التوصيل والخدمة، وتُعاد الإكرامية، ولا تُرد قيمة الأصناف التي تتطلب حفظًا مبردًا. |
| طرد | انظر PCL-05. |

وفي الطلب النقدي لم يُحصَّل أي مبلغ، فيتحول المبلغ المستحق إلى مديونية على الحساب بحد أقصى 30 ر.ق (CAN-05).

وإذا أظهرت السجلات أن المندوب انتظر أقل من 7 دقائق أو أجرى أقل من مكالمتين، فلا ينطبق هذا القسم، ويُعامل الطلب على أنه لم يُسلَّم مع استرداد كامل يشمل الإكرامية. ويُستثنى من ذلك المندوب الذي غادر لأسباب تتعلق بسلامته وفق DRV-04، إذ يبقى الطلب بحالة `failed_customer` وتنطبق نتائج الجدول.

</div>
