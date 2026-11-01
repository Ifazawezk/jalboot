---
id: grocery-substitutions
title: "Grocery substitutions"
title_ar: "بدائل أصناف البقالة"
audience: customer
verticals: [grocery]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: GRC-01
    title: "Substitution preferences"
    title_ar: "تفضيلات الاستبدال"
    visibility: public
    tags: [grocery, edge-case]
    rule_keys: [grocery.contact_timeout_minutes]
  - id: GRC-02
    title: "Substitute pricing and weighed items"
    title_ar: "سعر البديل والأصناف الموزونة"
    visibility: public
    tags: [grocery, calculation, edge-case]
    rule_keys: [grocery.substitute_approval_above_pct, grocery.weighed_charge_cap_pct, payments.grocery_hold_pct]
  - id: GRC-03
    title: "Items that are never substituted"
    title_ar: "أصناف لا تُستبدل أبدًا"
    visibility: public
    tags: [grocery, safety, edge-case]
    rule_keys: []
  - id: GRC-04
    title: "Rejecting a substitute"
    title_ar: "رفض البديل"
    visibility: public
    tags: [grocery, refunds, edge-case]
    rule_keys: [refunds.windows_hours.grocery_ambient, refunds.windows_hours.grocery_chilled_frozen]
  - id: GRC-05
    title: "Large shortfalls and expired items"
    title_ar: "النقص الكبير والأصناف منتهية الصلاحية"
    visibility: public
    tags: [grocery, refunds, edge-case]
    rule_keys: [grocery.large_shortfall_above_pct, grocery.contact_timeout_minutes, grocery.expired_item_credit_qar, refunds.windows_hours.expired_product]
---

# Grocery substitutions

<div lang="ar" dir="rtl">

# بدائل أصناف البقالة

</div>

## GRC-01: Substitution preferences

The customer sets one of three preferences for each item:

| Preference | What happens if the item is out of stock |
|---|---|
| `substitute` | The picker chooses a similar item |
| `contact_me` | The picker messages the customer |
| `refund` | The item is removed and refunded |

If the customer sets nothing, the default is `contact_me`. After a `contact_me` message, the customer has 5 minutes to reply. With no reply, the item is removed and refunded. The picker does not choose a substitute in that case.

A substitute the customer approved by message counts as the customer's own choice (GRC-04).

<div lang="ar" dir="rtl">

### تفضيلات الاستبدال

يحدد العميل أحد ثلاثة تفضيلات لكل صنف:

| التفضيل | ما يحدث إذا نفد الصنف |
|---|---|
| `substitute` | يختار موظف التجهيز صنفًا مشابهًا |
| `contact_me` | يراسل موظف التجهيز العميل |
| `refund` | يُزال الصنف وتُرد قيمته |

وإذا لم يحدد العميل شيئًا، يكون الخيار الافتراضي `contact_me`. وبعد رسالة موظف التجهيز تكون أمام العميل 5 دقائق للرد، فإذا لم يرد أُزيل الصنف ورُدت قيمته، ولا يختار موظف التجهيز بديلًا في هذه الحالة.

ويُعد البديل الذي وافق عليه العميل عبر الرسالة اختيارًا منه (GRC-04).

</div>

## GRC-02: Substitute pricing and weighed items

**Substitute price.** The customer pays the lower of the original price and the substitute price. If the substitute is cheaper, the customer pays less.

**Approval needed.** Even with the `substitute` preference, a substitute priced above 125% of the original needs the customer's approval. At exactly 125%, no approval is needed.

**Weighed items.** The final price uses the actual weight. If the actual weight is above the estimate, the charge is capped at 110% of the estimated price. If it is below, the customer simply pays less. This matches the 110% hold in PAY-02.

A later price change does not reopen free delivery, minimum order or promo tests (FEE-03, FEE-04).

<div lang="ar" dir="rtl">

### سعر البديل والأصناف الموزونة

**سعر البديل:** يدفع العميل الأقل من بين السعر الأصلي وسعر البديل، فإذا كان البديل أرخص دفع أقل.

**الحاجة إلى موافقة:** حتى مع تفضيل `substitute`، يحتاج البديل الذي يتجاوز سعره 125% من السعر الأصلي إلى موافقة العميل. أما عند 125% تمامًا فلا تلزم الموافقة.

**الأصناف الموزونة:** يُحتسب السعر النهائي بحسب الوزن الفعلي. فإذا زاد الوزن على التقدير، لا يتجاوز المبلغ 110% من السعر التقديري، وإذا قل دفع العميل أقل. ويتفق ذلك مع حجز 110% الوارد في PAY-02.

ولا يعيد أي تغير لاحق في السعر فتح اختبارات التوصيل المجاني أو الحد الأدنى للطلب أو رمز الخصم (FEE-03 و FEE-04).

</div>

## GRC-03: Items that are never substituted

These are treated as `refund`, even if the customer chose `substitute`:

- Infant formula and baby food.
- Items labelled free from an allergen, such as gluten free or nut free.
- Any item the app flags against the customer's saved allergy profile.
- Medicines and supplements.

The allergy profile always overrides the item preference. An item labelled halal can only be replaced by another item labelled halal.

<div lang="ar" dir="rtl">

### أصناف لا تُستبدل أبدًا

تُعامل الأصناف الآتية معاملة `refund` حتى لو اختار العميل `substitute`:

- حليب الرضع وأغذية الأطفال.
- الأصناف الموسومة بخلوها من مادة مسببة للحساسية، مثل الخالية من الغلوتين أو المكسرات.
- أي صنف ينبه التطبيق إلى تعارضه مع ملف الحساسية المحفوظ للعميل.
- الأدوية والمكملات الغذائية.

ويتقدم ملف الحساسية دائمًا على تفضيل الصنف. ولا يُستبدل الصنف الموسوم بأنه حلال إلا بصنف موسوم بالوصف نفسه.

</div>

## GRC-04: Rejecting a substitute

- A substitute the customer did not approve can be rejected at the door or later: within 48 hours for shelf-stable items, and within 6 hours for chilled or frozen items.
- The refund is what the customer paid for the substitute. A simple rejection needs no photo.
- A substitute the customer approved can be rejected only if it is damaged, spoiled or expired, and REF-06 then sets when a photo is needed.
- A rejected substitute is not counted as a claim under REF-05, and it does not count toward the 70% rule in REF-03.

<div lang="ar" dir="rtl">

### رفض البديل

- يمكن رفض البديل الذي لم يوافق عليه العميل عند الباب أو لاحقًا: خلال 48 ساعة للأصناف التي تُحفظ على الرف، وخلال 6 ساعات للأصناف المبردة أو المجمدة.
- المبلغ المردود هو ما دفعه العميل مقابل البديل، ولا يحتاج الرفض العادي إلى صورة.
- لا يمكن رفض البديل الذي وافق عليه العميل إلا إذا كان تالفًا أو فاسدًا أو منتهي الصلاحية، ويحدد REF-06 عندئذ متى تلزم الصورة.
- لا يُحسب البديل المرفوض مطالبة بموجب REF-05، ولا يدخل في قاعدة 70% الواردة في REF-03.

</div>

## GRC-05: Large shortfalls and expired items

**Large shortfall.** If items out of stock with no substitute make up more than 50% of the item subtotal, the picker pauses. The customer has 5 minutes to continue or to cancel free (CAN-04). With no reply, picking continues with what is available. At exactly 50%, there is no pause.

Fees stay as quoted at checkout. No small order fee is added and free delivery stays (FEE-03, FEE-04).

**Expired at delivery.** Refund the full net item price and add QAR 10 of expired item credit, once per order, however many items are affected. The window is 7 days (168 hours), with a photo of the date. The credit counts toward the QAR 30 per order cap in REF-07.

<div lang="ar" dir="rtl">

### النقص الكبير والأصناف منتهية الصلاحية

**النقص الكبير:** إذا تجاوزت الأصناف النافدة التي لا بديل لها 50% من إجمالي الأصناف، يتوقف موظف التجهيز، وتكون أمام العميل 5 دقائق ليواصل الطلب أو يلغيه مجانًا (CAN-04). فإذا لم يرد، يستمر التجهيز بالمتوفر. وعند 50% تمامًا لا يتوقف التجهيز.

وتبقى الرسوم كما ظهرت عند إتمام الطلب، فلا تضاف رسوم الطلب الصغير ويبقى التوصيل المجاني (FEE-03 و FEE-04).

**منتهي الصلاحية عند التسليم:** يُرد كامل صافي سعر الصنف، ويضاف رصيد بقيمة 10 ر.ق مرة واحدة لكل طلب مهما بلغ عدد الأصناف المتأثرة. والمهلة 7 أيام (168 ساعة)، مع صورة تظهر التاريخ. ويدخل هذا الرصيد في سقف 30 ر.ق للطلب الواحد الوارد في REF-07.

</div>
