---
id: allergens-and-food-safety
title: "Allergens and food safety"
title_ar: "مسببات الحساسية وسلامة الغذاء"
audience: customer
verticals: [food, grocery]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: SAF-01
    title: "Allergen information and its limits"
    title_ar: "معلومات مسببات الحساسية وحدودها"
    visibility: public
    tags: [allergens, safety]
    rule_keys: []
  - id: SAF-02
    title: "Allergic reaction or urgent health concern"
    title_ar: "التفاعل التحسسي أو الحالة الصحية العاجلة"
    visibility: public
    tags: [allergens, safety, escalation, edge-case]
    rule_keys: [escalation.p1_first_reply_minutes]
  - id: SAF-03
    title: "Allergen mismatch refunds"
    title_ar: "الاسترداد عند عدم تطابق معلومات الحساسية"
    visibility: public
    tags: [allergens, refunds, edge-case]
    rule_keys: [refunds.windows_hours.allergen_mismatch]
  - id: SAF-04
    title: "Foreign objects, tampering and suspected illness"
    title_ar: "الأجسام الغريبة والعبث بالتغليف والاشتباه في التسمم"
    visibility: public
    tags: [safety, refunds, edge-case]
    rule_keys: [refunds.windows_hours.foreign_object, refunds.windows_hours.broken_seal, refunds.windows_hours.suspected_illness]
  - id: SAF-05
    title: "Merchant pause after safety reports"
    title_ar: "إيقاف التاجر بعد بلاغات السلامة"
    visibility: internal
    tags: [safety, merchants]
    rule_keys: [safety.merchant_pause]
---

# Allergens and food safety

<div lang="ar" dir="rtl">

# مسببات الحساسية وسلامة الغذاء

</div>

## SAF-01: Allergen information and its limits

Merchants supply the allergen details shown in the app, and each merchant is responsible for keeping them correct. Jalboot does not prepare food and cannot promise that any item is free of an allergen. Kitchens handle many ingredients, so cross-contact can happen.

Customers can save an allergy profile, choose allergy modifiers, or add a note. Each of these reaches the merchant, but none is a guarantee. Support can read out what the listing says. It cannot say that an item is safe for a person. A customer with a serious allergy should ask the merchant directly before ordering.

<div lang="ar" dir="rtl">

### معلومات مسببات الحساسية وحدودها

يقدم التجار تفاصيل مسببات الحساسية الظاهرة في التطبيق، ويتحمل كل تاجر مسؤولية دقتها. ولا تُعد جالبوت الطعام، ولا تستطيع التعهد بخلو أي صنف من مادة مسببة للحساسية، فالمطابخ تتعامل مع مكونات كثيرة وقد يحدث تلامس غير مقصود بينها.

ويمكن للعميل حفظ ملف للحساسية، أو اختيار خيارات الحساسية، أو إضافة ملاحظة. وكل ذلك يصل إلى التاجر، لكنه ليس ضمانًا. ويستطيع الدعم إخبار العميل بما ورد في بيانات الصنف، ولا يستطيع القول إن صنفًا ما آمن لشخص معين. وينبغي لمن لديه حساسية شديدة أن يسأل التاجر مباشرة قبل الطلب.

</div>

## SAF-02: Allergic reaction or urgent health concern

If a customer describes a reaction, trouble breathing, or any urgent health concern:

1. Tell them to contact local emergency services or a doctor at once.
2. Stop any refund or order flow. Do not ask for photos or order details first.
3. Do not give medical advice or say what caused the problem.
4. Hand off as P1. The safety team replies within 15 minutes (ESC-01).
5. Ask the customer to keep the packaging and any remaining food, once they are safe.

<div lang="ar" dir="rtl">

### التفاعل التحسسي أو الحالة الصحية العاجلة

إذا وصف العميل تفاعلًا تحسسيًا أو صعوبة في التنفس أو أي حالة صحية عاجلة:

1. يُطلب منه التواصل فورًا مع خدمات الطوارئ المحلية أو الطبيب.
2. يتوقف أي مسار للاسترداد أو الطلب، ولا تُطلب منه صور أو تفاصيل الطلب أولًا.
3. لا تُقدم نصيحة طبية ولا يُحدد سبب المشكلة.
4. تُحال الحالة بأولوية P1، ويرد فريق السلامة خلال 15 دقيقة (ESC-01).
5. يُطلب من العميل، بعد اطمئنانه على سلامته، الاحتفاظ بالتغليف وما تبقى من الطعام.

</div>

## SAF-03: Allergen mismatch refunds

An allergen mismatch means one of these:

- An item contained an allergen its listing did not show.
- The customer recorded the allergen through the allergy profile, a modifier or a note, and the item contained it.

The window is 72 hours from `delivered_at`. A support agent or the safety team handles it, never automated support.

If confirmed, the customer gets a full-order refund, even if only one item was affected. The tip stays because a delivery took place. This overrides the 50% rule in WRG-02, and it is not counted as a claim under REF-05.

If the listing was correct and the customer recorded no allergy, this section does not apply. Normal item rules apply instead. Any further offer is for the safety team alone. Support does not admit fault or promise anything beyond this refund.

<div lang="ar" dir="rtl">

### الاسترداد عند عدم تطابق معلومات الحساسية

يُقصد بعدم التطابق إحدى الحالتين:

- أن يحتوي الصنف على مادة مسببة للحساسية لم تُذكر في بياناته.
- أن يسجل العميل الحساسية في ملفه أو في الخيارات أو في ملاحظة، ثم يحتوي الصنف على تلك المادة.

والمهلة 72 ساعة من `delivered_at`. ويتولى الحالة موظف الدعم أو فريق السلامة، ولا يتولاها الدعم الآلي بحال.

وعند تأكيد الحالة يحصل العميل على استرداد كامل للطلب حتى لو تأثر صنف واحد، وتبقى الإكرامية لأن التوصيل قد تم. ويتقدم هذا على قاعدة 50% في WRG-02، ولا يُحسب مطالبة بموجب REF-05.

وإذا كانت بيانات الصنف صحيحة ولم يسجل العميل أي حساسية، فلا ينطبق هذا القسم وتسري قواعد الأصناف المعتادة. وأي عرض إضافي يعود إلى فريق السلامة وحده، ولا يقر الدعم بأي خطأ ولا يتعهد بما يتجاوز هذا الاسترداد.

</div>

## SAF-04: Foreign objects, tampering and suspected illness

| Issue | Window | Remedy | Evidence |
|---|---|---|---|
| Foreign object in food | 72 hours | Full net item price | Photo always required |
| Broken tamper seal | 24 hours, or refuse at the door | Full-order refund | Photo always required |
| Suspected foodborne illness | 7 days (168 hours) | Full-order refund after safety review | No medical note needed |

- A support agent or the safety team handles all three. Any injury or urgent symptom moves to SAF-02 first.
- For suspected illness, support does not say whether the food caused it. Ask the customer to keep any leftovers and packaging.
- These windows override the shorter food window in REF-02.

<div lang="ar" dir="rtl">

### الأجسام الغريبة والعبث بالتغليف والاشتباه في التسمم

| المشكلة | المهلة | الحل | الإثبات |
|---|---|---|---|
| جسم غريب في الطعام | 72 ساعة | كامل صافي سعر الصنف | الصورة مطلوبة دائمًا |
| ختم أمان مكسور | 24 ساعة، أو الرفض عند الباب | استرداد كامل للطلب | الصورة مطلوبة دائمًا |
| اشتباه في تسمم غذائي | 7 أيام (168 ساعة) | استرداد كامل للطلب بعد مراجعة السلامة | لا يلزم تقرير طبي |

- يتولى الحالات الثلاث موظف الدعم أو فريق السلامة، وتنتقل أي إصابة أو أعراض عاجلة إلى SAF-02 أولًا.
- عند الاشتباه في التسمم، لا يقول الدعم إن كان الطعام هو السبب أم لا، ويُطلب من العميل الاحتفاظ بما تبقى من الطعام والتغليف.
- تتقدم هذه المهل على مهلة الطعام الأقصر الواردة في REF-02.

</div>

## SAF-05: Merchant pause after safety reports

Internal rule. Do not discuss a merchant's safety record with customers.

- With 3 confirmed safety reports in the rolling 30 days, the merchant's listing is paused.
- One confirmed allergen case that needed medical treatment pauses the listing at once.
- The review finishes within 3 business days. The listing returns only after the merchant shows what it has fixed.

<div lang="ar" dir="rtl">

### إيقاف التاجر بعد بلاغات السلامة

قاعدة داخلية: لا يُناقش سجل السلامة الخاص بالتاجر مع العملاء.

- عند ثبوت 3 بلاغات سلامة خلال 30 يومًا متحركة، يُوقف عرض التاجر في التطبيق.
- تؤدي حالة حساسية واحدة مؤكدة احتاجت إلى علاج طبي إلى الإيقاف فورًا.
- تنتهي المراجعة خلال 3 أيام عمل، ولا يعود العرض إلا بعد أن يوضح التاجر ما أصلحه.

</div>
