---
id: delivery-fees-and-zones
title: "Delivery fees and zones"
title_ar: "رسوم التوصيل والمناطق"
audience: customer
verticals: [food, grocery, pharmacy]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: FEE-01
    title: "Delivery zones"
    title_ar: "مناطق التوصيل"
    visibility: public
    tags: [zones]
    rule_keys: []
  - id: FEE-02
    title: "Delivery fee table"
    title_ar: "جدول رسوم التوصيل"
    visibility: public
    tags: [fees]
    rule_keys: [fees.delivery_fee_qar]
  - id: FEE-03
    title: "Minimum order and small order fee"
    title_ar: "الحد الأدنى للطلب ورسوم الطلب الصغير"
    visibility: public
    tags: [fees, edge-case]
    rule_keys: [fees.minimum_order_qar, fees.small_order]
  - id: FEE-04
    title: "Free delivery thresholds"
    title_ar: "حدود التوصيل المجاني"
    visibility: public
    tags: [fees, edge-case]
    rule_keys: [fees.free_delivery.food.min_subtotal_qar, fees.free_delivery.grocery.min_subtotal_qar, fees.free_delivery.pharmacy.min_subtotal_qar]
  - id: FEE-05
    title: "Service, peak and weather fees and tips"
    title_ar: "رسوم الخدمة والذروة والطقس والإكرامية"
    visibility: public
    tags: [fees, calculation, edge-case]
    rule_keys: [fees.service_fee, fees.peak.fee_qar, fees.weather.fee_qar, fees.surcharge_cap_qar, fees.tip_max_qar]
---

# Delivery fees and zones

<div lang="ar" dir="rtl">

# رسوم التوصيل والمناطق

</div>

## FEE-01: Delivery zones

| Zone | Name | Areas |
|---|---|---|
| A | Central | Al Dafna, West Bay, Msheireb, Al Sadd, Bin Mahmoud, Al Mansoura, Najma, Old Airport |
| B | Inner | Madinat Khalifa, Al Gharrafa, Al Waab, Al Aziziyah, Onaiza, The Pearl, Al Duhail |
| C | Outer | Lusail, Al Rayyan, Al Wakrah, Al Wukair, Muaither, Umm Salal |
| D | Extended | Al Khor, Mesaieed, Al Shahaniya |

The zone comes from the delivery pin on the map, not from the merchant's location and not from the area name typed in the address. Food delivery is not offered in Zone D. A merchant can also set a smaller delivery area of its own.

<div lang="ar" dir="rtl">

### مناطق التوصيل

| المنطقة | الاسم | الأحياء |
|---|---|---|
| A | الوسط | الدفنة، الخليج الغربي، مشيرب، السد، بن محمود، المنصورة، نجمة، المطار القديم |
| B | الداخلية | مدينة خليفة، الغرافة، الوعب، العزيزية، عنيزة، اللؤلؤة، الدحيل |
| C | الخارجية | لوسيل، الريان، الوكرة، الوكير، معيذر، أم صلال |
| D | الموسعة | الخور، مسيعيد، الشحانية |

تُحدد المنطقة بحسب موقع التوصيل على الخريطة، لا بحسب موقع التاجر ولا اسم الحي المكتوب في العنوان. ولا تتوفر خدمة توصيل الطعام في المنطقة D. ويجوز للتاجر أيضًا تحديد نطاق توصيل أضيق خاص به.

</div>

## FEE-02: Delivery fee table

Amounts in QAR.

| Zone | Food | Grocery | Pharmacy |
|---|---|---|---|
| A | 5 | 7 | 5 |
| B | 8 | 10 | 8 |
| C | 12 | 15 | 12 |
| D | Not available | 25 | 20 |

Parcel prices are in PCL-02. The delivery fee shown at checkout is final. It is not recalculated if items are later removed or replaced. The only exception is a customer address change (ACC-03).

<div lang="ar" dir="rtl">

### جدول رسوم التوصيل

المبالغ بالريال القطري (ر.ق).

| المنطقة | طعام | بقالة | صيدلية |
|---|---|---|---|
| A | 5 | 7 | 5 |
| B | 8 | 10 | 8 |
| C | 12 | 15 | 12 |
| D | غير متاح | 25 | 20 |

وترد أسعار الطرود في PCL-02. ورسوم التوصيل الظاهرة عند إتمام الطلب نهائية، ولا يُعاد حسابها إذا أُزيلت أصناف أو استُبدلت لاحقًا. والاستثناء الوحيد هو تغيير العميل للعنوان (ACC-03).

</div>

## FEE-03: Minimum order and small order fee

| Order type | Minimum order | Small order fee |
|---|---|---|
| Food | QAR 20 | QAR 3 if item subtotal is below QAR 30 |
| Grocery | QAR 40 | QAR 5 if item subtotal is below QAR 60 |
| Pharmacy | QAR 0 (no minimum) | None |

Both are tested on the item subtotal before any promo code. An item subtotal of exactly QAR 30 on a food order pays no small order fee. A code that brings the amount below these values does not add the fee.

If items drop out after checkout, the minimum is not tested again and no small order fee is added.

<div lang="ar" dir="rtl">

### الحد الأدنى للطلب ورسوم الطلب الصغير

| نوع الطلب | الحد الأدنى للطلب | رسوم الطلب الصغير |
|---|---|---|
| طعام | 20 ر.ق | 3 ر.ق إذا قل إجمالي الأصناف عن 30 ر.ق |
| بقالة | 40 ر.ق | 5 ر.ق إذا قل إجمالي الأصناف عن 60 ر.ق |
| صيدلية | 0 ر.ق (لا حد أدنى) | لا يوجد |

ويُختبر الأمران على إجمالي الأصناف قبل أي رمز خصم. فطلب الطعام الذي يبلغ إجمالي أصنافه 30 ر.ق تمامًا لا تُفرض عليه رسوم الطلب الصغير، ولا تضاف هذه الرسوم إذا نزل المبلغ عن هذه القيم بسبب رمز خصم.

وإذا سقطت أصناف بعد إتمام الطلب، فلا يُعاد اختبار الحد الأدنى ولا تضاف رسوم الطلب الصغير.

</div>

## FEE-04: Free delivery thresholds

| Order type | Item subtotal at or above | Free in | Half fee in |
|---|---|---|---|
| Food | QAR 150 | Zones A, B | None |
| Grocery | QAR 200 | Zones A, B | Zone C |
| Pharmacy | QAR 100 | Zone A | Zone B |

- The threshold is tested on the item subtotal before any promo code. An order of QAR 210 with a QAR 15 code still qualifies.
- Free delivery covers the delivery fee only. Peak, weather, service and small order fees still apply.
- If items drop out after checkout and the subtotal falls below the threshold, free delivery stays.

<div lang="ar" dir="rtl">

### حدود التوصيل المجاني

| نوع الطلب | إجمالي الأصناف يساوي أو يزيد على | مجاني في | بنصف الرسوم في |
|---|---|---|---|
| طعام | 150 ر.ق | المنطقتين A وB | لا يوجد |
| بقالة | 200 ر.ق | المنطقتين A وB | المنطقة C |
| صيدلية | 100 ر.ق | المنطقة A | المنطقة B |

- يُختبر الحد على إجمالي الأصناف قبل أي رمز خصم، فالطلب البالغ 210 ر.ق مع رمز بقيمة 15 ر.ق يبقى مؤهلًا.
- يشمل التوصيل المجاني رسوم التوصيل فقط، وتبقى رسوم الذروة والطقس والخدمة والطلب الصغير سارية.
- إذا سقطت أصناف بعد إتمام الطلب ونزل الإجمالي عن الحد، يبقى التوصيل مجانيًا.

</div>

## FEE-05: Service, peak and weather fees and tips

- **Service fee:** 3% of the item subtotal, minimum QAR 1, maximum QAR 7.
- **Peak fee:** QAR 4 on orders placed on Thursday or Friday from 18:00:00 to 21:59:59. The time of `placed_at` decides, not the delivery time.
- **Weather fee:** QAR 6 if the severe weather flag is active at `placed_at`.
- **Combined limit:** peak and weather fees together cannot exceed QAR 8.
- **Tip:** optional, up to QAR 50, set at checkout, and paid in full to the driver.
- Parcels pay none of these fees.

Example: grocery order in Zone C, item subtotal QAR 220, placed Friday at 19:00 with the weather flag on. Delivery fee QAR 7.50 (half of QAR 15), peak and weather QAR 8 (capped from QAR 10), service fee QAR 6.60. Total fees QAR 22.10.

<div lang="ar" dir="rtl">

### رسوم الخدمة والذروة والطقس والإكرامية

- **رسوم الخدمة:** 3% من إجمالي الأصناف، بحد أدنى 1 ر.ق وحد أقصى 7 ر.ق.
- **رسوم الذروة:** 4 ر.ق على الطلبات المقدمة يومي الخميس والجمعة من 18:00:00 إلى 21:59:59. والعبرة بوقت `placed_at` لا بوقت التسليم.
- **رسوم الطقس:** 6 ر.ق إذا كان مؤشر الطقس السيئ مفعلًا عند `placed_at`.
- **الحد المشترك:** لا يجوز أن يتجاوز مجموع رسوم الذروة والطقس 8 ر.ق.
- **الإكرامية:** اختيارية، بحد أقصى 50 ر.ق، تُحدد عند إتمام الطلب وتُدفع كاملة للمندوب.
- لا تُفرض أي من هذه الرسوم على الطرود.

مثال: طلب بقالة في المنطقة C، إجمالي أصنافه 220 ر.ق، قُدم يوم الجمعة الساعة 19:00 ومؤشر الطقس مفعل. رسوم التوصيل 7.50 ر.ق (نصف 15 ر.ق)، والذروة والطقس 8 ر.ق (بعد تخفيضها من 10 ر.ق)، ورسوم الخدمة 6.60 ر.ق. إجمالي الرسوم 22.10 ر.ق.

</div>
