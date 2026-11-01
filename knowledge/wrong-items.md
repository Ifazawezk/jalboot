---
id: wrong-items
title: "Wrong items"
title_ar: "الأصناف الخاطئة"
audience: customer
verticals: [food, grocery]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: WRG-01
    title: "Wrong, missing and short items"
    title_ar: "الأصناف الخاطئة والناقصة ونقص الكمية"
    visibility: public
    tags: [items]
    rule_keys: []
  - id: WRG-02
    title: "Special instructions and modifiers"
    title_ar: "الخيارات والتعليمات الخاصة"
    visibility: public
    tags: [items, edge-case]
    rule_keys: [wrong_items.modifier_miss_refund_pct]
  - id: WRG-03
    title: "Combos, bundles and free items"
    title_ar: "الوجبات المجمعة والعروض والأصناف المجانية"
    visibility: public
    tags: [items, calculation, edge-case]
    rule_keys: []
  - id: WRG-04
    title: "Redelivery instead of a refund"
    title_ar: "إعادة التوصيل بدلًا من الاسترداد"
    visibility: public
    tags: [redelivery, edge-case]
    rule_keys: [wrong_items.redelivery_window_minutes, wrong_items.redelivery_arrival_minutes, wrong_items.redelivery_max_per_order]
  - id: WRG-05
    title: "Food quality complaints"
    title_ar: "شكاوى جودة الطعام"
    visibility: public
    tags: [quality, edge-case]
    rule_keys: [wrong_items.quality_refund_pct, refunds.windows_hours.food_temperature, refunds.windows_hours.food_quality]
---

# Wrong items

<div lang="ar" dir="rtl">

# الأصناف الخاطئة

</div>

## WRG-01: Wrong, missing and short items

- **Missing item:** paid for but not in the bag. Refund the net item price.
- **Short quantity:** fewer units than ordered. Refund only the units not received.
- **Wrong item:** a different item arrived. Refund the net price of the item ordered. If the item received costs more, the customer owes nothing extra.
- **Missing add-on:** refund the add-on price only, not the main item.
- **Whole wrong order:** the bag belongs to another customer. Give a full-order refund. The tip stays with the driver because a delivery took place (REF-03).

The customer does not need to return food. Anyone with an allergy should not eat an item they did not order. Windows are in REF-02, evidence rules in REF-06, and the 70% rule in REF-03.

<div lang="ar" dir="rtl">

### الأصناف الخاطئة والناقصة ونقص الكمية

- **صنف ناقص:** دُفع ثمنه ولم يوجد في الكيس، فيُرد صافي سعره.
- **نقص الكمية:** وصل عدد أقل من المطلوب، فتُرد قيمة الوحدات غير المستلمة فقط.
- **صنف خاطئ:** وصل صنف مختلف، فيُرد صافي سعر الصنف المطلوب. وإذا كان الصنف المستلم أغلى، فلا يدفع العميل أي فرق.
- **إضافة ناقصة:** يُرد سعر الإضافة فقط لا الصنف الرئيسي.
- **طلب خاطئ بالكامل:** الكيس يخص عميلًا آخر، فيُرد الطلب كاملًا، وتبقى الإكرامية للمندوب لأن التوصيل قد تم (REF-03).

ولا يُطلب من العميل إعادة الطعام. وينبغي لمن لديه حساسية ألا يتناول صنفًا لم يطلبه. وترد المهل في REF-02، وقواعد الإثبات في REF-06، وقاعدة 70% في REF-03.

</div>

## WRG-02: Special instructions and modifiers

- **Modifier selected in the app and missed** (for example "no onions"): refund 50% of the net item price.
- **Free-text note missed:** notes are followed where possible. No refund applies.
- **Exception:** if the modifier or the note states an allergy, the case moves to SAF-03 and the 50% rule does not apply. A note that only says "no onions, please" is a preference. A note that says "onion allergy" is an allergy.

<div lang="ar" dir="rtl">

### الخيارات والتعليمات الخاصة

- **خيار محدد في التطبيق ولم يُنفذ** (مثل "بدون بصل"): يُرد 50% من صافي سعر الصنف.
- **ملاحظة نصية لم تُنفذ:** تُراعى الملاحظات قدر الإمكان، ولا يُرد مقابلها أي مبلغ.
- **الاستثناء:** إذا ذكر الخيار أو الملاحظة وجود حساسية، تنتقل الحالة إلى SAF-03 ولا تنطبق قاعدة 50%. فعبارة "بدون بصل من فضلك" تفضيل شخصي، أما عبارة "لدي حساسية من البصل" فهي حساسية.

</div>

## WRG-03: Combos, bundles and free items

**Combos.** If part of a combo is missing, its value is the combo price multiplied by the part's standalone price, divided by the sum of all standalone prices. Apply any promo share afterward.

Example: a combo costs QAR 36. Standalone prices are burger QAR 30, fries QAR 12 and drink QAR 8, a total of QAR 50. Fries are missing, so the value is 36 x 12 / 50 = QAR 8.64. With a 20% code, the refund is QAR 6.91.

**Free items.** A free item has a refund value of QAR 0.

**Buy one, get one free.** The first missing unit in a pair counts as the free unit. If one unit of a pair is missing, the refund is QAR 0, though a support agent can offer goodwill credit. If both units are missing, refund the price paid for the pair.

<div lang="ar" dir="rtl">

### الوجبات المجمعة والعروض والأصناف المجانية

**الوجبات المجمعة:** إذا نقص جزء من الوجبة، فقيمته هي سعر الوجبة مضروبًا في سعر ذلك الجزء منفردًا، مقسومًا على مجموع الأسعار المنفردة لجميع الأجزاء، ثم تُطبق بعد ذلك حصة خصم الرمز إن وجدت.

مثال: سعر الوجبة 36 ر.ق، والأسعار المنفردة: برجر 30 ر.ق، وبطاطس 12 ر.ق، ومشروب 8 ر.ق، بمجموع 50 ر.ق. إذا نقصت البطاطس فقيمتها 36 x 12 / 50 = 8.64 ر.ق. ومع رمز خصم 20% يكون المبلغ المردود 6.91 ر.ق.

**الأصناف المجانية:** قيمة الصنف المجاني عند الاسترداد 0 ر.ق.

**عرض اشترِ واحدًا واحصل على الثاني مجانًا:** تُعد أول وحدة ناقصة من الزوج هي الوحدة المجانية. فإذا نقصت وحدة واحدة كان المبلغ المردود 0 ر.ق، ويجوز لموظف الدعم أن يعرض رصيد ترضية. وإذا نقصت الوحدتان، يُرد ما دُفع مقابل الزوج.

</div>

## WRG-04: Redelivery instead of a refund

For a missing or wrong item, the customer can choose redelivery if:

- The request comes within 60 minutes of `delivered_at`.
- The merchant is still open and has the item.
- The address is the same.
- No redelivery has happened on this order. The limit is 1 per order.

Redelivery is free. The customer gets redelivery or a refund, never both. If the item does not arrive within 60 minutes of the request, refund it instead. Redelivery is not offered on pharmacy orders or while the severe weather flag is active.

<div lang="ar" dir="rtl">

### إعادة التوصيل بدلًا من الاسترداد

إذا كان الصنف ناقصًا أو خاطئًا، يمكن للعميل اختيار إعادة التوصيل بالشروط الآتية:

- أن يُقدم الطلب خلال 60 دقيقة من `delivered_at`.
- أن يكون التاجر ما زال مفتوحًا والصنف متوفرًا.
- أن يبقى العنوان نفسه.
- ألا تكون إعادة التوصيل قد تمت في هذا الطلب، إذ يُسمح بها مرة واحدة (1) لكل طلب.

وإعادة التوصيل مجانية. ويحصل العميل إما عليها وإما على الاسترداد، لا على كليهما. وإذا لم يصل الصنف خلال 60 دقيقة من طلب إعادة التوصيل، تُرد قيمته بدلًا من ذلك. ولا تتاح إعادة التوصيل في طلبات الصيدلية أو أثناء تفعيل مؤشر الطقس السيئ.

</div>

## WRG-05: Food quality complaints

| Complaint | Window | Refund |
|---|---|---|
| Arrived at the wrong temperature | 2 hours | 50% of net item price |
| Soggy, stale, overcooked or similar | 24 hours | 50% of net item price |
| Spilled or crushed in transit | 24 hours | Treat as damaged: full net item price |
| Taste or personal preference | Not applicable | None |

A quality claim does not count toward the 70% rule, even if every item in the order is affected. If food may be unsafe, stop and use SAF-04 instead.

<div lang="ar" dir="rtl">

### شكاوى جودة الطعام

| الشكوى | المهلة | المبلغ المردود |
|---|---|---|
| وصل بدرجة حرارة غير مناسبة | ساعتان (2) | 50% من صافي سعر الصنف |
| طري أكثر من اللازم أو غير طازج أو مطهو أكثر من اللازم أو ما شابه | 24 ساعة | 50% من صافي سعر الصنف |
| انسكب أو تضرر أثناء النقل | 24 ساعة | يُعامل معاملة التالف: كامل صافي سعر الصنف |
| المذاق أو التفضيل الشخصي | لا ينطبق | لا يوجد |

ولا تدخل شكوى الجودة في قاعدة 70% حتى لو شملت جميع أصناف الطلب. وإذا كان الطعام قد يكون غير آمن، يتوقف هذا الإجراء ويُطبق SAF-04 بدلًا منه.

</div>
