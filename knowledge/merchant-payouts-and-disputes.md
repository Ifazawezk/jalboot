---
id: merchant-payouts-and-disputes
title: "Merchant payouts and disputes"
title_ar: "مستحقات التجار والاعتراضات"
audience: merchant
verticals: [food, grocery, pharmacy]
languages: [en, ar]
version: 1
effective_from: "2026-11-01"
fictional: true
sections:
  - id: MPO-01
    title: "Payout schedule"
    title_ar: "جدول تحويل المستحقات"
    visibility: public
    tags: [merchants, payouts, edge-case]
    rule_keys: [merchant_payouts.pay_within_business_days, merchant_payouts.minimum_payout_qar, merchant_payouts.max_rollover_weeks]
  - id: MPO-02
    title: "What is deducted"
    title_ar: "ما يُستقطع من المستحقات"
    visibility: public
    tags: [merchants, payouts, calculation]
    rule_keys: [merchant_onboarding.commission_pct.food, merchant_payouts.processing_fee_pct]
  - id: MPO-03
    title: "Who pays for a refund"
    title_ar: "من يتحمل قيمة الاسترداد"
    visibility: public
    tags: [merchants, refunds, edge-case]
    rule_keys: [merchant_payouts.unknown_cause_split_pct, merchant_payouts.merchant_fault_review_pct]
  - id: MPO-04
    title: "Disputing a deduction"
    title_ar: "الاعتراض على استقطاع"
    visibility: public
    tags: [merchants, disputes, edge-case]
    rule_keys: [merchant_payouts.dispute_window_days, merchant_payouts.dispute_response_business_days, merchant_payouts.small_deduction_qar, merchant_payouts.small_deduction_bundle_count]
  - id: MPO-05
    title: "Reserve, bank changes, negative balances and final payout"
    title_ar: "مبلغ الضمان وتغيير الحساب المصرفي والرصيد السالب والتسوية النهائية"
    visibility: public
    tags: [merchants, payouts, edge-case]
    rule_keys: [merchant_payouts.reserve_pct, merchant_payouts.reserve_days, merchant_payouts.reserve_release_days, merchant_payouts.bank_change_hold_business_days, merchant_payouts.bank_change_cutoff_hours, merchant_payouts.negative_balance_invoice_days, merchant_payouts.negative_balance_suspend_qar, merchant_payouts.final_payout_days]
---

# Merchant payouts and disputes

<div lang="ar" dir="rtl">

# مستحقات التجار والاعتراضات

</div>

## MPO-01: Payout schedule

- A payout week runs from Sunday 00:00:00 to Saturday 23:59:59.
- The statement comes out on Sunday. Money is paid within 3 business days of the statement.
- The minimum payout is QAR 100. A smaller balance rolls into the next week.
- After 4 weeks of rolling over, the balance is paid whatever its size.
- Cash orders are included. Jalboot collects through the driver and pays the merchant in the same statement.

<div lang="ar" dir="rtl">

### جدول تحويل المستحقات

- يمتد أسبوع المستحقات من الأحد 00:00:00 إلى السبت 23:59:59.
- يصدر كشف الحساب يوم الأحد، وتُحوَّل الأموال خلال 3 أيام عمل منه.
- الحد الأدنى للتحويل 100 ر.ق، ويُرحَّل الرصيد الأقل منه إلى الأسبوع التالي.
- بعد 4 أسابيع من الترحيل، يُحوَّل الرصيد مهما كان مقداره.
- تدخل الطلبات النقدية في الكشف نفسه، إذ تحصّل جالبوت قيمتها عبر المندوب ثم تحولها إلى التاجر.

</div>

## MPO-02: What is deducted

- **Commission:** the rate in MOB-03, on the item subtotal after merchant-funded discounts. Delivery fees, service fees and tips are not commissionable and do not go to the merchant.
- **Processing fee:** 1.5% on the same base.
- **Merchant-fault refunds:** see MPO-03.
- **Merchant-funded offers:** as agreed for each campaign. Jalboot funds the codes in PRM-01.

Example: a food order with an item subtotal of QAR 200. Commission is 22%, or QAR 44.00. Processing fee is QAR 3.00. The merchant receives QAR 153.00. A QAR 30 merchant-fault refund later deducts QAR 30, and QAR 6.60 of commission is returned, so the net deduction is QAR 23.40. The processing fee is not returned. The merchant is left with QAR 129.60.

<div lang="ar" dir="rtl">

### ما يُستقطع من المستحقات

- **العمولة:** بالنسبة الواردة في MOB-03، وتُحسب على إجمالي الأصناف بعد الخصومات التي يمولها التاجر. ولا تدخل رسوم التوصيل ورسوم الخدمة والإكرامية في حساب العمولة ولا تذهب إلى التاجر.
- **رسوم المعالجة:** 1.5% على الأساس نفسه.
- **الاسترداد بخطأ التاجر:** انظر MPO-03.
- **العروض التي يمولها التاجر:** بحسب الاتفاق في كل حملة، وتمول جالبوت الرموز الواردة في PRM-01.

مثال: طلب طعام إجمالي أصنافه 200 ر.ق. العمولة 22%، أي 44.00 ر.ق، ورسوم المعالجة 3.00 ر.ق، فيحصل التاجر على 153.00 ر.ق. وإذا صدر لاحقًا استرداد بقيمة 30 ر.ق بخطأ التاجر، يُستقطع 30 ر.ق وتُعاد 6.60 ر.ق من العمولة، فيكون صافي الاستقطاع 23.40 ر.ق. ولا تُعاد رسوم المعالجة، ويبقى للتاجر 129.60 ر.ق.

</div>

## MPO-03: Who pays for a refund

| Cause | Who pays |
|---|---|
| Missing, wrong or poor-quality item, allergen mismatch, expired item, merchant cancellation after accepting | Merchant pays the net item value |
| Late delivery, order lost by the driver, not received, damage in transit | Jalboot. The merchant is paid in full |
| Cause cannot be established | Split 50% merchant, 50% Jalboot |

Delivery fees, service fees, tips and all compensation credit are always funded by Jalboot, never by the merchant.

If merchant-fault refunds exceed 5% of a merchant's orders in the rolling 30 days, Jalboot opens a quality review.

<div lang="ar" dir="rtl">

### من يتحمل قيمة الاسترداد

| السبب | من يتحمل |
|---|---|
| صنف ناقص أو خاطئ أو رديء الجودة، أو عدم تطابق معلومات الحساسية، أو صنف منتهي الصلاحية، أو إلغاء التاجر بعد القبول | يتحمل التاجر صافي قيمة الصنف |
| تأخر التوصيل، أو فقدان الطلب لدى المندوب، أو عدم الاستلام، أو التلف أثناء النقل | تتحملها جالبوت، ويحصل التاجر على مستحقاته كاملة |
| تعذر تحديد السبب | تُقسم بنسبة 50% على التاجر و50% على جالبوت |

وتتحمل جالبوت دائمًا رسوم التوصيل ورسوم الخدمة والإكرامية وجميع الأرصدة التعويضية، ولا يتحملها التاجر.

وإذا تجاوز الاسترداد بخطأ التاجر 5% من طلباته خلال 30 يومًا متحركة، تفتح جالبوت مراجعة للجودة.

</div>

## MPO-04: Disputing a deduction

- Dispute in the merchant portal within 14 days of the statement date, with evidence.
- Jalboot replies within 5 business days.
- A deduction of QAR 15 or less on one order cannot be disputed alone. It can be disputed when 5 or more such deductions appear on one statement, as one bundle.
- Evidence can include a photo from the packing station or a sealed-bag record.
- If the dispute succeeds, the amount is added to the next statement. The customer's refund is not reversed.

<div lang="ar" dir="rtl">

### الاعتراض على استقطاع

- يُقدم الاعتراض عبر بوابة التجار خلال 14 يومًا من تاريخ كشف الحساب، مع الأدلة.
- ترد جالبوت خلال 5 أيام عمل.
- لا يجوز الاعتراض منفردًا على استقطاع قيمته 15 ر.ق أو أقل في الطلب الواحد. ويجوز الاعتراض إذا ظهر 5 استقطاعات أو أكثر من هذا النوع في كشف واحد، على أن تُقدم مجمعة.
- يمكن أن تشمل الأدلة صورة من منطقة التغليف أو سجل إغلاق الكيس.
- إذا قُبل الاعتراض، يضاف المبلغ إلى الكشف التالي، ولا يُسترجع ما رُد إلى العميل.

</div>

## MPO-05: Reserve, bank changes, negative balances and final payout

**Reserve.** Jalboot holds 5% of each payout during a merchant's first 90 days. It releases the reserve 30 days after those 90 days end.

**Bank change.** A new bank account needs verification and a hold of 3 business days. A change made within 48 hours before a payout moves that payout to the next cycle.

**Negative balance.** A negative balance rolls forward. After 30 days, Jalboot issues an invoice. If it passes QAR 5,000, the listing is suspended until it is settled.

**Final payout.** After a contract ends, the final payout comes 30 days after the last order, so late refunds can be counted. The reserve is included.

<div lang="ar" dir="rtl">

### مبلغ الضمان وتغيير الحساب المصرفي والرصيد السالب والتسوية النهائية

**مبلغ الضمان:** تحتجز جالبوت 5% من كل تحويل خلال أول 90 يومًا للتاجر، وتفرج عنه بعد 30 يومًا من انتهاء هذه المدة.

**تغيير الحساب المصرفي:** يحتاج الحساب الجديد إلى تحقق وتعليق مدته 3 أيام عمل. وإذا تم التغيير خلال 48 ساعة قبل التحويل، ينتقل ذلك التحويل إلى الدورة التالية.

**الرصيد السالب:** يُرحَّل الرصيد السالب، وبعد 30 يومًا تصدر جالبوت فاتورة به. وإذا تجاوز 5,000 ر.ق، يُوقف عرض التاجر حتى تسويته.

**التسوية النهائية:** بعد انتهاء العقد، تتم التسوية النهائية بعد 30 يومًا من آخر طلب، حتى يمكن احتساب أي استرداد متأخر، ويدخل فيها مبلغ الضمان.

</div>
