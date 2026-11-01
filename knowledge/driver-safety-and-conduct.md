---
id: driver-safety-and-conduct
title: "Driver safety and conduct"
title_ar: "سلامة مندوبي التوصيل وسلوكهم"
audience: all
verticals: [food, grocery, pharmacy, parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: DRV-01
    title: "Driver standards and work limits"
    title_ar: "معايير المندوبين وحدود العمل"
    visibility: public
    tags: [drivers, safety]
    rule_keys: [drivers.min_age, drivers.max_online_hours_per_day, drivers.min_rest_hours, drivers.continuous_hours_before_break, drivers.break_minutes, drivers.heat_alert, drivers.rating, drivers.cash_holding_max_qar, drivers.cash_deposit_hours, drivers.appeal_days]
  - id: DRV-02
    title: "Reporting a driver"
    title_ar: "الإبلاغ عن مندوب"
    visibility: public
    tags: [drivers, safety, escalation, edge-case]
    rule_keys: [drivers.report_window_days, drivers.hold_within_minutes, drivers.decision_business_days]
  - id: DRV-03
    title: "Road accidents and order handling"
    title_ar: "الحوادث المرورية ومعالجة الطلب"
    visibility: public
    tags: [drivers, safety, edge-case]
    rule_keys: [drivers.accident_report_minutes, cancellations.merchant_cancel_credit_qar, cancellations.merchant_cancel_credit_min_minutes_after_placed]
  - id: DRV-04
    title: "Customer conduct toward drivers"
    title_ar: "سلوك العملاء تجاه المندوبين"
    visibility: public
    tags: [drivers, conduct, edge-case]
    rule_keys: [drivers.customer_conduct]
---

# Driver safety and conduct

<div lang="ar" dir="rtl">

# سلامة مندوبي التوصيل وسلوكهم

</div>

## DRV-01: Driver standards and work limits

These are Jalboot company standards.

**Conduct.** Drivers must be at least 21 and hold a valid licence for their vehicle. Riders wear a helmet and reflective gear. Drivers do not hold a phone while moving, open sealed bags, enter a customer's home, ask for cash tips, or contact a customer outside the app.

**Work limits.** A driver can be online for up to 12 hours a day, with at least 10 hours of rest between shifts. After 5 hours of continuous work, a driver takes a 30-minute break.

**Heat alert.** When the forecast feels-like temperature reaches 42 C, Jalboot raises a heat alert. Riders take a 10-minute shaded break every 60 minutes, and can decline orders without penalty. A heat alert does not change late credit rules.

**Ratings.** After 50 orders, a rating below 4.2 leads to coaching, and a rating below 3.8 leads to suspension pending review.

**Cash.** A driver can hold up to QAR 1,000 in collected cash, and must deposit it within 24 hours.

A driver can appeal a suspension within 7 days.

<div lang="ar" dir="rtl">

### معايير المندوبين وحدود العمل

هذه معايير خاصة بشركة جالبوت.

**السلوك:** يجب ألا يقل عمر المندوب عن 21 عامًا وأن يحمل رخصة سارية لمركبته. ويرتدي سائقو الدراجات خوذة وملابس عاكسة. ولا يمسك المندوب هاتفه أثناء القيادة، ولا يفتح الأكياس المختومة، ولا يدخل منزل العميل، ولا يطلب إكرامية نقدية، ولا يتواصل مع العميل خارج التطبيق.

**حدود العمل:** يمكن للمندوب أن يبقى متصلًا حتى 12 ساعة في اليوم، مع راحة لا تقل عن 10 ساعات بين المناوبات. وبعد 5 ساعات من العمل المتواصل يأخذ استراحة مدتها 30 دقيقة.

**تنبيه الحرارة:** إذا بلغت درجة الحرارة المحسوسة المتوقعة 42 درجة مئوية، تصدر جالبوت تنبيه حرارة. فيأخذ سائقو الدراجات استراحة في الظل مدتها 10 دقائق كل 60 دقيقة، ويحق لهم رفض الطلبات دون عقوبة. ولا يغيّر تنبيه الحرارة قواعد رصيد التأخير.

**التقييم:** بعد 50 طلبًا، يؤدي التقييم الأقل من 4.2 إلى التوجيه والتدريب، والتقييم الأقل من 3.8 إلى الإيقاف لحين المراجعة.

**النقد:** يمكن للمندوب الاحتفاظ بما يصل إلى 1,000 ر.ق من النقد المحصل، وعليه إيداعه خلال 24 ساعة.

ويحق للمندوب التظلم من الإيقاف خلال 7 أيام.

</div>

## DRV-02: Reporting a driver

A customer can report a driver in the app within 7 days of delivery.

**Serious reports:** harassment, threats, discrimination, unsafe driving or theft. These go to P1 (ESC-01). The driver is held from new orders within 60 minutes while the case is reviewed. A decision comes within 3 business days.

- If the customer is in danger now, tell them to contact local emergency services first.
- Do not share the driver's personal details or the outcome of any action taken against them.
- A report does not create a refund by itself. Refund rules apply separately.

<div lang="ar" dir="rtl">

### الإبلاغ عن مندوب

يمكن للعميل الإبلاغ عن المندوب عبر التطبيق خلال 7 أيام من التسليم.

**البلاغات الخطيرة:** التحرش أو التهديد أو التمييز أو القيادة غير الآمنة أو السرقة. وتُعالج بأولوية P1 (ESC-01)، ويُوقف المندوب عن تلقي طلبات جديدة خلال 60 دقيقة أثناء مراجعة الحالة، ويصدر القرار خلال 3 أيام عمل.

- إذا كان العميل في خطر الآن، يُطلب منه التواصل مع خدمات الطوارئ المحلية أولًا.
- لا تُشارك البيانات الشخصية للمندوب ولا نتيجة أي إجراء يُتخذ بحقه.
- لا يترتب على البلاغ وحده أي استرداد، وتسري قواعد الاسترداد بصورة مستقلة.

</div>

## DRV-03: Road accidents and order handling

After an accident, the driver stops safely, gets help if needed, and reports it in the app within 30 minutes. Safety comes before the order.

Jalboot reassigns or cancels the order. If cancelled, it counts as a cancellation by Jalboot (CAN-04): a full refund including tip, plus QAR 10 cancellation credit if it happened 30 minutes or more after `placed_at`.

Support does not share a driver's health or personal details. If a customer was involved in the accident, hand off as P1 and do not discuss fault.

<div lang="ar" dir="rtl">

### الحوادث المرورية ومعالجة الطلب

بعد وقوع الحادث، يتوقف المندوب في مكان آمن، ويطلب المساعدة عند الحاجة، ويبلغ عبر التطبيق خلال 30 دقيقة. فالسلامة تسبق الطلب.

وتعيد جالبوت إسناد الطلب أو تلغيه. وإذا أُلغي عُد إلغاءً من جانب جالبوت (CAN-04)، فيُرد كامل المبلغ مع الإكرامية، مع رصيد إلغاء بقيمة 10 ر.ق إذا وقع ذلك بعد 30 دقيقة أو أكثر من `placed_at`.

ولا يشارك الدعم أي معلومات صحية أو شخصية عن المندوب. وإذا كان العميل طرفًا في الحادث، تُحال الحالة بأولوية P1 دون مناقشة المسؤولية عنه.

</div>

## DRV-04: Customer conduct toward drivers

Drivers do not have to accept threats, abuse, harassment or discriminatory language. A driver who feels unsafe can leave. The order then closes as `failed_customer` and LAT-05 applies.

After 2 verified reports in the rolling 12 months, the customer's account is suspended for 30 days. Threats or physical harm can lead to permanent closure after review. Appeals follow ACC-04.

<div lang="ar" dir="rtl">

### سلوك العملاء تجاه المندوبين

لا يُلزم المندوب بتحمل التهديد أو الإساءة أو التحرش أو الألفاظ التمييزية. ويحق للمندوب الذي يشعر بعدم الأمان مغادرة المكان، ويُغلق الطلب عندئذ بحالة `failed_customer` وينطبق LAT-05.

وبعد ثبوت بلاغين (2) خلال 12 شهرًا متحركة، يُوقف حساب العميل مدة 30 يومًا. وقد يؤدي التهديد أو الإيذاء الجسدي إلى إغلاق الحساب نهائيًا بعد المراجعة. ويكون التظلم وفق ACC-04.

</div>
