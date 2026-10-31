---
id: parcels
title: "Parcels"
title_ar: "الطرود"
audience: customer
verticals: [parcel]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: PCL-01
    title: "What can be sent"
    title_ar: "ما الذي يمكن إرساله"
    visibility: public
    tags: [parcels, eligibility, edge-case]
    rule_keys: [parcels.max_weight_kg, parcels.max_side_cm]
  - id: PCL-02
    title: "Parcel pricing"
    title_ar: "أسعار الطرود"
    visibility: public
    tags: [parcels, fees, calculation, edge-case]
    rule_keys: [parcels.base_fee_qar, parcels.base_weight_kg, parcels.weight_bands, parcels.reweigh_tolerance_kg, parcels.pickup_wait_minutes]
  - id: PCL-03
    title: "Cover"
    title_ar: "التغطية"
    visibility: public
    tags: [parcels, cover, calculation, edge-case]
    rule_keys: [parcels.default_cover_qar, parcels.documents_cover_qar, parcels.extended_cover_max_qar, parcels.extended_cover_rate_pct, parcels.extended_cover_min_fee_qar, parcels.otp_from_declared_value_qar, parcels.proof_required_above_qar]
  - id: PCL-04
    title: "Delays, loss and damage"
    title_ar: "التأخير والفقدان والتلف"
    visibility: public
    tags: [parcels, claims, edge-case]
    rule_keys: [parcels.delay_refund, parcels.lost_after_hours_past_promised, parcels.claim_window_days, parcels.claim_decision_business_days, parcels.damage_window_hours, parcels.keep_packaging_days]
  - id: PCL-05
    title: "Failed attempts and returns"
    title_ar: "محاولات التسليم الفاشلة والإعادة"
    visibility: public
    tags: [parcels, failed-delivery, edge-case]
    rule_keys: [parcels.free_attempts, parcels.extra_attempt_fee_qar, parcels.hub_hold_days, parcels.return_fee_pct_of_base, parcels.unclaimed_disposal_days]
---

# Parcels

<div lang="ar" dir="rtl">

# الطرود

</div>

## PCL-01: What can be sent

Parcels travel between addresses in Zones A to D only. There is no international service. A parcel can weigh up to 30 kg, and its longest side can be up to 120 cm.

**Not accepted:** cash, bank cards, gold and jewellery, medicines, perishable food, hazardous or flammable goods, loose batteries, weapons, live animals, and anything illegal.

If a banned item is found, the parcel has no cover. It goes back to the sender at the sender's cost, and the account is flagged for review.

Only the sender, meaning the account that booked the parcel, can change the booking or make a claim. A recipient with a problem should ask the sender to contact support.

<div lang="ar" dir="rtl">

### ما الذي يمكن إرساله

تُنقل الطرود بين العناوين الواقعة في المناطق من A إلى D فقط، ولا توجد خدمة دولية. ويصل وزن الطرد إلى 30 كجم كحد أقصى، وطول أطول أضلاعه إلى 120 سم.

**لا يُقبل ما يلي:** النقد، والبطاقات المصرفية، والذهب والمجوهرات، والأدوية، والأطعمة سريعة التلف، والمواد الخطرة أو القابلة للاشتعال، والبطاريات غير المثبتة في أجهزتها، والأسلحة، والحيوانات الحية، وأي شيء غير مشروع.

وإذا عُثر على صنف ممنوع، فلا تشمله أي تغطية، ويعود الطرد إلى المرسل على نفقته، ويُحال الحساب إلى المراجعة.

ولا يحق تعديل الحجز أو تقديم مطالبة إلا للمرسل، أي صاحب الحساب الذي حجز الطرد. وعلى المستلم الذي يواجه مشكلة أن يطلب من المرسل التواصل مع الدعم.

</div>

## PCL-02: Parcel pricing

Price = base fee + weight surcharge.

The base fee uses the higher zone of the pickup and drop-off addresses:

| Higher zone | Base fee |
|---|---|
| A | QAR 15 |
| B | QAR 20 |
| C | QAR 30 |
| D | QAR 45 |

| Weight | Surcharge |
|---|---|
| Up to 5 kg | None |
| Over 5 kg, up to 15 kg | QAR 10 |
| Over 15 kg, up to 30 kg | QAR 25 |

- Exactly 5 kg pays no surcharge. Exactly 15 kg pays QAR 10.
- If the weight on pickup is more than 1 kg above the booked weight, the sender pays any surcharge difference. A difference of exactly 1 kg changes nothing.
- The driver waits 10 minutes at pickup.
- Parcels pay no service, peak, weather or small order fee. Free delivery thresholds and Plus do not apply.

Example: Zone A to Zone C, 12 kg. Base fee QAR 30 plus surcharge QAR 10 is QAR 40.

<div lang="ar" dir="rtl">

### أسعار الطرود

السعر = الرسم الأساسي + رسم الوزن.

يُحسب الرسم الأساسي بحسب المنطقة الأعلى من بين عنواني الاستلام والتسليم:

| المنطقة الأعلى | الرسم الأساسي |
|---|---|
| A | 15 ر.ق |
| B | 20 ر.ق |
| C | 30 ر.ق |
| D | 45 ر.ق |

| الوزن | رسم الوزن |
|---|---|
| حتى 5 كجم | لا يوجد |
| أكثر من 5 كجم وحتى 15 كجم | 10 ر.ق |
| أكثر من 15 كجم وحتى 30 كجم | 25 ر.ق |

- الطرد الذي يزن 5 كجم تمامًا لا يدفع رسم وزن، والذي يزن 15 كجم تمامًا يدفع 10 ر.ق.
- إذا زاد الوزن عند الاستلام بأكثر من 1 كجم على الوزن المحجوز، يدفع المرسل فرق رسم الوزن إن وجد. أما الزيادة البالغة 1 كجم تمامًا فلا تغيّر شيئًا.
- ينتظر المندوب 10 دقائق عند نقطة الاستلام.
- لا تُفرض على الطرود رسوم الخدمة أو الذروة أو الطقس أو الطلب الصغير، ولا تنطبق عليها حدود التوصيل المجاني ولا اشتراك Plus.

مثال: من المنطقة A إلى المنطقة C بوزن 12 كجم: الرسم الأساسي 30 ر.ق مضافًا إليه رسم الوزن 10 ر.ق، فيكون المجموع 40 ر.ق.

</div>

## PCL-03: Cover

- **Default cover:** QAR 200 per parcel, free.
- **Documents:** QAR 50, whatever value is declared. Extended cover cannot raise this.
- **Extended cover:** up to QAR 2,000. It costs 1% of the declared value, minimum QAR 3, and must be added before pickup.
- **Handover code:** required at drop-off when the declared value is QAR 500 or more.

**Payout** is the lowest of the declared value, the proven value and the cover.

Proof of value, such as a receipt, is required for a claim above QAR 100. Without proof, the payout cannot exceed QAR 100.

Cover does not include banned items, or loss of use or other indirect loss.

Example: declared value QAR 1,500, extended cover fee QAR 15, receipt for QAR 1,200. The parcel is lost, so the payout is QAR 1,200. A parcel declared at QAR 300 with no extended cover has QAR 200 of cover.

<div lang="ar" dir="rtl">

### التغطية

- **التغطية الافتراضية:** 200 ر.ق للطرد الواحد مجانًا.
- **المستندات:** 50 ر.ق مهما كانت القيمة المعلنة، ولا ترفعها التغطية الموسعة.
- **التغطية الموسعة:** حتى 2,000 ر.ق، وتكلفتها 1% من القيمة المعلنة بحد أدنى 3 ر.ق، ويجب إضافتها قبل الاستلام.
- **رمز التسليم:** يلزم عند التسليم إذا بلغت القيمة المعلنة 500 ر.ق أو أكثر.

**مبلغ التعويض** هو الأقل من بين القيمة المعلنة والقيمة المثبتة ومبلغ التغطية.

ويلزم إثبات القيمة، كإيصال الشراء، في المطالبة التي تتجاوز 100 ر.ق. ودون إثبات لا يتجاوز التعويض 100 ر.ق.

ولا تشمل التغطية الأصناف الممنوعة ولا فوات المنفعة أو أي خسارة غير مباشرة.

مثال: القيمة المعلنة 1,500 ر.ق، ورسم التغطية الموسعة 15 ر.ق، والإيصال بمبلغ 1,200 ر.ق. فُقد الطرد، فيكون التعويض 1,200 ر.ق. أما الطرد المعلن بقيمة 300 ر.ق دون تغطية موسعة فتغطيته 200 ر.ق.

</div>

## PCL-04: Delays, loss and damage

**Promised time.** A parcel booked by 16:00:00 is promised by 23:59:59 the same day. A later booking is promised by 23:59:59 the next day.

**Delay.** The delivery fee is partly returned once, using the highest row that applies:

| Time past `promised_at` | Delivery fee refund |
|---|---|
| Over 24 hours | 50% |
| Over 48 hours | 100% |

Exactly 24 hours gives no refund.

**Lost parcel.** A parcel counts as lost if it has no tracking update 72 hours after `promised_at`. The sender can claim up to 14 days after `promised_at`. The payout follows PCL-03, and the delivery fee is refunded in full. A delay refund is not added on top.

**Damage.** Report within 72 hours of `delivered_at`, with a photo. Keep the packaging for 7 days. The payout follows PCL-03. The delivery fee is not refunded.

A support agent handles every claim and decides within 5 business days.

<div lang="ar" dir="rtl">

### التأخير والفقدان والتلف

**الموعد المحدد:** الطرد المحجوز حتى الساعة 16:00:00 يُسلَّم بحلول 23:59:59 من اليوم نفسه، والطرد المحجوز بعد ذلك يُسلَّم بحلول 23:59:59 من اليوم التالي.

**التأخير:** يُرد جزء من رسوم التوصيل مرة واحدة بحسب أعلى صف ينطبق:

| الوقت بعد `promised_at` | المردود من رسوم التوصيل |
|---|---|
| أكثر من 24 ساعة | 50% |
| أكثر من 48 ساعة | 100% |

والتأخر 24 ساعة تمامًا لا يُرد عنه شيء.

**فقدان الطرد:** يُعد الطرد مفقودًا إذا لم يظهر له أي تحديث تتبع بعد 72 ساعة من `promised_at`. ويحق للمرسل تقديم المطالبة حتى 14 يومًا بعد `promised_at`. ويُحسب التعويض وفق PCL-03 وتُرد رسوم التوصيل كاملة، ولا يضاف إليهما مبلغ التأخير.

**التلف:** يجب الإبلاغ خلال 72 ساعة من `delivered_at` مع صورة، والاحتفاظ بالتغليف مدة 7 أيام. ويُحسب التعويض وفق PCL-03، ولا تُرد رسوم التوصيل.

ويتولى موظف الدعم كل مطالبة ويبت فيها خلال 5 أيام عمل.

</div>

## PCL-05: Failed attempts and returns

- The first 2 delivery attempts are free. A third attempt costs QAR 10.
- After the last failed attempt, or if the recipient refuses the parcel, it stays at the hub for 5 days.
- If nobody arranges a new attempt, it returns to the sender for 50% of the base fee.
- After pickup, a parcel cannot be cancelled. The sender can only ask for return to sender, at the same 50%.
- If the sender cannot be reached for a return, the parcel is held until 30 days after the first failed attempt and then disposed of. Cover ends at that point.

<div lang="ar" dir="rtl">

### محاولات التسليم الفاشلة والإعادة

- أول محاولتين (2) للتسليم مجانيتان، وتكلف المحاولة الثالثة 10 ر.ق.
- بعد فشل آخر محاولة، أو إذا رفض المستلم الطرد، يبقى الطرد في مركز الفرز مدة 5 أيام.
- إذا لم يرتب أحد محاولة جديدة، يعود الطرد إلى المرسل مقابل 50% من الرسم الأساسي.
- لا يمكن إلغاء الطرد بعد استلامه من المرسل، وكل ما يمكنه هو طلب إعادته إليه مقابل 50% من الرسم الأساسي.
- إذا تعذر الوصول إلى المرسل لإعادة الطرد، يُحتفظ به حتى مرور 30 يومًا على أول محاولة فاشلة ثم يُتخلص منه، وتنتهي التغطية عند ذلك.

</div>
