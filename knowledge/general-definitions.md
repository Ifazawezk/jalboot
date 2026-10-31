---
id: general-definitions
title: "General definitions and rule order"
title_ar: "التعريفات العامة وترتيب القواعد"
audience: all
verticals: [food, grocery, pharmacy, parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: GEN-01
    title: "Scope and order statuses"
    title_ar: "نطاق السياسات وحالات الطلب"
    visibility: public
    tags: [definitions]
    rule_keys: []
  - id: GEN-02
    title: "Time limits and business days"
    title_ar: "المهل الزمنية وأيام العمل"
    visibility: public
    tags: [definitions, edge-case]
    rule_keys: []
  - id: GEN-03
    title: "Money terms and rounding"
    title_ar: "المصطلحات المالية والتقريب"
    visibility: public
    tags: [definitions, edge-case]
    rule_keys: []
  - id: GEN-04
    title: "Which rule wins"
    title_ar: "أي القواعد تُطبق أولًا"
    visibility: public
    tags: [precedence, edge-case]
    rule_keys: []
---

# General definitions and rule order

<div lang="ar" dir="rtl">

# التعريفات العامة وترتيب القواعد

</div>

## GEN-01: Scope and order statuses

Jalboot is a fictional delivery app for food, grocery, pharmacy and parcel orders in Doha and nearby towns. Every rule, price and time limit in this knowledge base is invented company policy. Nothing here is legal advice or a statement of what any law requires.

Each order has one merchant and one delivery address. Status moves in this order:

| Order type | Status path |
|---|---|
| Food | `placed`, `accepted`, `preparing`, `ready`, `picked_up`, `on_the_way`, `delivered` |
| Grocery | `placed`, `accepted`, `picking`, `picked_up`, `on_the_way`, `delivered` |
| Pharmacy | `placed`, `accepted`, `packed`, `picked_up`, `on_the_way`, `delivered` |
| Parcel | `placed`, `driver_assigned`, `picked_up`, `on_the_way`, `delivered` |

An order can also end as `cancelled` or `failed_customer`. The second means delivery failed for a reason on the customer's side (see LAT-05).

<div lang="ar" dir="rtl">

### نطاق السياسات وحالات الطلب

جالبوت تطبيق توصيل خيالي يخدم طلبات الطعام والبقالة والصيدلية والطرود في الدوحة والمدن القريبة منها. وجميع القواعد والأسعار والمهل الواردة في قاعدة المعرفة هذه سياسات شركة افتراضية، وليس فيها ما يُعد استشارة قانونية أو بيانًا لما يفرضه أي قانون.

لكل طلب تاجر واحد وعنوان توصيل واحد، وتتدرج حالته على النحو الآتي:

| نوع الطلب | تسلسل الحالات |
|---|---|
| طعام | `placed`، `accepted`، `preparing`، `ready`، `picked_up`، `on_the_way`، `delivered` |
| بقالة | `placed`، `accepted`، `picking`، `picked_up`، `on_the_way`، `delivered` |
| صيدلية | `placed`، `accepted`، `packed`، `picked_up`، `on_the_way`، `delivered` |
| طرد | `placed`، `driver_assigned`، `picked_up`، `on_the_way`، `delivered` |

وقد ينتهي الطلب أيضًا بحالة `cancelled` (ملغى) أو `failed_customer`، وتعني الأخيرة تعذر التسليم لسبب يعود إلى العميل (انظر LAT-05).

</div>

## GEN-02: Time limits and business days

- All times are Doha time (UTC+3).
- A time limit includes its last moment. If a window ends at 13:05:00, a request at 13:05:00 is in time and a request at 13:05:01 is late.
- Limits in minutes, hours or days run without pause through nights, weekends and holidays.
- Limits in business days count Sunday to Thursday. The day of the event itself is not counted.
- "Rolling" periods count back from the current moment, not from the start of a calendar month.
- Times come from Jalboot order and payment records. A screenshot or a device clock does not change them.
- A request counts from the moment the customer first reports the issue in the app or in chat. If a chat drops and the customer returns later, the first report time stands.

<div lang="ar" dir="rtl">

### المهل الزمنية وأيام العمل

- تُحسب جميع الأوقات بتوقيت الدوحة (UTC+3).
- تشمل المهلة لحظتها الأخيرة؛ فإذا انتهت عند الساعة 13:05:00 قُبل البلاغ المقدم عند 13:05:00، وعُد البلاغ المقدم عند 13:05:01 متأخرًا.
- تسري المهل المحسوبة بالدقائق أو الساعات أو الأيام دون توقف، بما في ذلك الليل وعطلات نهاية الأسبوع والإجازات.
- تُحسب أيام العمل من الأحد إلى الخميس، ولا يدخل في الحساب يوم وقوع الحدث نفسه.
- تُحسب الفترات المتحركة بالرجوع من اللحظة الحالية، لا من بداية الشهر الميلادي.
- يُعتمد في الأوقات على سجلات الطلبات والمدفوعات لدى جالبوت، ولا تغيّرها لقطة شاشة أو ساعة الجهاز.
- يُحتسب البلاغ من لحظة إبلاغ العميل بالمشكلة لأول مرة عبر التطبيق أو المحادثة. وإذا انقطعت المحادثة وعاد العميل لاحقًا، يبقى وقت البلاغ الأول هو المعتمد.

</div>

## GEN-03: Money terms and rounding

- **Item subtotal:** the sum of item prices in the cart, after any price cut shown on the item, before promo codes, fees and tip.
- **Promo discount:** money taken off by a promo code. A free delivery code changes the delivery fee and creates no promo discount.
- **Fees:** delivery fee, small order fee, service fee, peak fee and weather fee.
- **Amount paid:** item subtotal minus promo discount, plus fees and tip. It includes value paid with Jalboot Credit and points.
- **Net item price:** the listed price minus the item's share of the promo discount: `net = price x (1 - promo_discount / eligible_subtotal)`. The eligible subtotal is the total of the items the code applies to. An item the code does not apply to keeps its full price.
- **Compensation credit:** late credit, goodwill credit, expired item credit and cancellation credit.
- **Full-order refund:** the amount paid, minus the tip if the order was delivered, minus refunds already paid on the order, minus compensation credit already issued on the order.

All amounts are in QAR with two decimals. Round half up once per item line, after multiplying by quantity, then add the lines.

Tests made at checkout (fees, free delivery thresholds, minimum order and minimum spend) keep the checkout value. Refund and late credit calculations use the final item subtotal, after picking, weighing and substitutions.

<div lang="ar" dir="rtl">

### المصطلحات المالية والتقريب

- **إجمالي الأصناف:** مجموع أسعار الأصناف في السلة بعد أي تخفيض ظاهر على الصنف، وقبل رموز الخصم والرسوم والإكرامية.
- **خصم الرمز:** المبلغ الذي يخفضه رمز الخصم. أما رمز التوصيل المجاني فيغيّر رسوم التوصيل فقط ولا يُنشئ خصمًا.
- **الرسوم:** رسوم التوصيل، ورسوم الطلب الصغير، ورسوم الخدمة، ورسوم الذروة، ورسوم الطقس.
- **المبلغ المدفوع:** إجمالي الأصناف مطروحًا منه خصم الرمز، مضافًا إليه الرسوم والإكرامية، ويشمل ما سُدد برصيد جالبوت والنقاط.
- **صافي سعر الصنف:** السعر المعروض بعد طرح حصة الصنف من خصم الرمز: `net = price x (1 - promo_discount / eligible_subtotal)`. والإجمالي المؤهل هو مجموع الأصناف التي يشملها الرمز، أما الصنف الذي لا يشمله الرمز فيبقى بسعره الكامل.
- **الرصيد التعويضي:** رصيد التأخير، ورصيد الترضية، ورصيد الصنف منتهي الصلاحية، ورصيد الإلغاء.
- **الاسترداد الكامل للطلب:** المبلغ المدفوع، مطروحًا منه الإكرامية إذا سُلّم الطلب، وما سبق رده على الطلب نفسه، وما صدر عنه من رصيد تعويضي.

تُحسب جميع المبالغ بالريال القطري (ر.ق) إلى منزلتين عشريتين، ويُقرّب كل سطر من أسطر الأصناف مرة واحدة بعد ضربه في الكمية، بتقريب النصف إلى الأعلى، ثم تُجمع الأسطر.

وتبقى الاختبارات التي تجري عند إتمام الطلب (الرسوم وحدود التوصيل المجاني والحد الأدنى للطلب والحد الأدنى للإنفاق) على قيمتها في ذلك الوقت. أما حساب الاسترداد ورصيد التأخير فيعتمد على إجمالي الأصناف النهائي بعد التجهيز والوزن والاستبدال.

</div>

## GEN-04: Which rule wins

Apply these steps in order:

1. **Safety first.** A health, allergy, harassment, threat or road accident concern goes to escalation (ESC-02) before any talk of money.
2. **Blocks next.** An open bank dispute (PAY-05) or a Trust review (REF-05) stops refunds it covers.
3. **Specific beats general.** A rule in the pharmacy, parcel, allergen or grocery documents overrides the general rule in the refunds document.
4. **Full refund replaces partial remedies.** A full-order refund replaces partial refunds and late credit for that order. Amounts already paid or issued are subtracted (GEN-03). The one exception is cancellation credit (CAN-04), which is added on top.
5. **Lowest cap wins.** When two caps apply to the same amount, use the lower one.
6. **Unresolved conflict goes to a person.** If two rules still conflict, automated support does not choose. It hands off to a support agent.

<div lang="ar" dir="rtl">

### أي القواعد تُطبق أولًا

تُطبق الخطوات الآتية بالترتيب:

1. **السلامة أولًا.** أي مسألة تتعلق بالصحة أو الحساسية أو التحرش أو التهديد أو حادث مروري تُصعَّد وفق ESC-02 قبل أي حديث عن المال.
2. **ثم موانع الاسترداد.** يوقف الاعتراض البنكي المفتوح (PAY-05) أو مراجعة فريق الثقة (REF-05) عمليات الاسترداد المشمولة به.
3. **الخاص يقيد العام.** تتقدم القواعد الواردة في وثائق الصيدلية والطرود والحساسية والبقالة على القاعدة العامة في وثيقة الاسترداد.
4. **الاسترداد الكامل يحل محل الحلول الجزئية.** يغني الاسترداد الكامل عن الاسترداد الجزئي ورصيد التأخير في الطلب نفسه، ويُطرح ما سبق دفعه أو إصداره (GEN-03). ويُستثنى من ذلك رصيد الإلغاء (CAN-04) الذي يضاف فوق الاسترداد.
5. **السقف الأقل هو المعتمد.** إذا انطبق سقفان على المبلغ نفسه، يؤخذ بالأقل منهما.
6. **التعارض غير المحسوم يُحال إلى موظف.** إذا بقي تعارض بين قاعدتين، لا يختار الدعم الآلي بينهما بل يحيل الحالة إلى موظف الدعم.

</div>
